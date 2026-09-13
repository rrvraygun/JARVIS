#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import jarvis_power_control as power


class FakeProfileBus:
    def __init__(self, value: str = "balanced") -> None:
        self.value = value

    def __call__(self, argv: list[str]) -> str:
        if "get-property" in argv:
            return f's "{self.value}"'
        if "set-property" in argv:
            self.value = argv[-1]
            return ""
        raise AssertionError(argv)


class JarvisPowerControlTests(unittest.TestCase):
    def test_profile_apply_and_explicit_undo(self) -> None:
        bus = FakeProfileBus()
        changed = power.apply(
            "power.profile",
            "performance",
            "balanced",
            run=bus,
            thermal_guard=lambda: None,
        )
        self.assertEqual(bus.value, "performance")
        restored = power.undo(
            "power.profile",
            "performance",
            changed["pre_state"],
            run=bus,
            thermal_guard=lambda: None,
        )
        self.assertEqual(restored["restored"], "balanced")
        self.assertEqual(bus.value, "balanced")

    def test_multi_control_profile_uses_one_prepared_record_and_restores(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference"
            path.parent.mkdir(parents=True)
            path.write_text("balance_performance", encoding="utf-8")
            bus = FakeProfileBus()
            prepared: list[dict[str, object]] = []
            result = power.apply_profile(
                {"cpu.epp": "power", "power.profile": "power-saver"},
                {"cpu.epp": "balance_performance", "power.profile": "balanced"},
                root=root,
                run=bus,
                precommit=prepared.append,
                thermal_guard=lambda: None,
            )
            self.assertEqual(len(prepared), 1)
            self.assertEqual(result["operation"], "profile")
            restored = power.undo_profile(
                result["post_state"],  # type: ignore[arg-type]
                result["pre_state"],  # type: ignore[arg-type]
                root=root,
                run=bus,
                thermal_guard=lambda: None,
            )
            self.assertEqual(restored["status"], "passed")
            self.assertEqual(path.read_text(encoding="utf-8"), "balance_performance")
            self.assertEqual(bus.value, "balanced")

    def test_epp_apply_and_exact_multicpu_undo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for cpu in ("cpu0", "cpu1"):
                path = root / f"sys/devices/system/cpu/{cpu}/cpufreq/energy_performance_preference"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("balance_power", encoding="utf-8")
            changed = power.apply("cpu.epp", "performance", "balance_power", root=root)
            self.assertEqual(
                changed["pre_state"]["targets"],
                {"cpu0": "balance_power", "cpu1": "balance_power"},
            )
            restored = power.undo("cpu.epp", "performance", changed["pre_state"], root=root)
            self.assertEqual(restored["status"], "passed")
            for cpu in ("cpu0", "cpu1"):
                self.assertEqual(
                    (
                        root / f"sys/devices/system/cpu/{cpu}/cpufreq/energy_performance_preference"
                    ).read_text(encoding="utf-8"),
                    "balance_power",
                )

    def test_stale_prestate_and_unallowlisted_value_fail_closed(self) -> None:
        bus = FakeProfileBus("power-saver")
        with self.assertRaises(power.PowerControlError):
            power.apply(
                "power.profile",
                "performance",
                "balanced",
                run=bus,
                thermal_guard=lambda: None,
            )
        with self.assertRaises(power.PowerControlError):
            power.apply(
                "power.profile",
                "custom-profile",
                "power-saver",
                run=bus,
                thermal_guard=lambda: None,
            )

    def test_undo_rejects_target_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference"
            path.parent.mkdir(parents=True)
            path.write_text("balance_power", encoding="utf-8")
            changed = power.apply("cpu.epp", "performance", "balance_power", root=root)
            path.write_text("power", encoding="utf-8")
            with self.assertRaises(power.PowerControlError):
                power.undo("cpu.epp", "performance", changed["pre_state"], root=root)

    def test_control_write_rejects_a_symlink_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "outside"
            target.write_text("balance_power", encoding="utf-8")
            path = root / "sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference"
            path.parent.mkdir(parents=True)
            path.symlink_to(target)
            with self.assertRaisesRegex(power.PowerControlError, "unsafe"):
                power._write_target(path, "performance")
            self.assertEqual(target.read_text(encoding="utf-8"), "balance_power")

    def test_undo_digest_binds_the_exact_reviewed_record(self) -> None:
        record = {
            "control": "cpu.epp",
            "post_value": "performance",
            "pre_state": {"targets": {"cpu0": "balance_power"}},
            "status": "prepared",
        }
        digest = power._record_digest(record)
        power._verify_record_digest(record, digest)
        replacement = {**record, "post_value": "power"}
        with self.assertRaises(power.PowerControlError):
            power._verify_record_digest(replacement, digest)

    def test_profile_and_turbo_fail_closed_without_safe_thermal_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(power.PowerControlError, "thermal state is unavailable"):
                power.apply(
                    "power.profile",
                    "performance",
                    "balanced",
                    root=root,
                    run=FakeProfileBus(),
                )
            sensor = root / "sys/class/thermal/thermal_zone0/temp"
            sensor.parent.mkdir(parents=True)
            sensor.write_text("95000", encoding="ascii")
            with self.assertRaisesRegex(power.PowerControlError, "thermal degradation"):
                power.apply(
                    "power.profile",
                    "performance",
                    "balanced",
                    root=root,
                    run=FakeProfileBus(),
                )
            with self.assertRaisesRegex(power.PowerControlError, "thermal degradation"):
                power.undo(
                    "power.profile",
                    "performance",
                    {"profile": "balanced"},
                    root=root,
                    run=FakeProfileBus("performance"),
                )
            with self.assertRaisesRegex(power.PowerControlError, "thermal degradation"):
                power.recover_prepared(
                    "power.profile",
                    "performance",
                    {"profile": "balanced"},
                    root=root,
                    run=FakeProfileBus("performance"),
                )

    def test_secure_journal_traversal_rejects_symlink_and_writable_ancestor(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "safe").mkdir(mode=0o700)
            (root / "safe/link").symlink_to(root / "safe", target_is_directory=True)
            with self.assertRaises(power.PowerControlError):
                power._open_secure_directory(
                    root,
                    ("safe", "link"),
                    expected_uid=root.stat().st_uid,
                    create_from=99,
                )
            writable = root / "writable"
            writable.mkdir(mode=0o777)
            writable.chmod(0o777)
            with self.assertRaisesRegex(power.PowerControlError, "ownership or mode"):
                power._open_secure_directory(
                    root, ("writable",), expected_uid=root.stat().st_uid, create_from=99
                )

    def test_successful_apply_commits_the_same_prepared_record_by_rename(self) -> None:
        prepared_records: list[dict[str, object]] = []

        def fake_apply(*_: object, precommit=None, **__: object) -> dict[str, object]:
            record = {
                "control": "cpu.epp",
                "post_value": "performance",
                "pre_state": {"targets": {"cpu0": "balance_power"}},
                "status": "prepared",
            }
            precommit(record)
            return {
                "status": "passed",
                "control": "cpu.epp",
                "post_value": "performance",
                "pre_state": record["pre_state"],
            }

        with (
            patch.object(
                sys,
                "argv",
                [
                    "helper",
                    "apply",
                    "--control",
                    "cpu.epp",
                    "--value",
                    "performance",
                    "--expected",
                    "balance_power",
                ],
            ),
            patch.object(power.os, "geteuid", return_value=0),
            patch.dict(power.os.environ, {"PKEXEC_UID": "1000"}),
            patch.object(power, "_journal_exists", return_value=False),
            patch.object(
                power, "_actor_transaction_lock", return_value=nullcontext()
            ) as actor_lock,
            patch.object(
                power,
                "_write_authoritative_journal",
                side_effect=lambda _name, record: prepared_records.append(record),
            ),
            patch.object(power, "_replace_journal") as replace,
            patch.object(power, "apply", side_effect=fake_apply),
        ):
            self.assertEqual(power.main(), 0)
        self.assertEqual([record["status"] for record in prepared_records], ["prepared"])
        actor_lock.assert_called_once_with(1000)
        replace.assert_called_once_with("1000.pending.json", "1000.json")

    def test_prepared_recovery_restores_mixed_partial_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {}
            for cpu, value in (("cpu0", "performance"), ("cpu1", "balance_power")):
                path = root / f"sys/devices/system/cpu/{cpu}/cpufreq/energy_performance_preference"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value, encoding="utf-8")
                paths[cpu] = "balance_power"
            result = power.recover_prepared("cpu.epp", "performance", {"targets": paths}, root=root)
            self.assertEqual(result["operation"], "recovery")
            for cpu in paths:
                target = (
                    root / f"sys/devices/system/cpu/{cpu}/cpufreq/energy_performance_preference"
                )
                self.assertEqual(target.read_text(encoding="utf-8"), "balance_power")

    def test_prepared_recovery_rejects_external_value_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference"
            path.parent.mkdir(parents=True)
            path.write_text("power", encoding="utf-8")
            with self.assertRaisesRegex(power.PowerControlError, "current state drifted"):
                power.recover_prepared(
                    "cpu.epp",
                    "performance",
                    {"targets": {"cpu0": "balance_power"}},
                    root=root,
                )


if __name__ == "__main__":
    unittest.main()
