#!/usr/bin/env python3
"""Validate future controller and enrollment contracts without operational I/O."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "policy": "controller/policy.json",
    "operations": "controller/operations.json",
    "state_machine": "controller/state-machine.json",
    "sources": "enrollment/source-catalog.json",
    "proposal": "enrollment/fedora-workstation-proposal.json",
    "review": "enrollment/review.pending.json",
    "request": "fixtures/controller-request.json",
    "response": "fixtures/controller-response.json",
}
FORBIDDEN_KEYS = {
    "argv",
    "command",
    "commands",
    "device_path",
    "domain_xml",
    "executable",
    "host_path",
    "image_path",
    "raw_path",
    "script",
    "shell",
    "shell_line",
    "socket_path",
}
REQUIRED_EXCLUSIONS = {
    "credentials",
    "passwords",
    "tokens",
    "private_keys",
    "secret_environment_values",
    "browser_history",
    "document_or_file_contents",
    "shell_history",
    "usernames",
    "hostname",
    "network_addresses",
    "mac_addresses",
    "vpn_configuration",
    "hardware_serials",
    "filesystem_uuids",
    "disk_wwns",
    "personal_mount_paths",
    "gaming_inventory_or_optimization",
}
DISABLED_POLICY_FLAGS = {
    "service_process_exists",
    "operational_authority",
    "execution_enabled",
    "persistence_enabled",
    "host_observation_enabled",
    "virtualization_enabled",
    "network_enabled",
    "privilege_enabled",
    "device_access_enabled",
}


class ContractError(ValueError):
    """Raised when the controller contract must fail closed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def load(relative: str, root: Path = LAB_ROOT) -> Any:
    try:
        return json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"{relative}: {exc}") from exc


def file_digest(relative: str, root: Path = LAB_ROOT) -> str:
    try:
        return hashlib.sha256((root / relative).read_bytes()).hexdigest()
    except OSError as exc:
        raise ContractError(f"{relative}: {exc}") from exc


def walk_keys(value: Any, path: str = "$") -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield path, key
            yield from walk_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_keys(item, f"{path}[{index}]")


def reject_executable_fields(name: str, value: Any) -> None:
    for path, key in walk_keys(value):
        require(key not in FORBIDDEN_KEYS, f"{name}:{path}: forbidden key {key}")


def validate_policy(policy: dict[str, Any]) -> None:
    require(policy.get("schema_version") == 1, "controller policy: bad schema")
    if policy.get("implementation_status") == "h1_tier0_enabled":
        allowed_fields = {
            "schema_version",
            "version",
            "policy_id",
            "implementation_status",
            "transport",
            "service_process_exists",
            "operational_authority",
            "execution_enabled",
            "persistence_enabled",
            "host_observation_enabled",
            "virtualization_enabled",
            "network_enabled",
            "privilege_enabled",
            "device_access_enabled",
            "mutation_enabled",
            "current_capabilities",
            "activation_gate",
            "request_invariants",
            "future_separation",
            "never_exposed_to_tui_or_model",
        }
        require(
            set(policy).issubset(allowed_fields),
            "controller policy: undeclared authority field",
        )
        require(
            policy.get("current_capabilities") == ["bounded_tier0_read_only_observation"],
            "controller policy: capability scope drift",
        )
        require(
            set(policy.get("activation_gate", {}))
            == {
                "current_activation_authorized",
                "fixture_and_vm_rehearsal_required",
                "least_privilege_required",
                "new_security_review_required",
                "new_user_decision_required",
                "os_service_identity_required",
                "private_local_transport_required",
            },
            "controller policy: activation gate schema drift",
        )
        require(
            policy.get("transport") == "unix-user-private",
            "controller policy: live transport is not private",
        )
        require(
            policy.get("service_process_exists") is True,
            "controller policy: H1 service is absent",
        )
        require(
            policy.get("operational_authority") is True,
            "controller policy: H1 read authority is absent",
        )
        require(
            policy.get("host_observation_enabled") is True,
            "controller policy: H1 observation is disabled",
        )
        for flag in (
            "execution_enabled",
            "persistence_enabled",
            "virtualization_enabled",
            "network_enabled",
            "privilege_enabled",
            "device_access_enabled",
        ):
            require(
                policy.get(flag) is False,
                f"controller policy: unsafe capability {flag} enabled",
            )
        require(
            policy.get("mutation_enabled", False) is False,
            "controller policy: unsafe capability mutation_enabled enabled",
        )
        require(
            policy.get("activation_gate", {}).get("current_activation_authorized") is True,
            "controller policy: H1 activation gate is absent",
        )
        invariants = policy.get("request_invariants", {})
        require(
            set(invariants)
            == {
                "attempt_limit",
                "automatic_retry",
                "exact_operation_revision",
                "exact_parameter_allowlist",
                "exact_target_reference",
                "expiry_required",
                "idempotency_key_required",
                "policy_digest_required",
                "registered_operation_only",
                "state_digest_required_when_resolved",
                "unexpected_field_rejected",
            },
            "controller policy: request invariant schema drift",
        )
        require(invariants.get("automatic_retry") is False, "controller policy: retry on")
        require(invariants.get("attempt_limit") == 1, "controller policy: bad attempt limit")
        for key in (
            "exact_operation_revision",
            "exact_parameter_allowlist",
            "exact_target_reference",
            "expiry_required",
            "idempotency_key_required",
            "policy_digest_required",
            "registered_operation_only",
            "state_digest_required_when_resolved",
            "unexpected_field_rejected",
        ):
            require(
                invariants.get(key) is True,
                f"controller policy: invariant {key} is not enforced",
            )
        return
    require(
        policy.get("implementation_status") == "contract_only",
        "controller policy: implementation status must be contract_only",
    )
    require(policy.get("transport") == "none", "controller policy: transport exists")
    for flag in DISABLED_POLICY_FLAGS:
        require(policy.get(flag) is False, f"controller policy: {flag} must be false")
    invariants = policy.get("request_invariants", {})
    require(invariants.get("automatic_retry") is False, "controller policy: retry on")
    require(invariants.get("attempt_limit") == 1, "controller policy: bad attempt limit")
    activation = policy.get("activation_gate", {})
    require(
        activation.get("current_activation_authorized") is False,
        "controller policy: activation cannot be pre-authorized",
    )


