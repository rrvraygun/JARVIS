#!/usr/bin/env python3
"""Prepared, disabled executor bridge for the supervised power-profile adapter.

The bridge binds one exact request to a one-use approval and consumes that
approval before invoking a future registered adapter.  It has no default
adapter, no default ledger, no D-Bus access, and is disabled by default.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import power_profile_authorization as authorization
from power_profile_mutation import SupervisedPowerProfileAdapter
from power_profile_status import BUS_NAME, INTERFACE, OBJECT_PATH


class PowerProfileExecutorError(ValueError):
    """Raised when an exact one-use execution boundary cannot be admitted."""


TARGET = {
    "provider": "tuned-ppd",
    "bus_name": BUS_NAME,
    "object_path": OBJECT_PATH,
    "interface": INTERFACE,
    "mutation": "org.freedesktop.DBus.Properties.Set:ActiveProfile",
}
OPERATION_ID = "jarvis.powerprofile.select"
OPERATION_REVISION = "1.0.0"


def _canonical(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise PowerProfileExecutorError("binding is not canonical JSON") from exc


def _digest(value: Mapping[str, Any], label: str) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def current_policy_digest() -> str:
    """Return the canonical digest of the checked-in authorization policy."""
    return _digest(authorization.load_policy(), "authorization policy")


def _text(value: Any, label: str, limit: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > limit
        or any(ord(char) < 0x20 for char in value)
    ):
        raise PowerProfileExecutorError(f"{label} is invalid")
    return value


def _sha256(value: Any, label: str) -> str:
    value = _text(value, label, 64)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise PowerProfileExecutorError(f"{label} is not a SHA-256 digest")
    return value


def _expiry(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(_text(value, "expires_at", 128).replace("Z", "+00:00"))
    except ValueError as exc:
        raise PowerProfileExecutorError("expires_at is invalid") from exc
    if parsed.tzinfo is None:
        raise PowerProfileExecutorError("expires_at requires timezone")
    return parsed.astimezone(dt.timezone.utc)


@dataclass(frozen=True)
class PowerProfileApproval:
    """Exact durable approval document supplied by the authority ledger."""

    approval_id: str
    operation_id: str
    operation_revision: str
    parameters_digest: str
    target_digest: str
    policy_digest: str
    expires_at: str
    idempotency_key: str

    def document(self) -> dict[str, str]:
        return {
            "approval_id": self.approval_id,
            "operation_id": self.operation_id,
            "operation_revision": self.operation_revision,
            "parameters_digest": self.parameters_digest,
            "target_digest": self.target_digest,
            "policy_digest": self.policy_digest,
            "expires_at": self.expires_at,
            "idempotency_key": self.idempotency_key,
        }

    def validate(self, *, now: dt.datetime | None = None) -> None:
        for value, label in (
            (self.approval_id, "approval_id"),
            (self.operation_id, "operation_id"),
            (self.operation_revision, "operation_revision"),
            (self.idempotency_key, "idempotency_key"),
        ):
            _text(value, label)
        if self.operation_id != OPERATION_ID or self.operation_revision != OPERATION_REVISION:
            raise PowerProfileExecutorError("operation binding mismatch")
        for value, label in (
            (self.parameters_digest, "parameters_digest"),
            (self.target_digest, "target_digest"),
            (self.policy_digest, "policy_digest"),
        ):
            _sha256(value, label)
        current = now or dt.datetime.now(dt.timezone.utc)
        expiry = _expiry(self.expires_at)
        try:
            window = int(authorization.EXPECTED_AUTHORIZATION["expiry_seconds"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PowerProfileExecutorError("authorization expiry policy is invalid") from exc
        if window != 60:
            raise PowerProfileExecutorError("authorization expiry policy drift")
        if expiry <= current:
            raise PowerProfileExecutorError("approval is expired")
        if expiry > current + dt.timedelta(seconds=window):
            raise PowerProfileExecutorError("approval expiry exceeds policy window")


class PowerProfileApprovalLedger(Protocol):
    """Durable authority ledger boundary; implementation is supplied later."""

    def consume(self, approval: PowerProfileApproval) -> None:
        """Atomically consume this exact approval once."""


class PowerProfileAdapter(Protocol):
    operation_id: str
    revision: str

    def execute(
        self,
        requested_profile: str,
        *,
        pre_profile: str,
        tui_confirmed: bool,
        active_session: bool,
        on_battery: bool,
        thermal_degraded: bool,
        notification_sink: Callable[[str], None] | None,
    ) -> dict[str, Any]:
        """Execute one already-admitted profile transition."""


class PreparedPowerProfileExecutor:
    """Disabled bridge; no adapter is registered in the shipped state."""

    __slots__ = ("_adapter", "_enabled", "_ledger")

    def __init__(
        self,
        *,
        enabled: bool = False,
        adapter: SupervisedPowerProfileAdapter | None = None,
        ledger: PowerProfileApprovalLedger | None = None,
    ) -> None:
        if adapter is not None and type(adapter) is not SupervisedPowerProfileAdapter:
            raise PowerProfileExecutorError("adapter is not the reviewed implementation")
        if enabled and (adapter is None or ledger is None):
            raise PowerProfileExecutorError("enabled bridge requires adapter and durable ledger")
        if adapter is not None and (
            adapter.operation_id != OPERATION_ID or adapter.revision != OPERATION_REVISION
        ):
            raise PowerProfileExecutorError("registered adapter binding mismatch")
        object.__setattr__(self, "_enabled", enabled)
        object.__setattr__(self, "_adapter", adapter)
        object.__setattr__(self, "_ledger", ledger)

    def __setattr__(self, name: str, value: Any) -> None:
        if hasattr(self, name):
            raise AttributeError("executor bridge bindings are immutable")
        object.__setattr__(self, name, value)

    @staticmethod
    def parameters_digest(parameters: Mapping[str, Any]) -> str:
        if not isinstance(parameters, Mapping):
            raise PowerProfileExecutorError("parameters must be an object")
        return _digest(dict(parameters), "parameters")

    @staticmethod
    def target_digest(target: Mapping[str, Any]) -> str:
        if not isinstance(target, Mapping):
            raise PowerProfileExecutorError("target must be an object")
        return _digest(dict(target), "target")

    def execute(
        self,
        approval: PowerProfileApproval,
        *,
        requested_profile: str,
        pre_profile: str,
        tui_confirmed: bool,
        active_session: bool,
        target: Mapping[str, Any],
        active_policy_digest: str,
        on_battery: bool = False,
        thermal_degraded: bool = False,
        notification_sink: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        parameters = {
            "requested_profile": requested_profile,
            "pre_profile": pre_profile,
            "tui_confirmed": tui_confirmed,
            "active_session": active_session,
            "on_battery": on_battery,
            "thermal_degraded": thermal_degraded,
        }
        approval.validate()
        if approval.parameters_digest != self.parameters_digest(parameters):
            raise PowerProfileExecutorError("parameter binding mismatch")
        if dict(target) != TARGET:
            raise PowerProfileExecutorError("target is not the fixed PPD target")
        if approval.target_digest != self.target_digest(target):
            raise PowerProfileExecutorError("target binding mismatch")
        if active_policy_digest != current_policy_digest():
            raise PowerProfileExecutorError("active policy is not the checked-in policy")
        if approval.policy_digest != _sha256(active_policy_digest, "active_policy_digest"):
            raise PowerProfileExecutorError("policy binding mismatch")
        if not self._enabled:
            raise PowerProfileExecutorError("power-profile executor bridge is disabled")
        if self._adapter is None or self._ledger is None:
            raise PowerProfileExecutorError("power-profile execution dependencies are unavailable")
        self._ledger.consume(approval)
        return self._adapter.execute(
            requested_profile,
            pre_profile=pre_profile,
            tui_confirmed=tui_confirmed,
            active_session=active_session,
            on_battery=on_battery,
            thermal_degraded=thermal_degraded,
            notification_sink=notification_sink,
        )


__all__ = [
    "OPERATION_ID",
    "OPERATION_REVISION",
    "TARGET",
    "PowerProfileApproval",
    "PowerProfileApprovalLedger",
    "PowerProfileExecutorError",
    "PreparedPowerProfileExecutor",
]
