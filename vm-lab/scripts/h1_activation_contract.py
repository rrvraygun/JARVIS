#!/usr/bin/env python3
"""Validate the prepared H1 service, transport, and policy promotion packet.

This is a contract validator only. It never starts a service, opens a socket,
changes policy, consumes authorization, or observes the host.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class H1ContractError(ValueError):
    pass


TRUSTED_PROJECT_ROOT = "/home/tipexxx/Escritorio/Proyecto/codex-agent-system"
TRUSTED_USER_DECISION_PACKET_SHA256 = (
    "b603efb9b2a042d7e1249c0b098d73be27eb7b46df0b22c9cafe4f2f06d046c4"
)
TRUSTED_CONTROLLER_POLICY_SHA256 = (
    "4e124f94c06a18539ffe3303601c7426e9759cba3c6eb23236924551f5d3de6b"
)
TRUSTED_BROKER_POLICY_SHA256 = "1e672f5dfeae7df170dde358568721650dce3be3517d9a21365f09131175420a"
TRUSTED_CURRENT_CONTROLLER_POLICY_SHA256 = (
    "a3c04aaa57bb940feb16bb93d9ac48f419f66d92db9aac904289e15619f89f69"
)
TRUSTED_CURRENT_BROKER_POLICY_SHA256 = (
    "ea53b5c26fab84ced9e312dd4319a6c734c93d957d78530460b9ca6fc3575d81"
)
TRUSTED_SERVICE_IDENTITY_SHA256 = "d56b17862d3550b1ffab05f1c3430fe6b7660fbf145032705d57bb3e255f9211"
TRUSTED_SERVICE_SHA256 = "015023093b1d10256befeeb89a86d8fa92a565675d088a08648e8e7ee1173447"
TRUSTED_UNIT_SHA256 = "b7eadfff17f7ec49f98fc2584d6582e30e315c77568aa940ed712652db1b2a88"
TRUSTED_RUNTIME_DEPENDENCY_SHA256 = {
    "live_tier0_observation.py": "7c3e2db20443efd4ed0b26f01fbec521ebb691f71ff7ff290b59eea2908e7e17",
    "activation_authority.py": "502758133bdaea62a181c29a48de59aa4a06d50f4ce12da796f6473462b7670e",
    "observation_contract.py": "481dbf8c5f5b24e2aca0726b4a81999d94fb250c5f5572a98c2e4b98de9b5cf0",
    "restricted_fact_store.py": "635c8da0496ca33ecaab2bcc96d03280ba55e827174c94dba53310182eae4d7e",
    "live_lighting_observation.py": "28f41174b5bbd0499fd88e2f1cebc67f3b5a6bff3f3ed8ded2d2ce1fb288cd4c",
    "lighting_observation.py": "10cb3f7c5792cfacbc1308da76361d689197c10499b878b2feb18698b54ce230",
}


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise H1ContractError(f"invalid contract file: {path}") from exc
    if not isinstance(value, dict):
        raise H1ContractError(f"contract is not an object: {path}")
    return value


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise H1ContractError(f"cannot hash trusted artifact: {path}") from exc


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise H1ContractError(message)


def validate_policy(policy: dict[str, Any]) -> None:
    _require(
        set(policy)
        == {
            "schema_version",
            "policy_id",
            "version",
            "status",
            "transport",
            "service_process_exists",
            "operational_authority",
            "execution_enabled",
            "persistence_enabled",
            "host_observation_enabled",
            "network_enabled",
            "privilege_enabled",
            "mutation_enabled",
            "device_access_enabled",
            "protected_read_enabled",
            "device_wake_allowed",
            "allowed_adapters",
            "one_attempt",
            "automatic_retry",
            "requires_external_user_decision",
            "requires_fresh_independent_review",
        },
        "promotion policy fields drift",
    )
    _require(
        policy.get("status") == "prepared_unactivated",
        "promotion policy must remain prepared",
    )
    _require(
        policy.get("transport") == "unix-user-private",
        "promotion transport is not private user Unix",
    )
    _require(
        policy.get("service_process_exists") is False,
        "promotion service already exists",
    )
    _require(policy.get("operational_authority") is False, "operational authority is enabled")
    _require(policy.get("execution_enabled") is False, "execution is enabled")
    _require(policy.get("persistence_enabled") is False, "persistence is enabled")
    _require(
        policy.get("host_observation_enabled") is True,
        "promotion does not enable the reviewed Tier-0 collector",
    )
    for key in (
        "network_enabled",
        "privilege_enabled",
        "mutation_enabled",
        "device_access_enabled",
        "protected_read_enabled",
        "device_wake_allowed",
    ):
        _require(policy.get(key) is False, f"forbidden capability enabled: {key}")
    _require(
        policy.get("one_attempt") is True and policy.get("automatic_retry") is False,
        "attempt policy is unsafe",
    )
    _require(
        policy.get("requires_external_user_decision") is True,
        "user decision gate missing",
    )
    _require(
        policy.get("requires_fresh_independent_review") is True,
        "independent review gate missing",
    )
    expected = {
        "fedora.platform.os-release",
        "fedora.kernel.identity",
        "fedora.compute.cpu-summary",
        "fedora.compute.memory-summary",
    }
    _require(
        set(policy.get("allowed_adapters", [])) == expected,
        "adapter promotion scope drift",
    )


def validate_service_identity(identity: dict[str, Any]) -> None:
    _require(
        set(identity)
        == {
            "schema_version",
            "identity_id",
            "status",
            "service_manager",
            "unit_name",
            "user_binding",
            "root_required",
            "no_new_privileges",
            "capabilities",
            "private_network",
            "device_access",
            "protected_read_access",
            "write_paths",
            "authority_ledger_path",
            "allowed_read_interfaces",
            "arbitrary_command_execution",
            "shell_access",
        },
        "service identity fields drift",
    )
    _require(
        identity.get("status") == "prepared_uninstalled",
        "service identity is installed or active",
    )
    _require(identity.get("service_manager") == "systemd-user", "service is not user-scoped")
    _require(
        identity.get("user_binding") == "invoking-user-only",
        "service user binding is too broad",
    )
    _require(identity.get("root_required") is False, "service requires root")
    _require(identity.get("no_new_privileges") is True, "no-new-privileges missing")
    _require(identity.get("capabilities") == [], "service capabilities are not empty")
    _require(identity.get("private_network") is True, "service network is not private")
    _require(identity.get("device_access") is False, "service has device access")
    _require(identity.get("protected_read_access") is False, "service has protected reads")
    _require(identity.get("write_paths") == [], "service has write paths")
    _require(
        identity.get("authority_ledger_path") == "%S/jarvis/activation.sqlite3",
        "service authority-ledger path drift",
    )
    _require(
        identity.get("arbitrary_command_execution") is False,
        "service can execute arbitrary commands",
    )
    _require(identity.get("shell_access") is False, "service has shell access")
    _require(
        identity.get("allowed_read_interfaces")
        == [
            "/etc/os-release",
            "/proc/cpuinfo",
            "/proc/meminfo",
            "/proc/sys/kernel/osrelease",
            "/sys/devices/system/cpu/online",
            "/sys/devices/system/node/online",
            "/sys/class/backlight",
            "/sys/class/leds/kbd_backlight",
            "/sys/class/drm",
        ],
        "service read-interface scope drift",
    )


def validate_transport(transport: dict[str, Any]) -> None:
    _require(
        set(transport)
        == {
            "schema_version",
            "transport_id",
            "status",
            "kind",
            "socket_template",
            "socket_mode",
            "network_listener",
            "allowed_peer",
            "protocol_version",
            "max_frame_bytes",
            "request_timeout_ms",
            "automatic_retry",
            "arbitrary_method_dispatch",
            "allowed_methods",
        },
        "transport fields drift",
    )
    _require(transport.get("status") == "prepared_unbound", "transport is installed or bound")
    _require(
        transport.get("transport_id") == "jarvisd-private-unix-v1",
        "transport identity drift",
    )
    _require(transport.get("kind") == "unix-domain-jsonl", "transport is not Unix JSONL")
    _require(
        transport.get("socket_template") == "/run/user/%UID%/jarvis/jarvisd.sock",
        "transport socket location drift",
    )
    _require(
        transport.get("protocol_version") == "jarvis-control-v1",
        "transport protocol drift",
    )
    _require(transport.get("socket_mode") == "0600", "socket is not owner-only")
    _require(transport.get("network_listener") is False, "network listener is enabled")
    _require(
        transport.get("allowed_peer") == "same-user-uid-only",
        "transport peer scope is too broad",
    )
    _require(transport.get("max_frame_bytes") == 65536, "transport frame bound drift")
    _require(transport.get("request_timeout_ms") == 5000, "transport timeout drift")
    _require(transport.get("automatic_retry") is False, "transport retry enabled")
    _require(
        transport.get("arbitrary_method_dispatch") is False,
        "arbitrary method dispatch enabled",
    )
    _require(
        transport.get("allowed_methods")
        == [
            "health.read",
            "activation.status",
            "observation.prepare",
            "observation.stop",
            "lighting.observe",
        ],
        "transport method scope drift",
    )


def validate_user_decision(packet: dict[str, Any]) -> None:
    _require(
        packet.get("status") == "approved_pending_runtime_gate",
        "user decision is not the approved pending packet",
    )
    body = dict(packet)
    supplied = body.pop("decision_digest", None)
    expected = hashlib.sha256(
        json.dumps(
            body,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    _require(supplied == expected, "user decision digest mismatch")
    scope = packet.get("decision_scope", {})
    _require(
        scope.get("approved_groups") == ["compute-summary", "platform-identity"],
        "user decision group scope drift",
    )
    _require(
        scope.get("approved_mode") == "one-use-read-only-tier0",
        "user decision mode drift",
    )
    gate = packet.get("current_gate_state", {})
    _require(
        gate.get("controller_execution_enabled") is False,
        "user decision sees execution enabled",
    )
    _require(
        gate.get("controller_persistence_enabled") is False,
        "user decision sees persistence enabled",
    )
    _require(
        gate.get("controller_host_observation_enabled") is False,
        "user decision sees controller observation enabled",
    )
    _require(
        gate.get("broker_host_observation_enabled") is False,
        "user decision sees broker observation enabled",
    )
    _require(
        packet.get("activation", {}).get("status") == "not_consumed",
        "user decision already consumed",
    )


def validate_prepared_current_controller_policy(policy: dict[str, Any]) -> None:
    """Require the pre-promotion controller policy to remain disabled."""
    _require(
        policy.get("implementation_status") == "contract_only",
        "current controller is not contract-only",
    )
    _require(policy.get("transport") == "none", "current controller transport is enabled")
    for key in (
        "service_process_exists",
        "operational_authority",
        "execution_enabled",
        "persistence_enabled",
        "host_observation_enabled",
        "virtualization_enabled",
        "network_enabled",
        "privilege_enabled",
        "device_access_enabled",
    ):
        _require(policy.get(key) is False, f"current controller capability enabled: {key}")
    _require(
        policy.get("activation_gate", {}).get("current_activation_authorized") is False,
        "current controller activation is authorized",
    )


def validate_prepared_current_broker_policy(policy: dict[str, Any]) -> None:
    """Require the pre-promotion broker policy to remain fixture-only."""
    _require(
        policy.get("implementation_status") == "no_effect_simulator",
        "current broker is not fixture-only",
    )
    _require(policy.get("transport") == "none", "current broker transport is enabled")
    for key in (
        "service_process_exists",
        "execution_enabled",
        "host_observation_enabled",
        "persistence_enabled",
        "network_enabled",
        "privilege_enabled",
        "mutation_enabled",
    ):
        _require(policy.get(key) is False, f"current broker capability enabled: {key}")
    _require(
        policy.get("activation_gate", {}).get("host_read_authority_granted") is False,
        "current broker host-read authority is granted",
    )


def validate_current_controller_policy(policy: dict[str, Any]) -> None:
    """Validate the approved live Tier-0 controller state without mutation authority."""
    _require(
        policy.get("implementation_status") == "h1_tier0_enabled",
        "current controller is not H1 Tier-0",
    )
    _require(
        policy.get("transport") == "unix-user-private",
        "current controller transport is not private",
    )
    _require(
        policy.get("service_process_exists") is True,
        "current controller service is absent",
    )
    _require(
        policy.get("operational_authority") is True,
        "current controller read authority is absent",
    )
    _require(
        policy.get("host_observation_enabled") is True,
        "current controller observation is disabled",
    )
    for key in (
        "execution_enabled",
        "persistence_enabled",
        "virtualization_enabled",
        "network_enabled",
        "privilege_enabled",
        "device_access_enabled",
    ):
        _require(
            policy.get(key) is False,
            f"current controller unsafe capability enabled: {key}",
        )
    _require(
        policy.get("mutation_enabled", False) is False,
        "current controller unsafe capability enabled: mutation_enabled",
    )
    gate = policy.get("activation_gate", {})
    _require(
        gate.get("current_activation_authorized") is True,
        "current controller activation is not authorized",
    )
    _require(
        gate.get("private_local_transport_required") is True,
        "current controller transport gate is absent",
    )


def validate_current_broker_policy(policy: dict[str, Any]) -> None:
    """Validate the approved live Tier-0 broker state without mutation authority."""
    _require(
        policy.get("implementation_status") == "tier0_live_read_enabled",
        "current broker is not live Tier-0",
    )
    _require(policy.get("transport") == "none", "current broker has an unexpected transport")
    _require(
        policy.get("service_process_exists") is False,
        "current broker service process is unexpected",
    )
    _require(
        policy.get("host_observation_enabled") is True,
        "current broker observation is disabled",
    )
    for key in (
        "execution_enabled",
        "persistence_enabled",
        "network_enabled",
        "privilege_enabled",
        "mutation_enabled",
    ):
        _require(policy.get(key) is False, f"current broker unsafe capability enabled: {key}")
    gate = policy.get("activation_gate", {})
    _require(
        gate.get("host_read_authority_granted") is True,
        "current broker host-read authority is absent",
    )
    _require(
        gate.get("live_collector_implemented") is True,
        "current broker collector is not implemented",
    )
    _require(
        policy.get("authorization_ledger_persistence_enabled") is True,
        "current broker authorization ledger persistence is undeclared",
    )


def validate_prepared_promotion(root: Path) -> dict[str, Any]:
    _require(
        root.resolve().parent == Path(TRUSTED_PROJECT_ROOT),
        "promotion root is not the trusted checkout",
    )
    policy = _load(root / "controller" / "h1-promotion-policy.template.json")
    identity = _load(root / "controller" / "service-identity.template.json")
    transport = _load(root / "controller" / "private-transport.template.json")
    controller_policy_path = root / "controller" / "policy.json"
    broker_policy_path = root / "observation" / "broker-policy.json"
    decision_path = root.parent / "runtime" / "reports" / "2026-08-07-h1-user-decision-packet.json"
    decision = _load(decision_path)
    validate_policy(policy)
    validate_service_identity(identity)
    validate_transport(transport)
    validate_user_decision(decision)
    _require(
        _sha256(decision_path) == TRUSTED_USER_DECISION_PACKET_SHA256,
        "user decision packet artifact drift",
    )
    _require(
        _sha256(controller_policy_path) == TRUSTED_CONTROLLER_POLICY_SHA256,
        "controller policy artifact drift",
    )
    _require(
        _sha256(broker_policy_path) == TRUSTED_BROKER_POLICY_SHA256,
        "broker policy artifact drift",
    )
    _require(
        _sha256(root / "scripts" / "jarvisd_service.py") == TRUSTED_SERVICE_SHA256,
        "service executable artifact drift",
    )
    for filename, expected_digest in TRUSTED_RUNTIME_DEPENDENCY_SHA256.items():
        _require(
            _sha256(root / "scripts" / filename) == expected_digest,
            f"runtime dependency artifact drift: {filename}",
        )
    _require(
        _sha256(root / "controller" / "jarvisd.service.template") == TRUSTED_UNIT_SHA256,
        "service unit artifact drift",
    )
    _require(
        _sha256(root / "controller" / "service-identity.template.json")
        == TRUSTED_SERVICE_IDENTITY_SHA256,
        "service identity artifact drift",
    )
    validate_prepared_current_controller_policy(_load(controller_policy_path))
    validate_prepared_current_broker_policy(_load(broker_policy_path))
    return {"status": "valid_prepared_promotion", "host_activation_performed": False}


def validate_current_runtime(root: Path) -> dict[str, Any]:
    """Validate the already-approved active Tier-0 runtime artifacts."""
    controller_path = root / "controller" / "policy.json"
    broker_path = root / "observation" / "broker-policy.json"
    validate_current_controller_policy(_load(controller_path))
    validate_current_broker_policy(_load(broker_path))
    _require(
        _sha256(controller_path) == TRUSTED_CURRENT_CONTROLLER_POLICY_SHA256,
        "current controller policy artifact drift",
    )
    _require(
        _sha256(broker_path) == TRUSTED_CURRENT_BROKER_POLICY_SHA256,
        "current broker policy artifact drift",
    )
    _require(
        _sha256(root / "scripts" / "jarvisd_service.py") == TRUSTED_SERVICE_SHA256,
        "service executable artifact drift",
    )
    for filename, expected_digest in TRUSTED_RUNTIME_DEPENDENCY_SHA256.items():
        _require(
            _sha256(root / "scripts" / filename) == expected_digest,
            f"runtime dependency artifact drift: {filename}",
        )
    _require(
        _sha256(root / "controller" / "jarvisd.service.template") == TRUSTED_UNIT_SHA256,
        "service unit artifact drift",
    )
    return {"status": "valid_h1_runtime", "host_activation_performed": True}
