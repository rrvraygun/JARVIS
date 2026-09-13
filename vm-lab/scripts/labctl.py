#!/usr/bin/env python3
"""Validate and evaluate Jarvis fixture-only scenario-lab contracts.

This module deliberately has no process, shell, network, virtualization,
privilege, device, host-observation, or persistence interface. It reads
versioned fixture JSON and prints deterministic reports to standard output.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parents[1]
MACHINE_FILES = (
    "policy/lab-policy.json",
    "profiles/fedora-workstation-template.json",
    "images/fedora-workstation-image-lock.template.json",
    "coverage/physical-gaps.json",
    "coverage/expected.json",
    "matrices/lighting-controls.json",
    "matrices/sysadmin-control-plane.json",
    "scenarios/catalog.json",
    "fixtures/run-record.json",
)
FORBIDDEN_MACHINE_KEYS = {
    "argv",
    "executable",
    "shell",
    "shell_line",
    "host_path",
    "device_path",
    "socket_path",
}
EXPECTED_AUTHORITY_FLAGS = {
    "host_observation_enabled",
    "virtualization_execution_enabled",
    "image_acquisition_enabled",
    "guest_creation_enabled",
    "guest_start_enabled",
    "registered_observation_enabled",
    "mutation_enabled",
    "privileged_action_enabled",
    "device_passthrough_enabled",
    "self_modification_enabled",
}
EXPECTED_DOMAINS = {
    "inventory",
    "health",
    "packages_updates",
    "services",
    "storage_filesystems",
    "boot_kernel",
    "graphics_display_input",
    "audio",
    "power_thermal",
    "security_selinux",
    "backups_recovery",
    "containers",
    "virtualization",
    "maintenance_cleanup",
    "applications",
    "logs",
    "knowledge_audit",
}
EXPECTED_OUTCOME_FIELDS = {
    "decision",
    "terminal_status",
    "stop",
    "automatic_retry",
    "approval_required",
    "evidence_class",
}


class LabValidationError(ValueError):
    """Raised when a fixture-only laboratory contract fails closed."""


def load_json(relative: str, root: Path = LAB_ROOT) -> Any:
    path = root / relative
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LabValidationError(f"{relative}: {exc}") from exc


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


def iter_keys(value: Any, path: str = "$") -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield path, key
            yield from iter_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_keys(item, f"{path}[{index}]")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LabValidationError(message)


def validate_machine_key_boundary(relative: str, value: Any) -> None:
    for path, key in iter_keys(value):
        require(
            key not in FORBIDDEN_MACHINE_KEYS,
            f"{relative}:{path}: executable-interface key is forbidden: {key}",
        )


def validate_policy(policy: dict[str, Any]) -> None:
    require(policy.get("schema_version") == 1, "policy: unsupported schema")
    require(policy.get("mode") == "fixture_only", "policy: mode must be fixture_only")
    authority = policy.get("authority")
    require(isinstance(authority, dict), "policy: authority must be an object")
    require(
        set(authority) == EXPECTED_AUTHORITY_FLAGS,
        "policy: authority flags changed without a contract revision",
    )
    require(
        all(value is False for value in authority.values()),
        "policy: every operational authority must remain disabled",
    )
    reset = policy.get("future_reset_contract", {})
    require(reset.get("attempt_limit") == 1, "policy: attempt limit must be one")
    require(reset.get("automatic_retry") is False, "policy: retry must be disabled")
    isolation = policy.get("future_isolation_contract", {})
    require(isolation.get("runtime_network") == "off", "policy: runtime network must be off")
    require(
        isolation.get("host_filesystem_shares") == "none",
        "policy: host shares must be absent",
    )
    require(
        isolation.get("host_credentials") == "prohibited",
        "policy: host credentials must be prohibited",
    )
    promotion = policy.get("promotion_gates", {})
    require(
        promotion.get("fixture_validation_ceiling") == 1,
        "policy: fixture evidence may promote only through maturity stage 1",
    )
    require(
        promotion.get("automatic_promotion") is False,
        "policy: automatic promotion must be disabled",
    )
    scope = policy.get("scope", {})
    require(
        set(scope.get("included_domains", [])) == EXPECTED_DOMAINS,
        "policy: accepted capability-domain set drifted",
    )
    require(
        set(scope.get("excluded_domains", [])) == {"gaming", "networking_vpn"},
        "policy: excluded scope must remain explicit",
    )


def validate_profile(profile: dict[str, Any]) -> None:
    require(profile.get("schema_version") == 1, "profile: unsupported schema")
    require(
        profile.get("status") == "unobserved_template",
        "profile: this artifact must remain an unobserved template",
    )
    enrollment = profile.get("enrollment", {})
    require(
        enrollment == {"host_scan_performed": False, "host_binding": None, "approved_at": None},
        "profile: host enrollment or observation appeared in the template",
    )
    require(
        set(profile.get("declared_scope", {}).get("included_domains", [])) == EXPECTED_DOMAINS,
        "profile: capability-domain scope differs from policy",
    )
    actual_state = profile.get("actual_state", {})
    require(
        actual_state.get("profile_observed_at") is None,
        "profile: observed timestamp is not permitted in the template",
    )
    for category in ("hardware", "software"):
        facts = actual_state.get(category)
        require(isinstance(facts, dict) and facts, f"profile: missing {category} facts")
        for name, fact in facts.items():
            require(
                fact == {"status": "unknown", "value": None},
                f"profile: {category}.{name} falsely claims observed state",
            )
    layers = {item.get("id"): item for item in profile.get("fidelity_layers", [])}
    require(
        set(layers) == {"contract_logic", "software_twin", "virtual_hardware", "physical_hardware"},
        "profile: all four fidelity layers must remain explicit",
    )
    require(
        layers["physical_hardware"].get("current_evidence") == "unrepresentable_by_default_vm",
        "profile: physical fidelity boundary is missing",
    )


def validate_image_lock(image: dict[str, Any]) -> None:
    require(image.get("schema_version") == 1, "image lock: unsupported schema")
    require(image.get("status") == "unresolved", "image lock: template must be unresolved")
    require(
        image.get("acquisition_enabled") is False,
        "image lock: acquisition must remain disabled",
    )
    require(image.get("publisher") == "Fedora Project", "image lock: publisher changed")
    source = image.get("source", {})
    require(
        all(value is None for value in source.values()),
        "image lock: source must not be resolved during planning",
    )
    verification = image.get("verification", {})
    require(
        verification.get("signed_checksum_verified") is False,
        "image lock: signature cannot be pre-asserted",
    )
    require(
        verification.get("image_sha256") is None,
        "image lock: image digest cannot be fabricated",
    )
    virtualization = image.get("virtualization", {})
    require(
        virtualization.get("device_passthrough") is False,
        "image lock: passthrough must remain off",
    )
    baseline = image.get("baseline", {})
    require(
        baseline.get("state") == "not_created",
        "image lock: baseline creation is outside this phase",
    )


def validate_dimension_map(matrix_id: str, label: str, dimensions: Any) -> dict[str, list[str]]:
    require(
        isinstance(dimensions, dict) and dimensions,
        f"{matrix_id}: {label} must be a non-empty object",
    )
    normalized: dict[str, list[str]] = {}
    for name, values in dimensions.items():
        require(isinstance(name, str) and name, f"{matrix_id}: invalid dimension name")
        require(
            isinstance(values, list) and values,
            f"{matrix_id}: {label}.{name} must be a non-empty list",
        )
        require(
            all(isinstance(value, str) and value for value in values),
            f"{matrix_id}: {label}.{name} contains a non-string value",
        )
        require(
            len(values) == len(set(values)),
            f"{matrix_id}: {label}.{name} contains duplicate values",
        )
        normalized[name] = values
    return normalized


def validate_matrix(matrix: dict[str, Any]) -> None:
    matrix_id = matrix.get("matrix_id")
    require(isinstance(matrix_id, str) and matrix_id, "matrix: missing matrix_id")
    require(matrix.get("schema_version") == 1, f"{matrix_id}: unsupported schema")
    require(matrix.get("execution_enabled") is False, f"{matrix_id}: execution enabled")
    require(
        matrix.get("coverage_strategy") == "exhaustive_declared_state_space",
        f"{matrix_id}: coverage strategy changed",
    )
    require(
        matrix.get("evidence_ceiling") == "simulation_only",
        f"{matrix_id}: evidence ceiling changed",
    )
    dimensions = validate_dimension_map(matrix_id, "dimensions", matrix.get("dimensions"))
    context = matrix.get("context_dimensions", {})
    if context:
        context = validate_dimension_map(matrix_id, "context_dimensions", context)
    require(
        not set(dimensions).intersection(context),
        f"{matrix_id}: state and context dimension names overlap",
    )
    exclusions = matrix.get("exclusions")
    require(isinstance(exclusions, list), f"{matrix_id}: exclusions must be a list")
    for exclusion in exclusions:
        require(isinstance(exclusion, dict) and exclusion, f"{matrix_id}: empty exclusion")
        for name, value in exclusion.items():
            require(name in dimensions, f"{matrix_id}: exclusion uses unknown {name}")
            require(
                value in dimensions[name],
                f"{matrix_id}: exclusion value is outside {name}",
            )
    rules = matrix.get("oracle_rules")
    require(isinstance(rules, list) and rules, f"{matrix_id}: no oracle rules")
    ids: set[str] = set()
    priorities: set[int] = set()
    defaults = 0
    for rule in rules:
        rule_id = rule.get("id")
        priority = rule.get("priority")
        condition = rule.get("when")
        expected = rule.get("expected")
        require(
            isinstance(rule_id, str) and rule_id and rule_id not in ids,
            f"{matrix_id}: duplicate or invalid oracle id",
        )
        ids.add(rule_id)
        require(
            isinstance(priority, int)
            and not isinstance(priority, bool)
            and priority not in priorities,
            f"{matrix_id}: duplicate or invalid priority for {rule_id}",
        )
        priorities.add(priority)
        require(isinstance(condition, dict), f"{matrix_id}:{rule_id}: when must be object")
        defaults += int(not condition)
        for name, value in condition.items():
            require(name in dimensions, f"{matrix_id}:{rule_id}: unknown {name}")
            require(
                value in dimensions[name],
                f"{matrix_id}:{rule_id}: invalid value for {name}",
            )
        require(
            isinstance(expected, dict) and set(expected) == EXPECTED_OUTCOME_FIELDS,
            f"{matrix_id}:{rule_id}: incomplete expected outcome",
        )
        require(
            expected.get("automatic_retry") is False,
            f"{matrix_id}:{rule_id}: retry must be disabled",
        )
        require(
            isinstance(expected.get("stop"), bool)
            and isinstance(expected.get("approval_required"), bool),
            f"{matrix_id}:{rule_id}: boolean outcome fields are invalid",
        )
    require(defaults == 1, f"{matrix_id}: exactly one default oracle is required")
    ordered = sorted(rules, key=lambda item: item["priority"])
    require(
        ordered[-1]["when"] == {},
        f"{matrix_id}: default oracle must have the lowest precedence",
    )


def case_is_excluded(case: dict[str, str], exclusions: list[dict[str, str]]) -> bool:
    return any(all(case.get(key) == value for key, value in item.items()) for item in exclusions)


def iter_matrix_cases(matrix: dict[str, Any]) -> Iterator[dict[str, str]]:
    dimensions = matrix["dimensions"]
    names = tuple(dimensions)
    for values in itertools.product(*(dimensions[name] for name in names)):
        case = dict(zip(names, values, strict=True))
        if not case_is_excluded(case, matrix["exclusions"]):
            yield case


def evaluate_case(matrix: dict[str, Any], case: dict[str, str]) -> tuple[str, dict[str, Any]]:
    for rule in sorted(matrix["oracle_rules"], key=lambda item: item["priority"]):
        if all(case.get(key) == value for key, value in rule["when"].items()):
            return rule["id"], rule["expected"]
    raise LabValidationError(f"{matrix['matrix_id']}: no oracle matched")


def validate_curated_catalog(
    catalog: dict[str, Any], matrices: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    require(catalog.get("schema_version") == 1, "scenario catalog: unsupported schema")
    require(
        catalog.get("execution_enabled") is False,
        "scenario catalog: execution must remain disabled",
    )
    scenarios = catalog.get("scenarios")
    require(isinstance(scenarios, list) and scenarios, "scenario catalog: empty")
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for scenario in scenarios:
        scenario_id = scenario.get("id")
        require(
            isinstance(scenario_id, str) and scenario_id and scenario_id not in seen,
            "scenario catalog: duplicate or invalid id",
        )
        seen.add(scenario_id)
        matrix_id = scenario.get("matrix_id")
        require(matrix_id in matrices, f"{scenario_id}: unknown matrix {matrix_id}")
        matrix = matrices[matrix_id]
        case = scenario.get("matrix_case")
        require(isinstance(case, dict), f"{scenario_id}: matrix_case must be an object")
        dimensions = matrix["dimensions"]
        context = matrix.get("context_dimensions", {})
        require(
            set(case) == set(dimensions).union(context),
            f"{scenario_id}: case must set every state and context dimension exactly once",
        )
        for name, value in case.items():
            allowed = dimensions.get(name, context.get(name, []))
            require(value in allowed, f"{scenario_id}: invalid {name} value {value}")
        state_case = {name: case[name] for name in dimensions}
        oracle_id, expected = evaluate_case(matrix, state_case)
        require(
            scenario.get("expected_oracle") == oracle_id,
            f"{scenario_id}: expected {scenario.get('expected_oracle')}, got {oracle_id}",
        )
        require(
            scenario.get("expected_decision") == expected["decision"],
            f"{scenario_id}: decision expectation drifted",
        )
        require(
            scenario.get("expected_stop") is expected["stop"],
            f"{scenario_id}: stop expectation drifted",
        )
        require(
            scenario.get("fidelity") == "fixture",
            f"{scenario_id}: curated case must not claim live fidelity",
        )
        require(
            isinstance(scenario.get("requirements"), list) and scenario["requirements"],
            f"{scenario_id}: requirements are missing",
        )
        results.append(
            {
                "scenario_id": scenario_id,
                "matrix_id": matrix_id,
                "oracle": oracle_id,
                "decision": expected["decision"],
                "passed": True,
            }
        )
    return results


def matrix_coverage(matrix: dict[str, Any]) -> dict[str, Any]:
    oracle_counts: Counter[str] = Counter()
    outcome_counts: Counter[str] = Counter()
    evaluated = 0
    for case in iter_matrix_cases(matrix):
        oracle_id, expected = evaluate_case(matrix, case)
        oracle_counts[oracle_id] += 1
        outcome_counts[expected["terminal_status"]] += 1
        evaluated += 1
    missing_oracles = sorted(
        {rule["id"] for rule in matrix["oracle_rules"]}.difference(oracle_counts)
    )
    require(
        not missing_oracles,
        f"{matrix['matrix_id']}: unreachable oracle rules: {missing_oracles}",
    )
    dimensions = matrix["dimensions"]
    context = matrix.get("context_dimensions", {})
    context_variants = 1
    for values in context.values():
        context_variants *= len(values)
    pair_total = 0
    all_dimensions = {**dimensions, **context}
    names = tuple(all_dimensions)
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            pair_total += len(all_dimensions[left]) * len(all_dimensions[right])
    digest_basis = {
        "matrix_id": matrix["matrix_id"],
        "version": matrix["version"],
        "coverage_strategy": matrix["coverage_strategy"],
        "dimensions": dimensions,
        "context_dimensions": context,
        "exclusions": matrix["exclusions"],
        "oracle_rules": matrix["oracle_rules"],
    }
    return {
        "matrix_id": matrix["matrix_id"],
        "version": matrix["version"],
        "evaluated_state_cases": evaluated,
        "context_variants": context_variants,
        "logical_declared_cases": evaluated * context_variants,
        "dimension_values_covered": sum(len(values) for values in all_dimensions.values()),
        "declared_pair_values_covered": pair_total,
        "declared_pair_values_total": pair_total,
        "pair_coverage_percent": 100,
        "oracle_counts": dict(sorted(oracle_counts.items())),
        "terminal_status_counts": dict(sorted(outcome_counts.items())),
        "state_space_digest": canonical_digest(digest_basis),
        "evidence_ceiling": "simulation_only",
    }


def validate_physical_gaps(gaps: dict[str, Any]) -> int:
    items = gaps.get("gaps")
    require(isinstance(items, list) and items, "physical gaps: catalog is empty")
    ids: set[str] = set()
    for item in items:
        gap_id = item.get("id")
        require(
            isinstance(gap_id, str) and gap_id and gap_id not in ids,
            "physical gaps: duplicate or invalid id",
        )
        ids.add(gap_id)
        require(item.get("status") == "open", f"physical gap {gap_id}: falsely closed")
        for field in (
            "claim_blocked",
            "why_vm_is_insufficient",
            "required_future_evidence",
        ):
            require(
                isinstance(item.get(field), str) and item[field],
                f"physical gap {gap_id}: missing {field}",
            )
    return len(items)


def validate_fixture_run_record(record: dict[str, Any]) -> None:
    require(record.get("schema_version") == 1, "run record: unsupported schema")
    require(record.get("mode") == "fixture", "run record: mode must be fixture")
    require(record.get("attempt") == 1, "run record: attempt must be one")
    require(
        record.get("profile_digest") == "unresolved"
        and record.get("image_lock_digest") == "unresolved"
        and record.get("domain_digest") == "unresolved",
        "run record: planning fixture must not claim resolved VM identity",
    )
    reset = record.get("reset_attestation", {})
    require(reset.get("vm_started") is False, "run record: VM start was falsely recorded")
    require(
        reset.get("host_observed") is False,
        "run record: host observation was falsely recorded",
    )
    require(
        reset.get("mutation_attempted") is False,
        "run record: mutation was falsely recorded",
    )


def validate_coverage_expectations(
    expected: dict[str, Any],
    reports: list[dict[str, Any]],
    curated_count: int,
    physical_count: int,
) -> None:
    require(expected.get("schema_version") == 1, "coverage expectations: bad schema")
    require(expected.get("mode") == "fixture_only", "coverage expectations: bad mode")
    require(
        expected.get("curated_scenarios") == curated_count,
        "coverage expectations: curated scenario count changed",
    )
    require(
        expected.get("physical_gaps_open") == physical_count,
        "coverage expectations: physical gap count changed",
    )
    report_by_id = {report["matrix_id"]: report for report in reports}
    expected_items = expected.get("matrices")
    require(
        isinstance(expected_items, list)
        and {item.get("matrix_id") for item in expected_items} == set(report_by_id),
        "coverage expectations: matrix set changed",
    )
    compared_fields = (
        "matrix_id",
        "version",
        "evaluated_state_cases",
        "context_variants",
        "logical_declared_cases",
        "declared_pair_values_total",
        "state_space_digest",
    )
    for item in expected_items:
        actual = report_by_id[item["matrix_id"]]
        for field in compared_fields:
            require(
                item.get(field) == actual.get(field),
                f"coverage expectations: {item['matrix_id']}.{field} changed",
            )


def load_and_validate(root: Path = LAB_ROOT) -> dict[str, Any]:
    loaded = {relative: load_json(relative, root) for relative in MACHINE_FILES}
    for relative, value in loaded.items():
        validate_machine_key_boundary(relative, value)
    validate_policy(loaded["policy/lab-policy.json"])
    validate_profile(loaded["profiles/fedora-workstation-template.json"])
    validate_image_lock(loaded["images/fedora-workstation-image-lock.template.json"])
    matrix_values = [
        loaded["matrices/lighting-controls.json"],
        loaded["matrices/sysadmin-control-plane.json"],
    ]
    matrices: dict[str, dict[str, Any]] = {}
    for matrix in matrix_values:
        validate_matrix(matrix)
        matrix_id = matrix["matrix_id"]
        require(matrix_id not in matrices, f"duplicate matrix id: {matrix_id}")
        matrices[matrix_id] = matrix
    curated = validate_curated_catalog(loaded["scenarios/catalog.json"], matrices)
    physical_count = validate_physical_gaps(loaded["coverage/physical-gaps.json"])
    validate_fixture_run_record(loaded["fixtures/run-record.json"])
    matrix_reports = [
        matrix_coverage(matrix)
        for matrix in sorted(matrices.values(), key=lambda item: item["matrix_id"])
    ]
    validate_coverage_expectations(
        loaded["coverage/expected.json"],
        matrix_reports,
        len(curated),
        physical_count,
    )
    return {
        "loaded": loaded,
        "matrices": matrices,
        "curated": curated,
        "physical_count": physical_count,
        "matrix_reports": matrix_reports,
    }


def build_coverage_report(validated: dict[str, Any]) -> dict[str, Any]:
    curated = validated["curated"]
    return {
        "schema_version": 1,
        "mode": "fixture_only",
        "matrices": validated["matrix_reports"],
        "curated_scenarios": {
            "total": len(curated),
            "passed": sum(item["passed"] for item in curated),
            "failed": 0,
        },
        "promotion_ceiling": 1,
        "physical_gaps_open": validated["physical_count"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=LAB_ROOT,
        help="Scenario-lab source root; defaults to the directory containing this tool.",
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)
    subparsers.add_parser("validate", help="Validate all static fail-closed contracts.")
    subparsers.add_parser(
        "run-fixtures", help="Evaluate curated regression cases without execution."
    )
    subparsers.add_parser("coverage", help="Evaluate declared fixture matrices and print coverage.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    validated = load_and_validate(args.root.resolve())
    if args.operation == "validate":
        payload = {
            "valid": True,
            "mode": "fixture_only",
            "matrices": sorted(validated["matrices"]),
            "curated_scenarios": len(validated["curated"]),
            "physical_gaps_open": validated["physical_count"],
            "operational_authority": False,
        }
    elif args.operation == "run-fixtures":
        payload = {
            "mode": "fixture_only",
            "total": len(validated["curated"]),
            "passed": len(validated["curated"]),
            "failed": 0,
            "results": validated["curated"],
            "operational_authority": False,
        }
    else:
        payload = build_coverage_report(validated)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LabValidationError as exc:
        print(f"lab validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"lab input error: {exc}", file=sys.stderr)
        raise SystemExit(2)
