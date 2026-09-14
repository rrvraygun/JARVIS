"""Normalize App Server events into safe, deterministic broker events."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .terminal_safety import sanitize_terminal_text

MAX_DISPLAY_CHARS = 16_000
MAX_EVENT_INPUT_CHARS = 128 * 1024
MAX_EVENT_NESTING = 32
MAX_EVENT_VALUES = 10_000
SERVER_REQUEST_METHODS = frozenset(
    {
        "item/commandExecution/requestApproval",
        "item/fileChange/requestApproval",
        "item/permissions/requestApproval",
        "item/tool/requestUserInput",
        "tool/requestUserInput",
        "mcpServer/elicitation/request",
        "item/tool/call",
        "account/chatgptAuthTokens/refresh",
        "attestation/generate",
        "applyPatchApproval",
        "execCommandApproval",
    }
)


def _fingerprint(message: dict[str, Any]) -> str:
    encoded = json.dumps(
        message, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _within_event_limits(value: object) -> bool:
    """Bound direct/fake protocol ingress before canonical hashing."""
    pending: list[tuple[object, int]] = [(value, 0)]
    active: set[int] = set()
    seen = 0
    while pending:
        current, depth = pending.pop()
        seen += 1
        if seen > MAX_EVENT_VALUES or depth > MAX_EVENT_NESTING:
            return False
        if isinstance(current, (dict, list)):
            identifier = id(current)
            if identifier in active:
                return False
            active.add(identifier)
            values = current.values() if isinstance(current, dict) else current
            if len(current) > MAX_EVENT_VALUES:
                return False
            pending.extend((item, depth + 1) for item in values)
        elif (
            isinstance(current, str)
            and len(current.encode("utf-8", "replace")) > MAX_EVENT_INPUT_CHARS
        ):
            return False
    return True


def _object(value: object) -> dict[str, Any]:
    """Convert an untrusted protocol object into a typed mapping."""
    return {str(key): item for key, item in value.items()} if isinstance(value, dict) else {}


def _safe_text(value: Any) -> tuple[str | None, bool]:
    if not isinstance(value, str) or not value:
        return None, False
    display_source = value[:MAX_DISPLAY_CHARS]
    safe, truncated = sanitize_terminal_text(display_source)
    return safe, truncated or safe != display_source or len(value) > MAX_DISPLAY_CHARS


def _safe_metadata_text(value: Any, limit: int = 4_000) -> str | None:
    if value is None:
        return None
    safe, _ = sanitize_terminal_text(str(value)[:limit], limit=limit)
    return safe


def _item_lifecycle_status(method: str, status: str) -> str:
    """Derive a displayable status when App Server omits item.status."""
    normalized = {
        "inProgress": "in_progress",
        "notStarted": "not_started",
    }.get(status, status)
    if method == "item/started" and normalized == "received":
        return "in_progress"
    if method == "item/completed" and normalized in {"received", "in_progress"}:
        return "completed"
    return normalized


@dataclass(frozen=True)
class NormalizedEvent:
    fingerprint: str
    method: str
    kind: str
    status: str
    thread_id: str | None = None
    turn_id: str | None = None
    item_id: str | None = None
    request_id: str | int | None = None
    item_type: str | None = None
    text: str | None = None
    text_sanitized_or_capped: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def journal_details(self) -> dict[str, Any]:
        """Return correlation data without persisting model or tool text."""
        details: dict[str, Any] = {
            "fingerprint": self.fingerprint,
            "method": self.method,
            "kind": self.kind,
            "thread_id": self.thread_id,
            "turn_id": self.turn_id,
            "item_id": self.item_id,
            "request_id": self.request_id,
            "item_type": self.item_type,
            "metadata": {
                "keys": sorted(self.metadata),
                "sha256": hashlib.sha256(
                    json.dumps(
                        self.metadata,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                        default=str,
                    ).encode()
                ).hexdigest(),
                "withheld": bool(self.metadata.get("withheld", False)),
            },
        }
        if self.text is not None:
            details["display_text"] = {
                "sha256": hashlib.sha256(self.text.encode()).hexdigest(),
                "characters": len(self.text),
                "sanitized_or_capped": self.text_sanitized_or_capped,
            }
        return details


class AppServerEventReducer:
    """Idempotent mapper that never exposes raw reasoning or raw command output."""

    def __init__(self, seen_fingerprints: set[str] | None = None) -> None:
        self._seen: set[str] = set(seen_fingerprints or ())

    def normalize(self, message: dict[str, Any]) -> NormalizedEvent | None:
        if not isinstance(message, dict) or not _within_event_limits(message):
            return NormalizedEvent(
                fingerprint=hashlib.sha256(b"jarvis:message_limits_exceeded").hexdigest(),
                method="jarvis/protocolError",
                kind="protocol_error",
                status="failed",
                metadata={"reason": "message_limits_exceeded"},
            )
        fingerprint = _fingerprint(message)
        method = str(message.get("method", "jarvis/protocolError"))
        # Authoritative lifecycle events and server requests can be replayed on
        # reconnect. Deltas are not deduplicated because two legitimate chunks
        # may have identical text.
        deduplicated = "/delta" not in method and not method.endswith("Delta")
        if deduplicated and fingerprint in self._seen:
            return None
        if deduplicated:
            self._seen.add(fingerprint)

        params = _object(message.get("params"))
        thread = _object(params.get("thread"))
        turn = _object(params.get("turn"))
        item = _object(params.get("item"))
        thread_id = params.get("threadId") or thread.get("id")
        turn_id = params.get("turnId") or turn.get("id")
        item_id = params.get("itemId") or item.get("id")
        item_type = item.get("type") if item else None
        status = str(turn.get("status") or item.get("status") or params.get("status") or "received")
        kind = "protocol_event"
        text: str | None = None
        changed = False
        metadata: dict[str, Any] = {}

        if method == "thread/started":
            kind = "thread_started"
        elif method in {"thread/tokenUsage/updated", "thread/token_usage/updated"}:
            kind = "token_usage_updated"
            usage = _object(
                params.get("tokenUsage")
                or params.get("usage")
                or thread.get("tokenUsage")
                or turn.get("tokenUsage")
            )
            total = _object(usage.get("total"))
            last = _object(usage.get("last"))
            fields = {
                "total_tokens": "totalTokens",
                "input_tokens": "inputTokens",
                "cached_input_tokens": "cachedInputTokens",
                "cache_write_input_tokens": "cacheWriteInputTokens",
                "output_tokens": "outputTokens",
                "reasoning_output_tokens": "reasoningOutputTokens",
            }
            for prefix, values in (("total", total), ("last", last)):
                for name, wire in fields.items():
                    key = f"{prefix}_{name}" if name != "total_tokens" else f"{prefix}_total_tokens"
                    value = values.get(wire, values.get(name))
                    if value is not None:
                        metadata[key] = value
            if "total_total_tokens" in metadata:
                metadata["total_tokens"] = metadata.pop("total_total_tokens")
            window = usage.get("modelContextWindow", usage.get("contextWindow"))
            if window is not None:
                metadata["context_window"] = window
            valid = all(type(value) is int and value >= 0 for value in metadata.values())
            metadata = {
                key: value for key, value in metadata.items() if type(value) is int and value >= 0
            }
            # Cumulative usage can exceed a context window across many responses.
            metadata["usage_valid"] = valid
        elif method == "thread/status/changed":
            kind = "thread_status"
            raw_status = params.get("status")
            status = str(raw_status.get("type") if isinstance(raw_status, dict) else raw_status)
        elif method == "thread/closed":
            kind, status = "thread_closed", "closed"
        elif method == "turn/started":
            kind = "turn_started"
        elif method == "turn/completed":
            kind = "turn_completed"
            error = _object(turn.get("error"))
            if error:
                text, changed = _safe_text(error.get("message"))
        elif method == "turn/plan/updated":
            kind = "plan_updated"
            raw_plan = params.get("plan")
            plan: list[object] = list(raw_plan) if isinstance(raw_plan, list) else []
            metadata["steps"] = [
                {
                    "step": str(entry.get("step", ""))[:500],
                    "status": entry.get("status"),
                }
                for entry in plan
                if isinstance(entry, dict)
            ][:100]
        elif method == "turn/diff/updated":
            # Allow file diffs - was previously blocked
            kind = "file_diff_updated"
            status = "received"
            metadata["diff_available"] = True
        elif method in {"item/started", "item/completed"}:
            kind = "item"
            status = _item_lifecycle_status(method, status)
            if item_type == "contextCompaction":
                kind = "context_compaction"
            elif item_type == "agentMessage":
                kind = "agent_message"
                text, changed = _safe_text(item.get("text"))
            elif item_type == "plan":
                kind = "plan_message"
                text, changed = _safe_text(item.get("text"))
            elif item_type == "reasoning":
                kind = "reasoning_withheld"
                metadata["withheld"] = True
            elif item_type == "mcpToolCall":
                kind = "tool_execution"
                metadata["tool_type"] = item_type
                metadata["server"] = _safe_metadata_text(item.get("server", ""), 120)
                metadata["tool"] = _safe_metadata_text(item.get("tool", ""), 160)
                arguments = item.get("arguments")
                if isinstance(arguments, dict) and isinstance(arguments.get("query"), str):
                    metadata["query"] = _safe_metadata_text(arguments["query"], 160)
                if status == "failed":
                    metadata["error_code"] = "tool_call_failed"
            elif item_type in {"commandExecution", "fileChange"}:
                # Allow tool execution - was previously blocked
                kind = "tool_execution"
                metadata["tool_type"] = item_type
                # Extract command/file info if available
                if "command" in item:
                    metadata["command"] = _safe_metadata_text(item["command"], 500)
                if "path" in item:
                    metadata["path"] = _safe_metadata_text(item["path"], 500)
            elif item_type:
                metadata["type"] = item_type
        elif method in {"item/agentMessage/delta", "item/plan/delta"}:
            kind = "agent_delta" if "agentMessage" in method else "plan_delta"
            text, changed = _safe_text(params.get("delta"))
        elif method.startswith("item/reasoning/"):
            kind = "reasoning_withheld"
            metadata["withheld"] = True
        elif method == "item/commandExecution/outputDelta":
            # Allow command output - was previously blocked
            kind = "command_output"
            status = "streaming"
            text, changed = _safe_text(params.get("delta"))
            metadata["output_delta"] = True
        elif method in SERVER_REQUEST_METHODS:
            kind, status = "server_request", "pending"
            metadata = {
                "request_type": method,
                "requires_explicit_handling": True,
                "command": _safe_metadata_text(params.get("command")),
                "cwd": _safe_metadata_text(params.get("cwd")),
                "reason": _safe_metadata_text(params.get("reason")),
                "grant_root": _safe_metadata_text(params.get("grantRoot")),
            }
            if method == "mcpServer/elicitation/request":
                metadata.update(
                    {
                        "message": _safe_metadata_text(params.get("message"), 1_000),
                        "mode": _safe_metadata_text(params.get("mode"), 100),
                        "server_name": _safe_metadata_text(params.get("serverName"), 200),
                        "url": _safe_metadata_text(params.get("url"), 1_000),
                    }
                )
        elif method == "serverRequest/resolved":
            kind, status = "server_request_resolved", "resolved"
            if params.get("requestId") is not None:
                metadata["request_id"] = str(params["requestId"])
        elif method == "account/updated":
            kind = "account_updated"
            metadata = {
                "auth_mode": params.get("authMode"),
                "plan_type": params.get("planType"),
            }
        elif method == "account/login/completed":
            kind = "login_completed"
            status = "completed" if params.get("success") else "failed"
            text, changed = _safe_text(params.get("error"))
        elif method == "account/rateLimits/updated":
            kind = "rate_limits_updated"
            metadata["rate_limits"] = params.get("rateLimits")
            metadata["rate_limits_by_id"] = params.get("rateLimitsByLimitId")
        elif method in {"warning", "configWarning", "jarvis/appServerStderr"}:
            kind, status = "warning", "warning"
            text, changed = _safe_text(params.get("message") or params.get("summary"))
        elif method == "error":
            kind, status = "error", "failed"
            error = _object(params.get("error"))
            text, changed = _safe_text(error.get("message"))
            metadata["will_retry"] = bool(params.get("willRetry", False))
        elif method in {"jarvis/disconnected", "jarvis/protocolError"}:
            kind = "disconnected" if method.endswith("disconnected") else "protocol_error"
            status = "disconnected" if kind == "disconnected" else "failed"
            text, changed = _safe_text(params.get("reason"))

        return NormalizedEvent(
            fingerprint=fingerprint,
            method=method,
            kind=kind,
            status=status,
            thread_id=str(thread_id) if thread_id is not None else None,
            turn_id=str(turn_id) if turn_id is not None else None,
            item_id=str(item_id) if item_id is not None else None,
            request_id=(
                message["id"]
                if "id" in message
                else params["requestId"]
                if method == "serverRequest/resolved" and params.get("requestId") is not None
                else None
            ),
            item_type=str(item_type) if item_type is not None else None,
            text=text,
            text_sanitized_or_capped=changed,
            metadata=metadata,
        )
