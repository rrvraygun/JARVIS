import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis_tui.energy_controls import energy_control_preview


class EnergyControlPreviewTests(unittest.TestCase):
    def test_preview_is_bounded_and_simulation_only(self):
        value = energy_control_preview(
            operations=[{"control": "cpu.epp", "requested": "performance"}],
            thermal_degraded=False,
            on_battery=False,
        )
        self.assertTrue(value["simulation_only"])
        self.assertTrue(value["one_use"])

    def test_thermal_gate_rejects_profile(self):
        with self.assertRaises(ValueError):
            energy_control_preview(
                operations=[{"control": "power.profile", "requested": "performance"}],
                thermal_degraded=True,
                on_battery=False,
            )


if __name__ == "__main__":
    unittest.main()
