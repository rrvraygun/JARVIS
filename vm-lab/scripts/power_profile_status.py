#!/usr/bin/env python3
"""Read-only status adapter for the fixed TuneD/PPD D-Bus interface.

This module intentionally exposes no profile-changing method.  It reads only
org.freedesktop.DBus.Properties.GetAll from the system Power Profiles object,
then validates and normalizes the bounded profile contract for Jarvis.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

BUS_NAME = "org.freedesktop.UPower.PowerProfiles"
OBJECT_PATH = "/org/freedesktop/UPower/PowerProfiles"
INTERFACE = "org.freedesktop.UPower.PowerProfiles"
PROFILE_NAMES = ("power-saver", "balanced", "performance")
DRIVER_NAMES = ("tuned",)
DEGRADED_VALUES = ("", "lap-detected", "high-operating-temperature")


class PowerProfileStatusError(ValueError):
    """Raised when the fixed provider contract is unavailable or invalid."""


class PropertyReader(Protocol):
    def get_all(self, interface: str) -> Mapping[str, Any]:
        """Return properties for exactly one fixed D-Bus interface."""


@dataclass(frozen=True)
class PowerProfileStatus:
    active_profile: str
    profiles: tuple[dict[str, str], ...]
    performance_degraded: str
    provider: str = "tuned-ppd"
    api: str = BUS_NAME

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "provider": self.provider,
            "api": self.api,
            "active_profile": self.active_profile,
            "profiles": [dict(profile) for profile in self.profiles],
            "performance_degraded": self.performance_degraded,
            "read_only": True,
        }


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or any(ord(char) < 0x20 for char in value):
        raise PowerProfileStatusError(f"invalid power-profile {field}")
    return value


def parse_properties(properties: Mapping[str, Any]) -> PowerProfileStatus:
    """Validate a bounded PPD property response without performing writes."""

    if not isinstance(properties, Mapping):
        raise PowerProfileStatusError("power-profile properties are not a mapping")
    active = _text(properties.get("ActiveProfile"), "active profile")
    if active not in PROFILE_NAMES:
        raise PowerProfileStatusError("provider returned an unsupported active profile")

    raw_profiles = properties.get("Profiles")
    if not isinstance(raw_profiles, Sequence) or isinstance(raw_profiles, (str, bytes)):
        raise PowerProfileStatusError("power-profile profiles are not a sequence")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in raw_profiles:
        if not isinstance(raw, Mapping):
            raise PowerProfileStatusError("power-profile entry is not a mapping")
        name = _text(raw.get("Profile"), "profile name")
        driver = _text(raw.get("Driver"), "profile driver")
        if name not in PROFILE_NAMES:
            raise PowerProfileStatusError("provider returned an unsupported profile")
        if driver not in DRIVER_NAMES:
            raise PowerProfileStatusError("provider returned an unsupported profile driver")
        if name in seen:
            raise PowerProfileStatusError("provider returned duplicate profiles")
        seen.add(name)
        normalized.append({"Profile": name, "Driver": driver})
    profile_order = {name: index for index, name in enumerate(PROFILE_NAMES)}
    normalized.sort(key=lambda profile: profile_order[profile["Profile"]])
    if active not in seen:
        raise PowerProfileStatusError("active profile is not in the provider profile set")

    degraded = properties.get("PerformanceDegraded", "")
    if not isinstance(degraded, str) or degraded not in DEGRADED_VALUES:
        raise PowerProfileStatusError("invalid performance-degraded value")
    return PowerProfileStatus(active, tuple(normalized), degraded)


class FixedDbusPowerProfileReader:
    """Read the fixed system-bus object through Properties.GetAll only."""

    def __init__(self, bus_factory: Callable[[], Any] | None = None) -> None:
        self._bus_factory = bus_factory or self._system_bus

    @staticmethod
    def _system_bus() -> Any:
        try:
            import dbus  # type: ignore[import-not-found]
        except ImportError as exc:
            raise PowerProfileStatusError("Python D-Bus bindings are unavailable") from exc
        return dbus.SystemBus()

    def read(self) -> PowerProfileStatus:
        try:
            bus = self._bus_factory()
            proxy = bus.get_object(BUS_NAME, OBJECT_PATH)
            import dbus  # type: ignore[import-not-found]

            properties = dbus.Interface(proxy, dbus.PROPERTIES_IFACE)
            raw = properties.GetAll(INTERFACE)
        except PowerProfileStatusError:
            raise
        except Exception as exc:  # D-Bus implementations expose varied exception types.
            raise PowerProfileStatusError("power-profile provider is unavailable") from exc
        return parse_properties(raw)


def main() -> int:
    try:
        print(json.dumps(FixedDbusPowerProfileReader().read().as_dict(), sort_keys=True))
    except PowerProfileStatusError as exc:
        print(
            json.dumps(
                {"status": "error", "error": str(exc), "read_only": True},
                sort_keys=True,
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
