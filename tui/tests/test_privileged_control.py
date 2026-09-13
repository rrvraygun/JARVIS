"""Root boundary regression tests; no real privileged program is invoked."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "root_control_fixture", ROOT / "vm-lab/scripts/jarvis_privileged_control.py"
)
assert spec and spec.loader
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class PrivilegedControlTests(unittest.TestCase):
    def request(self):
        return {
            "id": "a" * 32,
            "operation": "select_kernel",
            "kernel": "6.14.0-1.fc44.x86_64",
            "entry": "fixture-6.14.0-1.fc44.x86_64",
            "pre_state_digest": "b" * 64,
        }

    def test_request_cannot_escape_ledger_or_boot_paths(self):
        for field, value in [
            ("id", "/tmp/escape"),
            ("id", "../../escape"),
            ("kernel", "1/../../etc/passwd"),
            ("entry", "../../grubenv"),
        ]:
            request = self.request()
            request[field] = value
            with (
                self.subTest(field=field, value=value),
                patch.object(helper, "run") as run,
                self.assertRaises(ValueError),
            ):
                helper.perform(request, "boot", 1000)
            run.assert_not_called()

    def test_no_root_review_means_no_writes_or_commands(self):
        with (
            patch.object(helper, "read_file", side_effect=FileNotFoundError),
            patch.object(helper, "directory") as directory,
            patch.object(helper, "run") as run,
            self.assertRaises(FileNotFoundError),
        ):
            helper.perform(self.request(), "boot", 1000)
        run.assert_not_called()
        directory.assert_not_called()

    def test_caller_booleans_or_matching_missing_digests_cannot_authorize(self):
        request = {
            "id": "a" * 32,
            "transaction_id": "c" * 32,
            "pre_state_digest": "b" * 64,
            "transaction_digest": "d" * 64,
        }
        with (
            patch.object(helper, "read_file", return_value=("ignored", b"{}")),
            self.assertRaises(ValueError),
        ):
            helper.perform(request, "update", 1000)
        now = time.time()
        valid = {
            "kind": "update",
            "request_digest": helper.digest(request),
            "expires_at": now + 60,
            "known_good_boot_verified": True,
            "recovery": {
                "level": "R2",
                "digest": "f" * 64,
                "verified_at": now,
                "target_pre_state_digest": request["pre_state_digest"],
            },
        }
        with patch.object(
            helper, "read_file", return_value=("ignored", json.dumps(valid).encode())
        ):
            self.assertEqual(helper.review(request, "update", 1000), valid)
        valid["expires_at"] = float("nan")
        with (
            patch.object(helper, "read_file", return_value=("ignored", json.dumps(valid).encode())),
            self.assertRaises(ValueError),
        ):
            helper.review(request, "update", 1000)

    def test_atomic_record_does_not_overwrite_existing_or_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with patch.object(
                helper,
                "directory",
                side_effect=lambda path: os.open(path, os.O_RDONLY | os.O_DIRECTORY),
            ):
                path = directory / "record.json"
                helper.write_once(path, {"before": True})
                with self.assertRaises(FileExistsError):
                    helper.write_once(path, {"overwrite": True})
                linked = directory / "link.json"
                linked.symlink_to(path)
                with self.assertRaises(FileExistsError):
                    helper.write_once(linked, {"overwrite": True})
                self.assertEqual(json.loads(path.read_text()), {"before": True})

    def test_next_boot_uses_one_time_entry_after_reservation(self):
        request = self.request()
        state = {"/boot/vmlinuz-fixture": "c" * 64}
        request["pre_state_digest"] = helper.digest(state)
        events = []

        def run(argv, **kwargs):
            self.assertIn("reserved", events)
            events.append(argv)
            if "grub2-editenv" in argv[0]:
                return 0, ("next_entry=" + request["entry"] + "\n").encode()
            return 0, b""

        def record(path, payload):
            events.append("reserved" if "reservations" in path.parts else "result")

        with (
            patch.object(helper, "review", return_value={}),
            patch.object(helper, "boot_state", return_value=state),
            patch.object(helper, "read_file", return_value=("f" * 64, b"")),
            patch.object(helper, "write_once", side_effect=record),
            patch.object(helper, "run", side_effect=run),
        ):
            result = helper._perform(request, "boot", 1000)
        self.assertTrue(result["next_entry_verified"])
        self.assertFalse(result["bootability_verified"])
        self.assertIn(["/usr/bin/grub2-reboot", request["entry"]], events)
        self.assertFalse(any("--set-default" in item for item in events if isinstance(item, list)))

    def test_update_replays_exact_stored_transaction_without_ignore_flags(self):
        before = {"fixture-0:1.0-1.x86_64"}
        after = {"fixture-0:2.0-1.x86_64"}
        before_digest = helper.digest(sorted(before))
        after_digest = helper.digest(sorted(after))
        request = {
            "id": "a" * 32,
            "transaction_id": "c" * 32,
            "pre_state_digest": before_digest,
            "transaction_digest": "d" * 64,
        }
        events = []

        def run(argv, **kwargs):
            events.append(argv)
            if argv[0].endswith("rpmkeys"):
                return 0, b"fixture: digests signatures OK"
            if "--assumeno" in argv:
                return 1, b"exact solver preview"
            self.assertIn("reserved", events)
            self.assertIn("--cacheonly", argv)
            self.assertIn("--disable-repo=*", argv)
            self.assertIn("--setopt=installonly_limit=0", argv)
            self.assertIn("replay", argv)
            self.assertFalse(any(flag.startswith(("--ignore", "--skip")) for flag in argv))
            return 0, b""

        with (
            patch.object(helper, "review", return_value={}),
            patch.object(
                helper,
                "rpm_state",
                side_effect=[before_digest, before_digest, before_digest, after_digest],
            ),
            patch.object(helper, "rpm_packages", return_value=before),
            patch.object(
                helper,
                "load_transaction",
                return_value={
                    "digest": "d" * 64,
                    "actions": [
                        {"action": "Replaced", "nevra": next(iter(before))},
                        {"action": "Upgrade", "nevra": next(iter(after))},
                    ],
                },
            ),
            patch.object(helper, "read_file", return_value=("c" * 64, b"")),
            patch.object(
                helper,
                "write_once",
                side_effect=lambda path, record: events.append(
                    "reserved" if "reservations" in path.parts else "result"
                ),
            ),
            patch.object(helper, "run", side_effect=run),
        ):
            result = helper._perform(request, "update", 1000)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["expected_post_state_digest"], after_digest)
        self.assertFalse(result["bootability_verified"])
        self.assertEqual(sum(isinstance(e, list) and "-y" in e for e in events), 1)

    def test_boot_drift_after_reservation_blocks_effect(self):
        request = self.request()
        state = {"kernel": "before"}
        request["pre_state_digest"] = helper.digest(state)
        with (
            patch.object(helper, "review", return_value={}),
            patch.object(helper, "boot_state", side_effect=[state, {"kernel": "after"}]),
            patch.object(helper, "read_file", return_value=("f" * 64, b"")),
            patch.object(helper, "write_once"),
            patch.object(helper, "run") as run,
        ):
            result = helper._perform(request, "boot", 1000)
        self.assertEqual(result["status"], "indeterminate")
        run.assert_not_called()

    def test_transaction_drift_after_reservation_blocks_replay(self):
        before = {"fixture-0:1.0-1.x86_64"}
        state = helper.digest(sorted(before))
        request = {
            "id": "a" * 32,
            "transaction_id": "c" * 32,
            "pre_state_digest": state,
            "transaction_digest": "d" * 64,
        }
        with (
            patch.object(helper, "review", return_value={}),
            patch.object(helper, "rpm_state", return_value=state),
            patch.object(helper, "rpm_packages", return_value=before),
            patch.object(
                helper,
                "load_transaction",
                side_effect=[
                    {"digest": "d" * 64, "actions": []},
                    {"digest": "e" * 64, "actions": []},
                ],
            ),
            patch.object(helper, "write_once"),
            patch.object(helper, "run") as run,
        ):
            result = helper._perform(request, "update", 1000)
        self.assertEqual(result["status"], "indeterminate")
        run.assert_not_called()

    def test_install_guard_compares_active_state_separately_from_staged_image(self):
        request = self.request()
        request.update(operation="install_initramfs", source_operation="b" * 32)
        staged = "/boot/.jarvis-initramfs-" + "b" * 32 + ".img"
        active = {"/boot/initramfs-" + request["kernel"] + ".img": "c" * 64}
        request["pre_state_digest"] = helper.digest({**active, staged: "d" * 64})
        source = {
            "kernel": request["kernel"],
            "staged_image": staged,
            "image_parse_exit": 0,
            "staged_sha256": "d" * 64,
            "status": "command_completed_requires_independent_verification",
        }
        with (
            patch.object(helper, "review", return_value={"independent_image_sha256": "d" * 64}),
            patch.object(helper, "boot_state", side_effect=lambda request: dict(active)),
            patch.object(
                helper,
                "read_file",
                side_effect=[
                    ("f" * 64, b""),
                    ("e" * 64, json.dumps(source).encode()),
                    ("d" * 64, b""),
                ],
            ),
            patch.object(helper, "write_once"),
            patch.object(
                helper, "directory", side_effect=OSError("fixture stops before write")
            ) as directory,
        ):
            result = helper._perform(request, "boot", 1000)
        directory.assert_called_once_with(helper.ROOT / "backups")
        self.assertEqual(result["status"], "indeterminate")

    def test_replay_rejects_external_package_references_and_wrong_payloads(self):
        rpm = {
            "nevra": "fixture-0:2.0-1.x86_64",
            "action": "Upgrade",
            "reason": "User",
            "package_path": "packages/fixture.rpm",
        }
        files = {"transaction.json": "a" * 64, "packages/fixture.rpm": "b" * 64}
        headers = {"packages/fixture.rpm": rpm["nevra"]}
        self.assertTrue(
            helper.validate_transaction({"version": "1.0", "rpms": [rpm]}, files, headers)
        )
        for path in (
            "/tmp/other.rpm",
            "../other.rpm",
            "https://example.test/a.rpm",
            "./packages/fixture.rpm",
            "missing.rpm",
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                helper.validate_transaction(
                    {"version": "1.0", "rpms": [{**rpm, "package_path": path}]}, files, headers
                )
        with self.assertRaises(ValueError):
            helper.validate_transaction(
                {"version": "1.0", "rpms": [rpm]},
                files,
                {"packages/fixture.rpm": "other-0:1-1.x86_64"},
            )
        with self.assertRaises(ValueError):
            helper.validate_transaction(
                {"version": "1.0", "rpms": [rpm], "groups": [{"id": "extra"}]}, files, headers
            )

    def test_expected_replay_result_preserves_unaffected_packages(self):
        before = {"fixture-0:1-1.x86_64", "untouched-0:1-1.noarch"}
        actions = [
            {"action": "Replaced", "nevra": "fixture-0:1-1.x86_64"},
            {"action": "Upgrade", "nevra": "fixture-0:2-1.x86_64"},
        ]
        self.assertEqual(
            helper.expected_packages(actions, before),
            {"fixture-0:2-1.x86_64", "untouched-0:1-1.noarch"},
        )
        with self.assertRaises(ValueError):
            helper.expected_packages(actions, {"untouched-0:1-1.noarch"})

    def test_root_review_expiring_during_preparation_stops_before_reservation(self):
        request = self.request()
        state = {"image": "fixture"}
        request["pre_state_digest"] = helper.digest(state)
        with (
            patch.object(helper, "review", side_effect=[{}, ValueError("expired")]),
            patch.object(helper, "boot_state", return_value=state),
            patch.object(helper, "read_file", return_value=("a" * 64, b"")),
            patch.object(helper, "write_once") as record,
            patch.object(helper, "run") as run,
            self.assertRaises(ValueError),
        ):
            helper._perform(request, "boot", 1000)
        record.assert_not_called()
        run.assert_not_called()

    def test_atomic_exchange_retains_concurrently_changed_inode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active = root / "active.img"
            staged = root / "staged.img"
            active.write_bytes(b"concurrent change")
            staged.write_bytes(b"new image")
            old_inode = active.stat().st_ino
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                helper.exchange(fd, staged.name, active.name)
            finally:
                os.close(fd)
            self.assertEqual(staged.stat().st_ino, old_inode)
            self.assertEqual(staged.read_bytes(), b"concurrent change")
            self.assertEqual(active.read_bytes(), b"new image")
