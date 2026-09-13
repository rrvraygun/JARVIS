from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "plugins/jarvis-system-admin/scripts/collect_lighting_tier3_connector_association.py"
)
REGISTRY = (
    ROOT
    / "plugins/jarvis-system-admin/registry/collectors/lighting-tier3-connector-association.json"
)
KNOWLEDGE = ROOT / "plugins/jarvis-system-admin/scripts/knowledge_store.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


collector = load_module("collect_lighting_tier3_connector_association", SCRIPT)
knowledge = load_module("knowledge_store_for_lighting_tier3", KNOWLEDGE)


class LightingTier3ConnectorAssociationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for relative in (
            "sys/class/drm",
            "sys/class/backlight",
            "sys/bus/pci/devices",
            "sys/bus/pci/drivers/i915",
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

    def populate(self):
        card = self.root / "sys/class/drm/card0"
        card.mkdir(parents=True)
        pci = self.root / "sys/bus/pci/devices/0000:00:02.0"
        pci.mkdir(parents=True)
        self.write("sys/bus/pci/devices/0000:00:02.0/vendor", "0x8086\n")
        self.write("sys/bus/pci/devices/0000:00:02.0/device", "0x46a3\n")
        self.write("sys/bus/pci/devices/0000:00:02.0/class", "0x030000\n")
        (pci / "driver").symlink_to(
            self.root / "sys/bus/pci/drivers/i915", target_is_directory=True
        )
        (card / "device").symlink_to(pci, target_is_directory=True)
        connector = self.root / "sys/class/drm/card0-eDP-1"
        connector.mkdir()
        self.write("sys/class/drm/card0-eDP-1/status", "connected\n")
        provider = self.root / "sys/class/backlight/acpi_video1"
        provider.mkdir()
        self.write("sys/class/backlight/acpi_video1/type", "firmware\n")
        (self.root / "sys/bus/pci/devices/0000:00:02.0/backlight").mkdir(parents=True)
        (provider / "device").symlink_to(pci, target_is_directory=True)

    def test_collects_edp_status_and_backlight_pci_association(self):
        self.populate()
        result = collector.collect(self.config(), self.root, fixture_mode=True)
        value = result["facts"][0]["value"]
        self.assertEqual(value["cards"][0]["pci_device"], "0000:00:02.0")
        self.assertEqual(
            value["internal_edp_connectors"],
            [{"card": "card0", "connector": "card0-eDP-1", "status": "connected"}],
        )
        self.assertEqual(value["backlights"][0]["pci_device"], "0000:00:02.0")
        self.assertTrue(result["attempts"][0]["actual"]["connector_status_may_wake_hardware"])

    def test_malformed_connector_status_fails_closed(self):
        self.populate()
        self.write("sys/class/drm/card0-eDP-1/status", "maybe\n")
        with self.assertRaisesRegex(collector.CollectorError, "connector-status-malformed"):
            collector.collect(self.config(), self.root, fixture_mode=True)

    def test_symlink_escape_fails_closed(self):
        self.populate()
        outside = self.root.parent / f"outside-tier3-{self.root.name}"
        outside.mkdir(exist_ok=True)
        (outside / "acpi_video2").mkdir()
        (outside / "acpi_video2/type").write_text("firmware\n", encoding="utf-8")
        (self.root / "sys/class/backlight/acpi_video2").symlink_to(
            outside / "acpi_video2", target_is_directory=True
        )
        with self.assertRaisesRegex(collector.CollectorError, "escaped-sysfs"):
            collector.collect(self.config(), self.root, fixture_mode=True)

    def test_atomic_output_refuses_overwrite(self):
        output = self.root / "result.json"
        output.write_text("existing", encoding="utf-8")
        with self.assertRaisesRegex(collector.CollectorError, "refusing-to-overwrite"):
            collector.atomic_write(output, {"new": True})
        self.assertEqual(output.read_text(encoding="utf-8"), "existing")

    def test_source_has_no_subprocess_or_write_primitives(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("import socket", source)
        self.assertNotIn("os.O_WRONLY", source)
        self.assertNotIn("wmi_evaluate_method", source)

    def test_inventory_import_is_supported(self):
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
