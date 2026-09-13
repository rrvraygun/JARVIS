"""Conservative recovery eligibility from the registered mutation journal."""

from __future__ import annotations

from typing import Any


def recovery_binding(events: tuple[dict[str, Any], ...]) -> str | None:
    """Return the sole verified package receipt, or reject unsupported history."""
    if not events:
        return None
    if any(
        event.get("event_type")
        not in {"package.transaction.execution.reserved", "package.transaction.completed"}
        for event in events
    ):
        raise ValueError("registered mutations require their own exact recovery")
    completed = [e for e in events if e.get("event_type") == "package.transaction.completed"]
    reserved = [
        e for e in events if e.get("event_type") == "package.transaction.execution.reserved"
    ]
    if len(completed) != 1 or len(reserved) != 1:
        raise ValueError("mutation outcome is incomplete or multiple changes exist")
    receipt = completed[0]
    digest = receipt.get("details", {}).get("record_digest")
    if (
        receipt.get("status") != "completed"
        or not receipt.get("task_id")
        or receipt.get("task_id") != reserved[0].get("task_id")
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(c not in "0123456789abcdef" for c in digest)
    ):
        raise ValueError("verified recovery receipt is missing")
    return digest
