#!/usr/bin/env python3
"""Bounded unprivileged Tier-0 host observation, kept behind a disabled gate.

The production policy currently rejects this collector.  When a separately
reviewed policy revision enables it, the collector consumes one durable user
authorization and reads only the four registered platform/compute interfaces.
It never invokes a command, opens a device, uses the network, or persists
observed facts. Consuming the one-use authorization is an intentional durable
mutation and is reported explicitly in the result.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import stat
import time
from pathlib import Path
from typing import Any

import activation_authority as authority
import observation_contract as contract
from restricted_fact_store import (
    ApprovedFactScope,
    fact_scope_digest,
    load_approved_scope,
)


class LiveObservationError(ValueError):
    """Raised when live Tier-0 observation must fail closed."""


EXPECTED_GROUPS = ("compute-summary", "platform-identity")
MAX_BYTES = {
    "os_release": 16_384,
    "kernel_identity": 4_096,
    "cpu_info": 1_048_576,
    "cpu_topology": 4_096,
    "memory_info": 65_536,
    "numa_topology": 4_096,
}


def _check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise LiveObservationError("live observation deadline exceeded")


def _read(root: Path, relative: str, maximum: int, *, deadline: float | None = None) -> str:
    _check_deadline(deadline)
    path = root / relative
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as exc:
        # Fedora commonly exposes /etc/os-release as a symlink to the
        # canonical vendor file. Follow only that one fixed target, then open
        # the target itself with O_NOFOLLOW; arbitrary symlink traversal stays
        # rejected.
        if relative == "etc/os-release" and exc.errno == getattr(os, "ELOOP", 40):
            try:
                target = os.readlink(path)
            except OSError:
                target = ""
            if target not in {"/usr/lib/os-release", "../usr/lib/os-release"}:
                raise LiveObservationError(f"live source unavailable: {relative}") from exc
            try:
                descriptor = os.open(
                    root / "usr/lib/os-release",
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                )
            except OSError as target_exc:
                raise LiveObservationError(f"live source unavailable: {relative}") from target_exc
        else:
            raise LiveObservationError(f"live source unavailable: {relative}") from exc
    try:
        identity = os.fstat(descriptor)
        if not stat.S_ISREG(identity.st_mode):
            raise LiveObservationError(f"live source is not a regular file: {relative}")
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            _check_deadline(deadline)
            block = os.read(descriptor, min(65_536, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        raw = b"".join(chunks)
    except OSError as exc:
        raise LiveObservationError(f"live source read failed: {relative}") from exc
    finally:
        os.close(descriptor)
    if len(raw) > maximum:
        raise LiveObservationError(f"live source exceeds bound: {relative}")
    _check_deadline(deadline)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LiveObservationError(f"live source is not UTF-8: {relative}") from exc
    contract.reject_terminal_controls(text, relative)
    return text


def _range_count(value: str) -> int:
    total = 0
    for part in value.strip().split(","):
        if "-" in part:
            start, end = part.split("-", 1)
            if not start.isdigit() or not end.isdigit() or int(end) < int(start):
                raise LiveObservationError("invalid kernel topology range")
            total += int(end) - int(start) + 1
        elif part.strip().isdigit():
            total += 1
        else:
            raise LiveObservationError("invalid kernel topology range")
    if total <= 0:
        raise LiveObservationError("empty kernel topology range")
    return total


def _live_payloads(host_root: Path, *, deadline: float | None = None) -> dict[str, str]:
    cpu_info = _read(host_root, "proc/cpuinfo", MAX_BYTES["cpu_info"], deadline=deadline)
    blocks = contract._parse_cpu_blocks(cpu_info)
    physical_pairs = {
        (block.get("physical id"), block.get("core id"))
        for block in blocks
        if block.get("physical id") is not None and block.get("core id") is not None
    }
    physical_count = len(physical_pairs) or len(blocks)
    logical_count = len(blocks)
    architecture = os.uname().machine
    release = _read(host_root, "proc/sys/kernel/osrelease", 256, deadline=deadline).strip()
    if not architecture or not release:
        raise LiveObservationError("kernel identity is incomplete")
    online = _read(host_root, "sys/devices/system/cpu/online", 256, deadline=deadline).strip()
    if _range_count(online) != logical_count:
        raise LiveObservationError("kernel CPU topology disagrees with cpuinfo")
    numa = _read(host_root, "sys/devices/system/node/online", 256, deadline=deadline).strip()
    return {
        "os_release": _read(
            host_root, "etc/os-release", MAX_BYTES["os_release"], deadline=deadline
        ),
        "kernel_identity": json.dumps({"release": release, "machine": architecture}),
        "cpu_info": cpu_info,
        "cpu_topology": json.dumps(
            {
                "architecture": architecture,
                "physical_core_count": physical_count,
                "logical_thread_count": logical_count,
            }
        ),
        "memory_info": _read(
            host_root, "proc/meminfo", MAX_BYTES["memory_info"], deadline=deadline
        ),
        "numa_topology": json.dumps({"node_count": _range_count(numa)}),
    }


def _validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("implementation_status") != "tier0_live_read_enabled":
        raise LiveObservationError("live policy implementation status is not approved")
    if policy.get("current_capabilities") != [
        "validate_registered_adapters",
        "collect_bounded_tier0_host_facts",
        "emit_ephemeral_candidate_facts",
    ]:
        raise LiveObservationError("live policy capability scope is not approved")
    if policy.get("host_observation_enabled") is not True:
        raise LiveObservationError("live host observation is disabled by policy")
    for key in (
        "execution_enabled",
        "network_enabled",
        "privilege_enabled",
        "mutation_enabled",
        "persistence_enabled",
        "device_access_enabled",
        "protected_read_enabled",
    ):
        if policy.get(key) is not False:
            raise LiveObservationError(f"live policy enables forbidden capability: {key}")
    if policy.get("transport") != "none":
        raise LiveObservationError("live observation transport is not approved")
    gate = policy.get("activation_gate", {})
    if (
        gate.get("host_read_authority_granted") is not True
        or policy.get("authorization_ledger_persistence_enabled") is not True
    ):
        raise LiveObservationError("live policy activation gate is incomplete")


def _scope_facts(scope: ApprovedFactScope) -> tuple[str, ...]:
    return tuple(sorted({fact_id for entry in scope.entries for fact_id in entry.fact_ids}))


def collect_tier0(
    ledger: authority.ActivationAuthorityLedger,
    authorization_id: str,
    *,
    expected_authorization: authority.UserAuthorization,
    project_root: Path = contract.LAB_ROOT,
    host_root: Path = Path("/"),
    deadline: float | None = None,
) -> dict[str, Any]:
    """Consume one authorization and collect only approved Tier-0 facts.

    The policy check runs before ledger consumption, so a disabled deployment
    cannot burn an authorization accidentally.
    """

    _check_deadline(deadline)
    if expected_authorization.authorization_id != authorization_id:
        raise LiveObservationError("expected authorization identity mismatch")
    try:
        authority.validate_authorization(expected_authorization)
    except authority.AuthorizationError as exc:
        raise LiveObservationError("expected authorization is invalid") from exc
    try:
        policy = contract.load_json(contract.FILES["policy"], project_root)
    except contract.ObservationError as exc:
        raise LiveObservationError("observation policy unavailable") from exc
    _validate_policy(policy)
    _check_deadline(deadline)
    registry = contract.load_json(contract.FILES["registry"], project_root)
    if registry.get("host_observation_enabled") is not True:
        raise LiveObservationError("live adapter registry is disabled")
    adapter_index = {item["id"]: item for item in registry.get("adapters", [])}
    expected_adapter_ids = {
        "fedora.platform.os-release",
        "fedora.kernel.identity",
        "fedora.compute.cpu-summary",
        "fedora.compute.memory-summary",
    }
    if set(adapter_index) != expected_adapter_ids:
        raise LiveObservationError("live adapter registry scope drift")
    scope = load_approved_scope(project_root / "enrollment" / "tier0-approved-fact-scope.json")
    proposal_digest = contract.digest(contract.FILES["proposal"], project_root)
    catalog_digest = contract.digest(contract.FILES["sources"], project_root)
    if (
        expected_authorization.proposal_digest != proposal_digest
        or expected_authorization.source_catalog_digest != catalog_digest
    ):
        raise LiveObservationError("authorization proposal or catalog binding drift")
    if expected_authorization.scope_digest != fact_scope_digest(scope):
        raise LiveObservationError("authorization scope binding drift")
    if expected_authorization.approved_group_ids != EXPECTED_GROUPS:
        raise LiveObservationError("authorization group scope is not exact Tier-0")
    if expected_authorization.approved_fact_ids != _scope_facts(scope):
        raise LiveObservationError("authorization fact scope is not exact Tier-0")
    _check_deadline(deadline)
    try:
        payloads = _live_payloads(host_root, deadline=deadline)
    except (contract.ObservationError, OSError, ValueError) as exc:
        raise LiveObservationError("live source validation failed closed") from exc
    facts: list[dict[str, Any]] = []
    for adapter_id, parser_id in (
        ("fedora.platform.os-release", "os_release_v1"),
        ("fedora.kernel.identity", "kernel_identity_v1"),
        ("fedora.compute.cpu-summary", "cpu_summary_v1"),
        ("fedora.compute.memory-summary", "memory_summary_v1"),
    ):
        _check_deadline(deadline)
        adapter = adapter_index[adapter_id]
        try:
            parsed = contract.PARSERS[parser_id](
                {key: payloads[key] for key in adapter["fixture_inputs"]}
            )
        except (contract.ObservationError, KeyError, TypeError, ValueError) as exc:
            raise LiveObservationError(f"{adapter_id}: parser validation failed closed") from exc
        if tuple(parsed) != tuple(adapter["expected_fact_ids"]):
            raise LiveObservationError(f"{adapter_id}: unexpected output")
        for fact_id, value in parsed.items():
            facts.append(
                {
                    "fact_id": fact_id,
                    "source_id": adapter["source_id"],
                    "value": value,
                    "synthetic": False,
                    "observer_scope": "direct-host-tier0-readonly",
                    "observed_at": dt.datetime.now(dt.timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            )
    _check_deadline(deadline)
    # Consume only after all bounded source reads and parser validation have
    # succeeded. A malformed host interface must not burn a one-use decision
    # or leave the client without a deterministic error response.
    try:
        ledger.consume(authorization_id, expected=expected_authorization)
    except authority.AuthorizationError as exc:
        raise LiveObservationError("authorization consumption failed closed") from exc
    return {
        "schema_version": 1,
        "status": "host_observed_tier0",
        "execution_performed": False,
        "effect_occurred": True,
        "host_effect_occurred": False,
        "persistence_performed": False,
        "authorization_ledger_persistence_performed": True,
        "fact_persistence_performed": False,
        "authorization_ledger_mutated": True,
        "authorization_id": authorization_id,
        "facts": facts,
    }