def validate_state_machine(machine: dict[str, Any]) -> set[str]:
    require(machine.get("schema_version") == 1, "state machine: bad schema")
    require(machine.get("execution_enabled") is False, "state machine: execution on")
    states = machine.get("states")
    require(isinstance(states, list) and states, "state machine: missing states")
    require(len(states) == len(set(states)), "state machine: duplicate states")
    state_set = set(states)
    require(machine.get("initial_state") in state_set, "state machine: bad initial state")
    require(
        set(machine.get("terminal_states", [])).issubset(state_set),
        "state machine: bad terminal state",
    )
    rules = machine.get("failure_rules", {})
    require(rules.get("automatic_retry") is False, "state machine: retry on")
    require(rules.get("attempt_limit") == 1, "state machine: bad attempt limit")
    return state_set


def validate_operations(registry: dict[str, Any], states: set[str]) -> dict[str, dict[str, Any]]:
    require(registry.get("schema_version") == 1, "operations: bad schema")
    require(
        registry.get("implementation_status") == "contract_only",
        "operations: registry is not contract-only",
    )
    require(registry.get("execution_enabled") is False, "operations: execution on")
    operations = registry.get("operations")
    require(isinstance(operations, list) and operations, "operations: empty")
    indexed: dict[str, dict[str, Any]] = {}
    simulation_count = 0
    for operation in operations:
        operation_id = operation.get("id")
        require(
            isinstance(operation_id, str) and operation_id and operation_id not in indexed,
            "operations: duplicate or invalid id",
        )
        indexed[operation_id] = operation
        require(operation.get("execution_enabled") is False, f"{operation_id}: enabled")
        availability = operation.get("availability")
        require(
            availability in {"contract_simulation_only", "unimplemented"},
            f"{operation_id}: bad availability",
        )
        if availability == "contract_simulation_only":
            simulation_count += 1
            require(operation.get("effect_class") == "none", f"{operation_id}: effect")
            require(operation.get("future_adapter") is None, f"{operation_id}: adapter")
        else:
            require(
                isinstance(operation.get("future_adapter"), str),
                f"{operation_id}: missing future adapter identifier",
            )
        allowed = operation.get("allowed_parameters")
        require(
            isinstance(allowed, list) and len(allowed) == len(set(allowed)),
            f"{operation_id}: duplicate parameters",
        )
        require(
            not set(allowed).intersection(FORBIDDEN_KEYS),
            f"{operation_id}: forbidden parameter",
        )
        require(
            set(operation.get("from_states", [])).issubset(states)
            and operation.get("to_state") in states,
            f"{operation_id}: invalid state transition",
        )
        bindings = operation.get("identity_bindings")
        require(
            isinstance(bindings, list)
            and "policy_digest" in bindings
            and len(bindings) == len(set(bindings)),
            f"{operation_id}: incomplete identity binding",
        )
    require(simulation_count == 1, "operations: exactly one no-effect simulation allowed")
    return indexed


