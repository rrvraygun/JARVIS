#!/usr/bin/env python3
"""Bounded, passive lighting and graphics observation contract.

This adapter is prepared for a future reviewed host registration.  It reads
only fixed sysfs-style paths supplied by the caller, never writes, never opens
a device, never invokes a command, and never uses the network.  Credentials,
tokens, private keys, cookies, and arbitrary protected files are outside its
scope.  A separate graphics-power probe is intentionally opt-in and still
rejects device-waking requests in this revision.
"""

from __future__ import annotations

import datetime as dt
import errno
import json
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class LightingObservationError(ValueError):
    """Raised when a bounded observation cannot be completed safely."""


ADAPTER_ID = "fedora.lighting.passive-readonly"
ADAPTER_REVISION = "1.0.0"
MAX_PROVIDERS = 32
MAX_FIELD_BYTES = 512
MAX_TOTAL_BYTES = 32_768
KEYBOARD_LED_NAMES = ("kbd_backlight", "kbd_zoned_backlight-")


@dataclass(frozen=True)
class LightingObservation:
    adapter_id: str
    adapter_revision: str
    observed_at: str
    backlights: tuple[dict[str, Any], ...]
    keyboard_leds: tuple[dict[str, Any], ...]
    graphics: tuple[dict[str, Any], ...]
    device_wake_performed: bool = False
    network_used: bool = False
    protected_reads_performed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "status": "observed_passive_readonly",
            "adapter_id": self.adapter_id,
            "adapter_revision": self.adapter_revision,
            "observed_at": self.observed_at,
            "backlights": list(self.backlights),
            "keyboard_leds": list(self.keyboard_leds),
            "graphics": list(self.graphics),
            "device_wake_performed": self.device_wake_performed,
            "network_used": self.network_used,
            "protected_reads_performed": self.protected_reads_performed,
        }


def _safe_name(value: str) -> str:
    if (
        not value
        or len(value) > 128
        or any(ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F for char in value)
    ):
        raise LightingObservationError("provider name is invalid")
    return value


def _open_directory(path: Path) -> int:
    try:
        return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as exc:
        raise LightingObservationError("observation root unavailable") from exc


def _open_child_directory(
    parent: int, name: str, *, optional: bool = False, boundary: int | None = None
) -> int | None:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    try:
        return os.open(
            name,
            flags | os.O_NOFOLLOW,
            dir_fd=parent,
        )
    except OSError as exc:
        if exc.errno not in (errno.ELOOP, errno.ENOTDIR):
            if isinstance(exc, FileNotFoundError) and optional:
                return None
            raise LightingObservationError(
                "observation directory is unsafe or unavailable"
            ) from exc
        # Sysfs class entries are normally symlinks into /sys/devices. Follow
        # the final link only after opening it, then bind the resulting
        # descriptor to the fixed sysfs boundary to prevent escape.
        try:
            descriptor = os.open(name, flags, dir_fd=parent)
            if boundary is not None:
                target = os.path.realpath(f"/proc/self/fd/{descriptor}")
                base = os.path.realpath(f"/proc/self/fd/{boundary}")
                if os.path.commonpath((base, target)) != base:
                    os.close(descriptor)
                    raise LightingObservationError("observation symlink escapes fixed boundary")
            return descriptor
        except FileNotFoundError:
            if optional:
                return None
            raise LightingObservationError("observation directory unavailable")
        except LightingObservationError:
            raise
        except OSError as follow_exc:
            raise LightingObservationError(
                "observation symlink target is unsafe or unavailable"
            ) from follow_exc


def _open_tree(root: int, parts: tuple[str, ...], *, boundary: int | None = None) -> int | None:
    """Open a fixed directory tree, closing intermediate descriptors."""
    current = root
    try:
        for part in parts:
            next_fd = _open_child_directory(current, part, optional=True, boundary=boundary or root)
            if next_fd is None:
                if current != root:
                    os.close(current)
                return None
            if current != root:
                os.close(current)
            current = next_fd
        return current
    except Exception:
        if current != root:
            os.close(current)
        raise


