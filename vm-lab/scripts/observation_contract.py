#!/usr/bin/env python3
"""Validate and simulate fixture-only Fedora Tier-0 observation parsers.

This module deliberately has no live collection backend. It reads only fixture
files registered inside this bundle and emits ephemeral synthetic candidate
facts to stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "registry": "observation/adapter-registry.json",
    "policy": "observation/broker-policy.json",
    "sources": "enrollment/source-catalog.json",
    "proposal": "enrollment/fedora-workstation-proposal.json",
    "request": "fixtures/observation-request.json",
    "response": "fixtures/observation-response.json",
}
EXPECTED_REQUEST_KEYS = {
    "schema_version",
    "request_id",
    "mode",
    "execution_enabled",
    "host_observation_requested",
    "fixture_set_id",
    "adapters",
    "attempt",
    "parameters",
    "expires_at",
    "bindings",
}
EXPECTED_BINDING_KEYS = {
    "adapter_registry_sha256",
    "broker_policy_sha256",
    "source_catalog_sha256",
    "proposal_sha256",
}
SAFE_ARCHITECTURES = {"x86_64", "aarch64"}
SAFE_KERNEL_RELEASE = re.compile(r"^[A-Za-z0-9._+~-]{1,160}$")
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9._+:-]{1,160}$")
SAFE_OS_UNQUOTED = re.compile(r"^[A-Za-z0-9._+:/()~-]+$")
HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class ObservationError(ValueError):
    """Raised when the fixture-only contract must fail closed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ObservationError(message)


def load_json(relative: str, root: Path = LAB_ROOT) -> Any:
    try:
        return json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ObservationError(f"{relative}: {exc}") from exc


def digest(relative: str, root: Path = LAB_ROOT) -> str:
    try:
        return hashlib.sha256((root / relative).read_bytes()).hexdigest()
    except OSError as exc:
        raise ObservationError(f"{relative}: {exc}") from exc


def reject_terminal_controls(text: str, label: str) -> None:
    for character in text:
        codepoint = ord(character)
        if codepoint == 27 or codepoint == 127 or (codepoint < 32 and character not in "\n\t"):
            raise ObservationError(f"{label}: terminal control character rejected")


def safe_text(text: Any, label: str, maximum: int = 512) -> str:
    require(isinstance(text, str), f"{label}: expected text")
    require(0 < len(text) <= maximum, f"{label}: invalid length")
    reject_terminal_controls(text, label)
    require("$(" not in text and "`" not in text, f"{label}: active shell syntax rejected")
    return text


def exact_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label}: expected object")
    require(set(value) == keys, f"{label}: unexpected or missing fields")
    return value


def _decode_os_release_value(raw: str, label: str) -> str:
    value = raw.strip()
    require(value != "", f"{label}: empty value")
    if value[0] in {'"', "'"}:
        quote = value[0]
        require(len(value) >= 2 and value[-1] == quote, f"{label}: unterminated quote")
        body = value[1:-1]
        if quote == "'":
            require("'" not in body, f"{label}: embedded single quote")
            decoded = body
        else:
            decoded_chars: list[str] = []
            index = 0
            while index < len(body):
                character = body[index]
                if character != "\\":
                    decoded_chars.append(character)
                    index += 1
                    continue
                require(index + 1 < len(body), f"{label}: trailing escape")
                escaped = body[index + 1]
                require(escaped in {'"', "\\", "$", "`"}, f"{label}: unsupported escape")
                decoded_chars.append(escaped)
                index += 2
            decoded = "".join(decoded_chars)
    else:
        require(
            SAFE_OS_UNQUOTED.fullmatch(value) is not None,
            f"{label}: unsafe unquoted value",
        )
        decoded = value
    # Optional os-release keys are commonly present with an empty quoted
    # value (for example VERSION_CODENAME on Fedora). Preserve that empty
    # value; required identity keys are checked by parse_os_release below.
    return "" if decoded == "" else safe_text(decoded, label)


