from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deployment/host/diagnose_lighting_tier1_input_driver_contract.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


diagnostic = load_module("diagnose_lighting_tier1_input_driver_contract", SCRIPT)


class LightingTier1InputDriverContractDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "sys"
        (self.root / "class/input").mkdir(parents=True)
        (self.root / "bus/platform/drivers/Acer Wireless Radio Control Driver").mkdir(parents=True)
        (self.root / "bus/serio/drivers/atkbd").mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def add_input(self, number: int, name: str, driver_target: str):
        base = self.root / f"class/input/input{number}"
        (base / "device").mkdir(parents=True)
        (base / "name").write_text(name + "\n", encoding="utf-8")
        (base / "device/driver").symlink_to(self.root / driver_target)

    def test_reports_only_relevant_rejected_driver_names(self):
        self.add_input(
            0,
            "Acer WMI hotkeys",
            "bus/platform/drivers/Acer Wireless Radio Control Driver",
        )
        self.add_input(1, "AT Translated Set 2 keyboard", "bus/serio/drivers/atkbd")
        self.add_input(2, "Power Button", "bus/serio/drivers/atkbd")
        result = diagnostic.diagnose(self.root)
        self.assertEqual(result["candidate_inputs"], 2)
        self.assertEqual(len(result["rejected_entries"]), 1)
        self.assertEqual(result["rejected_entries"][0]["input_name"], "Acer WMI hotkeys")
        self.assertEqual(
            result["rejected_entries"][0]["driver_name"],
            "Acer Wireless Radio Control Driver",
        )
        self.assertIn("U+0020", result["rejected_entries"][0]["driver_codepoints"])
        self.assertFalse(result["raw_input_events_read"])

    def test_entry_limit_fails_closed(self):
        for number in range(diagnostic.MAX_INPUT_ENTRIES + 1):
            (self.root / f"class/input/event{number}").mkdir()
        with self.assertRaisesRegex(diagnostic.DiagnosticError, "entry-limit-exceeded"):
            diagnostic.diagnose(self.root)

    def test_driver_symlink_escape_fails_closed(self):
        outside = Path(self.temporary.name) / "outside-driver"
        outside.mkdir()
        self.add_input(0, "Acer WMI hotkeys", "../outside-driver")
        link = self.root / "class/input/input0/device/driver"
        link.unlink()
        link.symlink_to(outside)
        with self.assertRaisesRegex(diagnostic.DiagnosticError, "escaped-sysfs"):
            diagnostic.diagnose(self.root)

    def test_source_has_no_active_input_probe(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("import socket", source)
        self.assertNotIn("/dev/input", source)
        self.assertNotIn("EVIOC", source)


if __name__ == "__main__":
    unittest.main()
