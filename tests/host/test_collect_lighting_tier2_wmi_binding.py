from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins/jarvis-system-admin/scripts/collect_lighting_tier2_wmi_binding.py"
REGISTRY = ROOT / "plugins/jarvis-system-admin/registry/collectors/lighting-tier2-wmi-binding.json"
KNOWLEDGE = ROOT / "plugins/jarvis-system-admin/scripts/knowledge_store.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


collector = load_module("collect_lighting_tier2_wmi_binding", SCRIPT)
knowledge = load_module("knowledge_store_for_lighting_tier2", KNOWLEDGE)


class LightingTier2WmiBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for relative in (
            "sys/bus/wmi/devices",
            "sys/bus/wmi/drivers/nvidia-wmi-ec-backlight",
            "sys/module/nvidia_wmi_ec_backlight/parameters",
            "sys/class/backlight",
        ):
            (self.root / relative).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, relative: str, value: str):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def config(self):
        return json.loads(REGISTRY.read_text(encoding="utf-8"))

    def populate(self, bound: bool = False):
        instance = collector.GUID + "-00"
        device = self.root / f"sys/bus/wmi/devices/{instance}"
        device.mkdir()
        if bound:
            (self.root / f"sys/bus/wmi/drivers/nvidia-wmi-ec-backlight/{instance}").symlink_to(
                device
            )
        self.write("sys/module/nvidia_wmi_ec_backlight/parameters/force", "N\n")
        self.write("sys/class/backlight/intel_backlight/type", "raw\n")
        self.write("sys/class/backlight/nvidia_0/type", "raw\n")

    def value(self, result):
        return result["facts"][0]["value"]

    def test_observes_present_guid_unbound_with_force_false(self):
        self.populate(bound=False)
        result = collector.collect(self.config(), self.root, fixture_mode=True)
        value = self.value(result)
        self.assertEqual(value["firmware_guid_instances"], [collector.GUID + "-00"])
        self.assertEqual(value["bound_guid_instances"], [])
        self.assertFalse(value["module_force"])
        self.assertEqual(
            value["registered_backlights"],
            [
                {"name": "intel_backlight", "type": "raw"},
                {"name": "nvidia_0", "type": "raw"},
            ],
        )
        self.assertFalse(result["attempts"][0]["actual"]["wmi_method_evaluated"])

    def test_observes_bound_guid_without_following_device(self):
        self.populate(bound=True)
        value = self.value(collector.collect(self.config(), self.root, fixture_mode=True))
        self.assertEqual(value["bound_guid_instances"], [collector.GUID + "-00"])

    def test_malformed_force_parameter_fails_closed(self):
        self.populate()
        self.write("sys/module/nvidia_wmi_ec_backlight/parameters/force", "maybe\n")
        with self.assertRaisesRegex(collector.CollectorError, "boolean-module-parameter-malformed"):
            collector.collect(self.config(), self.root, fixture_mode=True)

    def test_wmi_device_limit_fails_closed(self):
        for number in range(collector.MAX_WMI_DEVICES + 1):
            (self.root / f"sys/bus/wmi/devices/device{number}").mkdir()
        with self.assertRaisesRegex(collector.CollectorError, "entry-limit-exceeded"):
            collector.collect(self.config(), self.root, fixture_mode=True)

    def test_atomic_output_refuses_overwrite(self):
        output = self.root / "result.json"
        output.write_text("existing", encoding="utf-8")
        with self.assertRaisesRegex(collector.CollectorError, "refusing-to-overwrite"):
            collector.atomic_write(output, {"new": True})
        self.assertEqual(output.read_text(encoding="utf-8"), "existing")

    def test_source_and_registry_forbid_method_evaluation(self):
        source = SCRIPT.read_text(encoding="utf-8")
        forbidden = " ".join(self.config()["forbidden_operations"])
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("import socket", source)
        self.assertNotIn("wmidev_evaluate_method", source)
        self.assertNotIn("gdbus", source)
        self.assertIn("WMI method evaluation", forbidden)
        self.assertIn("module parameter write", forbidden)

    def test_wmi_inventory_import_is_supported(self):
        self.populate()
        result = collector.collect(self.config(), self.root, fixture_mode=True)
        database = self.root / "knowledge.db"
        knowledge.init_database(database)
        connection = knowledge.connect(database)
        try:
            with connection:
                imported = knowledge.import_inventory(connection, result)
            self.assertEqual(len(imported["attempts"]), 1)
            self.assertEqual(len(imported["facts"]), 1)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
