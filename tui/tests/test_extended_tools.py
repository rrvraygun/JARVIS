from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS_PATH = ROOT.parent / "plugins/jarvis-system-admin/scripts/extended_tools.py"
spec = importlib.util.spec_from_file_location("jarvis_extended_tools", TOOLS_PATH)
assert spec and spec.loader
extended_tools = importlib.util.module_from_spec(spec)
sys.modules["jarvis_extended_tools"] = extended_tools
spec.loader.exec_module(extended_tools)


class ExtendedToolTests(unittest.TestCase):
    @mock.patch("jarvis_extended_tools._run")
    def test_network_inventory_is_local_and_read_only(self, run):
        run.return_value = {"status": "completed", "output": "", "argv": []}
        result = extended_tools.network_inventory()
        self.assertTrue(result["read_only"])
        self.assertIn("interfaces", result["sources"])
        self.assertNotIn("ping", {call.args[0][0] for call in run.call_args_list})

    @mock.patch("jarvis_extended_tools._run")
    def test_security_and_recovery_are_read_only(self, run):
        run.return_value = {"status": "unavailable", "output": "", "argv": []}
        self.assertTrue(extended_tools.security_inventory()["read_only"])
        self.assertTrue(extended_tools.recovery_inventory()["read_only"])


if __name__ == "__main__":
    unittest.main()
