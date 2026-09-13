from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


TUI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.lighting_controls import (  # noqa: E402
    LightingControlError,
    LightingSelection,
    apply_driver_selection,
    driver_available,
    preview_driver_argv,
)


class LightingControlTests(unittest.TestCase):
    def test_static_preview_expands_selected_zones(self) -> None:
        commands = preview_driver_argv(
            Path("facer_rgb.py"),
            LightingSelection(mode=0, brightness=75, red=1, green=2, blue=3, zones=(1, 4)),
        )
        self.assertEqual(len(commands), 2)
        self.assertIn("-z", commands[0])
        self.assertIn("75", commands[1])
        self.assertNotIn("python", " ".join(commands[0]))

    def test_animation_preview_has_speed_direction_and_color_when_supported(self) -> None:
        command = preview_driver_argv(
            Path("facer_rgb.py"),
            LightingSelection(
                mode=4, brightness=50, speed=7, direction=2, red=10, green=20, blue=30
            ),
        )[0]
        self.assertEqual(command[1:4], ("-m", "4", "-b"))
        self.assertIn("-s", command)
        self.assertIn("-d", command)
        self.assertIn("-cR", command)

    def test_bounds_are_rejected(self) -> None:
        with self.assertRaises(LightingControlError):
            preview_driver_argv(Path("facer_rgb.py"), LightingSelection(brightness=101))
        with self.assertRaises(LightingControlError):
            preview_driver_argv(Path("facer_rgb.py"), LightingSelection(speed=10))

    def test_apply_uses_fixed_argv_without_shell(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            driver = Path(directory) / "facer_rgb.py"
            driver.write_text("fixture", encoding="utf-8")
            driver.chmod(0o755)
            calls = []

            def runner(argv, **kwargs):
                calls.append((argv, kwargs))
                return subprocess.CompletedProcess(argv, 0, "", "")

            self.assertTrue(driver_available(driver))
            self.assertEqual(
                apply_driver_selection(
                    driver, LightingSelection(mode=0, zones=(1, 2)), runner=runner
                ),
                2,
            )
            self.assertTrue(all(call[1]["shell"] is False for call in calls))
            self.assertTrue(all(call[0][0] == sys.executable for call in calls))


if __name__ == "__main__":
    unittest.main()
