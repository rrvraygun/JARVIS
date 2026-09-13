from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lighting_observation import (
    ADAPTER_ID,
    LightingObservationError,
    collect_passive,
    diagnose,
)


class LightingObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        for relative in (
            "sys/class/backlight/intel_backlight",
            "sys/class/leds/kbd_backlight",
            "sys/class/drm/card0",
            "sys/class/drm/card0-eDP-1",
        ):
            (self.root / relative).mkdir(parents=True)
        self._write("sys/class/backlight/intel_backlight/brightness", "42\n")
        self._write("sys/class/backlight/intel_backlight/actual_brightness", "42\n")
        self._write("sys/class/backlight/intel_backlight/max_brightness", "100\n")
        self._write("sys/class/backlight/intel_backlight/type", "raw\n")
        self._write("sys/class/leds/kbd_backlight/brightness", "2\n")
        self._write("sys/class/leds/kbd_backlight/max_brightness", "3\n")
        self._write("sys/class/leds/kbd_backlight/trigger", "none\n")
        self._write("sys/class/drm/card0-eDP-1/status", "connected\n")

    def _write(self, relative: str, value: str) -> None:
        path = self.root / relative
        path.write_text(value, encoding="utf-8")

    def test_collects_fixed_passive_fields_without_authority(self) -> None:
        observation = collect_passive(root=self.root, observed_at="2026-01-01T00:00:00Z")
        self.assertEqual(observation["adapter_id"], ADAPTER_ID)
        self.assertEqual(observation["backlights"][0]["brightness"], "42")
        self.assertEqual(observation["keyboard_leds"][0]["name"], "kbd_backlight")
        self.assertEqual(observation["graphics"][0]["name"], "card0")
        self.assertFalse(observation["graphics"][0]["connector_status_read"])
        self.assertFalse(observation["device_wake_performed"])
        self.assertFalse(observation["network_used"])
        self.assertFalse(observation["protected_reads_performed"])

    def test_diagnosis_is_evidence_linked_and_non_mutating(self) -> None:
        findings = diagnose(collect_passive(root=self.root, observed_at="fixed"))
        self.assertEqual(findings[0]["status"], "consistent")
        self.assertEqual(findings[-1]["id"], "lighting.keyboard.provider-set")

    def test_mismatch_and_missing_provider_are_explicit(self) -> None:
        self._write("sys/class/backlight/intel_backlight/actual_brightness", "12\n")
        observation = collect_passive(root=self.root, include_graphics=False)
        self.assertEqual(diagnose(observation)[0]["status"], "mismatch")
        shutil.rmtree(self.root / "sys/class/backlight/intel_backlight")
        missing = collect_passive(root=self.root, include_graphics=False)
        self.assertEqual(diagnose(missing)[0]["status"], "unknown")

    def test_device_wake_request_is_rejected(self) -> None:
        with self.assertRaises(LightingObservationError):
            collect_passive(root=self.root, allow_device_wake=True)

    def test_del_and_c1_controls_fail_closed(self) -> None:
        for control in ("\x7f", "\x9b"):
            with self.subTest(control=hex(ord(control))):
                self._write("sys/class/backlight/intel_backlight/brightness", f"42{control}\n")
                with self.assertRaises(LightingObservationError):
                    collect_passive(root=self.root)

    def test_symlink_source_fails_closed(self) -> None:
        target = self.root / "outside"
        target.write_text("99\n", encoding="utf-8")
        source = self.root / "sys/class/backlight/intel_backlight/brightness"
        source.unlink()
        source.symlink_to(target)
        with self.assertRaises(LightingObservationError):
            collect_passive(root=self.root)

    def test_symlinked_ancestor_fails_closed(self) -> None:
        class_path = self.root / "sys/class"
        real_class_path = self.root / "sys/class-real"
        class_path.rename(real_class_path)
        outside = self.root.parent / f"{self.root.name}-class-outside"
        outside.mkdir()
        self.addCleanup(shutil.rmtree, outside)
        class_path.symlink_to(outside, target_is_directory=True)
        try:
            with self.assertRaises(LightingObservationError):
                collect_passive(root=self.root)
        finally:
            class_path.unlink()
            real_class_path.rename(class_path)

    def test_sysfs_provider_symlink_is_followed_inside_fixed_boundary(self) -> None:
        provider = self.root / "sys/class/backlight/intel_backlight"
        target = self.root / "sys/devices/backlight0"
        target.parent.mkdir(parents=True)
        provider.rename(target)
        provider.symlink_to("../../devices/backlight0", target_is_directory=True)
        observation = collect_passive(root=self.root, include_graphics=False)
        self.assertEqual(observation["backlights"][0]["brightness"], "42")

    def test_sysfs_provider_symlink_escape_fails_closed(self) -> None:
        provider = self.root / "sys/class/backlight/intel_backlight"
        outside = self.root.parent / f"{self.root.name}-outside"
        outside.mkdir()
        (outside / "brightness").write_text("99\n", encoding="utf-8")
        self.addCleanup(shutil.rmtree, outside)
        shutil.rmtree(provider)
        provider.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(LightingObservationError):
            collect_passive(root=self.root, include_graphics=False)

    def test_connector_names_do_not_consume_graphics_provider_bound(self) -> None:
        drm = self.root / "sys/class/drm"
        for index in range(40):
            (drm / f"card0-DP-{index}").mkdir()
        (drm / "card1").mkdir()
        observation = collect_passive(root=self.root)
        self.assertEqual([item["name"] for item in observation["graphics"]], ["card0", "card1"])


if __name__ == "__main__":
    unittest.main()
