#!/usr/bin/env python3
"""Validate fixture-only L2 readiness adapters without host observation."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "registry": "readiness/adapter-registry.json",
    "plan": "readiness/fedora-kvm-readiness-plan.json",
    "sources": "enrollment/source-catalog.json",
    "proposal": "enrollment/fedora-workstation-proposal.json",
    "tier0_registry": "observation/adapter-registry.json",
    "tier0_response": "fixtures/observation-response.json",
    "response": "fixtures/readiness-response.json",
}
SAFE_TOKEN = re.compile(r"^[A-Za-z0-9._+:-]{1,160}$")
VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+)+(?:-[A-Za-z0-9.]+)?$")


class ReadinessError(ValueError):
    """Raised when the readiness fixture contract must fail closed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReadinessError(message)


def load(relative: str, root: Path = LAB_ROOT) -> Any:
    try:
        return json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReadinessError(f"{relative}: {exc}") from exc


def digest(relative: str, root: Path = LAB_ROOT) -> str:
    try:
        return hashlib.sha256((root / relative).read_bytes()).hexdigest()
    except OSError as exc:
        raise ReadinessError(f"{relative}: {exc}") from exc


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    require(
        isinstance(value, dict) and set(value) == keys,
        f"{label}: unexpected or missing fields",
    )
    return value


