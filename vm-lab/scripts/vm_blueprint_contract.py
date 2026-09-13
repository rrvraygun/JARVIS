#!/usr/bin/env python3
"""Validate the non-operational full Fedora Workstation VM blueprint."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "blueprint": "blueprints/fedora-workstation-full.json",
    "gates": "blueprints/provisioning-gates.json",
    "readiness": "readiness/fedora-kvm-readiness-plan.json",
    "sources": "enrollment/source-catalog.json",
    "image_lock": "images/fedora-workstation-image-lock.template.json",
    "lab_policy": "policy/lab-policy.json",
    "controller_policy": "controller/policy.json",
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


class BlueprintError(ValueError):
    """Raised when the blueprint fails a safety or completeness invariant."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BlueprintError(message)


def load(relative: str, root: Path = LAB_ROOT) -> Any:
    try:
        return json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BlueprintError(f"{relative}: {exc}") from exc


def walk_keys(value: Any, path: str = "$") -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield path, key
            yield from walk_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_keys(item, f"{path}[{index}]")


def reject_executable_fields(label: str, value: Any) -> None:
    for path, key in walk_keys(value):
        require(key not in FORBIDDEN_KEYS, f"{label}:{path}: forbidden executable key {key}")


def validate_blueprint(blueprint: dict[str, Any], image_lock: dict[str, Any]) -> None:
    require(blueprint.get("status") == "prepared_unresolved", "blueprint: status drift")
    require(
        blueprint.get("implementation_status") == "design_only",
        "blueprint: implementation exists",
    )
    for flag in (
        "execution_enabled",
        "vm_exists",
        "host_readiness_observed",
        "image_acquired",
    ):
        require(blueprint.get(flag) is False, f"blueprint: {flag} must be false")
    identity = blueprint.get("identity", {})
    require(
        identity.get("operating_system") == "Fedora Workstation",
        "blueprint: not Workstation",
    )
    require(
        identity.get("full_gui_payload_required") is True,
        "blueprint: full GUI payload is not required",
    )
    require(
        identity.get("architecture") is None and identity.get("release") is None,
        "blueprint: unresolved identity was guessed",
    )
    require(
        identity.get("image_lock_id") == image_lock.get("lock_id"),
        "blueprint: image-lock mismatch",
    )
    resources = blueprint.get("resource_policy", {})
    require(
        resources.get("status") == "unresolved_until_approved_readiness",
        "blueprint: resources already resolved",
    )
    for key in ("selected_vcpus", "selected_memory_bytes", "selected_disk_bytes"):
        require(resources.get(key) is None, f"blueprint: {key} was guessed")
    minimum = resources.get("minimum_full_workstation", {})
    preferred = resources.get("preferred_full_workstation", {})
    require(minimum.get("vcpus", 0) >= 4, "blueprint: full Workstation CPU floor too small")
    require(
        minimum.get("memory_bytes", 0) >= 8 * 1024**3,
        "blueprint: full Workstation memory floor too small",
    )
    require(
        minimum.get("disk_bytes", 0) >= 80 * 1024**3,
        "blueprint: full Workstation disk floor too small",
    )
    for key in ("vcpus", "memory_bytes", "disk_bytes"):
        require(
            preferred.get(key, 0) >= minimum.get(key, 0),
            f"blueprint: preferred {key} below minimum",
        )
    profiles = {item["id"]: item for item in blueprint.get("boot_profiles", [])}
    require(
        set(profiles) == {"headless_system_validation", "graphical_workstation_validation"},
        "blueprint: boot profile set drift",
    )
    headless = profiles["headless_system_validation"]
    graphical = profiles["graphical_workstation_validation"]
    require(
        headless.get("installed_payload") == "full_fedora_workstation",
        "blueprint: headless profile is a reduced guest",
    )
    require(
        graphical.get("installed_payload") == "full_fedora_workstation",
        "blueprint: graphical profile is incomplete",
    )
    require(
        headless.get("boot_goal") == "multi_user"
        and headless.get("graphical_session_started") is False,
        "blueprint: bad headless profile",
    )
    require(
        graphical.get("boot_goal") == "graphical"
        and graphical.get("graphical_session_started") is True,
        "blueprint: bad graphical profile",
    )
    require(
        headless.get("runtime_network") == "off" and graphical.get("runtime_network") == "off",
        "blueprint: runtime network enabled",
    )
    hardware = blueprint.get("virtual_hardware", {})
    for flag in (
        "device_passthrough",
        "physical_GPU_passthrough",
        "host_USB_passthrough",
    ):
        require(hardware.get(flag) is False, f"blueprint: {flag} enabled")
    require(hardware.get("machine_type") is None, "blueprint: machine type guessed")
    isolation = blueprint.get("isolation", {})
    require(isolation.get("runtime_network") == "none", "blueprint: runtime network exists")
    for key in ("host_filesystem_shares",):
        require(isolation.get(key) == "none", f"blueprint: {key} exists")
    for key in ("clipboard", "drag_and_drop", "host_USB", "GPU_passthrough"):
        require(isolation.get(key) == "off", f"blueprint: {key} enabled")
    for key in (
        "credential_transfer",
        "production_audit_mount",
        "production_knowledge_mount",
        "TUI_hypervisor_access",
        "model_hypervisor_access",
    ):
        require(isolation.get(key) == "prohibited", f"blueprint: {key} allowed")
    storage = blueprint.get("storage_lifecycle", {})
    require(
        storage.get("golden_base") == "powered_off_clean_read_only",
        "blueprint: golden base unsafe",
    )
    require(
        storage.get("scenario_storage") == "one_fresh_external_overlay_per_run",
        "blueprint: overlay policy unsafe",
    )
    require(
        storage.get("crash_consistent_snapshot_accepted_as_clean") is False,
        "blueprint: crash snapshot accepted",
    )
    control = blueprint.get("control_and_evidence", {})
    for flag in (
        "arbitrary_shell_from_model",
        "arbitrary_domain_definition",
        "arbitrary_image_reference",
        "automatic_retry",
        "private_chain_of_thought_persisted",
    ):
        require(control.get(flag) is False, f"blueprint: {flag} enabled")
    require(control.get("attempt_limit") == 1, "blueprint: attempt limit drift")
    require(
        control.get("registered_operation_only") is True
        and control.get("registered_scenario_only") is True,
        "blueprint: unregistered control allowed",
    )
    require(
        len(blueprint.get("known_physical_limits", [])) >= 4,
        "blueprint: physical limitations incomplete",
    )
    require(
        blueprint.get("next_gate") == "L2_virtualization_readiness_observation_not_authorized",
        "blueprint: next gate unexpectedly authorized",
    )


