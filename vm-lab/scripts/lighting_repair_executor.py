#!/usr/bin/env python3
"""Fail-closed lighting-repair execution boundary.

This is the construction contract for a future state-changing adapter.  It
accepts only an exact diagnosis/plan binding and an independent-review digest;
the shipped implementation never opens devices, writes sysfs, invokes a
process, or changes the host.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from lighting_repair_plan import (
    ALLOWED_TARGETS,
    OPERATION_ID,
    OPERATION_REVISION,
)


class LightingRepairExecutorError(ValueError):
    pass


def _digest(value: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise LightingRepairExecutorError("binding is not canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _sha(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise LightingRepairExecutorError(f"{label} is not a SHA-256 digest")
    return value


@dataclass(frozen=True)
class LightingRepairExecutionRequest:
    authorization_id: str
    approval_digest: str
    plan_digest: str
    diagnosis_digest: str
    target: str
    independent_review_digest: str
    one_use: bool = True
    rollback_requires_new_approval: bool = True

    def validate(self) -> None:
        if not isinstance(self.authorization_id, str) or not self.authorization_id:
            raise LightingRepairExecutorError("authorization_id is required")
        _sha(self.approval_digest, "approval_digest")
        _sha(self.plan_digest, "plan_digest")
        _sha(self.diagnosis_digest, "diagnosis_digest")
        _sha(self.independent_review_digest, "independent_review_digest")
        if self.target not in ALLOWED_TARGETS:
            raise LightingRepairExecutorError("target is outside the fixed repair scope")
        if self.one_use is not True or self.rollback_requires_new_approval is not True:
            raise LightingRepairExecutorError("repair authorization policy is unsafe")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": 1,
            "operation_id": OPERATION_ID,
            "operation_revision": OPERATION_REVISION,
            "authorization_id": self.authorization_id,
            "approval_digest": self.approval_digest,
            "plan_digest": self.plan_digest,
            "diagnosis_digest": self.diagnosis_digest,
            "target": self.target,
            "independent_review_digest": self.independent_review_digest,
            "one_use": True,
            "rollback_requires_new_approval": True,
            "simulation_only": True,
            "network_used": False,
            "credentials_used": False,
            "arbitrary_command": False,
            "device_handle_opened": False,
        }


def build_request(
    plan: Mapping[str, Any],
    *,
    diagnosis: Mapping[str, Any],
    target: str,
    independent_review_digest: str,
    authorization_id: str,
    approval_digest: str,
) -> dict[str, Any]:
    if not isinstance(plan, Mapping) or plan.get("operation_id") != OPERATION_ID:
        raise LightingRepairExecutorError("repair plan binding is invalid")
    if not isinstance(diagnosis, Mapping):
        raise LightingRepairExecutorError("diagnosis binding is invalid")
    request = LightingRepairExecutionRequest(
        authorization_id=authorization_id,
        approval_digest=approval_digest,
        plan_digest=_digest(plan),
        diagnosis_digest=_digest(diagnosis),
        target=target,
        independent_review_digest=independent_review_digest,
    )
    return request.as_dict()


class PreparedLightingRepairExecutor:
    """Construction-only executor; deployment is intentionally impossible."""

    enabled = False

    def execute(self, request: Mapping[str, Any], **_: Any) -> dict[str, Any]:
        if not isinstance(request, Mapping):
            raise LightingRepairExecutorError("execution request is invalid")
        if request.get("operation_id") != OPERATION_ID:
            raise LightingRepairExecutorError("operation binding is invalid")
        raise LightingRepairExecutorError("lighting repair executor is constructed but disabled")


__all__ = [
    "LightingRepairExecutionRequest",
    "LightingRepairExecutorError",
    "PreparedLightingRepairExecutor",
    "build_request",
]
