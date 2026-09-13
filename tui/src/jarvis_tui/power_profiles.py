"""Versioned per-user custom power profiles and deterministic goal planning."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .power_control_client import POWER_CONTROL_OPTIONS
from .power_inventory import PowerInventory

PROFILE_GOALS = ("battery", "performance", "quiet", "thermal", "balanced")
PROFILE_VARIANTS = ("ac", "battery")


@dataclass(frozen=True)
class PowerProfile:
    profile_id: str
    name: str
    goal: str
    variants: dict[str, dict[str, str]]
    version: int = 1
    profile_digest: str = ""

    def binding_payload(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "profile_id": self.profile_id,
            "name": self.name,
            "goal": self.goal,
            "variants": self.variants,
            "version": self.version,
        }

    def __post_init__(self) -> None:
        if (
            not self.profile_id
            or not 1 <= len(self.name) <= 120
            or self.goal not in PROFILE_GOALS
            or set(self.variants) != set(PROFILE_VARIANTS)
            or self.version < 1
        ):
            raise ValueError("invalid power profile")
        for variant in PROFILE_VARIANTS:
            settings = self.variants[variant]
            if not isinstance(settings, dict):
                raise ValueError("power profile variant is invalid")
            for control, value in settings.items():
                if value not in POWER_CONTROL_OPTIONS.get(control, ()):
                    raise ValueError("power profile value is not allowlisted")
        expected = hashlib.sha256(
            json.dumps(self.binding_payload(), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if not self.profile_digest:
            object.__setattr__(self, "profile_digest", expected)
        elif self.profile_digest != expected:
            raise ValueError("power profile digest mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {**self.binding_payload(), "profile_digest": self.profile_digest}


@dataclass(frozen=True)
class PowerProfilePlan:
    profile: PowerProfile
    omitted: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    unsupported: tuple[str, ...] = ()

    @property
    def executable(self) -> bool:
        return not self.conflicts and bool(
            self.profile.variants["ac"] or self.profile.variants["battery"]
        )


def _desired(goal: str, variant: str) -> dict[str, str]:
    battery = variant == "battery"
    if goal == "battery":
        return {
            "power.profile": "power-saver",
            "cpu.epp": "power",
            "cpu.turbo": "disabled",
            "intel_gpu.runtime_pm": "auto",
            "nvidia_gpu.runtime_pm": "auto",
        }
    if goal == "performance":
        return {
            "power.profile": "performance",
            "cpu.epp": "performance",
            "cpu.turbo": "enabled",
            "intel_gpu.runtime_pm": "on",
            "nvidia_gpu.runtime_pm": "on",
        }
    if goal in {"quiet", "thermal"}:
        return {
            "power.profile": "power-saver" if battery else "balanced",
            "cpu.epp": "power",
            "cpu.turbo": "disabled",
            "intel_gpu.runtime_pm": "auto",
            "nvidia_gpu.runtime_pm": "auto",
        }
    return {
        "power.profile": "balanced",
        "cpu.epp": "balance_performance",
        "cpu.turbo": "enabled",
        "intel_gpu.runtime_pm": "auto",
        "nvidia_gpu.runtime_pm": "auto",
    }


def plan_power_profile(
    *, name: str, goal: str, inventory: PowerInventory, profile_id: str, scope: str = "both"
) -> PowerProfilePlan:
    """Build paired variants using only controls exposed by current hardware."""
    if goal not in PROFILE_GOALS or scope not in {"ac", "battery", "both"}:
        raise ValueError("unsupported power profile goal")
    controls = {
        item.control_id: item
        for item in inventory.settings
        if item.control_id and item.writable_by_jarvis and item.available
    }
    variants: dict[str, dict[str, str]] = {}
    omitted: list[str] = []
    unsupported: list[str] = []
    for variant in PROFILE_VARIANTS:
        selected: dict[str, str] = {}
        for control, value in _desired(goal, variant).items():
            item = controls.get(control)
            if item is None:
                unsupported.append(f"{variant}:{control}={value}")
                continue
            choices = {choice.strip() for choice in item.choices.split(",")}
            if value not in POWER_CONTROL_OPTIONS.get(control, ()) or (
                choices and value not in choices and item.current != value
            ):
                omitted.append(f"{variant}:{control}={value}")
                continue
            selected[control] = value
        variants[variant] = selected
    if scope == "ac":
        variants["battery"] = {}
    elif scope == "battery":
        variants["ac"] = {}
    conflicts = tuple(inventory.conflicts)
    profile = PowerProfile(profile_id, name.strip(), goal, variants)
    return PowerProfilePlan(profile, tuple(omitted), conflicts, tuple(unsupported))


class PowerProfileStore:
    """Owner-only profile persistence with atomic versioned JSON documents."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.home() / ".local/state/jarvis/power-profiles"

    def save(self, profile: PowerProfile) -> Path:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        target = self.root / f"{profile.profile_id}.json"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{profile.profile_id}.", suffix=".tmp", dir=self.root
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                descriptor = -1
                json.dump(profile.to_dict(), stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            os.chmod(target, 0o600)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)
        return target

    def load(self, profile_id: str) -> PowerProfile | None:
        target = self.root / f"{profile_id}.json"
        try:
            info = target.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or not stat.S_ISREG(info.st_mode)
                or info.st_size > 128_000
            ):
                return None
            value = json.loads(target.read_text(encoding="utf-8"))
            return PowerProfile(
                str(value["profile_id"]),
                str(value["name"]),
                str(value["goal"]),
                {str(key): dict(settings) for key, settings in value["variants"].items()},
                int(value.get("version", 1)),
                str(value.get("profile_digest", "")),
            )
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            return None

    def list(self) -> tuple[PowerProfile, ...]:
        try:
            paths = sorted(self.root.glob("*.json"))
        except OSError:
            return ()
        values = [profile for path in paths if (profile := self.load(path.stem)) is not None]
        return tuple(sorted(values, key=lambda profile: profile.name.casefold()))
