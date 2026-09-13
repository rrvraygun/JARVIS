#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import json
import tempfile
import unittest
from unittest import mock


TUI_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = TUI_ROOT.parent
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.local_control import (
    MAX_INSPECTION_DISPLAY_BYTES,
    ReadOnlyLocalControl,
    format_host_inspection,
    format_power_inspection,
)  # noqa: E402
from jarvis_tui.power_inventory import PowerInventory, PowerSetting  # noqa: E402


class LocalControlTests(unittest.TestCase):
    def test_missing_knowledge_database_is_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            control = ReadOnlyLocalControl(Path(temporary))
            path = control.knowledge_db
            status = control.knowledge_status()
            self.assertFalse(status["available"])
            self.assertEqual(status["reason"], "knowledge_database_missing")
            self.assertFalse(status["package_catalog"]["available"])
            self.assertFalse(path.exists())

    def test_registry_and_knowledge_reads_are_read_only(self) -> None:
        control = ReadOnlyLocalControl(BUNDLE_ROOT)
        self.assertTrue(any(item["id"] == "health" for item in control.capabilities()))
        self.assertTrue(any(item["id"] == "health.lighting.diagnose" for item in control.actions()))
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "knowledge.db"
            module_path = BUNDLE_ROOT / "plugins/jarvis-system-admin/scripts/knowledge_store.py"
            spec = importlib.util.spec_from_file_location("fixture_knowledge", module_path)
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            spec.loader.exec_module(module)
            module.init_database(database)
            before = database.stat().st_mtime_ns
            control.knowledge_db = database
            status = control.knowledge_status()
            results = control.query_knowledge("sources", "fixture", 5)
            after = database.stat().st_mtime_ns
            self.assertTrue(status["available"])
            self.assertTrue(status["read_only"])
            self.assertEqual(results, ())
            self.assertEqual(before, after)

    def test_recovery_status_is_redacted_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "runtime/reports"
            reports.mkdir(parents=True)
            (reports / "2026-08-07-r1-local-snapshot.json").write_text(
                json.dumps({"status": "completed", "target": "fixture-private-target"})
            )
            (reports / "2026-08-07-r2-live-recovery-boundary.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "independent_comparison": {"mismatch_total": 0, "proof_gaps": []},
                    }
                )
            )
            control = ReadOnlyLocalControl(root)
            status = control.recovery_status()
            self.assertEqual(status["r1"]["status"], "completed")
            self.assertEqual(status["r2"]["mismatch_total"], 0)
            self.assertEqual(status["r2"]["proof_gaps"], 0)
            self.assertNotIn("target", status["r1"])

    @mock.patch("jarvis_tui.local_control.scan_rpm")
    @mock.patch("jarvis_tui.local_control.scan_power_inventory")
    def test_power_inspection_includes_settings_packages_and_modules(
        self, power_mock, rpm_mock
    ) -> None:
        power_mock.return_value = PowerInventory(
            providers=("intel_pstate",),
            settings=(PowerSetting("CPU", "EPP", "balance_power", "performance", "/sys/test"),),
            limitations=("read-only",),
        )
        rpm_mock.return_value = ()
        result = ReadOnlyLocalControl(BUNDLE_ROOT).inspect_power()
        self.assertTrue(result["read_only"])
        self.assertEqual(result["providers"], ["intel_pstate"])
        self.assertEqual(result["settings"][0]["current"], "balance_power")
        self.assertIn("loaded_modules", result)
        self.assertIn("packages", result)
        rendered = format_power_inspection(result)
        self.assertIn("HOST INSPECTION: POWER", rendered)
        self.assertIn("SETTINGS: CPU", rendered)
        self.assertNotIn('"providers"', rendered)
        self.assertLessEqual(len(rendered.encode("utf-8")), MAX_INSPECTION_DISPLAY_BYTES + 180)

    @mock.patch.object(ReadOnlyLocalControl, "inspect_packages")
    @mock.patch.object(ReadOnlyLocalControl, "inspect_power")
    def test_host_inspection_selects_only_bounded_relevant_collectors(
        self, power_mock, packages_mock
    ) -> None:
        power_mock.return_value = {
            "read_only": True,
            "providers": [],
            "settings": [],
            "packages": [],
            "loaded_modules": [],
            "limitations": [],
        }
        packages_mock.return_value = {
            "available": True,
            "matches": [],
            "installed_count": 1,
            "available_count": 2,
        }
        control = ReadOnlyLocalControl(BUNDLE_ROOT)
        result = control.inspect_host(
            "Which Rust package and power driver should I inspect?", refresh_packages=True
        )
        self.assertEqual(result["scopes"], ["platform", "power", "packages"])
        power_mock.assert_called_once_with()
        packages_mock.assert_called_once_with(
            "Which Rust package and power driver should I inspect?", refresh=True
        )
        rendered = format_host_inspection(result)
        self.assertIn("HOST INSPECTION (READ-ONLY)", rendered)
        self.assertIn("HOST INSPECTION: PACKAGES", rendered)


if __name__ == "__main__":
    unittest.main()