def validate_readiness(readiness: dict[str, Any], sources: dict[str, Any]) -> None:
    require(readiness.get("status") == "prepared_unapproved", "readiness: bad status")
    require(
        readiness.get("implementation_status") == "fixture_validated_parsers_only",
        "readiness: fixture parser status drift",
    )
    for flag in (
        "execution_enabled",
        "approval_granted",
        "host_scan_performed",
        "live_observation_backend_complete",
    ):
        require(readiness.get(flag) is False, f"readiness: {flag} must be false")
    require(
        readiness.get("fixture_adapter_registry_complete") is True,
        "readiness: fixture adapters incomplete",
    )
    authority = readiness.get("authority", {})
    require(authority.get("risk_tier") == 1, "readiness: wrong risk tier")
    for flag in (
        "privilege",
        "network",
        "mutation",
        "device_wake",
        "automatic_retry",
        "raw_output_persistence",
    ):
        require(authority.get(flag) is False, f"readiness: {flag} enabled")
    require(authority.get("attempt_limit_per_probe") == 1, "readiness: retries allowed")
    checks = readiness.get("checks")
    require(
        isinstance(checks, list) and len(checks) == 18,
        "readiness: expected 18 exact checks",
    )
    check_ids = [item.get("id") for item in checks]
    require(len(check_ids) == len(set(check_ids)), "readiness: duplicate checks")
    source_index = {item["id"]: item for item in sources.get("sources", [])}
    for check in checks:
        require(
            isinstance(check.get("fixture_adapter_id"), str) and check.get("fixture_adapter_id"),
            f"{check.get('id')}: fixture adapter missing",
        )
        require(
            check.get("live_backend_implemented") is False,
            f"{check.get('id')}: live backend falsely implemented",
        )
        source = source_index.get(check.get("source_id"))
        require(source is not None, f"{check.get('id')}: unknown source")
        require(
            source.get("network") is False and source.get("mutation") is False,
            f"{check.get('id')}: unsafe source",
        )
        require(
            source.get("potential_effect") in {"none", "none_expected"},
            f"{check.get('id')}: effectful source",
        )
    exclusions = " ".join(readiness.get("explicit_exclusions", [])).lower()
    for required in (
        "credentials",
        "network connectivity",
        "package repository",
        "service starts",
        "module loading",
        "permission changes",
        "performance benchmarks",
    ):
        require(required in exclusions, f"readiness: missing exclusion {required}")
    require(
        readiness.get("next_decision")
        == "fresh_user_authorization_required_before_any_live_readiness_backend_or_host_observation",
        "readiness: gate broadened",
    )