def _read_text_at(parent: int, name: str, maximum: int = MAX_FIELD_BYTES) -> str:
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
    except OSError as exc:
        raise LightingObservationError("observation source unavailable") from exc
    try:
        identity = os.fstat(descriptor)
        if not stat.S_ISREG(identity.st_mode):
            raise LightingObservationError("observation source is not a regular file")
        raw = os.read(descriptor, maximum + 1)
    except OSError as exc:
        raise LightingObservationError("observation source read failed") from exc
    finally:
        os.close(descriptor)
    if len(raw) > maximum:
        raise LightingObservationError("observation field exceeds bound")
    try:
        value = raw.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise LightingObservationError("observation field is not UTF-8") from exc
    if any(
        (ord(char) < 0x20 and char not in "\t\n\r") or 0x7F <= ord(char) <= 0x9F for char in value
    ):
        raise LightingObservationError("observation field contains terminal controls")
    return value


def _provider_names(
    directory: int,
    *,
    prefix: str | None = None,
    name_filter: Callable[[str], bool] | None = None,
) -> tuple[str, ...]:
    try:
        with os.scandir(directory) as iterator:
            entries = iterator
            names: list[str] = []
            for entry in entries:
                if not entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                    continue
                if prefix is not None and not (
                    entry.name == prefix or entry.name.startswith(prefix)
                ):
                    continue
                if name_filter is not None and not name_filter(entry.name):
                    continue
                names.append(_safe_name(entry.name))
                if len(names) > MAX_PROVIDERS:
                    raise LightingObservationError("observation provider count exceeds bound")
    except OSError as exc:
        raise LightingObservationError("observation provider directory unavailable") from exc
    return tuple(sorted(names))


def _optional_field(parent: int, name: str) -> str | None:
    try:
        os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise LightingObservationError("observation source unavailable") from exc
    return _read_text_at(parent, name)


def _backlight(directory: int, name: str, *, boundary: int) -> dict[str, Any]:
    base = _open_child_directory(directory, name, boundary=boundary)
    assert base is not None
    try:
        return {
            "name": name,
            "brightness": _optional_field(base, "brightness"),
            "actual_brightness": _optional_field(base, "actual_brightness"),
            "max_brightness": _optional_field(base, "max_brightness"),
            "type": _optional_field(base, "type"),
            "bl_power": _optional_field(base, "bl_power"),
        }
    finally:
        os.close(base)


def _keyboard_led(directory: int, name: str, *, boundary: int) -> dict[str, Any]:
    base = _open_child_directory(directory, name, boundary=boundary)
    assert base is not None
    try:
        return {
            "name": name,
            "brightness": _optional_field(base, "brightness"),
            "max_brightness": _optional_field(base, "max_brightness"),
            "trigger": _optional_field(base, "trigger"),
        }
    finally:
        os.close(base)


def _graphics(directory: int, *, boundary: int) -> tuple[dict[str, Any], ...]:
    # DRM connector directories (for example card0-eDP-1) are intentionally
    # excluded: reading connector status can wake display hardware. Card
    # identity is passive metadata and needs no attribute read.
    names = tuple(
        _provider_names(
            directory,
            prefix="card",
            name_filter=lambda name: name.startswith("card") and name[4:].isdigit(),
        )
    )
    return tuple({"name": name, "connector_status_read": False} for name in names)


