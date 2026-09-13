from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deployment/host/diagnose_lighting_tier1_name_contract.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


diagnostic = load_module("diagnose_lighting_tier1_name_contract", SCRIPT)


class LightingTier1NameContractDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "sys"
        (self.root / "bus/platform/drivers").mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def test_reports_only_relevant_rejected_names(self):
        for name in ("video", "ACPI PMIC opregion", "Fixed MDIO bus.0", "snd"):
            (self.root / f"bus/platform/drivers/{name}").mkdir()
        result = diagnostic.diagnose(self.root)
        self.assertEqual(result["relevant_entries"], 2)
        self.assertEqual(
            [item["name"] for item in result["rejected_entries"]],
            ["ACPI PMIC opregion"],
        )
        self.assertIn("U+0020", result["rejected_entries"][0]["codepoints"])
        self.assertEqual(result["files_read_inside_entries"], 0)
        self.assertFalse(result["state_change"])

    def test_entry_limit_fails_closed(self):
        for number in range(diagnostic.MAX_PLATFORM_DRIVERS + 1):
            (self.root / f"bus/platform/drivers/driver{number}").mkdir()
        with self.assertRaisesRegex(diagnostic.DiagnosticError, "entry-limit-exceeded"):
            diagnostic.diagnose(self.root)

    def test_symlink_escape_fails_closed(self):
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        drivers = self.root / "bus/platform/drivers"
        drivers.rmdir()
        drivers.symlink_to(outside)
        with self.assertRaisesRegex(diagnostic.DiagnosticError, "escaped-sysfs"):
            diagnostic.diagnose(self.root)

    def test_source_has_no_active_probe_facility(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("import socket", source)
        self.assertNotIn("open(", source)
        self.assertNotIn("/dev/", source)


if __name__ == "__main__":
    unittest.main()