def validate_gates(gates: dict[str, Any]) -> None:
    require(gates.get("status") == "prepared_not_started", "gates: already started")
    require(gates.get("execution_enabled") is False, "gates: execution enabled")
    expected = [
        "P0_L2_adapter_implementation",
        "P1_virtualization_readiness_observation",
        "P2_host_virtualization_changes_if_needed",
        "P3_official_image_resolution_and_lock",
        "P4_domain_lock_and_storage_allocation",
        "P5_full_workstation_installation",
        "P6_baseline_attestation",
        "P7_scenario_overlays",
    ]
    items = gates.get("gates")
    require(
        isinstance(items, list) and [item.get("id") for item in items] == expected,
        "gates: order or identity drift",
    )
    require(gates.get("current_gate") == expected[1], "gates: current gate drift")
    require(items[0].get("current_status") == "completed", "gates: P0 not completed")
    require(
        items[1].get("current_status") == "next_blocked_on_user_authorization",
        "gates: P1 boundary drift",
    )
    require(
        all(item.get("current_status") == "blocked" for item in items[2:]),
        "gates: downstream gate unblocked",
    )
    require(
        items[0].get("state_change") is False and items[1].get("state_change") is False,
        "gates: observation phase marked mutating",
    )
    require(
        all(item.get("state_change") is True for item in items[2:]),
        "gates: mutating phase mislabeled",
    )
    require(
        items[1].get("authority") == "fresh_group_confirmation",
        "gates: readiness lacks fresh confirmation",
    )
    require(
        items[2].get("authority") == "per_command_approval",
        "gates: host changes lack per-command approval",
    )
    require(
        all(item.get("user_action_if_reached") for item in items),
        "gates: missing user checkpoints",
    )


def validate_policies(
    lab_policy: dict[str, Any],
    controller_policy: dict[str, Any],
    image_lock: dict[str, Any],
) -> None:
    for flag, value in lab_policy.get("authority", {}).items():
        require(value is False, f"lab policy: {flag} enabled")
    if controller_policy.get("implementation_status") == "h1_tier0_enabled":
        require(
            controller_policy.get("host_observation_enabled") is True,
            "controller policy: H1 observation is disabled",
        )
        require(
            controller_policy.get("transport") == "unix-user-private",
            "controller policy: H1 transport is not private",
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
                controller_policy.get(flag) is False,
                f"controller policy: unsafe capability {flag} enabled",
            )
        require(
            controller_policy.get("mutation_enabled", False) is False,
            "controller policy: unsafe capability mutation_enabled enabled",
        )
    else:
        for flag in (
            "operational_authority",
            "execution_enabled",
            "host_observation_enabled",
            "virtualization_enabled",
            "network_enabled",
            "privilege_enabled",
            "device_access_enabled",
        ):
            require(
                controller_policy.get(flag) is False,
                f"controller policy: {flag} enabled",
            )
    require(image_lock.get("status") == "unresolved", "image lock: unexpectedly resolved")
    require(
        image_lock.get("acquisition_enabled") is False,
        "image lock: acquisition enabled",
    )
    require(
        image_lock.get("baseline", {}).get("state") == "not_created",
        "image lock: baseline exists",
    )


def validate_all(root: Path = LAB_ROOT) -> dict[str, Any]:
    assets = {name: load(relative, root) for name, relative in FILES.items()}
    for name in ("blueprint", "gates", "readiness"):
        reject_executable_fields(name, assets[name])
    validate_blueprint(assets["blueprint"], assets["image_lock"])
    validate_readiness(assets["readiness"], assets["sources"])
    validate_gates(assets["gates"])
    validate_policies(assets["lab_policy"], assets["controller_policy"], assets["image_lock"])
    return {
        "status": "valid",
        "execution_performed": False,
        "host_observed": False,
        "vm_exists": False,
        "boot_profiles": 2,
        "readiness_checks": len(assets["readiness"]["checks"]),
        "provisioning_gates": len(assets["gates"]["gates"]),
        "next_gate": assets["gates"]["current_gate"],
    }


def main() -> int:
    try:
        report = validate_all()
    except BlueprintError as exc:
        print(f"VM blueprint rejected: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
