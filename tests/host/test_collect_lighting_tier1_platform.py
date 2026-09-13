from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins/jarvis-system-admin/scripts/collect_lighting_tier1_platform.py"
REGISTRY = ROOT / "plugins/jarvis-system-admin/registry/collectors/lighting-tier1-platform.json"
KNOWLEDGE = ROOT / "plugins/jarvis-system-admin/scripts/knowledge_store.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


collector = load_module("collect_lighting_tier1_platform", SCRIPT)
knowledge = load_module("knowledge_store_for_lighting_tier1", KNOWLEDGE)


class LightingTier1PlatformTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for relative in (
            "sys/class/dmi/id",
            "sys/module",
            "sys/bus/platform/drivers",
            "sys/bus/platform/devices",
            "sys/class/backlight",
            "sys/class/leds",
            "sys/class/input",
            "sys/bus/pci/drivers/nvidia",
            "sys/bus/pci",
            "sys/bus/acpi",
            "sys/bus/serio/drivers/atkbd",
        ):
            (self.root / relative).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, relative: str, value: str):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def link(self, relative: str, target: str):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(self.root / target)

    def config(self):
        return json.loads(REGISTRY.read_text(encoding="utf-8"))

    def populate(self):
        for field, value in {
            "sys_vendor": "Example Vendor",
            "product_name": "Example Laptop 15",
            "product_version": "REV:1",
            "board_vendor": "Example Vendor",
            "board_name": "EX15",
            "product_serial": "SERIAL-MUST-NOT-APPEAR",
            "product_uuid": "UUID-MUST-NOT-APPEAR",
        }.items():
            self.write(f"sys/class/dmi/id/{field}", value + "\n")
        for name in ("video", "wmi", "nvidia_wmi_ec_backlight", "snd"):
            (self.root / f"sys/module/{name}").mkdir()
        for name in (
            "Acer Wireless Radio Control Driver",
            "nvidia-wmi-ec-backlight",
            "i8042",
        ):
            (self.root / f"sys/bus/platform/drivers/{name}").mkdir()
        for name in ("MSI0007:00", "Fixed MDIO bus.0"):
            (self.root / f"sys/bus/platform/devices/{name}").mkdir()
        device = "sys/class/backlight/nvidia_0/device"
        (self.root / device).mkdir(parents=True)
        self.link(f"{device}/driver", "sys/bus/pci/drivers/nvidia")
        self.link(f"{device}/subsystem", "sys/bus/pci")
        self.link(f"{device}/firmware_node/subsystem", "sys/bus/acpi")
        self.write(
            f"{device}/uevent",
            "DRIVER=nvidia\nPCI_CLASS=30000\nPCI_ID=10DE:28A0\nPCI_SLOT_NAME=01:00.0\nMODALIAS=pci:v000010DEd000028A0\n",
        )
        (self.root / "sys/class/leds/platform::kbd_backlight").mkdir()
        (self.root / "sys/class/leds/input3::capslock").mkdir()
        self.write("sys/class/input/input0/name", "AT Translated Set 2 keyboard\n")
        for field, value in {
            "bustype": "0011",
            "vendor": "0001",
            "product": "0001",
            "version": "ab41",
        }.items():
            self.write(f"sys/class/input/input0/id/{field}", value + "\n")
        self.link("sys/class/input/input0/device/driver", "sys/bus/serio/drivers/atkbd")
        self.write("sys/class/input/input1/name", "Power Button\n")
        self.write("sys/class/input/input2/name", "Acer Wireless Radio Control\n")
        self.link(
            "sys/class/input/input2/device/driver",
            "sys/bus/platform/drivers/Acer Wireless Radio Control Driver",
        )

    def fact_map(self, result):
        return {item["fact_key"]: item["value"] for item in result["facts"]}

    def test_collects_bounded_platform_and_interface_metadata(self):
        self.populate()
        result = collector.collect(self.config(), self.root, fixture_mode=True)
        facts = self.fact_map(result)
        self.assertEqual(facts["hardware.platform.identity"]["product_name"], "Example Laptop 15")
        self.assertEqual(
            facts["lighting.platform.interfaces"]["module_names"],
            ["nvidia_wmi_ec_backlight", "video", "wmi"],
        )
        self.assertEqual(
            facts["lighting.platform.interfaces"]["platform_driver_names"],
            ["Acer Wireless Radio Control Driver", "nvidia-wmi-ec-backlight"],
        )
        self.assertEqual(
            facts["lighting.platform.interfaces"]["platform_device_names"],
            ["MSI0007:00"],
        )
        self.assertEqual(
            facts["lighting.platform.interfaces"]["candidate_led_names"],
            ["platform::kbd_backlight"],
        )
        topology = facts["lighting.backlight.topology"][0]
        self.assertEqual(topology["driver"], "nvidia")
        self.assertEqual(topology["device_bus"], "pci")
        self.assertEqual(topology["firmware_node_class"], "acpi")
        self.assertEqual(topology["uevent_identity"]["pci_id"], "10DE:28A0")
        self.assertNotIn("pci_slot_name", topology["uevent_identity"])
        self.assertEqual(facts["input.hotkey.candidates"][0]["driver"], "atkbd")
        self.assertEqual(
            facts["input.hotkey.candidates"][1]["driver"],
            "Acer Wireless Radio Control Driver",
        )
        self.assertFalse(result["attempts"][0]["actual"]["state_change"])

    def test_serials_and_uuid_are_never_collected(self):
        self.populate()
        encoded = json.dumps(collector.collect(self.config(), self.root, fixture_mode=True))
        self.assertNotIn("SERIAL-MUST-NOT-APPEAR", encoded)
        self.assertNotIn("UUID-MUST-NOT-APPEAR", encoded)
        self.assertFalse(json.loads(encoded)["privacy"]["serial_or_uuid_persisted"])

    def test_sensitive_field_policy_tampering_fails_closed(self):
        self.populate()
        config = self.config()
        config["probe_groups"][0]["forbidden_fields"].remove("product_uuid")
        with self.assertRaisesRegex(collector.CollectorError, "sensitive-field-policy-invalid"):
            collector.collect(config, self.root, fixture_mode=True)

    def test_symlink_escape_fails_closed(self):
        outside = self.root.parent / "outside-tier1-platform"
        outside.mkdir(exist_ok=True)
        (outside / "product_name").write_text("Outside\n", encoding="utf-8")
        dmi = self.root / "sys/class/dmi/id"
        for child in dmi.iterdir():
            child.unlink()
        dmi.rmdir()
        dmi.symlink_to(outside)
        with self.assertRaisesRegex(collector.CollectorError, "escaped-allowlisted-root"):
            collector.collect(self.config(), self.root, fixture_mode=True)

    def test_backlight_provider_limit_fails_closed(self):
        for number in range(collector.MAX_BACKLIGHTS + 1):
            (self.root / f"sys/class/backlight/provider{number}").mkdir()
        with self.assertRaisesRegex(collector.CollectorError, "entry-limit-exceeded"):
            collector.collect(self.config(), self.root, fixture_mode=True)

    def test_malformed_allowlisted_uevent_fails_closed(self):
        self.populate()
        self.write("sys/class/backlight/nvidia_0/device/uevent", "DRIVER=nvidia\nBROKEN\n")
        with self.assertRaisesRegex(collector.CollectorError, "uevent-line-malformed"):
            collector.collect(self.config(), self.root, fixture_mode=True)

    def test_relevant_interface_control_character_fails_closed(self):
        (self.root / "sys/bus/platform/drivers/Acer\nDriver").mkdir()
        with self.assertRaisesRegex(collector.CollectorError, "unsafe-platform-driver-name"):
            collector.collect(self.config(), self.root, fixture_mode=True)

    def test_atomic_output_refuses_overwrite(self):
        output = self.root / "result.json"
        output.write_text("existing", encoding="utf-8")
        with self.assertRaisesRegex(collector.CollectorError, "refusing-to-overwrite"):
            collector.atomic_write(output, {"new": True})
        self.assertEqual(output.read_text(encoding="utf-8"), "existing")

    def test_source_and_registry_forbid_active_probes(self):
        source = SCRIPT.read_text(encoding="utf-8")
        config = self.config()
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("import socket", source)
        self.assertNotIn("/dev/input", source)
        self.assertNotIn("connector/status", source)
        self.assertNotIn("gdbus", source)
        forbidden = " ".join(config["forbidden_operations"])
        self.assertIn("D-Bus call", forbidden)
        self.assertIn("raw input-event", forbidden)
        self.assertIn("serial or UUID", forbidden)

    def test_platform_inventory_import_is_supported(self):
        self.populate()
        result = collector.collect(self.config(), self.root, fixture_mode=True)
        database = self.root / "knowledge.db"
        knowledge.init_database(database)
        connection = knowledge.connect(database)
        try:
            with connection:
                imported = knowledge.import_inventory(connection, result)
            self.assertEqual(len(imported["attempts"]), 1)
            self.assertEqual(len(imported["facts"]), 4)
            count = connection.execute("SELECT COUNT(*) FROM current_facts").fetchone()[0]
            self.assertEqual(count, 4)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
