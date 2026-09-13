"""Prepare a conservative, non-executable Restic recovery sequence."""

from __future__ import annotations

import hashlib
import json
from typing import Any

REPOSITORY_RELATIVE = "JARVIS_BACKUP/restic-repository"
BOUNDARIES = ("root", "home", "machines", "boot", "efi")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def prepare(
    *,
    device_uuid: str,
    mountpoint: str,
    repository_prefix: str,
    destination: str,
    retention: int = 10,
) -> dict[str, Any]:
    """Return an approval-ready plan; this function never opens the device."""
    if (
        len(device_uuid) != 16
        or any(c not in "0123456789ABCDEFabcdef" for c in device_uuid)
        or not mountpoint.startswith("/run/media/")
        or "/" in repository_prefix
        or len(repository_prefix) != 8
        or not destination.startswith("/")
        or retention != 10
    ):
        raise ValueError("recovery_target_identity_invalid")
    repository = f"{mountpoint.rstrip('/')}/{REPOSITORY_RELATIVE}"
    plan: dict[str, Any] = {
        "schema_version": 1,
        "id": _digest({"uuid": device_uuid, "repository": repository, "destination": destination})[
            :32
        ],
        "device": {"uuid": device_uuid.upper(), "transport": "usb", "identity_required": True},
        "repository": {
            "path": repository,
            "prefix": repository_prefix,
            "backend": "restic-local",
            "password": "interactive-user-terminal-only",
            "cache": "disabled",
        },
        "destination": {"path": destination, "must_be_new": True, "must_be_isolated": True},
        "boundaries": list(BOUNDARIES),
        "retention": {"keep_last": retention, "deletion": "separate-exact-approval"},
        "operations": [
            {"sequence": 1, "operation": "inspect_storage", "approval": "read-only"},
            {"sequence": 2, "operation": "create_root_snapshot", "approval": "exact-one-use"},
            {"sequence": 3, "operation": "create_home_snapshot", "approval": "exact-one-use"},
            {"sequence": 4, "operation": "create_machines_snapshot", "approval": "exact-one-use"},
            {"sequence": 5, "operation": "capture_boot_efi", "approval": "exact-one-use"},
            {
                "sequence": 6,
                "operation": "restic_backup",
                "sources": list(BOUNDARIES),
                "approval": "exact-one-use",
            },
            {
                "sequence": 7,
                "operation": "restic_check_read_data",
                "snapshot": "created-set",
                "approval": "exact-one-use",
            },
            {"sequence": 8, "operation": "restore_to_new_destination", "approval": "exact-one-use"},
            {"sequence": 9, "operation": "verify_restored_boundaries", "approval": "exact-one-use"},
            {
                "sequence": 10,
                "operation": "freeze_restore_target_read_only",
                "approval": "exact-one-use",
            },
            {
                "sequence": 11,
                "operation": "retention_preview",
                "keep_last": retention,
                "approval": "read-only",
            },
            {
                "sequence": 12,
                "operation": "retention_delete_exact_ids",
                "approval": "separate-exact-one-use",
            },
        ],
        "blockers": [
            "repository_integrity_not_currently_verified",
            "usb_connection_stability_must_be_reconfirmed",
            "password_must_be_entered_in_user_terminal",
            "no_automatic_repair_or_retry",
        ],
        "claims": {"full_system_recovery": False, "bare_metal_boot": False},
    }
    plan["digest"] = _digest(plan)
    return plan
