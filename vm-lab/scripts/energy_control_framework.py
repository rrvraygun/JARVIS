#!/usr/bin/env python3
"""Allowlisted energy-control planning boundary.

The framework models Powertop/CPU/GPU/profile controls without invoking
Powertop, D-Bus, sysfs, subprocesses, or device handles. The shipped executor
is disabled; deployment requires a separate reviewed adapter per control.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class EnergyControlError(ValueError):
    pass


ALLOWED_CONTROLS = {
    "power.profile": {"power-saver", "balanced", "performance"},
    "cpu.epp": {"power", "balance_power", "balance_performance", "performance"},
    "cpu.turbo": {True, False},
    "intel_gpu.runtime_pm": {"auto", "on"},
    "nvidia_gpu.runtime_pm": {"auto", "on"},
}
ALLOWED_POWERTOP_TUNABLES = frozenset(
    {
        "runtime-pm-pci",
        "runtime-pm-usb",
        "audio-powersave",
        "wifi-power-save",
    }
)
MAX_OPERATIONS = 6


def _digest(value: Any) -> str:
    try:
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise EnergyControlError("energy binding is not canonical JSON") from exc
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class EnergyOperation:
    control: str
    requested: Any
    current: Any
    source: str

    def validate(self) -> None:
        if self.control not in ALLOWED_CONTROLS:
            if not self.control.startswith("powertop.tunable."):
                raise EnergyControlError("control is not allowlisted")
            name = self.control.removeprefix("powertop.tunable.")
            if name not in ALLOWED_POWERTOP_TUNABLES:
                raise EnergyControlError("Powertop tunable is not allowlisted")
        else:
            allowed = ALLOWED_CONTROLS[self.control]
            if self.requested not in allowed:
                raise EnergyControlError("requested energy value is not allowlisted")
        if self.requested == self.current:
            raise EnergyControlError("energy operation is a no-op")
        if self.source not in {"powertop", "sysfs-readonly", "tuned-ppd"}:
            raise EnergyControlError("energy source is invalid")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "control": self.control,
            "requested": self.requested,
            "current": self.current,
            "source": self.source,
        }


@dataclass(frozen=True)
class EnergyControlPlan:
    plan_id: str
    operations: tuple[EnergyOperation, ...]
    state_digest: str
    thermal_degraded: bool
    on_battery: bool
    review_digest: str

    def validate(self) -> None:
        if not self.operations or len(self.operations) > MAX_OPERATIONS:
            raise EnergyControlError("energy plan operation count is unsafe")
        if len({op.control for op in self.operations}) != len(self.operations):
            raise EnergyControlError("duplicate energy controls are not allowed")
        if not isinstance(self.state_digest, str) or len(self.state_digest) != 64:
            raise EnergyControlError("state digest is required")
        if not isinstance(self.review_digest, str) or len(self.review_digest) != 64:
            raise EnergyControlError("independent review digest is required")
        if self.thermal_degraded and any(
            op.control in {"cpu.turbo", "power.profile"} for op in self.operations
        ):
            raise EnergyControlError("thermal degradation blocks turbo/profile mutation")
        for operation in self.operations:
            operation.validate()

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": 1,
            "plan_id": self.plan_id,
            "operations": [op.as_dict() for op in self.operations],
            "state_digest": self.state_digest,
            "thermal_degraded": self.thermal_degraded,
            "on_battery": self.on_battery,
            "review_digest": self.review_digest,
            "one_use": True,
            "rollback_requires_new_approval": True,
            "simulation_only": True,
            "network_used": False,
            "credentials_used": False,
            "arbitrary_command": False,
        }


class PreparedEnergyControlExecutor:
    """Disabled until each concrete control adapter is independently reviewed."""

    enabled = False

    def execute(self, plan: Mapping[str, Any], **_: Any) -> dict[str, Any]:
        if not isinstance(plan, Mapping) or plan.get("schema_version") != 1:
            raise EnergyControlError("energy plan is invalid")
        raise EnergyControlError("energy-control executor is constructed but disabled")


def powertop_reading_summary(
    *,
    tunables: Mapping[str, str],
    cpu_epp: str | None,
    gpu_runtime_pm: Mapping[str, str],
) -> dict[str, Any]:
    """Normalize bounded, already-collected Powertop readings without probing."""
    if not isinstance(tunables, Mapping) or not isinstance(gpu_runtime_pm, Mapping):
        raise EnergyControlError("Powertop reading shape is invalid")
    unknown = set(tunables) - ALLOWED_POWERTOP_TUNABLES
    if unknown:
        raise EnergyControlError("Powertop reading contains an unallowlisted tunable")
    return {
        "schema_version": 1,
        "source": "powertop-read-only-summary",
        "tunable_count": len(tunables),
        "tunables": dict(sorted(tunables.items())),
        "cpu_epp": cpu_epp,
        "gpu_runtime_pm": dict(sorted(gpu_runtime_pm.items())),
        "mutation_performed": False,
    }
