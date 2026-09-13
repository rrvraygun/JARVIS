from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import phase5_power_profile_rehearsal as REHEARSAL


class PowerProfileRehearsalTests(unittest.TestCase):
    def test_transition_and_rollback_are_verified_in_memory(self) -> None:
        result = REHEARSAL.rehearse_transition()
        self.assertEqual(result["pre_profile"], "balanced")
        self.assertEqual(result["post_profile"], "performance")
        self.assertEqual(result["rollback_profile"], "balanced")
        self.assertTrue(result["rollback_verified"])
        self.assertFalse(result["host_effect_occurred"])

    def test_power_saver_transition_is_supported(self) -> None:
        result = REHEARSAL.rehearse_transition("power-saver")
        self.assertEqual(result["post_profile"], "power-saver")
        self.assertEqual(result["rollback_profile"], "balanced")

    def test_rejects_unknown_requested_profile_without_state_change(self) -> None:
        with self.assertRaisesRegex(REHEARSAL.RehearsalError, "unsupported"):
            REHEARSAL.rehearse_transition("jarvis-balanced")

    def test_rejects_stale_precondition_without_state_change(self) -> None:
        with self.assertRaisesRegex(REHEARSAL.RehearsalError, "pre-profile"):
            REHEARSAL.rehearse_transition("balanced", initial_profile="performance")

    def test_rejects_invalid_simulator_initial_state(self) -> None:
        with self.assertRaisesRegex(REHEARSAL.RehearsalError, "initial profile"):
            REHEARSAL.SimulatedProvider("jarvis-balanced")

    def test_result_explicitly_excludes_live_effects(self) -> None:
        result = REHEARSAL.rehearse_transition()
        self.assertEqual(result["dbus_calls"], 0)
        self.assertEqual(result["filesystem_writes"], 0)
        self.assertFalse(result["executor_invoked"])
        self.assertTrue(result["temporary_state_discarded"])


if __name__ == "__main__":
    unittest.main()