def collect_passive(
    *,
    root: Path = Path("/"),
    observed_at: str | None = None,
    include_graphics: bool = True,
    allow_device_wake: bool = False,
) -> dict[str, Any]:
    """Collect one bounded passive observation from a fixed filesystem root."""
    if allow_device_wake:
        raise LightingObservationError("device-waking probes are a separate reviewed adapter")
    root_descriptor = _open_directory(root)
    try:
        sys_directory = _open_child_directory(
            root_descriptor, "sys", optional=True, boundary=root_descriptor
        )
        if sys_directory is None:
            backlights, keyboard, graphics = (), (), ()
        else:
            try:
                backlight_directory = _open_tree(
                    sys_directory, ("class", "backlight"), boundary=sys_directory
                )
                try:
                    backlights = tuple(
                        _backlight(backlight_directory, name, boundary=sys_directory)
                        for name in (
                            _provider_names(backlight_directory)
                            if backlight_directory is not None
                            else ()
                        )
                    )
                finally:
                    if backlight_directory is not None:
                        os.close(backlight_directory)

                led_directory = _open_tree(sys_directory, ("class", "leds"), boundary=sys_directory)
                try:
                    keyboard = tuple(
                        _keyboard_led(led_directory, name, boundary=sys_directory)
                        for name in (
                            _provider_names(led_directory) if led_directory is not None else ()
                        )
                        if name == KEYBOARD_LED_NAMES[0] or name.startswith(KEYBOARD_LED_NAMES[1])
                    )
                finally:
                    if led_directory is not None:
                        os.close(led_directory)

                if include_graphics:
                    drm_directory = _open_tree(
                        sys_directory, ("class", "drm"), boundary=sys_directory
                    )
                    try:
                        graphics = (
                            _graphics(drm_directory, boundary=sys_directory)
                            if drm_directory is not None
                            else ()
                        )
                    finally:
                        if drm_directory is not None:
                            os.close(drm_directory)
                else:
                    graphics = ()
            finally:
                os.close(sys_directory)
    finally:
        os.close(root_descriptor)
    result = LightingObservation(
        adapter_id=ADAPTER_ID,
        adapter_revision=ADAPTER_REVISION,
        observed_at=observed_at
        or dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        backlights=backlights,
        keyboard_leds=keyboard,
        graphics=graphics,
    ).as_dict()
    if (
        len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        > MAX_TOTAL_BYTES
    ):
        raise LightingObservationError("observation output exceeds bound")
    return result


def diagnose(observation: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Produce evidence-linked, non-mutating diagnostic findings."""
    if not isinstance(observation, dict) or observation.get("adapter_id") != ADAPTER_ID:
        raise LightingObservationError("observation identity is invalid")
    findings: list[dict[str, Any]] = []
    backlights = observation.get("backlights")
    if not isinstance(backlights, list):
        raise LightingObservationError("backlight observation shape is invalid")
    if not backlights:
        findings.append(
            {
                "id": "lighting.backlight.provider-missing",
                "status": "unknown",
                "evidence": "no provider observed",
            }
        )
    for provider in backlights:
        name = _safe_name(str(provider.get("name", "")))
        brightness = provider.get("brightness")
        actual = provider.get("actual_brightness")
        maximum = provider.get("max_brightness")
        if brightness is None or actual is None or maximum is None:
            findings.append(
                {
                    "id": "lighting.backlight.incomplete-state",
                    "status": "unknown",
                    "provider": name,
                }
            )
            continue
        try:
            requested, current, limit = int(brightness), int(actual), int(maximum)
        except (TypeError, ValueError):
            findings.append(
                {
                    "id": "lighting.backlight.invalid-numeric-state",
                    "status": "failed",
                    "provider": name,
                }
            )
            continue
        status = "consistent" if requested == current and 0 <= current <= limit else "mismatch"
        findings.append(
            {
                "id": "lighting.backlight.requested-vs-actual",
                "status": status,
                "provider": name,
            }
        )
    leds = observation.get("keyboard_leds")
    if not isinstance(leds, list):
        raise LightingObservationError("keyboard LED observation shape is invalid")
    findings.append(
        {
            "id": "lighting.keyboard.provider-set",
            "status": "observed" if leds else "unknown",
            "provider_count": len(leds),
        }
    )
    return tuple(findings)


__all__ = [
    "ADAPTER_ID",
    "ADAPTER_REVISION",
    "LightingObservationError",
    "collect_passive",
    "diagnose",
]
