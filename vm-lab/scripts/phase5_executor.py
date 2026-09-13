"""Fail-closed contract for future supervised mutation adapters.

This module deliberately has no subprocess, shell, privilege, network, device,
or filesystem-mutation implementation. It validates an exact operation context
and refuses execution until a separately reviewed adapter and OS authorization
boundary are supplied.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import threading
from dataclasses import dataclass
from typing import Any, Protocol


class ExecutorError(ValueError):
    pass


def _text(value: Any, label: str, limit: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > limit
        or any(ord(c) < 0x20 for c in value)
    ):
        raise ExecutorError(f"{label} is invalid")
    return value


def _digest(value: Any, label: str) -> str:
    value = _text(value, label, 64)
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ExecutorError(f"{label} is not a SHA-256 digest")
    return value


def _canonical_digest(value: Any, label: str) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ExecutorError(f"{label} is not canonical JSON") from exc
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OperationApproval:
    approval_id: str
    request_id: str
    operation_id: str
    operation_revision: str
    target_digest: str
    parameters_digest: str
    policy_digest: str
    expires_at: str
    idempotency_key: str
    approved: bool = False
    consumed: bool = False

    def validate(self, *, now: dt.datetime | None = None) -> None:
        for value, label in (
            (self.approval_id, "approval_id"),
            (self.request_id, "request_id"),
            (self.operation_id, "operation_id"),
            (self.operation_revision, "operation_revision"),
            (self.idempotency_key, "idempotency_key"),
        ):
            _text(value, label)
        for value, label in (
            (self.target_digest, "target_digest"),
            (self.parameters_digest, "parameters_digest"),
            (self.policy_digest, "policy_digest"),
        ):
            _digest(value, label)
        try:
            expiry = dt.datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ExecutorError("expires_at is invalid") from exc
        if expiry <= (now or dt.datetime.now(dt.timezone.utc)):
            raise ExecutorError("approval is expired")
        if self.consumed:
            raise ExecutorError("approval is already consumed")
        if not self.approved:
            raise ExecutorError("approval is not granted")


class RegisteredAdapter(Protocol):
    operation_id: str
    revision: str

    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]: ...


class ApprovalLedger(Protocol):
    """Atomic one-use boundary supplied by the trusted authority layer."""

    def consume(self, approval: OperationApproval) -> None: ...


class InMemoryApprovalLedger:
    """Test-only atomic ledger; production must use the durable authority ledger."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._consumed: set[tuple[str, str]] = set()

    def consume(self, approval: OperationApproval) -> None:
        approval.validate()
        key = (approval.approval_id, approval.idempotency_key)
        with self._lock:
            if key in self._consumed:
                raise ExecutorError("approval has already been consumed")
            self._consumed.add(key)


class SupervisedExecutor:
    """Admission-only executor; no adapter is enabled in this revision."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        adapters: tuple[RegisteredAdapter, ...] = (),
        ledger: ApprovalLedger | None = None,
    ) -> None:
        self.enabled = enabled
        self.adapters = {(adapter.operation_id, adapter.revision): adapter for adapter in adapters}
        self.ledger = ledger
        if enabled and ledger is None:
            raise ExecutorError("enabled executor requires an approval ledger")

    @staticmethod
    def parameters_digest(parameters: dict[str, Any]) -> str:
        if not isinstance(parameters, dict):
            raise ExecutorError("parameters must be an object")
        return _canonical_digest(parameters, "parameters")

    @staticmethod
    def target_digest(target: dict[str, Any]) -> str:
        if not isinstance(target, dict):
            raise ExecutorError("target must be an object")
        return _canonical_digest(target, "target")

    def execute(
        self,
        approval: OperationApproval,
        *,
        parameters: dict[str, Any],
        target: dict[str, Any],
        active_policy_digest: str,
    ) -> dict[str, Any]:
        approval.validate()
        if approval.parameters_digest != self.parameters_digest(parameters):
            raise ExecutorError("parameter binding mismatch")
        if approval.target_digest != self.target_digest(target):
            raise ExecutorError("target binding mismatch")
        if approval.policy_digest != _digest(active_policy_digest, "active_policy_digest"):
            raise ExecutorError("policy binding mismatch")
        adapter = self.adapters.get((approval.operation_id, approval.operation_revision))
        if adapter is None:
            raise ExecutorError("operation adapter is not registered")
        if not self.enabled:
            raise ExecutorError("supervised executor is disabled")
        if self.ledger is None:  # defensive; constructor rejects this when enabled
            raise ExecutorError("approval ledger is unavailable")
        # Consumption is the trusted, atomic one-use boundary. It must happen
        # before any future adapter effect and must be backed by the durable
        # authority ledger in a production deployment.
        self.ledger.consume(approval)
        # Kept unreachable until a separately reviewed OS authorization and
        # rollback-capable adapter are wired in.
        raise ExecutorError("supervised execution boundary is not activated")
