from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins/jarvis-system-admin/scripts/collect_lighting_tier0.py"
REGISTRY = ROOT / "plugins/jarvis-system-admin/registry/collectors/lighting-tier0.json"
KNOWLEDGE = ROOT / "plugins/jarvis-system-admin/scripts/knowledge_store.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


collector = load_module("collect_lighting_tier0", SCRIPT)
knowledge = load_module("knowledge_store_for_lighting", KNOWLEDGE)


class LightingTier0Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "sys/class/backlight").mkdir(parents=True)
        (self.root / "sys/class/leds").mkdir(parents=True)
        (self.root / "sys/class/drm").mkdir(parents=True)
        (self.root / "sys/bus/pci/drivers/i915").mkdir(parents=True)
        (self.root / "sys/bus/pci/drivers/nvidia").mkdir(parents=True)
        (self.root / "proc").mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, relative: str, value: str):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def driver(self, relative: str, driver: str):
        link = self.root / relative
        link.parent.mkdir(parents=True, exist_ok=True)
        target = self.root / f"sys/bus/pci/drivers/{driver}"
        link.symlink_to(target)

    def populate(self):
        for field, value in {
            "brightness": "400\n",
            "actual_brightness": "399\n",
            "max_brightness": "1200\n",
            "type": "raw\n",
            "bl_power": "0\n",
        }.items():
            self.write(f"sys/class/backlight/intel_backlight/{field}", value)
        self.driver("sys/class/backlight/intel_backlight/device/driver", "i915")
        self.write("sys/class/leds/platform::kbd_backlight/brightness", "1\n")
        self.write("sys/class/leds/platform::kbd_backlight/max_brightness", "3\n")
        self.write("sys/class/leds/platform::kbd_backlight/trigger", "none [kbd-scrolllock]\n")
        self.write("sys/class/leds/input3::capslock/brightness", "0\n")
        for card, vendor, device, driver, boot, status, usage, control in (
            ("card0", "0x8086", "0x1234", "i915", "1", "active", "1", "auto"),
            ("card1", "0x10de", "0x5678", "nvidia", "0", "suspended", "0", "auto"),
        ):
            base = f"sys/class/drm/{card}/device"
            self.write(f"{base}/vendor", vendor + "\n")
            self.write(f"{base}/device", device + "\n")
            self.write(f"{base}/class", "0x030000\n")
            self.write(f"{base}/boot_vga", boot + "\n")
            self.write(f"{base}/power/runtime_status", status + "\n")
            self.write(f"{base}/power/runtime_usage", usage + "\n")
            self.write(f"{base}/power/control", control + "\n")
            self.driver(f"{base}/driver", driver)
        (self.root / "sys/class/drm/card0-eDP-1").mkdir()
        (self.root / "sys/class/drm/card1-HDMI-A-1").mkdir()
        self.write(
            "proc/cmdline",
            "quiet rd.luks.uuid=private nvidia-drm.modeset=1 acpi_backlight=native\n",
        )
        self.write(
            "proc/modules",
            "i915 1 0 - Live 0x0\nnvidia 1 0 - Live 0x0\nsnd 1 0 - Live 0x0\n",
        )

    def config(self):
        return json.loads(REGISTRY.read_text(encoding="utf-8"))

    def fact_map(self, result):
        return {item["fact_key"]: item["value"] for item in result["facts"]}

    def test_collects_only_bounded_relevant_metadata(self):
        self.populate()
        result = collector.collect(self.config(), self.root, fixture_mode=True)
        facts = self.fact_map(result)
        self.assertEqual(facts["lighting.display.providers"][0]["actual_brightness"], 399)
        self.assertEqual(
            [item["name"] for item in facts["lighting.keyboard.providers"]],
            ["platform::kbd_backlight"],
        )
        self.assertEqual(facts["graphics.adapters"][1]["runtime_status"], "suspended")
        self.assertEqual(facts["graphics.routing"]["card0"], ["card0-eDP-1"])
        self.assertEqual(
            facts["kernel.graphics.context"]["relevant_boot_parameters"],
            ["acpi_backlight=native", "nvidia-drm.modeset=1"],
        )
        self.assertNotIn("private", json.dumps(result))
        self.assertFalse(result["attempts"][0]["actual"]["device_wake_operation_attempted"])

    def test_malformed_numeric_field_fails_closed(self):
        self.populate()
        self.write("sys/class/backlight/intel_backlight/brightness", "not-a-number\n")
        with self.assertRaisesRegex(collector.CollectorError, "integer-malformed"):
            collector.collect(self.config(), self.root, fixture_mode=True)

    def test_symlink_escape_fails_closed(self):
        outside = self.root.parent / "outside-lighting-provider"
        outside.mkdir(exist_ok=True)
        (outside / "brightness").write_text("1\n", encoding="utf-8")
        (self.root / "sys/class/backlight/escape").symlink_to(outside)
        self.write("proc/cmdline", "quiet\n")
        self.write("proc/modules", "")
        with self.assertRaisesRegex(collector.CollectorError, "escaped-allowlisted-root"):
            collector.collect(self.config(), self.root, fixture_mode=True)

    def test_provider_limit_fails_closed(self):
        self.write("proc/cmdline", "quiet\n")
        self.write("proc/modules", "")
        for number in range(collector.MAX_BACKLIGHTS + 1):
            (self.root / f"sys/class/backlight/provider{number}").mkdir()
        with self.assertRaisesRegex(collector.CollectorError, "entry-limit-exceeded"):
            collector.collect(self.config(), self.root, fixture_mode=True)

    def test_atomic_output_refuses_overwrite(self):
        output = self.root / "result.json"
        output.write_text("existing", encoding="utf-8")
        with self.assertRaisesRegex(collector.CollectorError, "refusing-to-overwrite"):
            collector.atomic_write(output, {"new": True})
        self.assertEqual(output.read_text(encoding="utf-8"), "existing")

    def test_source_has_no_subprocess_or_network_import(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("import socket", source)
        self.assertNotIn("connector/status", source)
        self.assertNotIn("nvidia-smi", source)

    def test_lighting_inventory_import_is_supported(self):
        self.populate()
        result = collector.collect(self.config(), self.root, fixture_mode=True)
        database = self.root / "knowledge.db"
        knowledge.init_database(database)
        connection = knowledge.connect(database)
        try:
            with connection:
                imported = knowledge.import_inventory(connection, result)
            self.assertEqual(len(imported["attempts"]), 1)
            self.assertEqual(len(imported["facts"]), 5)
            count = connection.execute("SELECT COUNT(*) FROM current_facts").fetchone()[0]
            self.assertEqual(count, 5)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
