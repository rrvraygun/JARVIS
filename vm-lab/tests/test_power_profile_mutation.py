from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import power_profile_mutation as MUTATION


def properties(active: str = "balanced", degraded: str = "") -> dict[str, object]:
    return {
        "ActiveProfile": active,
        "Profiles": [
            {"Profile": "power-saver", "Driver": "tuned"},
            {"Profile": "balanced", "Driver": "tuned"},
            {"Profile": "performance", "Driver": "tuned"},
        ],
        "PerformanceDegraded": degraded,
    }


class FakeTransport:
    def __init__(
        self,
        active: str = "balanced",
        *,
        mismatch_after_set: bool = False,
        fail_post_read: bool = False,
        invalid_post_read: bool = False,
        available_profiles: tuple[str, ...] = (
            "power-saver",
            "balanced",
            "performance",
        ),
        fail_set: bool = False,
    ) -> None:
        self.active = active
        self.mismatch_after_set = mismatch_after_set
        self.fail_post_read = fail_post_read
        self.invalid_post_read = invalid_post_read
        self.available_profiles = available_profiles
        self.fail_set = fail_set
        self.set_calls: list[str] = []

    def get_all(self) -> dict[str, object]:
        if self.set_calls and self.fail_post_read:
            raise RuntimeError("provider read failed")
        if self.set_calls and self.invalid_post_read:
            return {"ActiveProfile": self.active}
        raw = properties(self.active)
        raw["Profiles"] = [
            profile for profile in raw["Profiles"] if profile["Profile"] in self.available_profiles
        ]
        return raw

    def set_active_profile(self, profile: str) -> None:
        self.set_calls.append(profile)
        if self.fail_set:
            raise RuntimeError("setter reply lost")
        if not self.mismatch_after_set:
            self.active = profile


class PowerProfileMutationTests(unittest.TestCase):
    def _adapter(
        self, **kwargs: object
    ) -> tuple[MUTATION.SupervisedPowerProfileAdapter, FakeTransport]:
        transport = FakeTransport(**kwargs)
        return MUTATION.SupervisedPowerProfileAdapter(transport), transport

    def test_executes_one_exact_transition_and_verifies_postcondition(self) -> None:
        adapter, transport = self._adapter()
        result = adapter.execute(
            "performance",
            pre_profile="balanced",
            tui_confirmed=True,
            active_session=True,
        )
        self.assertEqual(result["pre_profile"], "balanced")
        self.assertEqual(result["post_profile"], "performance")
        self.assertEqual(transport.set_calls, ["performance"])
        self.assertFalse(result["automatic_rollback"])
        self.assertFalse(result["authorization_consumed_by_adapter"])

    def test_emits_notifications_before_successful_mutation(self) -> None:
        adapter, transport = self._adapter()
        notifications: list[str] = []
        result = adapter.execute(
            "performance",
            pre_profile="balanced",
            tui_confirmed=True,
            active_session=True,
            on_battery=True,
            thermal_degraded=True,
            notification_sink=notifications.append,
        )
        self.assertEqual(notifications, ["on-battery", "thermal-degradation"])
        self.assertEqual(result["notifications"], notifications)
        self.assertEqual(transport.set_calls, ["performance"])

    def test_emits_warnings_without_blocking(self) -> None:
        adapter, _ = self._adapter()
        result = adapter.execute(
            "performance",
            pre_profile="balanced",
            tui_confirmed=True,
            active_session=True,
            on_battery=True,
            thermal_degraded=True,
        )
        self.assertEqual(result["notifications"], ["on-battery", "thermal-degradation"])

    def test_rejects_stale_state_without_mutation(self) -> None:
        adapter, transport = self._adapter(active="performance")
        with self.assertRaisesRegex(MUTATION.PowerProfileMutationError, "stale"):
            adapter.execute(
                "balanced",
                pre_profile="balanced",
                tui_confirmed=True,
                active_session=True,
            )
        self.assertEqual(transport.set_calls, [])

    def test_rejects_missing_gates_without_mutation(self) -> None:
        adapter, transport = self._adapter()
        with self.assertRaisesRegex(MUTATION.PowerProfileMutationError, "TUI"):
            adapter.execute(
                "performance",
                pre_profile="balanced",
                tui_confirmed=False,
                active_session=True,
            )
        self.assertEqual(transport.set_calls, [])

    def test_stops_on_postcondition_failure_without_rollback(self) -> None:
        adapter, transport = self._adapter(mismatch_after_set=True)
        notifications: list[str] = []
        with self.assertRaisesRegex(MUTATION.PowerProfileMutationError, "new approval"):
            adapter.execute(
                "performance",
                pre_profile="balanced",
                tui_confirmed=True,
                active_session=True,
                on_battery=True,
                notification_sink=notifications.append,
            )
        self.assertEqual(transport.set_calls, ["performance"])
        self.assertEqual(notifications, ["on-battery"])

    def test_notification_sink_failure_does_not_block_transition(self) -> None:
        adapter, transport = self._adapter()

        def failing_sink(_: str) -> None:
            raise RuntimeError("notification channel unavailable")

        adapter.execute(
            "performance",
            pre_profile="balanced",
            tui_confirmed=True,
            active_session=True,
            on_battery=True,
            notification_sink=failing_sink,
        )
        self.assertEqual(transport.set_calls, ["performance"])

    def test_stops_on_indeterminate_setter_failure_without_rollback(self) -> None:
        adapter, transport = self._adapter(fail_set=True)
        with self.assertRaisesRegex(
            MUTATION.PowerProfileMutationError, "indeterminate.*new approval"
        ):
            adapter.execute(
                "performance",
                pre_profile="balanced",
                tui_confirmed=True,
                active_session=True,
            )
        self.assertEqual(transport.set_calls, ["performance"])

    def test_stops_when_post_state_read_fails_without_rollback(self) -> None:
        adapter, transport = self._adapter(fail_post_read=True)
        with self.assertRaisesRegex(MUTATION.PowerProfileMutationError, "new approval"):
            adapter.execute(
                "performance",
                pre_profile="balanced",
                tui_confirmed=True,
                active_session=True,
            )
        self.assertEqual(transport.set_calls, ["performance"])

    def test_stops_when_post_state_is_invalid_without_rollback(self) -> None:
        adapter, transport = self._adapter(invalid_post_read=True)
        with self.assertRaisesRegex(MUTATION.PowerProfileMutationError, "new approval"):
            adapter.execute(
                "performance",
                pre_profile="balanced",
                tui_confirmed=True,
                active_session=True,
            )
        self.assertEqual(transport.set_calls, ["performance"])

    def test_rejects_noop_transition(self) -> None:
        adapter, transport = self._adapter(active="performance")
        with self.assertRaisesRegex(MUTATION.PowerProfileMutationError, "already active"):
            adapter.execute(
                "performance",
                pre_profile="performance",
                tui_confirmed=True,
                active_session=True,
            )
        self.assertEqual(transport.set_calls, [])

    def test_rejects_profile_not_advertised_by_provider(self) -> None:
        adapter, transport = self._adapter(available_profiles=("power-saver", "balanced"))
        with self.assertRaisesRegex(MUTATION.PowerProfileMutationError, "unavailable"):
            adapter.execute(
                "performance",
                pre_profile="balanced",
                tui_confirmed=True,
                active_session=True,
            )
        self.assertEqual(transport.set_calls, [])


if __name__ == "__main__":
    unittest.main()
