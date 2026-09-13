"""Typed graphical controls for the Acer Predator RGB driver interface.

This module mirrors the checked-in ``acer-predator-rgb/facer_rgb.py`` argument
contract but never invokes it.  It validates controls and produces a bounded
preview tuple for a future reviewed executor.
"""

from __future__ import annotations

import stat
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

EFFECTS: dict[int, tuple[str, bool]] = {
    0: ("Static", True),
    1: ("Breathing", True),
    2: ("Neon", False),
    3: ("Wave", False),
    4: ("Shifting", True),
    5: ("Zoom", True),
}
COLORS: dict[str, tuple[int, int, int]] = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "cyan": (0, 255, 255),
    "yellow": (255, 255, 0),
    "orange": (255, 128, 0),
    "purple": (255, 0, 255),
    "pink": (255, 32, 160),
    "white": (255, 255, 255),
}


class LightingControlError(ValueError):
    pass


@dataclass(frozen=True)
class LightingSelection:
    mode: int = 0
    brightness: int = 100
    speed: int = 4
    direction: int = 1
    red: int = 255
    green: int = 255
    blue: int = 255
    zones: tuple[int, ...] = (1, 2, 3, 4)

    def validate(self) -> None:
        if self.mode not in EFFECTS:
            raise LightingControlError("unsupported lighting effect")
        if not 0 <= self.brightness <= 100:
            raise LightingControlError("brightness must be 0..100")
        if not 0 <= self.speed <= 9:
            raise LightingControlError("speed must be 0..9")
        if self.direction not in {1, 2}:
            raise LightingControlError("direction must be 1 or 2")
        if any(not 0 <= value <= 255 for value in (self.red, self.green, self.blue)):
            raise LightingControlError("RGB channels must be 0..255")
        if not self.zones or any(zone not in {1, 2, 3, 4} for zone in self.zones):
            raise LightingControlError("zones must be selected from 1..4")


def preview_driver_argv(driver: Path, selection: LightingSelection) -> tuple[tuple[str, ...], ...]:
    """Build fixed driver argv vectors without executing or shell-quoting them."""
    selection.validate()
    base = [str(driver), "-m", str(selection.mode), "-b", str(selection.brightness)]
    if selection.mode != 0:
        base.extend(("-s", str(selection.speed)))
    if EFFECTS[selection.mode][1]:
        base.extend(
            (
                "-cR",
                str(selection.red),
                "-cG",
                str(selection.green),
                "-cB",
                str(selection.blue),
            )
        )
    if selection.mode in {3, 4, 5}:
        base.extend(("-d", str(selection.direction)))
    if selection.mode == 0:
        return tuple(tuple((*base, "-z", str(zone))) for zone in selection.zones)
    return (tuple(base),)


def driver_available(driver: Path) -> bool:
    """Return whether the fixed user-session RGB driver is safe to invoke."""
    try:
        info = driver.lstat()
    except OSError:
        return False
    return (
        stat.S_ISREG(info.st_mode) and bool(info.st_mode & stat.S_IXUSR) and not driver.is_symlink()
    )


def apply_driver_selection(
    driver: Path,
    selection: LightingSelection,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> int:
    """Apply one validated RGB selection through the fixed local driver."""
    if not driver_available(driver):
        raise LightingControlError("Acer RGB driver is unavailable or unsafe")
    commands = preview_driver_argv(driver, selection)
    for command in commands:
        try:
            runner(
                [sys.executable, *command],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise LightingControlError("Acer RGB driver did not apply the selection") from exc
    return len(commands)


def color_name(rgb: tuple[int, int, int]) -> str:
    for name, value in COLORS.items():
        if value == rgb:
            return name
    return "custom"


__all__ = [
    "COLORS",
    "EFFECTS",
    "LightingControlError",
    "LightingSelection",
    "apply_driver_selection",
    "color_name",
    "driver_available",
    "preview_driver_argv",
]
