#!/usr/bin/env python3
"""High-confidence Codex hook denials. Not a complete policy boundary."""

import json
import re
import sys


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


try:
    payload = json.load(sys.stdin)
except json.JSONDecodeError:
    print("invalid hook input", file=sys.stderr)
    raise SystemExit(2)

event = payload.get("hook_event_name")
if event == "SessionStart":
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": (
                        "Jarvis control plane is active. Classify administration through a "
                        "registered capability and procedure; use deterministic policy and "
                        "digest-bound command approval before mutation; query version-matched "
                        "knowledge; run one attempt only; redact and audit material work."
                    ),
                }
            }
        )
    )
    raise SystemExit(0)

if event != "PreToolUse":
    print("{}")
    raise SystemExit(0)

tool = payload.get("tool_name", "")
tool_input = payload.get("tool_input") or {}
command = (
    tool_input.get("command", tool_input.get("cmd", "")) if isinstance(tool_input, dict) else ""
)

patterns = (
    (
        r"(^|\s)rm\s+-[^\n]*r[^\n]*f[^\n]*\s+/(?:\s|$)",
        "recursive deletion of filesystem root",
    ),
    (r"(^|\s)(mkfs(?:\.[a-z0-9]+)?|wipefs)\s+", "filesystem destruction"),
    (
        r"(^|\s)(blkdiscard|cryptsetup\s+(?:erase|luksErase)|sgdisk\s+--zap-all)\b",
        "storage metadata destruction",
    ),
    (r"(^|\s)dd\s+[^\n]*\bof=/dev/", "raw device overwrite"),
    (
        r"curl[^\n|]*\|\s*(?:sudo\s+)?(?:sh|bash)\b",
        "execute unreviewed network content",
    ),
    (
        r"wget[^\n|]*\|\s*(?:sudo\s+)?(?:sh|bash)\b",
        "execute unreviewed network content",
    ),
    (r"chmod\s+-R\s+777\s+/(?:\s|$)", "world-writable filesystem root"),
    (
        r"(?:rm|truncate|shred)[^\n]*(?:audit/events|audit\.log|knowledge\.db|backup|snapshots)",
        "audit, knowledge, backup, or recovery destruction",
    ),
    (
        r"(?:auditctl\s+-e\s*0|systemctl\s+(?:disable|mask|stop)\s+auditd)",
        "audit control disablement",
    ),
    (
        r"(?:cat|cp|scp|rsync|tar|zip)[^\n]*(?:/etc/shadow|/\.ssh/(?:id_[^/\s]+|[^/\s]+\.pem))",
        "credential or private-key export",
    ),
    (
        r"(?:>|\btee\b)[^\n]*(?:policy/policy\.json|hooks/hooks\.json)",
        "runtime policy overwrite",
    ),
)
if tool in {"Bash", "exec_command"}:
    for pattern, reason in patterns:
        if re.search(pattern, command, re.IGNORECASE):
            deny(f"Jarvis blocked {reason}.")
            raise SystemExit(0)

print("{}")
