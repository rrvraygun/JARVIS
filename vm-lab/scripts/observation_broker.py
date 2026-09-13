#!/usr/bin/env python3
"""Typed, fail-closed facade for the Phase 4 Tier-0 observation contract.

This broker deliberately remains fixture-only. It prepares and simulates the
minimal platform/compute scope, while rejecting live host observation until the
separate broker, storage, audit, rehearsal, and security-review gates exist.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import observation_contract as contract

MINIMAL_ADAPTERS = (
    ("fedora.platform.os-release", "1.0.0"),
    ("fedora.kernel.identity", "1.0.0"),
    ("fedora.compute.cpu-summary", "1.0.0"),
    ("fedora.compute.memory-summary", "1.0.0"),
)


class BrokerError(contract.ObservationError):
    """Raised when broker admission or execution must stop."""


def _parse_time(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BrokerError("expiry must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise BrokerError("expiry must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _expiry(expires_at: str, now: dt.datetime) -> None:
    if _parse_time(expires_at) <= now.astimezone(dt.timezone.utc):
        raise BrokerError("request expired")


def _bindings(root: Path) -> dict[str, str]:
    return {
        "adapter_registry_sha256": contract.digest(contract.FILES["registry"], root),
        "broker_policy_sha256": contract.digest(contract.FILES["policy"], root),
        "source_catalog_sha256": contract.digest(contract.FILES["sources"], root),
        "proposal_sha256": contract.digest(contract.FILES["proposal"], root),
    }


def prepare_minimal_request(
    request_id: str,
    expires_at: str,
    *,
    root: Path = contract.LAB_ROOT,
) -> dict[str, Any]:
    """Create the exact fixture request for platform and compute Tier 0."""

    contract.safe_text(request_id, "request_id", 128)
    _expiry(expires_at, _now())
    return {
        "schema_version": 1,
        "request_id": request_id,
        "mode": "fixture_simulation",
        "execution_enabled": False,
        "host_observation_requested": False,
        "fixture_set_id": "fedora-workstation-synthetic-v1",
        "adapters": [
            {"id": adapter_id, "version": version} for adapter_id, version in MINIMAL_ADAPTERS
        ],
        "attempt": 1,
        "parameters": {},
        "expires_at": expires_at,
        "bindings": _bindings(root),
    }


def simulate_minimal(
    request: dict[str, Any],
    *,
    root: Path = contract.LAB_ROOT,
    seen_request_ids: set[str] | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Validate and simulate a minimal request exactly once."""

    _expiry(request.get("expires_at", ""), now or _now())
    selections = request.get("adapters")
    expected = [{"id": adapter_id, "version": version} for adapter_id, version in MINIMAL_ADAPTERS]
    if selections != expected:
        raise BrokerError("minimal Tier-0 scope mismatch")
    result = contract.simulate(
        request,
        *contract.validate_contract(root),
        root=root,
        seen_request_ids=seen_request_ids,
    )
    if not result["host_observed"] and all(item["synthetic"] for item in result["candidate_facts"]):
        return result
    raise BrokerError("non-synthetic result rejected")


def run_live(*_: Any, **__: Any) -> None:
    """Reject live observation until all activation prerequisites are met."""

    raise BrokerError(
        "live host observation is disabled pending broker, encrypted storage, "
        "audit, rehearsal, independent review, and exact activation"
    )


def main() -> int:
    request = prepare_minimal_request(
        "obs-minimal-tier0-preview",
        (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5))
        .isoformat()
        .replace("+00:00", "Z"),
    )
    result = simulate_minimal(request)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
