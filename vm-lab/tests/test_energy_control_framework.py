import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from energy_control_framework import (
    EnergyControlError,
    EnergyControlPlan,
    EnergyOperation,
    PreparedEnergyControlExecutor,
    powertop_reading_summary,
)


class EnergyControlFrameworkTests(unittest.TestCase):
    def test_allowlisted_plan_is_simulation_only(self):
        plan = EnergyControlPlan(
            "energy-1",
            (EnergyOperation("cpu.epp", "performance", "power", "sysfs-readonly"),),
            "a" * 64,
            False,
            False,
            "b" * 64,
        )
        value = plan.as_dict()
        self.assertTrue(value["simulation_only"])
        with self.assertRaisesRegex(EnergyControlError, "constructed but disabled"):
            PreparedEnergyControlExecutor().execute(value)

    def test_thermal_degradation_blocks_turbo(self):
        plan = EnergyControlPlan(
            "energy-2",
            (EnergyOperation("cpu.turbo", True, False, "sysfs-readonly"),),
            "a" * 64,
            True,
            False,
            "b" * 64,
        )
        with self.assertRaisesRegex(EnergyControlError, "thermal"):
            plan.validate()

    def test_powertop_summary_is_read_only_and_bounded(self):
        value = powertop_reading_summary(
            tunables={"runtime-pm-pci": "Good"},
            cpu_epp="balance_performance",
            gpu_runtime_pm={"intel": "auto"},
        )
        self.assertFalse(value["mutation_performed"])


if __name__ == "__main__":
    unittest.main()
