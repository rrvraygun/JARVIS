#!/usr/bin/env python3
"""Validate the non-executable Fedora R2 recovery-set plan."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PLAN_FILE = ROOT / "deployment/host/recovery-set-plan.json"


class RecoverySetError(ValueError):
    """Raised when a recovery-set plan overclaims or weakens a safety gate."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RecoverySetError(message)


def load(path: Path = PLAN_FILE) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RecoverySetError(str(exc)) from exc
    require(isinstance(value, dict), "plan: expected object")
    return value


def validate(plan: dict[str, Any]) -> dict[str, Any]:
    require(plan.get("schema_version") == 1, "plan: bad schema")
    require(plan.get("plan_id") == "jarvis-fedora-r2-system-set-v1", "plan: identity drift")
    require(plan.get("status") == "prepared_not_executed", "plan: execution falsely claimed")
    target = plan.get("target", {})
    require(
        target.get("machine_scope") == "single-enrolled-workstation",
        "plan: target scope drift",
    )
    require(
        target.get("host_identity_storage") == "pseudonym-only",
        "plan: raw host identity allowed",
    )

    repository = plan.get("repository", {})
    require(repository.get("backend") == "restic", "plan: unreviewed repository backend")
    require(repository.get("repository_format") == 2, "plan: repository format drift")
    require(
        repository.get("encryption_initialized") is True,
        "plan: encryption not required",
    )
    require(
        repository.get("password_handling") == "interactive-user-terminal-only",
        "plan: password handling weakened",
    )
    require(
        repository.get("persistent_local_cache") is False,
        "plan: cache unexpectedly enabled",
    )
    require(
        repository.get("system_recovery_set_present") is False,
        "plan: system artifact falsely claimed",
    )

    consistency = plan.get("consistency_model", {})
    require(
        consistency.get("cross_subvolume_atomicity") is False,
        "plan: atomicity overclaim",
    )
    require(
        0 < int(consistency.get("maximum_snapshot_skew_seconds", 0)) <= 120,
        "plan: skew budget unsafe",
    )
    require(
        "crash-consistent" in consistency.get("application_consistency", ""),
        "plan: application consistency overclaim",
    )

    boundaries = plan.get("boundaries")
    expected = ["root", "home", "systemd_machines", "boot", "efi"]
    require(
        isinstance(boundaries, list) and [item.get("id") for item in boundaries] == expected,
        "plan: recovery boundary drift",
    )
    methods = {item["id"]: item.get("capture_method") for item in boundaries}
    require(
        all(methods[item] == "btrfs_readonly_snapshot" for item in expected[:3]),
        "plan: Btrfs snapshot boundary weakened",
    )
    require(
        all(methods[item] == "restic_live_filesystem_capture" for item in expected[3:]),
        "plan: boot or EFI capture drift",
    )
    for boundary in boundaries:
        require(
            boundary.get("included")
            and boundary.get("validation")
            and boundary.get("restore_scope"),
            f"plan: incomplete boundary {boundary.get('id')}",
        )

    exclusions = set(plan.get("explicit_exclusions", []))
    for required in (
        "partition table",
        "LUKS header and recovery material",
        "UEFI NVRAM variables",
        "firmware configuration or firmware flash state",
        "external backup repository itself",
    ):
        require(required in exclusions, f"plan: exclusion missing: {required}")

    operations = plan.get("operations")
    require(
        isinstance(operations, list) and len(operations) >= 10,
        "plan: operation sequence incomplete",
    )
    require(
        [item.get("sequence") for item in operations] == list(range(1, len(operations) + 1)),
        "plan: operation order invalid",
    )
    require(
        all(item.get("status") not in {"complete", "succeeded", "running"} for item in operations),
        "plan: operation falsely executed",
    )
    mutating = [
        item
        for item in operations
        if item.get("effect") != "read-only" and item.get("id") != "snapshot-retention-decision"
    ]
    require(
        all(
            "per-command" in item.get("approval", "")
            or item.get("approval") == "separately-designed-procedure-and-per-command"
            or item.get("approval") == "project-scope"
            for item in mutating
        ),
        "plan: mutation lacks command approval",
    )

    proofs = plan.get("proof_matrix")
    require(isinstance(proofs, list) and len(proofs) >= 10, "plan: proof matrix incomplete")
    proof_by_id = {item.get("id"): item for item in proofs}
    for proof_id in (
        "acl",
        "extended-attributes",
        "selinux-label",
        "sparse-file",
        "boot-files",
        "efi-files",
        "full-restore-to-nonproduction-target",
        "bootability-or-offline-reconstruction",
    ):
        require(
            proof_id in proof_by_id and proof_by_id[proof_id].get("required") is True,
            f"plan: proof missing: {proof_id}",
        )
    require(
        proof_by_id["full-restore-to-nonproduction-target"].get("status", "").startswith("blocked"),
        "plan: full restore falsely passed",
    )

    approvals = plan.get("approval_policy", {})
    require(approvals.get("initial_scope") == "command", "plan: initial approval broadened")
    require(
        approvals.get("one_state_changing_attempt") is True,
        "plan: multiple attempts enabled",
    )
    require(
        approvals.get("automatic_retry") is False and approvals.get("automatic_rollback") is False,
        "plan: automation safety weakened",
    )
    require(
        approvals.get("restore_requires_separate_approval") is True,
        "plan: restore approval missing",
    )
    require(
        approvals.get("cleanup_requires_separate_approval") is True,
        "plan: cleanup approval missing",
    )
    require(
        approvals.get("snapshot_deletion_requires_separate_approval") is True,
        "plan: snapshot deletion approval missing",
    )

    stops = plan.get("stop_conditions")
    require(isinstance(stops, list) and len(stops) >= 10, "plan: stop conditions incomplete")
    require(
        any("unreadable" in item for item in stops),
        "plan: unreadable-source stop missing",
    )
    require(any("audit" in item for item in stops), "plan: audit fail-closed stop missing")

    claims = plan.get("claims", {})
    require(
        claims.get("current") == "minimal-restic-mechanism-verified-system-set-not-created",
        "plan: current claim drift",
    )
    for key in (
        "r1_system_set",
        "r2_system_artifact",
        "r2_full_restore_rehearsed",
        "r2_sufficient_for_a3",
        "r3_available",
    ):
        require(claims.get(key) is False, f"plan: {key} falsely claimed")
    require(
        "bare-metal recovery" in claims.get("must_not_claim", []),
        "plan: bare-metal overclaim not prohibited",
    )

    return {
        "status": "valid",
        "plan_status": plan["status"],
        "boundaries": len(boundaries),
        "operations": len(operations),
        "proofs": len(proofs),
        "current_claim": claims["current"],
    }


def main() -> int:
    try:
        report = validate(load())
    except RecoverySetError as exc:
        print(f"recovery-set plan rejected: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