def walk_strings(value: Any, label: str = "$") -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield label, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from walk_strings(item, f"{label}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_strings(item, f"{label}[{index}]")


def reject_unsafe_text(value: Any, label: str) -> None:
    for path, text in walk_strings(value, label):
        require(len(text) <= 512, f"{path}: text too long")
        for character in text:
            codepoint = ord(character)
            require(
                codepoint >= 32 and codepoint not in {127},
                f"{path}: control character rejected",
            )
        require(
            "$(" not in text and "`" not in text,
            f"{path}: active shell syntax rejected",
        )


def parse_package(value: Any, label: str, optional: bool = False) -> dict[str, str]:
    exact(value, {"status", "version"}, label)
    statuses = {"installed", "absent"} | ({"optional_absent"} if optional else set())
    require(value["status"] in statuses, f"{label}: invalid status")
    if value["status"] == "installed":
        require(
            isinstance(value["version"], str) and VERSION.fullmatch(value["version"]) is not None,
            f"{label}: invalid version",
        )
    else:
        require(value["version"] is None, f"{label}: absent package has version")
    return value


def parse_virtualization(value: Any) -> dict[str, Any]:
    keys = {
        "kvm_interface",
        "kvm_kernel_support",
        "qemu",
        "libvirt",
        "libvirt_service",
        "virt_install",
        "graphical_manager",
        "uefi_firmware",
        "current_user_access",
        "cgroup_mode",
        "conflict_summary",
    }
    exact(value, keys, "virtualization-summary")
    require(
        value["kvm_interface"] in {"absent", "present_inaccessible", "accessible", "unknown"},
        "virtualization-summary: bad KVM interface",
    )
    require(
        value["kvm_kernel_support"] in {"absent", "available", "active", "unknown"},
        "virtualization-summary: bad KVM kernel state",
    )
    parse_package(value["qemu"], "virtualization-summary.qemu")
    parse_package(value["libvirt"], "virtualization-summary.libvirt")
    parse_package(value["virt_install"], "virtualization-summary.virt_install")
    parse_package(
        value["graphical_manager"],
        "virtualization-summary.graphical_manager",
        optional=True,
    )
    require(
        value["libvirt_service"] in {"uninstalled", "inactive", "active", "unknown"},
        "virtualization-summary: bad service state",
    )
    require(
        value["uefi_firmware"] in {"available", "absent", "unknown"},
        "virtualization-summary: bad UEFI state",
    )
    require(
        value["current_user_access"]
        in {"sufficient_without_identity", "insufficient_without_identity", "unknown"},
        "virtualization-summary: bad access state",
    )
    require(
        value["cgroup_mode"] in {"v1", "v2", "hybrid", "unknown"},
        "virtualization-summary: bad cgroup mode",
    )
    require(
        value["conflict_summary"]
        in {
            "none_detected_without_guest_names",
            "bounded_conflict_detected",
            "unknown",
        },
        "virtualization-summary: bad conflict state",
    )
    return {
        "readiness.kvm_interface": value["kvm_interface"],
        "readiness.kvm_kernel_support": value["kvm_kernel_support"],
        "readiness.qemu": value["qemu"],
        "readiness.libvirt": value["libvirt"],
        "readiness.libvirt_service": value["libvirt_service"],
        "readiness.virt_install": value["virt_install"],
        "readiness.graphical_manager": value["graphical_manager"],
        "readiness.uefi_firmware": value["uefi_firmware"],
        "readiness.current_user_access": value["current_user_access"],
        "readiness.cgroup_mode": value["cgroup_mode"],
        "readiness.conflict_summary": value["conflict_summary"],
    }


def parse_storage(value: Any) -> dict[str, Any]:
    exact(value, {"capacity_class", "filesystem_capability"}, "storage-summary")
    require(
        value["capacity_class"]
        in {
            "below_minimum",
            "meets_minimum",
            "meets_preferred_full_workstation",
            "unknown",
        },
        "storage-summary: bad capacity class",
    )
    require(
        value["filesystem_capability"]
        in {
            "supports_sparse_qcow2_and_atomic_rename",
            "limited",
            "unsupported",
            "unknown",
        },
        "storage-summary: bad filesystem capability",
    )
    return {
        "readiness.storage_capacity": value["capacity_class"],
        "readiness.storage_filesystem": value["filesystem_capability"],
    }


def parse_selinux(value: Any) -> dict[str, Any]:
    exact(value, {"mode", "policy_class"}, "selinux-summary")
    require(
        value["mode"] in {"enforcing", "permissive", "disabled", "unknown"},
        "selinux-summary: bad mode",
    )
    require(
        isinstance(value["policy_class"], str)
        and SAFE_TOKEN.fullmatch(value["policy_class"]) is not None,
        "selinux-summary: bad policy class",
    )
    return {"readiness.selinux": value}


PARSERS: dict[str, Callable[[Any], dict[str, Any]]] = {
    "virtualization_readiness_v1": parse_virtualization,
    "storage_readiness_v1": parse_storage,
    "selinux_readiness_v1": parse_selinux,
}


def validate_contract(root: Path = LAB_ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = load(FILES["registry"], root)
    plan = load(FILES["plan"], root)
    sources = load(FILES["sources"], root)
    tier0_registry = load(FILES["tier0_registry"], root)
    require(
        registry.get("implementation_status") == "fixture_validated_parsers_only",
        "registry: bad status",
    )
    for flag in (
        "execution_enabled",
        "host_observation_enabled",
        "live_backend_implemented",
    ):
        require(registry.get(flag) is False, f"registry: {flag} must be false")
    expected_bindings = {
        "source_catalog_sha256": digest(FILES["sources"], root),
        "proposal_sha256": digest(FILES["proposal"], root),
        "tier0_adapter_registry_sha256": digest(FILES["tier0_registry"], root),
        "readiness_plan_sha256": digest(FILES["plan"], root),
    }
    require(registry.get("bindings") == expected_bindings, "registry: digest binding drift")
    require(
        plan.get("fixture_adapter_registry_complete") is True,
        "plan: fixture registry not complete",
    )
    require(
        plan.get("live_observation_backend_complete") is False,
        "plan: false live backend claim",
    )
    require(
        plan.get("host_scan_performed") is False and plan.get("approval_granted") is False,
        "plan: operational claim",
    )
    source_index = {item["id"]: item for item in sources["sources"]}
    plan_checks = {item["id"]: item for item in plan["checks"]}
    tier0_index = {item["id"]: item for item in tier0_registry["adapters"]}
    bound_checks: set[str] = set()
    for binding in registry.get("existing_tier0_bindings", []):
        exact(binding, {"check_id", "adapter_id", "fact_id", "transform"}, "tier0-binding")
        check = plan_checks.get(binding["check_id"])
        adapter = tier0_index.get(binding["adapter_id"])
        require(
            check is not None and adapter is not None,
            "tier0-binding: missing check or adapter",
        )
        require(check["fixture_adapter_id"] == adapter["id"], "tier0-binding: plan drift")
        require(
            binding["fact_id"] in adapter["expected_fact_ids"],
            "tier0-binding: fact drift",
        )
        require(check["source_id"] == adapter["source_id"], "tier0-binding: source drift")
        bound_checks.add(check["id"])
    adapters = registry.get("adapters")
    require(
        isinstance(adapters, list) and len(adapters) == 3,
        "registry: expected three L2 parsers",
    )
    for adapter in adapters:
        adapter_id = adapter.get("id")
        require(
            adapter.get("maturity_level") == 1 and adapter.get("execution_enabled") is False,
            f"{adapter_id}: operational or over-mature",
        )
        require(adapter.get("parser_id") in PARSERS, f"{adapter_id}: unknown parser")
        risk = adapter.get("risk", {})
        require(risk.get("tier") == 1, f"{adapter_id}: wrong tier")
        for flag in ("privilege", "network", "mutation", "device_wake"):
            require(risk.get(flag) is False, f"{adapter_id}: {flag} enabled")
        require(
            adapter.get("bounds", {}).get("attempt_limit") == 1,
            f"{adapter_id}: retries allowed",
        )
        source = source_index.get(adapter.get("source_id"))
        require(
            source is not None and source.get("interface") == adapter.get("source_interface"),
            f"{adapter_id}: source binding drift",
        )
        require(
            source.get("network") is False
            and source.get("mutation") is False
            and source.get("potential_effect") in {"none", "none_expected"},
            f"{adapter_id}: unsafe source",
        )
        for check_id in adapter.get("expected_check_ids", []):
            check = plan_checks.get(check_id)
            require(
                check is not None and check["fixture_adapter_id"] == adapter_id,
                f"{adapter_id}: check binding drift",
            )
            require(
                check["source_id"] == adapter["source_id"],
                f"{adapter_id}: check source drift",
            )
            require(
                check["live_backend_implemented"] is False,
                f"{adapter_id}: false live backend claim",
            )
            require(check_id not in bound_checks, f"{adapter_id}: duplicate check binding")
            bound_checks.add(check_id)
    require(bound_checks == set(plan_checks), "registry: not all eighteen checks are bound")
    fixture_set = registry.get("fixture_set", {})
    require(
        fixture_set.get("synthetic") is True and fixture_set.get("represents_host") is False,
        "registry: fixture identity unsafe",
    )
    allowed = (root / "fixtures/readiness").resolve()
    for reference in fixture_set.get("files", {}).values():
        require(
            isinstance(reference, str) and reference.startswith("fixtures/readiness/"),
            "registry: arbitrary fixture reference",
        )
        target = (root / reference).resolve()
        require(
            target.is_relative_to(allowed) and target.is_file(),
            "registry: fixture escaped or missing",
        )
    return registry, plan


def _load_registered_fixture(
    registry: dict[str, Any], input_id: str, maximum: int, root: Path
) -> Any:
    reference = registry["fixture_set"]["files"][input_id]
    raw = (root / reference).read_bytes()
    require(len(raw) <= maximum, f"{input_id}: input bound exceeded")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReadinessError(f"{input_id}: malformed UTF-8 JSON") from exc
    reject_unsafe_text(value, input_id)
    return value


def simulate(
    registry: dict[str, Any], plan: dict[str, Any], root: Path = LAB_ROOT
) -> dict[str, Any]:
    tier0 = load(FILES["tier0_response"], root)
    require(
        tier0.get("host_observed") is False and tier0.get("execution_performed") is False,
        "tier0 response: operational claim",
    )
    tier0_facts = {item["fact_id"]: item for item in tier0.get("candidate_facts", [])}
    plan_checks = {item["id"]: item for item in plan["checks"]}
    results: dict[str, Any] = {}
    sources: dict[str, str] = {}
    for binding in registry["existing_tier0_bindings"]:
        fact = tier0_facts.get(binding["fact_id"])
        require(
            fact is not None and fact.get("synthetic") is True,
            "tier0 fixture fact missing",
        )
        value = fact["value"]
        if binding["transform"] == "fedora_compatibility":
            value = "fedora" if value == "fedora" else "incompatible"
        elif binding["transform"] == "workstation_capacity_class":
            require(type(value) is int and value > 0, "tier0 memory fact invalid")
            value = (
                "meets_preferred_full_workstation"
                if value >= 16 * 1024**3
                else "meets_minimum"
                if value >= 8 * 1024**3
                else "below_minimum"
            )
        results[binding["check_id"]] = value
        sources[binding["check_id"]] = plan_checks[binding["check_id"]]["source_id"]
    for adapter in registry["adapters"]:
        value = _load_registered_fixture(
            registry,
            adapter["fixture_input"],
            adapter["bounds"]["max_input_bytes"],
            root,
        )
        parsed = PARSERS[adapter["parser_id"]](value)
        require(
            list(parsed) == adapter["expected_check_ids"],
            f"{adapter['id']}: unexpected parser output",
        )
        require(
            len(parsed) <= adapter["bounds"]["max_output_results"],
            f"{adapter['id']}: output bound exceeded",
        )
        for check_id, result in parsed.items():
            require(check_id not in results, f"{adapter['id']}: duplicate result")
            results[check_id] = result
            sources[check_id] = adapter["source_id"]
    require(set(results) == set(plan_checks), "simulation: incomplete readiness result set")
    response = {
        "schema_version": 1,
        "status": "fixture_simulated",
        "fixture_set_id": registry["fixture_set"]["id"],
        "execution_performed": False,
        "host_observed": False,
        "effect_occurred": False,
        "persistence_performed": False,
        "attempts": 1,
        "candidate_results": [
            {
                "check_id": check["id"],
                "result": results[check["id"]],
                "source_id": sources[check["id"]],
                "synthetic": True,
            }
            for check in plan["checks"]
        ],
        "warnings": [
            "Synthetic readiness results test parsers only and do not describe the host or authorize VM work."
        ],
    }
    reject_unsafe_text(response, "response")
    return response


def validate_all(root: Path = LAB_ROOT) -> dict[str, Any]:
    registry, plan = validate_contract(root)
    response = simulate(registry, plan, root)
    require(response == load(FILES["response"], root), "readiness response drift")
    return {
        "status": "valid",
        "execution_performed": False,
        "host_observed": False,
        "live_backend_implemented": False,
        "fixture_parsers": len(registry["adapters"]),
        "bound_checks": len(response["candidate_results"]),
    }


def main() -> int:
    try:
        report = validate_all()
    except ReadinessError as exc:
        print(f"readiness contract rejected: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
