#!/usr/bin/env python3
"""Validate the static direct-host deployment and recovery policy."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
POLICY_FILE = ROOT / "deployment/host/policy.json"
FORBIDDEN_KEYS = {
    "argv",
    "command",
    "commands",
    "device_path",
    "executable",
    "host_path",
    "raw_path",
    "script",
    "shell",
    "shell_line",
    "socket_path",
}


class HostPolicyError(ValueError):
    """Raised when the direct-host policy fails closed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HostPolicyError(message)


def load(path: Path = POLICY_FILE) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HostPolicyError(str(exc)) from exc
    require(isinstance(value, dict), "policy: expected object")
    return value


def walk_keys(value: Any, location: str = "$") -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield location, key
            yield from walk_keys(item, f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_keys(item, f"{location}[{index}]")


def validate(policy: dict[str, Any]) -> dict[str, Any]:
    for location, key in walk_keys(policy):
        require(key not in FORBIDDEN_KEYS, f"{location}: executable field {key} forbidden")
    require(policy.get("schema_version") == 1, "policy: bad schema")
    require(policy.get("status") == "prepared_unenrolled", "policy: target falsely enrolled")
    target = policy.get("target", {})
    require(target.get("workstation_count") == 1, "policy: target count drift")
    require(
        target.get("operating_system_family") == "Fedora Workstation",
        "policy: target OS drift",
    )
    require(target.get("identity") == "unresolved", "policy: host identity guessed")
    authority = policy.get("current_authority", {})
    require(
        isinstance(authority, dict) and len(authority) >= 10,
        "policy: authority incomplete",
    )
    require(
        all(value is False for value in authority.values()),
        "policy: current authority enabled",
    )
    relationship = policy.get("laboratory_relationship", {})
    require(
        relationship.get("vm_success_proves_physical_hardware_behavior") is False,
        "policy: VM overclaim",
    )
    modes = policy.get("operating_modes")
    require(isinstance(modes, list), "policy: modes missing")
    expected_modes = ["fixture", "shadow", "supervised", "earned_safe_list"]
    require(
        [item.get("id") for item in modes] == expected_modes,
        "policy: mode order or identity drift",
    )
    require(
        modes[0].get("current_status") == "available",
        "policy: fixture mode unavailable",
    )
    require(
        modes[0].get("host_reads") is False and modes[0].get("host_mutations") is False,
        "policy: fixture mode operational",
    )
    require(
        modes[1].get("host_reads") is True and modes[1].get("host_mutations") is False,
        "policy: shadow mode unsafe",
    )
    require(
        modes[2].get("host_mutations") is True
        and modes[2].get("current_status") == "blocked_on_shadow_and_recovery",
        "policy: supervised mode unblocked",
    )
    require(modes[3].get("current_status") == "disabled", "policy: safe list enabled")
    recovery = policy.get("recovery_levels")
    expected_recovery = [
        "R0_record_only",
        "R1_local_filesystem_snapshot",
        "R2_external_system_backup",
        "R3_offline_full_device_recovery",
    ]
    require(
        isinstance(recovery, list) and [item.get("id") for item in recovery] == expected_recovery,
        "policy: recovery levels drift",
    )
    for level in recovery:
        require(
            level.get("protects")
            and level.get("does_not_protect")
            and level.get("required_evidence"),
            f"{level.get('id')}: incomplete recovery claim",
        )
    backend = policy.get("backend_selection", {})
    require(
        backend.get("status") == "unresolved_until_read_only_enrollment",
        "policy: backend guessed",
    )
    require(
        backend.get("never_assume_default_fedora_layout") is True,
        "policy: Fedora layout assumed",
    )
    require(
        backend.get("same_device_snapshot_is_backup") is False,
        "policy: local snapshot mislabeled backup",
    )
    require(
        backend.get("package_history_is_system_restore") is False,
        "policy: package history mislabeled restore",
    )
    action_classes = policy.get("action_classes")
    expected_actions = [
        "A0_read_only",
        "A1_user_space_reversible",
        "A2_package_or_system_configuration",
        "A3_kernel_driver_boot_or_graphics",
        "A4_storage_security_or_recovery_critical",
        "A5_never_positive",
    ]
    require(
        isinstance(action_classes, list)
        and [item.get("id") for item in action_classes] == expected_actions,
        "policy: action classes drift",
    )
    minimums = [
        "R0_record_only",
        "R0_record_only",
        "R1_local_filesystem_snapshot",
        "R2_external_system_backup",
        "R3_offline_full_device_recovery",
        None,
    ]
    require(
        [item.get("minimum_recovery_level") for item in action_classes] == minimums,
        "policy: recovery floors weakened",
    )
    require(
        action_classes[-1].get("approval") == "prohibited",
        "policy: never-positive action approvable",
    )
    require(
        action_classes[2].get("snapshot_required") is True
        and action_classes[3].get("snapshot_required") is True
        and action_classes[4].get("snapshot_required") is True,
        "policy: mutation snapshot gate missing",
    )
    invariants = policy.get("transaction_invariants", {})
    for required_true in (
        "exact_target_required",
        "fresh_pre_state_required",
        "planned_effects_and_surprise_conditions_required",
        "recovery_level_must_cover_every_touched_boundary",
        "recovery_artifact_created_and_verified_before_mutation",
        "snapshot_identifier_bound_to_approval",
        "one_state_changing_attempt",
        "post_change_validation_required",
        "unexpected_output_or_effect_stops",
        "failed_validation_requires_diagnosis_before_restore_decision",
        "restore_is_separately_approved_state_change",
        "audit_finalization_required",
    ):
        require(
            invariants.get(required_true) is True,
            f"policy: invariant {required_true} disabled",
        )
    require(invariants.get("automatic_retry") is False, "policy: automatic retry enabled")
    require(
        invariants.get("automatic_rollback") is False,
        "policy: automatic rollback enabled",
    )
    gates = policy.get("gates")
    expected_gates = [
        "H0_direct_host_contract",
        "H1_bounded_read_only_enrollment",
        "H2_recovery_backend_selection",
        "H3_recovery_artifact_creation",
        "H4_restore_rehearsal",
        "H5_shadow_mode_deployment",
        "H6_first_supervised_lighting_case",
        "H7_evidence_based_safe_list",
    ]
    require(
        isinstance(gates, list) and [item.get("id") for item in gates] == expected_gates,
        "policy: gate order drift",
    )
    require(gates[0].get("status") == "complete", "policy: structural gate incomplete")
    require(
        gates[1].get("status") == "blocked_on_fresh_user_authorization"
        and gates[1].get("user_decision_required") is True,
        "policy: enrollment boundary missing",
    )
    require(
        all(item.get("status") in {"blocked", "disabled"} for item in gates[2:]),
        "policy: downstream gate open",
    )
    require(
        policy.get("next_gate") == "H1_bounded_read_only_enrollment",
        "policy: next gate broadened",
    )
    return {
        "status": "valid",
        "host_observed": False,
        "mutation_performed": False,
        "current_mode": "fixture",
        "next_gate": policy["next_gate"],
        "recovery_levels": len(recovery),
        "action_classes": len(action_classes),
    }


def main() -> int:
    try:
        report = validate(load())
    except HostPolicyError as exc:
        print(f"direct-host policy rejected: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