def parse_os_release(payloads: dict[str, str]) -> dict[str, Any]:
    text = payloads["os_release"]
    values: dict[str, str] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        require("=" in stripped, f"os-release:{line_number}: missing assignment")
        key, raw_value = stripped.split("=", 1)
        require(
            re.fullmatch(r"[A-Z0-9_]+", key) is not None,
            f"os-release:{line_number}: invalid key",
        )
        require(key not in values, f"os-release:{line_number}: duplicate key {key}")
        values[key] = _decode_os_release_value(raw_value, f"os-release:{key}")
    required = {"ID", "VERSION_ID", "VARIANT_ID", "PRETTY_NAME"}
    require(required.issubset(values), "os-release: required fields missing")
    require(values["ID"] == "fedora", "os-release: fixture is not Fedora")
    return {
        "os.id": values["ID"],
        "os.version_id": values["VERSION_ID"],
        "os.variant_id": values["VARIANT_ID"],
        "os.pretty_name": values["PRETTY_NAME"],
    }


def parse_kernel_identity(payloads: dict[str, str]) -> dict[str, Any]:
    try:
        data = json.loads(payloads["kernel_identity"])
    except json.JSONDecodeError as exc:
        raise ObservationError(f"kernel-identity: {exc}") from exc
    exact_object(data, {"release", "machine"}, "kernel-identity")
    release = safe_text(data["release"], "kernel.release", 160)
    machine = safe_text(data["machine"], "kernel.machine", 32)
    require(
        SAFE_KERNEL_RELEASE.fullmatch(release) is not None,
        "kernel.release: invalid syntax",
    )
    require(machine in SAFE_ARCHITECTURES, "kernel.machine: unsupported architecture")
    return {"kernel.release": release, "system.architecture": machine}


