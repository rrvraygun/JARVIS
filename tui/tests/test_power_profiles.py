from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis_tui.power_inventory import PowerInventory, PowerSetting  # noqa: E402
from jarvis_tui.power_profile_results import (  # noqa: E402
    PowerProfileApplicationRecord,
    PowerProfileApplicationStore,
)
from jarvis_tui.power_profiles import PowerProfileStore, plan_power_profile  # noqa: E402


class PowerProfileTests(unittest.TestCase):
    def inventory(self) -> PowerInventory:
        return PowerInventory(
            providers=("Power Profiles D-Bus",),
            settings=(
                PowerSetting(
                    "Profiles",
                    "Desktop profile",
                    "balanced",
                    "power-saver, balanced, performance",
                    "/profile",
                    True,
                    "power.profile",
                ),
                PowerSetting(
                    "CPU",
                    "EPP",
                    "balance_performance",
                    "power, balance_power, balance_performance, performance",
                    "/epp",
                    True,
                    "cpu.epp",
                ),
                PowerSetting(
                    "CPU", "Turbo", "enabled", "enabled, disabled", "/turbo", True, "cpu.turbo"
                ),
            ),
            limitations=(),
        )

    def test_goal_planner_builds_paired_variants_and_marks_missing_controls(self) -> None:
        plan = plan_power_profile(
            name="Battery friendly",
            goal="battery",
            inventory=self.inventory(),
            profile_id="profile_test",
        )
        self.assertEqual(plan.profile.variants["ac"]["power.profile"], "power-saver")
        self.assertEqual(plan.profile.variants["battery"]["cpu.epp"], "power")
        self.assertTrue(any("intel_gpu.runtime_pm" in item for item in plan.unsupported))
        self.assertTrue(plan.profile.profile_digest)

    def test_profile_store_round_trip_is_versioned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = plan_power_profile(
                name="Balanced",
                goal="balanced",
                inventory=self.inventory(),
                profile_id="profile_test",
            )
            store = PowerProfileStore(Path(directory))
            store.save(plan.profile)
            loaded = store.load("profile_test")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.profile_digest, plan.profile.profile_digest)  # type: ignore[union-attr]

    def test_verified_application_record_round_trip_and_three_way_diff(self) -> None:
        plan = plan_power_profile(
            name="Balanced", goal="balanced", inventory=self.inventory(), profile_id="profile_test"
        )
        requested = {"power.profile": "balanced", "cpu.epp": "balance_performance"}
        record = PowerProfileApplicationRecord.from_transaction(
            profile=plan.profile,
            variant="ac",
            pre_activation={"power.profile": "performance", "cpu.epp": "power"},
            requested=requested,
            result={"post_state": requested},
        )
        with tempfile.TemporaryDirectory() as directory:
            store = PowerProfileApplicationStore(Path(directory))
            store.save(record)
            loaded = store.load_latest()
            self.assertEqual(loaded, record)
            self.assertEqual(loaded.changed["cpu.epp"]["before"], "power")  # type: ignore[union-attr]

    def test_invalid_result_digest_is_ignored(self) -> None:
        plan = plan_power_profile(
            name="Balanced", goal="balanced", inventory=self.inventory(), profile_id="profile_test"
        )
        record = PowerProfileApplicationRecord.from_transaction(
            profile=plan.profile,
            variant="battery",
            pre_activation={},
            requested={},
            result={"post_state": {}},
            status="indeterminate",
        )
        with tempfile.TemporaryDirectory() as directory:
            store = PowerProfileApplicationStore(Path(directory))
            path = store.save(record)
            value = path.read_text()
            path.write_text(value.replace(record.record_digest, "0" * 64))
            self.assertIsNone(store.load_latest())


if __name__ == "__main__":
    unittest.main()
