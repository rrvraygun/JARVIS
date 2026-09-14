"""Content-free request sizes and cumulative usage accounting."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


def payload_metrics(params: dict[str, Any]) -> dict[str, Any]:
    """Measure only known payload components; never persist payload values."""

    def size(value: Any) -> int:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())

    return {
        "serialized_bytes": size(params),
        "component_bytes": {
            key: size(params[key])
            for key in (
                "input",
                "items",
                "outputSchema",
                "baseInstructions",
                "developerInstructions",
                "config",
                "tools",
                "arguments",
                "result",
                "error",
            )
            if key in params
        },
        "units": "utf8_bytes_not_tokens",
        "server_added_context_measured": False,
    }


def journal_usage(value: dict[str, Any]) -> dict[str, Any]:
    """Use count suffixes so credential-key redaction still rejects token fields."""
    return {
        key.removesuffix("_tokens") + "_count" if key.endswith("_tokens") else key: journal_usage(
            item
        )
        if isinstance(item, dict)
        else item
        for key, item in value.items()
    }


@dataclass
class UsageLedger:
    """Delta cumulative counters, never sum repeated last-response snapshots.

    A fresh thread has a known zero baseline. A resumed thread needs its first
    observation as baseline; that initial interval remains explicitly incomplete.
    """

    thread_id: str | None = None
    previous: dict[str, int] = field(default_factory=dict)
    task_id: str | None = None
    totals: dict[str, int] = field(default_factory=dict)
    phases: dict[str, dict[str, int]] = field(default_factory=dict)
    complete: bool = True
    fresh: bool = False

    def start_thread(self, thread_id: str) -> None:
        self.thread_id = thread_id
        self.previous.clear()
        self.fresh = True

    def reset_baseline(self) -> None:
        """Forget the pre-compaction cumulative baseline without losing task totals."""
        self.previous.clear()
        self.fresh = True

    def observe(
        self, thread_id: str | None, task_id: str | None, phase: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        if task_id != self.task_id:
            self.task_id = task_id
            self.totals.clear()
            self.phases.clear()
            self.complete = True
        if thread_id != self.thread_id:
            self.thread_id = thread_id
            self.previous.clear()
            self.fresh = False
        current = {
            key: value
            for key, value in metadata.items()
            if key.startswith("total_") and type(value) is int and value >= 0
        }
        if metadata.get("usage_valid") is False:
            self.complete = False
            current = {}
        if not current:
            self.complete = False
        for key, value in current.items():
            previous = self.previous.get(key, 0 if self.fresh else None)
            if previous is None or value < previous:
                self.complete = False
            elif task_id:
                delta = value - previous
                self.totals[key] = self.totals.get(key, 0) + delta
                counters = self.phases.setdefault(phase, {})
                counters[key] = counters.get(key, 0) + delta
            self.previous[key] = value
        self.fresh = False
        return {
            "phase": phase,
            "response": {key: value for key, value in metadata.items() if key.startswith("last_")},
            "thread_cumulative": current,
            "logical_turn": dict(self.totals),
            "phase_totals": {key: dict(value) for key, value in self.phases.items()},
            "complete": self.complete and task_id is not None,
        }
