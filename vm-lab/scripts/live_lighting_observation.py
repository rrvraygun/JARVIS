#!/usr/bin/env python3
"""One-use, passive lighting observation bound to the owner-only Jarvisd service."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import activation_authority as authority
import lighting_observation as observer
import observation_contract as contract
from restricted_fact_store import fact_scope_digest, load_approved_scope


class LiveLightingObservationError(ValueError):
    """Raised when the lighting observer must fail closed."""


ADAPTER_ID = "fedora.lighting.passive-readonly"
ADAPTER_VERSION = "1.0.0"
GROUPS = ("graphics-display-input",)
SCOPE_PATH = "enrollment/lighting-approved-fact-scope.json"
POLICY_PATH = "controller/lighting-observation-policy.json"
REGISTRY_PATH = "controller/lighting-observation-registry.json"
OPERATION_PATH = "controller/lighting-observation-operation.json"
CONTRACT_FILES = (
    "scripts/lighting_observation.py",
    "scripts/live_lighting_observation.py",
    "scripts/jarvisd_service.py",
    "scripts/activation_authority.py",
    "scripts/observation_contract.py",
    "scripts/restricted_fact_store.py",
    POLICY_PATH,
    REGISTRY_PATH,
    OPERATION_PATH,
    SCOPE_PATH,
)


def _deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise LiveLightingObservationError("lighting observation deadline exceeded")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LiveLightingObservationError("lighting binding is unavailable") from exc
    if not isinstance(value, dict):
        raise LiveLightingObservationError("lighting binding is not an object")
    return value


def runtime_contract_digest(root: Path) -> str:
    """Hash every promoted implementation and binding artifact canonically."""
    parts: dict[str, str] = {}
    try:
        for relative in CONTRACT_FILES:
            parts[relative] = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    except OSError as exc:
        raise LiveLightingObservationError("lighting runtime contract is unavailable") from exc
    canonical = json.dumps(parts, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()


def _validate_policy(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = _load_json(root / POLICY_PATH)
    required = {
        "schema_version": 1,
        "policy_id": "lighting-passive-readonly-v1",
        "status": "enabled_for_one_use_promotion",
        "host_observation_enabled": True,
        "execution_enabled": True,
        "registered_adapter_only": True,
        "attempt_limit": 1,
        "automatic_retry": False,
        "output_limit_bytes": 32768,
        "network_enabled": False,
        "credentials_enabled": False,
        "protected_read_enabled": False,
        "device_wake_allowed": False,
        "mutation_enabled": False,
        "persistence_enabled": False,
        "connector_status_read": False,
        "terminal_control_rejection": True,
        "unexpected_output": "stop_and_report",
    }
    if policy != required:
        raise LiveLightingObservationError("lighting policy scope drift")
    registry = _load_json(root / REGISTRY_PATH)
    adapters = registry.get("adapters")
    if set(registry) != {
        "schema_version",
        "registry_id",
        "status",
        "host_observation_enabled",
        "execution_enabled",
        "adapters",
    }:
        raise LiveLightingObservationError("lighting registry fields drift")
    if not isinstance(adapters, list) or len(adapters) != 1:
        raise LiveLightingObservationError("lighting registry adapter count drift")
    expected_adapter_keys = {
        "id",
        "version",
        "operation_id",
        "source_ids",
        "expected_output",
        "device_wake",
        "mutation",
        "network",
        "credentials",
        "protected_reads",
        "attempt_limit",
        "output_limit_bytes",
    }
    if set(adapters[0]) != expected_adapter_keys:
        raise LiveLightingObservationError("lighting adapter registry fields drift")
    if (
        registry.get("schema_version") != 1
        or registry.get("registry_id") != "fedora-lighting-passive-readonly"
        or registry.get("status") != "enabled_for_one_use_promotion"
        or registry.get("host_observation_enabled") is not True
        or registry.get("execution_enabled") is not True
        or adapters[0].get("id") != ADAPTER_ID
        or adapters[0].get("version") != ADAPTER_VERSION
        or adapters[0].get("operation_id") != "jarvis.lighting.observe"
        or adapters[0].get("device_wake") is not False
        or adapters[0].get("mutation") is not False
        or adapters[0].get("network") is not False
        or adapters[0].get("credentials") is not False
        or adapters[0].get("protected_reads") is not False
        or adapters[0].get("attempt_limit") != 1
        or adapters[0].get("output_limit_bytes") != 32768
        or adapters[0].get("source_ids")
        != ["graphics.backlight", "input.keyboard-led", "graphics.drm-topology"]
        or adapters[0].get("expected_output") != "ephemeral_lighting_observation"
    ):
        raise LiveLightingObservationError("lighting adapter registry scope drift")
    return policy, adapters[0]


def _validate_operation(root: Path) -> None:
    operation = _load_json(root / OPERATION_PATH)
    expected = {
        "schema_version": 1,
        "operation_id": "jarvis.lighting.observe",
        "operation_revision": "1.0.0",
        "status": "registered_one_use_readonly",
        "execution_enabled": True,
        "registered": True,
        "sources": [
            "/sys/class/backlight",
            "/sys/class/leds/kbd_backlight",
            "/sys/class/drm",
        ],
        "network": False,
        "credentials": False,
        "protected_reads": False,
        "device_wake": False,
        "attempt_limit": 1,
        "automatic_retry": False,
        "output_limit_bytes": 32768,
        "unexpected_output": "stop_and_report",
        "independent_review_required": True,
        "deployment_required": True,
        "authorization_scope": f"vm-lab/{SCOPE_PATH}",
        "policy": f"vm-lab/{POLICY_PATH}",
        "registry": f"vm-lab/{REGISTRY_PATH}",
    }
    if operation != expected:
        raise LiveLightingObservationError("lighting operation contract drift")


def _scope(root: Path):
    document = _load_json(root / SCOPE_PATH)
    if set(document) != {
        "schema_version",
        "scope_id",
        "status",
        "proposal_digest",
        "source_catalog_digest",
        "groups",
        "entries",
    }:
        raise LiveLightingObservationError("lighting scope fields drift")
    if (
        document.get("schema_version") != 1
        or document.get("scope_id") != "lighting-passive-readonly-v1"
        or document.get("status") != "approved_for_one_use_promotion"
        or document.get("groups") != ["graphics-display-input"]
    ):
        raise LiveLightingObservationError("lighting scope identity drift")
    expected_entries = [
        {
            "adapter_id": ADAPTER_ID,
            "adapter_version": ADAPTER_VERSION,
            "source_id": "graphics.backlight",
            "fact_ids": [
                "backlight.providers",
                "backlight.requested_actual_relationship",
            ],
        },
        {
            "adapter_id": ADAPTER_ID,
            "adapter_version": ADAPTER_VERSION,
            "source_id": "input.keyboard-led",
            "fact_ids": ["keyboard_light.providers", "keyboard_light.ranges"],
        },
        {
            "adapter_id": ADAPTER_ID,
            "adapter_version": ADAPTER_VERSION,
            "source_id": "graphics.drm-topology",
            "fact_ids": ["gpu.adapters"],
        },
    ]
    if document.get("entries") != expected_entries:
        raise LiveLightingObservationError("lighting scope membership drift")
    scope = load_approved_scope(root / SCOPE_PATH)
    if scope.proposal_digest != contract.digest(contract.FILES["proposal"], root):
        raise LiveLightingObservationError("lighting proposal binding drift")
    if scope.source_catalog_digest != contract.digest(contract.FILES["sources"], root):
        raise LiveLightingObservationError("lighting catalog binding drift")
    return scope


def collect_lighting(
    ledger: authority.ActivationAuthorityLedger,
    authorization_id: str,
    *,
    expected_authorization: authority.UserAuthorization,
    project_root: Path = contract.LAB_ROOT,
    include_graphics: bool = True,
    host_root: Path = Path("/"),
    deadline: float | None = None,
) -> dict[str, Any]:
    """Collect one ephemeral passive observation, then consume its approval."""
    _deadline(deadline)
    if expected_authorization.authorization_id != authorization_id:
        raise LiveLightingObservationError("lighting authorization identity mismatch")
    try:
        authority.validate_authorization(expected_authorization)
    except authority.AuthorizationError as exc:
        raise LiveLightingObservationError("lighting authorization is invalid") from exc
    _validate_operation(project_root)
    _validate_policy(project_root)
    scope = _scope(project_root)
    expected_facts = tuple(
        sorted({fact_id for entry in scope.entries for fact_id in entry.fact_ids})
    )
    if expected_authorization.attestation_digest != runtime_contract_digest(project_root):
        raise LiveLightingObservationError("lighting runtime contract binding drift")
    if expected_authorization.proposal_digest != scope.proposal_digest:
        raise LiveLightingObservationError("lighting authorization proposal binding drift")
    if expected_authorization.source_catalog_digest != scope.source_catalog_digest:
        raise LiveLightingObservationError("lighting authorization catalog binding drift")
    if expected_authorization.scope_digest != fact_scope_digest(scope):
        raise LiveLightingObservationError("lighting authorization scope binding drift")
    if expected_authorization.approved_group_ids != GROUPS:
        raise LiveLightingObservationError("lighting authorization group scope drift")
    if expected_authorization.approved_fact_ids != expected_facts:
        raise LiveLightingObservationError("lighting authorization fact scope drift")
    try:
        ledger.begin_attempt(authorization_id, expected=expected_authorization)
    except authority.AuthorizationError as exc:
        raise LiveLightingObservationError("lighting authorization attempt unavailable") from exc
    if type(include_graphics) is not bool:
        raise LiveLightingObservationError("include_graphics must be boolean")
    _deadline(deadline)
    try:
        observation = observer.collect_passive(
            root=host_root,
            include_graphics=include_graphics,
            allow_device_wake=False,
            observed_at=dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        )
    except observer.LightingObservationError as exc:
        raise LiveLightingObservationError("lighting observation failed closed") from exc
    _deadline(deadline)
    if (
        len(json.dumps(observation, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))
        > 32768
    ):
        raise LiveLightingObservationError("lighting observation exceeds bound")
    try:
        ledger.consume(authorization_id, expected=expected_authorization)
    except authority.AuthorizationError as exc:
        raise LiveLightingObservationError(
            "lighting authorization consumption failed closed"
        ) from exc
    return {
        "schema_version": 1,
        "status": "host_observed_lighting",
        "execution_performed": False,
        "effect_occurred": True,
        "host_effect_occurred": False,
        "persistence_performed": False,
        "fact_persistence_performed": False,
        "authorization_ledger_mutated": True,
        "authorization_id": authorization_id,
        "observation": observation,
    }


__all__ = [
    "ADAPTER_ID",
    "ADAPTER_VERSION",
    "LiveLightingObservationError",
    "collect_lighting",
]
