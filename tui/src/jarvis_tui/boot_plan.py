"""Read-only planning for exact kernel and initramfs operations."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def prepare(operation: str, kernel: str, *, recovery_verified: bool) -> dict[str, Any]:
    if operation not in {"select_kernel", "repair_initramfs"}:
        raise ValueError("boot_operation_not_registered")
    if not re.fullmatch(r"[0-9][A-Za-z0-9_.+-]{0,127}", kernel):
        raise ValueError("kernel_identity_invalid")
    image = Path("/boot") / ("vmlinuz-" + kernel)
    initramfs = Path("/boot") / ("initramfs-" + kernel + ".img")
    if not image.is_file() or not initramfs.is_file():
        raise ValueError("kernel_or_initramfs_not_present")
    plan = {
        "schema_version": 1,
        "operation": operation,
        "kernel": kernel,
        "targets": {"image": str(image), "initramfs": str(initramfs)},
        "recovery": "R2 external verified" if recovery_verified else "blocked-unverified-R2",
        "approval": "exact-one-use",
        "privilege": "registered root helper only",
        "bootability_claim": False,
        "execution_authorized": False,
        "selection_duration": "next-boot-only" if operation == "select_kernel" else None,
        "recovery_evidence_status": "caller_report_only; requires independent root review",
        "blockers": ["exact_root_review_and_prestate_required"]
        + ([] if recovery_verified else ["current_R2_recovery_not_verified"]),
    }
    plan["digest"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return plan