def _parse_cpu_blocks(text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    for block_number, raw_block in enumerate(re.split(r"\n\s*\n", text.strip()), start=1):
        fields: dict[str, str] = {}
        for line in raw_block.splitlines():
            require(":" in line, f"cpuinfo:{block_number}: malformed line")
            key, value = (part.strip() for part in line.split(":", 1))
            require(
                key and key not in fields,
                f"cpuinfo:{block_number}: duplicate or empty key",
            )
            # The flags field is a bounded, variable-width kernel interface;
            # modern CPUs can expose more than 512 characters while the
            # parser only derives a small capability classification from it.
            field_limit = 4096 if key == "flags" else 512
            # Several legitimate kernel cpuinfo fields (for example
            # ``power management`` on this host) are present but empty. They
            # are not used for identity or capability classification, so keep
            # them bounded without rejecting the whole host record. Required
            # fields are validated below and must remain non-empty.
            fields[key] = (
                safe_text(value, f"cpuinfo:{block_number}:{key}", field_limit) if value else ""
            )
        required = {"processor", "vendor_id", "model name", "flags"}
        require(
            required.issubset(fields),
            f"cpuinfo:{block_number}: required fields missing",
        )
        require(fields["processor"].isdigit(), f"cpuinfo:{block_number}: bad processor id")
        blocks.append(fields)
    require(blocks, "cpuinfo: no processor blocks")
    processors = [int(block["processor"]) for block in blocks]
    require(len(processors) == len(set(processors)), "cpuinfo: duplicate processor id")
    return blocks


def parse_cpu_summary(payloads: dict[str, str]) -> dict[str, Any]:
    blocks = _parse_cpu_blocks(payloads["cpu_info"])
    try:
        topology = json.loads(payloads["cpu_topology"])
    except json.JSONDecodeError as exc:
        raise ObservationError(f"cpu-topology: {exc}") from exc
    exact_object(
        topology,
        {"architecture", "physical_core_count", "logical_thread_count"},
        "cpu-topology",
    )
    architecture = safe_text(topology["architecture"], "cpu.architecture", 32)
    require(architecture in SAFE_ARCHITECTURES, "cpu-topology: unsupported architecture")
    physical = topology["physical_core_count"]
    logical = topology["logical_thread_count"]
    require(type(physical) is int and physical > 0, "cpu-topology: bad physical core count")
    require(
        type(logical) is int and logical == len(blocks),
        "cpu-topology: logical count mismatch",
    )
    require(physical <= logical, "cpu-topology: physical count exceeds logical count")
    vendors = {block["vendor_id"] for block in blocks}
    models = {block["model name"] for block in blocks}
    require(
        len(vendors) == 1 and len(models) == 1,
        "cpuinfo: inconsistent processor identity",
    )
    vendor = safe_text(next(iter(vendors)), "cpu.vendor", 64)
    model = safe_text(next(iter(models)), "cpu.model_family", 160)
    require(SAFE_IDENTIFIER.fullmatch(vendor) is not None, "cpu.vendor: invalid syntax")
    flag_sets = [set(block["flags"].split()) for block in blocks]
    has_vmx = all("vmx" in flags for flags in flag_sets)
    has_svm = all("svm" in flags for flags in flag_sets)
    require(not (has_vmx and has_svm), "cpuinfo: contradictory virtualization extensions")
    extension_class = "intel_vt" if has_vmx else "amd_v" if has_svm else "none_reported"
    return {
        "cpu.architecture": architecture,
        "cpu.vendor": vendor,
        "cpu.model_family": model,
        "cpu.physical_core_count": physical,
        "cpu.logical_thread_count": logical,
        "cpu.virtualization_extension_class": extension_class,
    }


def parse_memory_summary(payloads: dict[str, str]) -> dict[str, Any]:
    fields: dict[str, int] = {}
    for line_number, line in enumerate(payloads["memory_info"].splitlines(), start=1):
        match = re.fullmatch(r"([A-Za-z0-9_()]+):\s+([0-9]+)(?:\s+(kB))?", line.strip())
        require(match is not None, f"meminfo:{line_number}: malformed field")
        key, amount, unit = match.groups()
        # HugePages_* are kernel page counters and intentionally omit a kB
        # unit; byte-valued memory fields must retain the kB unit.
        require(
            unit == "kB" or key.startswith("HugePages_"),
            f"meminfo:{line_number}: missing kB unit",
        )
        require(key not in fields, f"meminfo:{line_number}: duplicate key {key}")
        fields[key] = int(amount)
    require(
        "MemTotal" in fields and fields["MemTotal"] > 0,
        "meminfo: valid MemTotal missing",
    )
    try:
        topology = json.loads(payloads["numa_topology"])
    except json.JSONDecodeError as exc:
        raise ObservationError(f"numa-topology: {exc}") from exc
    exact_object(topology, {"node_count"}, "numa-topology")
    node_count = topology["node_count"]
    require(type(node_count) is int and node_count > 0, "numa-topology: bad node count")
    return {
        "memory.total_bytes": fields["MemTotal"] * 1024,
        "memory.numa_node_count": node_count,
    }


PARSERS: dict[str, Callable[[dict[str, str]], dict[str, Any]]] = {
    "os_release_v1": parse_os_release,
    "kernel_identity_v1": parse_kernel_identity,
    "cpu_summary_v1": parse_cpu_summary,
    "memory_summary_v1": parse_memory_summary,
}


def validate_contract(root: Path = LAB_ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = load_json(FILES["registry"], root)
    policy = load_json(FILES["policy"], root)
    sources = load_json(FILES["sources"], root)
    proposal = load_json(FILES["proposal"], root)
    require(
        set(registry).issubset(
            {
                "schema_version",
                "version",
                "registry_id",
                "implementation_status",
                "execution_enabled",
                "host_observation_enabled",
                "invariants",
                "source_catalog_binding",
                "proposal_binding",
                "fixture_sets",
                "adapters",
            }
        ),
        "registry: undeclared authority field",
    )
    require(
        registry.get("implementation_status")
        in {"fixture_validated_parsers_only", "tier0_live_read_enabled"},
        "registry: bad status",
    )
    require(registry.get("execution_enabled") is False, "registry: execution enabled")
    if registry.get("implementation_status") == "tier0_live_read_enabled":
        require(
            registry.get("host_observation_enabled") is True,
            "registry: live Tier-0 host observation is disabled",
        )
    else:
        require(
            registry.get("host_observation_enabled") is False,
            "registry: fixture host observation enabled",
        )
    require(
        registry.get("source_catalog_binding", {}).get("sha256") == digest(FILES["sources"], root),
        "registry: source catalog digest drift",
    )
    require(
        registry.get("proposal_binding", {}).get("sha256") == digest(FILES["proposal"], root),
        "registry: proposal digest drift",
    )
    require(
        registry.get("source_catalog_binding", {}).get("catalog_id") == sources.get("catalog_id"),
        "registry: source catalog identity drift",
    )
    require(
        registry.get("source_catalog_binding", {}).get("version") == sources.get("version"),
        "registry: source catalog version drift",
    )
    require(
        registry.get("proposal_binding", {}).get("proposal_id") == proposal.get("proposal_id"),
        "registry: proposal identity drift",
    )
    require(
        registry.get("proposal_binding", {}).get("version") == proposal.get("version"),
        "registry: proposal version drift",
    )
    invariants = registry.get("invariants", {})
    require(invariants.get("attempt_limit") == 1, "registry: retry allowed")
    require(invariants.get("automatic_retry") is False, "registry: automatic retry enabled")
    for key in (
        "arbitrary_input_reference_allowed",
        "device_wake_allowed",
        "mutation_allowed",
        "network_allowed",
        "persistence_allowed",
        "privilege_allowed",
    ):
        require(invariants.get(key) is False, f"registry: unsafe invariant {key} enabled")
    for key in (
        "registered_fixture_set_only",
        "terminal_control_characters_rejected",
        "unexpected_output_stops",
    ):
        require(invariants.get(key) is True, f"registry: safety invariant {key} is absent")
    for flag in (
        "execution_enabled",
        "persistence_enabled",
        "network_enabled",
        "privilege_enabled",
        "mutation_enabled",
    ):
        require(policy.get(flag) is False, f"policy: {flag} must remain false")
    if policy.get("implementation_status") == "tier0_live_read_enabled":
        allowed_fields = {
            "schema_version",
            "version",
            "policy_id",
            "implementation_status",
            "transport",
            "service_process_exists",
            "execution_enabled",
            "persistence_enabled",
            "host_observation_enabled",
            "network_enabled",
            "privilege_enabled",
            "mutation_enabled",
            "device_access_enabled",
            "protected_read_enabled",
            "current_capabilities",
            "activation_gate",
            "request_invariants",
            "output_invariants",
            "authorization_ledger_persistence_enabled",
        }
        require(set(policy).issubset(allowed_fields), "policy: undeclared authority field")
        require(
            policy.get("current_capabilities")
            == [
                "validate_registered_adapters",
                "collect_bounded_tier0_host_facts",
                "emit_ephemeral_candidate_facts",
            ],
            "policy: capability scope drift",
        )
        require(
            set(policy.get("activation_gate", {}))
            == {
                "host_read_authority_granted",
                "live_collector_implemented",
                "new_security_review_required",
                "new_user_decision_required",
            },
            "policy: activation gate schema drift",
        )
        require(
            set(policy.get("request_invariants", {}))
            == {
                "arbitrary_input_reference_rejected",
                "attempt_limit",
                "automatic_retry",
                "expiry_required",
                "parameters_allowed",
                "proposal_digest_required",
                "registered_adapter_only",
                "registered_fixture_set_only",
                "registry_digest_required",
                "replay_rejected",
                "source_catalog_digest_required",
            },
            "policy: request invariant schema drift",
        )
        request_invariants = policy["request_invariants"]
        require(
            request_invariants
            == {
                "arbitrary_input_reference_rejected": True,
                "attempt_limit": 1,
                "automatic_retry": False,
                "expiry_required": True,
                "parameters_allowed": False,
                "proposal_digest_required": True,
                "registered_adapter_only": True,
                "registered_fixture_set_only": True,
                "registry_digest_required": True,
                "replay_rejected": True,
                "source_catalog_digest_required": True,
            },
            "policy: request invariant values drift",
        )
        require(
            set(policy.get("output_invariants", {}))
            == {
                "candidate_facts_only",
                "effect_occurred",
                "host_observed",
                "persistence_performed",
                "terminal_safe_text_only",
                "unexpected_output_is_failure",
            },
            "policy: output invariant schema drift",
        )
        require(
            policy["output_invariants"]
            == {
                "candidate_facts_only": False,
                "effect_occurred": True,
                "host_observed": True,
                "persistence_performed": False,
                "terminal_safe_text_only": True,
                "unexpected_output_is_failure": True,
            },
            "policy: output invariant values drift",
        )
        for key in ("device_access_enabled", "protected_read_enabled"):
            require(
                policy.get(key, False) is False,
                f"policy: unsafe capability {key} enabled",
            )
        require(
            policy.get("host_observation_enabled") is True,
            "policy: live Tier-0 observation is disabled",
        )
        require(
            policy.get("activation_gate", {}).get("host_read_authority_granted") is True,
            "policy: live host-read authority is absent",
        )
        require(
            policy.get("authorization_ledger_persistence_enabled") is True,
            "policy: authorization ledger persistence is not declared",
        )
        output = policy.get("output_invariants", {})
        require(
            output.get("host_observed") is True,
            "policy: live output does not declare host observation",
        )
        require(
            output.get("effect_occurred") is True,
            "policy: live output does not declare observation effect",
        )
        require(
            output.get("candidate_facts_only") is False,
            "policy: live output is incorrectly marked candidate-only",
        )
    else:
        require(
            policy.get("host_observation_enabled") is False,
            "policy: fixture host observation enabled",
        )
    require(policy.get("transport") == "none", "policy: transport exists")
    require(policy.get("service_process_exists") is False, "policy: service exists")
    source_index = {item["id"]: item for item in sources.get("sources", [])}
    proposal_fact_sources: dict[str, str] = {}
    for group in proposal.get("groups", []):
        for fact in group.get("facts", []):
            fact_id = fact.get("id")
            require(
                isinstance(fact_id, str) and fact_id not in proposal_fact_sources,
                "proposal: duplicate or invalid fact id",
            )
            proposal_fact_sources[fact_id] = fact.get("source_id")
    fixtures = registry.get("fixture_sets")
    require(isinstance(fixtures, list) and fixtures, "registry: fixture sets missing")
    fixture_ids: set[str] = set()
    for fixture_set in fixtures:
        fixture_id = fixture_set.get("id")
        require(
            isinstance(fixture_id, str) and fixture_id not in fixture_ids,
            "registry: duplicate fixture set",
        )
        fixture_ids.add(fixture_id)
        require(
            fixture_set.get("synthetic") is True and fixture_set.get("represents_host") is False,
            f"{fixture_id}: fixture identity unsafe",
        )
        files = fixture_set.get("files")
        require(isinstance(files, dict) and files, f"{fixture_id}: fixture files missing")
        for reference in files.values():
            require(
                isinstance(reference, str) and reference.startswith("fixtures/observations/"),
                f"{fixture_id}: fixture reference outside registry root",
            )
            resolved = (root / reference).resolve()
            allowed = (root / "fixtures/observations").resolve()
            require(
                resolved.is_relative_to(allowed),
                f"{fixture_id}: fixture reference escaped root",
            )
            require(resolved.is_file(), f"{fixture_id}: fixture missing")
    adapters = registry.get("adapters")
    require(
        isinstance(adapters, list) and len(adapters) == 4,
        "registry: expected four Tier-0 adapters",
    )
    adapter_ids: set[str] = set()
    for adapter in adapters:
        require(
            set(adapter).issubset(
                {
                    "id",
                    "version",
                    "implementation_status",
                    "maturity_level",
                    "execution_enabled",
                    "parser_id",
                    "source_id",
                    "source_interface",
                    "fixture_inputs",
                    "expected_fact_ids",
                    "bounds",
                    "risk",
                }
            ),
            "adapter: undeclared authority field",
        )
        adapter_id = adapter.get("id")
        require(
            isinstance(adapter_id, str) and adapter_id not in adapter_ids,
            "registry: duplicate adapter",
        )
        adapter_ids.add(adapter_id)
        require(adapter.get("version") == "1.0.0", f"{adapter_id}: version drift")
        require(
            adapter.get("maturity_level") == 1,
            f"{adapter_id}: maturity exceeds parser-only level",
        )
        require(
            adapter.get("execution_enabled") is False,
            f"{adapter_id}: execution enabled",
        )
        require(adapter.get("parser_id") in PARSERS, f"{adapter_id}: unknown parser")
        risk = adapter.get("risk", {})
        require(
            set(risk) == {"tier", "privilege", "network", "mutation", "device_wake"},
            f"{adapter_id}: risk schema drift",
        )
        require(
            set(adapter.get("bounds", {}))
            == {"attempt_limit", "max_input_bytes", "max_output_facts"},
            f"{adapter_id}: bounds schema drift",
        )
        require(risk.get("tier") == 0, f"{adapter_id}: not Tier-0")
        for risk_flag in ("privilege", "network", "mutation", "device_wake"):
            require(risk.get(risk_flag) is False, f"{adapter_id}: {risk_flag} enabled")
        require(
            adapter.get("bounds", {}).get("attempt_limit") == 1,
            f"{adapter_id}: retry allowed",
        )
        source = source_index.get(adapter.get("source_id"))
        require(source is not None, f"{adapter_id}: source missing")
        require(
            source.get("network") is False
            and source.get("mutation") is False
            and source.get("potential_effect") == "none",
            f"{adapter_id}: source is not Tier-0 safe",
        )
        require(
            source.get("interface") == adapter.get("source_interface"),
            f"{adapter_id}: source interface drift",
        )
        expected_facts = adapter.get("expected_fact_ids", [])
        require(
            expected_facts
            and all(
                proposal_fact_sources.get(fact_id) == adapter.get("source_id")
                for fact_id in expected_facts
            ),
            f"{adapter_id}: fact binding drift",
        )
    require(
        proposal.get("host_scan_performed") is False and proposal.get("execution_enabled") is False,
        "proposal: operational state detected",
    )
    return registry, policy


def _fixture_payloads(
    fixture_set: dict[str, Any], adapter: dict[str, Any], root: Path
) -> dict[str, str]:
    payloads: dict[str, str] = {}
    total_bytes = 0
    for input_id in adapter["fixture_inputs"]:
        require(input_id in fixture_set["files"], f"{adapter['id']}: fixture input missing")
        reference = fixture_set["files"][input_id]
        raw = (root / reference).read_bytes()
        total_bytes += len(raw)
        require(
            total_bytes <= adapter["bounds"]["max_input_bytes"],
            f"{adapter['id']}: input bound exceeded",
        )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ObservationError(f"{adapter['id']}: non-UTF-8 fixture") from exc
        reject_terminal_controls(text, f"{adapter['id']}:fixture")
        payloads[input_id] = text
    return payloads


def validate_request(
    request: Any,
    registry: dict[str, Any],
    policy: dict[str, Any],
    root: Path = LAB_ROOT,
) -> None:
    exact_object(request, EXPECTED_REQUEST_KEYS, "request")
    require(
        request["schema_version"] == 1 and request["mode"] == "fixture_simulation",
        "request: invalid protocol",
    )
    require(
        request["execution_enabled"] is False and request["host_observation_requested"] is False,
        "request: operational access requested",
    )
    require(request["attempt"] == 1, "request: only attempt one is permitted")
    require(request["parameters"] == {}, "request: parameters are forbidden")
    require(
        isinstance(request["expires_at"], str) and request["expires_at"].endswith("Z"),
        "request: invalid expiry",
    )
    bindings = exact_object(request["bindings"], EXPECTED_BINDING_KEYS, "request.bindings")
    for name, value in bindings.items():
        require(
            isinstance(value, str) and HEX_DIGEST.fullmatch(value) is not None,
            f"request.bindings.{name}: bad digest",
        )
    expected_bindings = {
        "adapter_registry_sha256": digest(FILES["registry"], root),
        "broker_policy_sha256": digest(FILES["policy"], root),
        "source_catalog_sha256": digest(FILES["sources"], root),
        "proposal_sha256": digest(FILES["proposal"], root),
    }
    require(bindings == expected_bindings, "request: identity binding drift")
    fixture_ids = {item["id"] for item in registry["fixture_sets"]}
    require(request["fixture_set_id"] in fixture_ids, "request: unknown fixture set")
    adapter_index = {item["id"]: item for item in registry["adapters"]}
    selections = request["adapters"]
    require(isinstance(selections, list) and selections, "request: adapters missing")
    selected_ids: set[str] = set()
    for selection in selections:
        exact_object(selection, {"id", "version"}, "request.adapter")
        adapter = adapter_index.get(selection["id"])
        require(adapter is not None, "request: unknown adapter")
        require(selection["id"] not in selected_ids, "request: duplicate adapter")
        selected_ids.add(selection["id"])
        require(selection["version"] == adapter["version"], "request: adapter version drift")
    require(
        policy.get("request_invariants", {}).get("attempt_limit") == 1,
        "policy: request limit drift",
    )


def simulate(
    request: dict[str, Any],
    registry: dict[str, Any],
    policy: dict[str, Any],
    root: Path = LAB_ROOT,
    seen_request_ids: set[str] | None = None,
) -> dict[str, Any]:
    validate_request(request, registry, policy, root)
    seen = seen_request_ids if seen_request_ids is not None else set()
    request_id = safe_text(request["request_id"], "request_id", 128)
    require(request_id not in seen, "request: replay rejected")
    seen.add(request_id)
    fixture_set = next(
        item for item in registry["fixture_sets"] if item["id"] == request["fixture_set_id"]
    )
    adapter_index = {item["id"]: item for item in registry["adapters"]}
    facts: list[dict[str, Any]] = []
    fact_ids: set[str] = set()
    for selection in request["adapters"]:
        adapter = adapter_index[selection["id"]]
        parsed = PARSERS[adapter["parser_id"]](_fixture_payloads(fixture_set, adapter, root))
        require(
            list(parsed) == adapter["expected_fact_ids"],
            f"{adapter['id']}: unexpected parser output",
        )
        require(
            len(parsed) <= adapter["bounds"]["max_output_facts"],
            f"{adapter['id']}: output bound exceeded",
        )
        for fact_id, value in parsed.items():
            require(fact_id not in fact_ids, f"{adapter['id']}: duplicate fact id")
            fact_ids.add(fact_id)
            if isinstance(value, str):
                safe_text(value, fact_id)
            facts.append(
                {
                    "fact_id": fact_id,
                    "value": value,
                    "source_id": adapter["source_id"],
                    "synthetic": True,
                }
            )
    return {
        "schema_version": 1,
        "request_id": request_id,
        "status": "fixture_simulated",
        "execution_performed": False,
        "host_observed": False,
        "effect_occurred": False,
        "persistence_performed": False,
        "fixture_set_id": fixture_set["id"],
        "attempts": 1,
        "candidate_facts": facts,
        "warnings": [
            "Synthetic fixture values are parser-test evidence only and do not describe the host."
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation", nargs="?", choices=("validate", "simulate"), default="validate"
    )
    args = parser.parse_args(argv)
    try:
        registry, policy = validate_contract()
        request = load_json(FILES["request"])
        response = simulate(request, registry, policy)
        expected = load_json(FILES["response"])
        require(response == expected, "fixture response drift")
    except ObservationError as exc:
        print(f"observation contract rejected: {exc}", file=sys.stderr)
        return 1
    if args.operation == "simulate":
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "status": "valid",
                    "execution_performed": False,
                    "host_observed": False,
                    "adapters": len(registry["adapters"]),
                    "candidate_facts": len(response["candidate_facts"]),
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
