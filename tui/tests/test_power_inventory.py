#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


TUI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.power_inventory import scan_power_inventory  # noqa: E402


class PowerInventoryTests(unittest.TestCase):
    def test_reads_fixed_cpu_gpu_and_supply_interfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def write(relative: str, value: str) -> None:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value, encoding="utf-8")

            write("sys/devices/system/cpu/cpu0/cpufreq/scaling_driver", "intel_pstate\n")
            write("sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "powersave\n")
            write(
                "sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors",
                "performance powersave\n",
            )
            write(
                "sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference",
                "balance_performance\n",
            )
            write(
                "sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences",
                "performance balance_performance power\n",
            )
            write("sys/devices/system/cpu/intel_pstate/no_turbo", "0\n")
            write("sys/class/drm/card0/device/vendor", "0x8086\n")
            write("sys/class/drm/card0/device/power/control", "auto\n")
            write("sys/class/drm/card0/device/power/runtime_status", "active\n")
            write("sys/class/power_supply/BAT0/type", "Battery\n")
            write("sys/class/power_supply/BAT0/status", "Discharging\n")
            write("sys/class/power_supply/BAT0/capacity", "72\n")

            value = scan_power_inventory(root=root, include_commands=False)
            settings = {(item.section, item.setting): item.current for item in value.settings}
            self.assertEqual(settings[("CPU", "Scaling driver")], "intel_pstate")
            self.assertEqual(settings[("CPU", "Governor")], "powersave")
            self.assertEqual(settings[("Intel GPU", "card0 runtime policy")], "auto")
            self.assertEqual(settings[("Battery / AC", "BAT0 Capacity")], "72")
            self.assertIn("CPU frequency: intel_pstate", value.providers)
            writable = {item.control_id for item in value.settings if item.writable_by_jarvis}
            self.assertEqual(writable, {"cpu.epp", "cpu.turbo", "intel_gpu.runtime_pm"})

    def test_missing_interfaces_are_explicitly_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            value = scan_power_inventory(root=Path(directory), include_commands=False)
            driver = next(item for item in value.settings if item.setting == "Scaling driver")
            self.assertEqual(driver.current, "unavailable")


if __name__ == "__main__":
    unittest.main()