def validate_sources(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    require(catalog.get("schema_version") == 1, "sources: bad schema")
    require(
        catalog.get("implementation_status") == "definitions_only",
        "sources: must remain definitions-only",
    )
    require(catalog.get("execution_enabled") is False, "sources: execution on")
    sources = catalog.get("sources")
    require(isinstance(sources, list) and sources, "sources: empty")
    indexed: dict[str, dict[str, Any]] = {}
    for source in sources:
        source_id = source.get("id")
        require(
            isinstance(source_id, str) and source_id and source_id not in indexed,
            "sources: duplicate or invalid id",
        )
        indexed[source_id] = source
        require(source.get("network") is False, f"{source_id}: network on")
        require(source.get("mutation") is False, f"{source_id}: mutation on")
        require(
            source.get("future_adapter_required") is True,
            f"{source_id}: missing future adapter gate",
        )
        effect = source.get("potential_effect")
        access = source.get("access")
        if effect == "protected_access":
            require(access == "protected_read", f"{source_id}: protected effect mismatch")
        if access == "protected_read":
            require(
                source.get("privacy") == "restricted",
                f"{source_id}: protected source must be restricted",
            )
    return indexed


def validate_proposal(
    proposal: dict[str, Any],
    sources: dict[str, dict[str, Any]],
    source_catalog_digest: str,
) -> dict[str, int]:
    require(proposal.get("schema_version") == 1, "proposal: bad schema")
    require(proposal.get("status") == "prepared_unapproved", "proposal: bad status")
    require(proposal.get("execution_enabled") is False, "proposal: execution on")
    require(proposal.get("approval_granted") is False, "proposal: pre-approved")
    require(proposal.get("host_scan_performed") is False, "proposal: fake host scan")
    require(proposal.get("host_binding") is None, "proposal: host already bound")
    catalog_binding = proposal.get("source_catalog_binding", {})
    require(
        catalog_binding
        == {
            "catalog_id": "fedora-workstation-enrollment-sources",
            "version": "1.0.0",
            "sha256": source_catalog_digest,
        },
        "proposal: source catalog binding mismatch",
    )
    require(
        proposal.get("authority_model", {}).get("current_authority") == "none",
        "proposal: current authority exists",
    )
    invariants = proposal.get("observation_invariants", {})
    require(invariants.get("network") is False, "proposal: network on")
    require(invariants.get("mutation") is False, "proposal: mutation on")
    require(invariants.get("automatic_retry") is False, "proposal: retry on")
    require(invariants.get("attempt_limit_per_probe") == 1, "proposal: bad attempt")
    exclusions = set(proposal.get("global_exclusions", []))
    require(
        REQUIRED_EXCLUSIONS.issubset(exclusions),
        f"proposal: missing exclusions {sorted(REQUIRED_EXCLUSIONS - exclusions)}",
    )
    groups = proposal.get("groups")
    require(isinstance(groups, list) and groups, "proposal: no groups")
    group_ids: set[str] = set()
    fact_ids: set[str] = set()
    tier_counts: dict[int, int] = {0: 0, 1: 0, 2: 0}
    for group in groups:
        group_id = group.get("id")
        require(
            isinstance(group_id, str) and group_id and group_id not in group_ids,
            "proposal: duplicate or invalid group",
        )
        group_ids.add(group_id)
        require(group.get("current_enabled") is False, f"{group_id}: enabled")
        tier = group.get("tier")
        require(tier in {0, 1, 2}, f"{group_id}: invalid tier")
        tier_counts[tier] += 1
        admission = group.get("future_admission", "")
        if tier == 0:
            require(
                admission == "automatic_after_exact_proposal_activation",
                f"{group_id}: invalid tier-0 admission",
            )
        elif tier == 1:
            require("group_confirmation" in admission, f"{group_id}: group gate missing")
        else:
            require(admission == "per_probe_confirmation", f"{group_id}: probe gate")
        source_ids = group.get("source_ids")
        require(
            isinstance(source_ids, list) and source_ids and set(source_ids).issubset(sources),
            f"{group_id}: unknown source",
        )
        effects = {sources[source_id]["potential_effect"] for source_id in source_ids}
        if tier < 2:
            require(
                not effects.intersection({"protected_access", "may_wake_device"}),
                f"{group_id}: strong-effect source requires tier 2",
            )
        if tier == 0:
            require(
                effects.issubset({"none"}),
                f"{group_id}: tier 0 source has possible effect",
            )
        if tier == 2:
            require(
                effects.intersection({"protected_access", "may_wake_device"}),
                f"{group_id}: tier 2 lacks a strong-effect source",
            )
        facts = group.get("facts")
        require(isinstance(facts, list) and facts, f"{group_id}: no facts")
        used_sources: set[str] = set()
        for fact in facts:
            fact_id = fact.get("id")
            require(
                isinstance(fact_id, str) and fact_id and fact_id not in fact_ids,
                f"{group_id}: duplicate or invalid fact",
            )
            fact_ids.add(fact_id)
            source_id = fact.get("source_id")
            require(source_id in source_ids, f"{fact_id}: source not declared by group")
            used_sources.add(source_id)
            require(
                isinstance(fact.get("transform"), str) and fact["transform"],
                f"{fact_id}: transform missing",
            )
        require(
            used_sources == set(source_ids),
            f"{group_id}: unused or unrepresented source",
        )
        for bound in ("maximum_records", "output_limit_bytes", "freshness_seconds"):
            require(
                isinstance(group.get(bound), int)
                and not isinstance(group.get(bound), bool)
                and group[bound] > 0,
                f"{group_id}: invalid {bound}",
            )
    require(
        tier_counts[0] > 0 and tier_counts[1] > 0 and tier_counts[2] > 0,
        "proposal: tiers incomplete",
    )
    l2_groups = [group["id"] for group in groups if group["phase"] == "L2"]
    require(
        l2_groups == ["virtualization-readiness"],
        "proposal: L2 boundary is not exact",
    )
    gate = proposal.get("completion_gate", {})
    require(gate.get("candidate_is_not_active_profile") is True, "proposal: auto-active")
    require(gate.get("user_review_required") is True, "proposal: no final review")
    require(gate.get("L2_not_automatically_started") is True, "proposal: auto-start L2")
    return {
        "sources": len(sources),
        "groups": len(groups),
        "facts": len(fact_ids),
        "tier_0_groups": tier_counts[0],
        "tier_1_groups": tier_counts[1],
        "tier_2_groups": tier_counts[2],
    }


def parse_time(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ContractError(f"request: invalid timestamp {value}") from exc
    require(parsed.tzinfo is not None, "request: timestamp lacks timezone")
    return parsed


def validate_pending_review(
    review: dict[str, Any],
    proposal_digest: str,
    source_catalog_digest: str,
) -> None:
    require(review.get("schema_version") == 1, "review: bad schema")
    require(review.get("status") == "pending", "review: status is not pending")
    require(review.get("decision") is None, "review: decision already exists")
    require(review.get("reviewed_at") is None, "review: reviewed timestamp exists")
    require(review.get("expires_at") is None, "review: expiry pre-created")
    require(review.get("host_binding") is None, "review: host already bound")
    require(review.get("approval_digest") is None, "review: approval exists")
    require(review.get("current_authority") == "none", "review: authority exists")
    for field in ("activated_tiers", "approved_group_ids", "approved_fact_ids"):
        require(review.get(field) == [], f"review: {field} must be empty")
    require(
        review.get("proposal_binding")
        == {
            "proposal_id": "fedora-workstation-enrollment",
            "version": "1.0.0",
            "sha256": proposal_digest,
        },
        "review: proposal binding mismatch",
    )
    require(
        review.get("source_catalog_binding")
        == {
            "catalog_id": "fedora-workstation-enrollment-sources",
            "version": "1.0.0",
            "sha256": source_catalog_digest,
        },
        "review: source binding mismatch",
    )


class ContractSimulator:
    """One-use, in-memory transition checker with no effect implementation."""

    def __init__(
        self,
        operations: dict[str, dict[str, Any]],
        policy_digest: str,
        proposal_digest: str,
    ) -> None:
        self._operations = operations
        self._policy_digest = policy_digest
        self._proposal_digest = proposal_digest
        self._consumed: set[str] = set()

    def validate_request(self, request: dict[str, Any]) -> dict[str, Any]:
        require(request.get("schema_version") == 1, "request: bad schema")
        require(request.get("fixture_only") is True, "request: not fixture-only")
        require(request.get("execute") is False, "request: execution requested")
        require(request.get("attempt") == 1, "request: attempt is not one")
        key = request.get("idempotency_key")
        require(isinstance(key, str) and len(key) >= 16, "request: bad idempotency key")
        require(key not in self._consumed, "request: idempotency replay")
        operation_id = request.get("operation_id")
        require(operation_id in self._operations, "request: unknown operation")
        operation = self._operations[operation_id]
        require(
            operation["availability"] == "contract_simulation_only",
            "request: operational or unimplemented operation cannot be simulated as available",
        )
        require(
            request.get("operation_revision") == operation["revision"],
            "request: operation revision mismatch",
        )
        require(
            request.get("current_state") in operation["from_states"],
            "request: invalid current state",
        )
        require(
            request.get("expected_next_state") == operation["to_state"],
            "request: invalid next state",
        )
        parameters = request.get("parameters")
        require(isinstance(parameters, dict), "request: parameters must be object")
        require(
            set(parameters) == set(operation["allowed_parameters"]),
            "request: parameter set mismatch",
        )
        bindings = request.get("identity_bindings")
        require(isinstance(bindings, dict), "request: identity bindings must be object")
        require(
            set(bindings) == set(operation["identity_bindings"]),
            "request: identity binding set mismatch",
        )
        require(
            bindings.get("policy_digest") == self._policy_digest,
            "request: policy digest mismatch",
        )
        require(
            bindings.get("proposal_digest") == self._proposal_digest,
            "request: proposal digest mismatch",
        )
        require(
            parameters.get("proposal_digest") == self._proposal_digest,
            "request: proposal parameter digest mismatch",
        )
        require(
            request.get("target_ref") == "proposal:fedora-workstation-enrollment@1.0.0",
            "request: target mismatch",
        )
        require(request.get("approval_ref") is None, "request: fake approval attached")
        requested = parse_time(request.get("requested_at"))
        expires = parse_time(request.get("expires_at"))
        require(expires > requested, "request: invalid expiry")
        require(
            expires - requested <= dt.timedelta(minutes=15),
            "request: expiry exceeds maximum",
        )
        self._consumed.add(key)
        return {
            "schema_version": 1,
            "request_id": request["request_id"],
            "operation_id": operation_id,
            "result": "contract_validated_no_effect",
            "state_before": request["current_state"],
            "state_after": operation["to_state"],
            "effect_occurred": False,
            "operational_authority": False,
            "idempotency_key_consumed": True,
            "reasons": [
                "operation is registered for contract simulation only",
                "request explicitly forbids execution",
                "no execution, persistence, privilege, network, or mutation authority is exposed",
            ],
        }


def validate_all(root: Path = LAB_ROOT) -> dict[str, Any]:
    values = {name: load(relative, root) for name, relative in FILES.items()}
    for name, value in values.items():
        reject_executable_fields(name, value)
    validate_policy(values["policy"])
    states = validate_state_machine(values["state_machine"])
    operations = validate_operations(values["operations"], states)
    sources = validate_sources(values["sources"])
    source_catalog_digest = file_digest(FILES["sources"], root)
    enrollment = validate_proposal(values["proposal"], sources, source_catalog_digest)
    policy_digest = file_digest(FILES["policy"], root)
    proposal_digest = file_digest(FILES["proposal"], root)
    validate_pending_review(values["review"], proposal_digest, source_catalog_digest)
    simulator = ContractSimulator(operations, policy_digest, proposal_digest)
    actual_response = simulator.validate_request(values["request"])
    require(
        actual_response == values["response"],
        "response fixture differs from deterministic no-effect result",
    )
    return {
        "valid": True,
        "implementation_status": values["policy"].get("implementation_status"),
        "operational_authority": values["policy"].get("operational_authority") is True,
        "operations_defined": len(operations),
        "operations_executable": 0,
        "enrollment": enrollment,
        "host_scan_performed": False,
        "vm_controller_service_exists": values["policy"].get("service_process_exists") is True,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=LAB_ROOT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(json.dumps(validate_all(args.root.resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(f"controller contract validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"controller contract input error: {exc}", file=sys.stderr)
        raise SystemExit(2)
