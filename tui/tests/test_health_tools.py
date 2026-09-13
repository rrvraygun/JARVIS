from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

HEALTH_PATH = ROOT.parent / "plugins/jarvis-system-admin/scripts/health_tools.py"
spec = importlib.util.spec_from_file_location("jarvis_health_tools", HEALTH_PATH)
assert spec and spec.loader
health_tools = importlib.util.module_from_spec(spec)
sys.modules["jarvis_health_tools"] = health_tools
spec.loader.exec_module(health_tools)


class HealthToolTests(unittest.TestCase):
    @mock.patch("jarvis_health_tools._run")
    def test_health_inventory_uses_only_fixed_read_commands(self, run):
        run.return_value = {"status": "completed", "output": "", "argv": []}
        result = health_tools.health_inventory()
        self.assertTrue(result["read_only"])
        commands = {tuple(call.args[0]) for call in run.call_args_list}
        self.assertIn(("ps", "-eo", "pid,comm,%cpu,%mem", "--sort=-%cpu"), commands)
        self.assertIn(("systemctl", "--failed", "--no-legend", "--plain"), commands)

    @mock.patch("jarvis_health_tools._run")
    def test_toolchain_detection_includes_rust_and_cargo(self, run):
        run.return_value = {"status": "unavailable", "output": "", "argv": []}
        result = health_tools.development_toolchains()
        self.assertTrue(result["read_only"])
        self.assertEqual(
            {"rustc", "cargo"},
            set(result["toolchains"]) & {"rustc", "cargo"},
        )

    def test_project_inspection_reads_bounded_manifests(self):
        with self.subTest("invalid root rejected"):
            with self.assertRaises(ValueError):
                health_tools.development_project_inspect("/")

    @mock.patch("jarvis_health_tools._run")
    def test_focused_health_collectors_have_fixed_scopes(self, run):
        run.return_value = {"status": "completed", "output": "", "argv": []}
        self.assertTrue(health_tools.health_processes()["read_only"])
        self.assertTrue(health_tools.health_services()["read_only"])
        self.assertTrue(health_tools.health_storage()["read_only"])
        with self.assertRaises(ValueError):
            health_tools.health_logs("../../etc")


if __name__ == "__main__":
    unittest.main()
