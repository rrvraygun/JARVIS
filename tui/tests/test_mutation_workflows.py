import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis_tui.mutation_workflows import lighting_repair_preview, power_profile_preview


class MutationWorkflowTests(unittest.TestCase):
    def test_lighting_preview_is_explicit_and_nonexecuting(self):
        value = lighting_repair_preview(
            repair_plan_id="plan-1", target="keyboard-leds", rollback="new approval"
        )
        self.assertTrue(value["simulation_only"])
        self.assertTrue(value["active_session_confirmation_required"])

    def test_power_preview_requires_one_transition(self):
        value = power_profile_preview(profile="balanced", current_profile="performance")
        self.assertTrue(value["simulation_only"])
        self.assertTrue(value["one_transition_per_approval"])


if __name__ == "__main__":
    unittest.main()
