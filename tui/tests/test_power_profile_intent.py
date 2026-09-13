from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis_tui.power_profile_intent import parse_power_profile_intent  # noqa: E402


class PowerProfileIntentTests(unittest.TestCase):
    def test_requested_setup_and_follow_up_clarifications_resolve(self) -> None:
        original = (
            "create a power profile optimized for max performance and low-requiring sessions/tasks"
        )
        first = parse_power_profile_intent(original)
        self.assertIsNotNone(first)
        self.assertIn("Separate Performance and Low-demand profiles", first.options)  # type: ignore[union-attr]
        second = parse_power_profile_intent(
            original + "\n\nUser clarification: i want to create a new low-demanding profile"
        )
        self.assertEqual(second.goal, "quiet")  # type: ignore[union-attr]
        self.assertIsNotNone(second.question)
        third = parse_power_profile_intent(
            original
            + "\n\nUser clarification: i want to create a new low-demanding profile"
            + "\n\nUser clarification: Both AC and battery"
        )
        self.assertTrue(third.complete)  # type: ignore[union-attr]
        self.assertEqual(third.scope, "both")  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
