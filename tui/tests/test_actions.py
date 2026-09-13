#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import unittest


TUI_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = TUI_ROOT.parent
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.actions import ActionRegistry  # noqa: E402


class ActionRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = ActionRegistry.load(
            BUNDLE_ROOT / "plugins/jarvis-system-admin/registry/actions.json"
        )

    def test_lighting_diagnosis_is_prepared_and_read_only(self) -> None:
        action = self.registry.get("health.lighting.diagnose")
        self.assertEqual(action.procedure, "health.lighting-diagnose@1.0.0")
        self.assertFalse(action.mutates_host)
        self.assertEqual(action.implementation_status, "prepared")
        self.assertIn("brightness", action.tags)

    def test_lighting_repair_execution_is_unavailable(self) -> None:
        action = self.registry.get("repair.lighting.execute")
        self.assertTrue(action.mutates_host)
        self.assertEqual(action.availability, "unavailable")
        with self.assertRaisesRegex(ValueError, "No state-changing executor"):
            self.registry.validate_selection(action.id, {"repair_plan_id": "plan-1"})

    def test_lighting_parameters_are_typed(self) -> None:
        action = self.registry.validate_selection(
            "health.lighting.diagnose",
            {
                "affected_controls": "both",
                "nvidia_power_correlation": "suspected",
                "external_display_affected": "not_tested",
            },
        )
        self.assertEqual(action.capability, "health")
        with self.assertRaisesRegex(ValueError, "not an allowed value"):
            self.registry.validate_selection(
                "health.lighting.diagnose",
                {
                    "affected_controls": "everything",
                    "nvidia_power_correlation": "certain",
                },
            )

    def test_action_search_uses_scenario_terms(self) -> None:
        matches = self.registry.search("nvidia brightness")
        self.assertIn("health.lighting.diagnose", {item.id for item in matches})


if __name__ == "__main__":
    unittest.main()
