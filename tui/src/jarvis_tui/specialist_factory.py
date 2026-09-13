"""Fail-closed specialist proposal builder used by the Architect workflow."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

MAX_PROMPT_BYTES = 8_000
ALLOWED_TOOLS = frozenset(
    {
        "read_project",
        "query_knowledge",
        "inspect_host_read_only",
        "generate_specialist",
        "run_tests_in_worktree",
    }
)


def build_specialist_proposal(
    *,
    specialist_id: str,
    display_name: str,
    purpose: str,
    prompt: str,
    knowledge_kinds: tuple[str, ...] = ("facts", "sources", "decisions", "lessons"),
    allowed_tools: tuple[str, ...] = (
        "read_project",
        "query_knowledge",
        "inspect_host_read_only",
    ),
    model: str = "gpt-5.6-luna",
    reasoning_effort: str = "low",
) -> dict[str, Any]:
    """Create a reviewable descriptor; no files, plugins, or models are activated."""
    if not specialist_id.startswith("jarvis-") or any(
        ch not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for ch in specialist_id
    ):
        raise ValueError("specialist_id is invalid")
    if (
        not display_name.strip()
        or len(display_name) > 160
        or not purpose.strip()
        or len(purpose) > 500
    ):
        raise ValueError("specialist identity is invalid")
    if not prompt.strip() or len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
        raise ValueError("specialist prompt exceeds the bounded limit")
    if not set(allowed_tools) <= ALLOWED_TOOLS:
        raise ValueError("specialist tool is outside the allowlist")
    if reasoning_effort not in {"low", "medium", "high"}:
        raise ValueError("reasoning effort is invalid")
    descriptor = {
        "schema_version": 1,
        "id": specialist_id,
        "display_name": display_name.strip(),
        "version": "0.1.0-proposal",
        "purpose": purpose.strip(),
        "prompt": prompt.strip(),
        "knowledge_kinds": list(knowledge_kinds),
        "allowed_tools": list(allowed_tools),
        "mutations": "approval-gated-current-user-and-registered-host",
        "network": "official-allowlist",
        "model": model,
        "reasoning_effort": reasoning_effort,
        "status": "proposal",
        "activation": "requires_independent_review_and_user_approval",
    }
    canonical = json.dumps(
        descriptor, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    descriptor["proposal_digest"] = hashlib.sha256(canonical).hexdigest()
    return descriptor


def write_proposal(bundle_root: Path, descriptor: dict[str, Any]) -> Path:
    """Persist a proposal in the private runtime area without enabling it."""
    target_dir = bundle_root / "runtime/agent-proposals"
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = target_dir / f"{descriptor['id']}-{descriptor['proposal_digest'][:12]}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(descriptor, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(target)
    return target
