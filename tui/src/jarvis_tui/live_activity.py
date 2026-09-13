"""Small live activity projection; contains no model reasoning or raw results."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .event_reducer import NormalizedEvent
from .presentation import safe_text


@dataclass
class LiveActivity:
    turn_id: str | None = None
    phase: str = "Ready"
    active: bool = False
    started: float = 0
    ended: float = 0
    characters: int = 0
    fragments: int = 0
    unverified: bool = False
    tools: dict[str, dict] = field(default_factory=dict)
    context_window: int | None = None
    context_used: int | None = None

    def reset_context(self) -> None:
        """Reset usage after a conversation checkpoint or new conversation."""
        self.context_used = 0

    def update(self, event: NormalizedEvent) -> None:
        now = time.monotonic()
        if event.kind == "turn_started":
            self.turn_id = event.turn_id
            self.phase, self.active, self.started = "Working", True, now
            self.ended = self.characters = self.fragments = 0
            self.unverified = False
            self.tools.clear()
        if self.turn_id and event.turn_id and event.turn_id != self.turn_id:
            return
        if event.kind == "token_usage_updated":
            total = event.metadata.get("total_tokens")
            window = event.metadata.get("context_window")
            if isinstance(total, (int, float)):
                self.context_used = max(0, int(total))
            if isinstance(window, (int, float)) and window > 0:
                self.context_window = int(window)
            return
        if event.kind in {"agent_delta", "agent_streaming"}:
            self.phase = (
                "Writing reply" if event.kind == "agent_delta" else "Checking current state"
            )
            self.fragments += 1
            self.characters += (
                len(event.text or "")
                if event.kind == "agent_delta"
                else int(event.metadata.get("characters", 0))
            )
            if event.kind == "agent_delta":
                self.unverified = False
        elif event.kind == "observation_unavailable":
            self.unverified = True
            self.phase = "Awaiting verified observation"
        elif event.kind == "agent_message" and event.text:
            self.unverified = False
        elif event.kind == "tool_execution":
            key = event.item_id or event.fingerprint
            if key not in self.tools:
                if len(self.tools) >= 4:
                    self.tools.pop(next(iter(self.tools)))
                self.tools[key] = {"started": now, "ended": None, "name": "Tool", "query": ""}
            tool = self.tools[key]
            name = (
                event.metadata.get("tool")
                or event.metadata.get("command")
                or event.metadata.get("tool_type")
            )
            if name:
                tool["name"] = safe_text(name, 100)
            if event.metadata.get("query"):
                tool["query"] = safe_text(event.metadata["query"], 100)
            tool["status"] = event.status
            if event.status in {"completed", "failed", "cancelled", "interrupted"}:
                tool["ended"] = now
            self.phase = "Tool failed" if event.status == "failed" else "Using tools"
        elif event.kind == "server_request":
            self.phase = "Waiting for approval or input"
        elif event.kind == "server_request_resolved":
            self.phase = "Working"
        elif event.kind in {"turn_completed", "turn_cancelled", "disconnected", "error"}:
            self.active, self.ended = False, now
            for tool in self.tools.values():
                if tool["ended"] is None:
                    tool["ended"] = now
                    tool["status"] = "outcome unknown"
            self.phase = (
                ("Inspection unavailable" if self.unverified else "Completed")
                if event.status == "completed"
                else safe_text(event.status, 60).title()
            )

    def text(self) -> str:
        if not self.started:
            if self.context_window:
                if self.context_used is None:
                    return f"○ Ready\nContext · unavailable / {self.context_window / 1024:.0f}k · — left"
                remaining = max(0, self.context_window - self.context_used)
                percent = max(0, min(100, remaining * 100 / self.context_window))
                return f"○ Ready\nContext · {self.context_used / 1024:.0f}k / {self.context_window / 1024:.0f}k · {percent:.0f}% left"
            return "○ Ready"
        now = time.monotonic()
        elapsed = (now if self.active else self.ended) - self.started
        glyph = (
            "◐◓◑◒"[int(now * 8) % 4] if self.active else "✓" if self.phase == "Completed" else "!"
        )
        lines = [
            f"{glyph} {self.phase} · {elapsed:.1f}s · {self.fragments} fragments · {self.characters} characters"
        ]

        def compact(value: int) -> str:
            return f"{value / 1024:.0f}k" if value >= 1024 else str(value)

        if self.context_window:
            if self.context_used is None:
                lines.append(f"Context · unavailable / {compact(self.context_window)} · — left")
            else:
                remaining = max(0, self.context_window - self.context_used)
                percent = max(0, min(100, remaining * 100 / self.context_window))
                lines.append(
                    f"Context · {compact(self.context_used)} / {compact(self.context_window)} · {percent:.0f}% left"
                )
        else:
            lines.append("Context · unavailable / auto · — left")
        for tool in self.tools.values():
            running = tool["ended"] is None
            duration = (now if running else tool["ended"]) - tool["started"]
            icon = "↻" if running else "✓" if tool.get("status") == "completed" else "!"
            query = f" · query: {tool['query']}" if tool["query"] else ""
            lines.append(
                f"{icon} {tool['name']}{query} · {tool.get('status', 'running')} · {duration:.1f}s"
            )
        return "\n".join(lines)
