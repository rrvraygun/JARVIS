#!/usr/bin/env python3
"""Prepared lighting-repair operation contract.

This module can turn an observed diagnosis into an exact, reviewable repair
plan, but it deliberately cannot execute it.  The plan contains no shell,
executable, arbitrary argv, credential, network, or device handle.  A future
adapter must be separately reviewed and bound to OS authorization before any
host mutation is possible.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class LightingRepairPlanError(ValueError):
    pass


OPERATION_ID = "jarvis.lighting.repair"
OPERATION_REVISION = "1.0.0"
ALLOWED_TARGETS = frozenset({"display-backlight", "keyboard-leds"})


def _text(value: Any, label: str, limit: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > limit
        or any(ord(char) < 0x20 for char in value)
    ):
        raise LightingRepairPlanError(f"{label} is invalid")
    return value


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LightingRepairPlan:
    repair_plan_id: str
    diagnosis_digest: str
    target: str
    pre_state_digest: str
    expected_effects: tuple[str, ...]
    rollback: tuple[str, ...]
    postconditions: tuple[str, ...]
    recovery_level: str
    execution_enabled: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "operation_id": OPERATION_ID,
            "operation_revision": OPERATION_REVISION,
            "repair_plan_id": self.repair_plan_id,
            "diagnosis_digest": self.diagnosis_digest,
            "target": self.target,
            "pre_state_digest": self.pre_state_digest,
            "expected_effects": list(self.expected_effects),
            "rollback": list(self.rollback),
            "postconditions": list(self.postconditions),
            "recovery_level": self.recovery_level,
            "execution_enabled": self.execution_enabled,
            "network_used": False,
            "credentials_used": False,
            "arbitrary_command": False,
            "device_handle_opened": False,
        }


def build_plan(
    diagnosis: Mapping[str, Any],
    *,
    target: str,
    pre_state: Mapping[str, Any],
    recovery_level: str = "R1-required; R2-required for graphics/driver changes",
) -> dict[str, Any]:
    """Create an exact disabled plan from a bounded diagnosis and pre-state."""
    if not isinstance(diagnosis, Mapping) or diagnosis.get("status") != "mismatch":
        raise LightingRepairPlanError("diagnosis is not eligible for a repair plan")
    target = _text(target, "target", 64)
    if target not in ALLOWED_TARGETS:
        raise LightingRepairPlanError("target is outside the lighting operation scope")
    if not isinstance(pre_state, Mapping) or not pre_state:
        raise LightingRepairPlanError("pre-state is required")
    plan = LightingRepairPlan(
        repair_plan_id=f"plan_{_digest({'diagnosis': dict(diagnosis), 'target': target, 'pre_state': dict(pre_state)})[:24]}",
        diagnosis_digest=_digest(dict(diagnosis)),
        target=target,
        pre_state_digest=_digest(dict(pre_state)),
        expected_effects=(f"restore {target} through a separately reviewed fixed adapter",),
        rollback=("restore the captured pre-state only with a new explicit approval",),
        postconditions=(
            f"re-observe {target}",
            "stop if the expected state is not verified",
        ),
        recovery_level=_text(recovery_level, "recovery_level", 256),
    )
    return plan.as_dict()


class PreparedLightingRepairExecutor:
    """Fail-closed placeholder; it can never execute in this revision."""

    operation_id = OPERATION_ID
    revision = OPERATION_REVISION

    def execute(self, plan: Mapping[str, Any], **_: Any) -> dict[str, Any]:
        if not isinstance(plan, Mapping) or plan.get("operation_id") != OPERATION_ID:
            raise LightingRepairPlanError("repair plan binding is invalid")
        raise LightingRepairPlanError("lighting repair executor is prepared but disabled")


__all__ = [
    "ALLOWED_TARGETS",
    "OPERATION_ID",
    "OPERATION_REVISION",
    "LightingRepairPlanError",
    "PreparedLightingRepairExecutor",
    "build_plan",
]
