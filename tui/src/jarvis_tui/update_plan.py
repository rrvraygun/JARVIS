"""Classify exact Fedora update sets before any privileged execution."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

NEVRA = re.compile(r"^[A-Za-z0-9_.+%-]+(?:-[A-Za-z0-9_.+:%~-]+){2,3}\.[A-Za-z0-9_]+$")
SENSITIVE_FAMILIES = (
    "kernel",
    "nvidia",
    "akmod",
    "kmod",
    "mesa",
    "xorg",
    "wayland",
    "grub",
    "shim",
    "dracut",
    "linux-firmware",
    "microcode",
    "cryptsetup",
    "systemd",
)


def prepare(packages: list[str], *, recovery_verified: bool) -> dict[str, Any]:
    if (
        not isinstance(packages, list)
        or not packages
        or len(packages) > 200
        or not all(isinstance(item, str) for item in packages)
    ):
        raise ValueError("update_package_set_invalid")
    if len(set(packages)) != len(packages):
        raise ValueError("update_package_set_invalid")
    if any(
        not isinstance(item, str) or len(item) > 240 or not NEVRA.fullmatch(item)
        for item in packages
    ):
        raise ValueError("update_requires_exact_nevra")
    critical = sorted(item for item in packages if item.casefold().startswith(SENSITIVE_FAMILIES))
    plan: dict[str, Any] = {
        "schema_version": 1,
        "packages": sorted(packages),
        "critical_families": critical,
        "recovery_required": bool(critical),
        "recovery": "R2 external verified" if recovery_verified else "blocked-unverified-R2",
        "approval": "exact-one-use",
        "privilege": "registered package helper only",
        "rollback": "fresh exact package recovery record; kernel/graphics changes also require boot-path verification",
        "execution_authorized": False,
        "recovery_evidence_status": "caller_report_only; not execution authority",
        "blockers": ["signed_local_artifacts_and_exact_root_review_required"]
        + ([] if recovery_verified else ["current_R2_recovery_not_verified"]),
        "bootability_claim": False,
    }
    plan["digest"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return plan
