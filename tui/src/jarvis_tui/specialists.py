"""Fail-closed loader for repository-local JARVIS specialist descriptors."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_PROMPT_CHARS = 8_000
MAX_PURPOSE_CHARS = 500
VALID_MUTATION_BOUNDARIES = {
    "project-branch-only",
    "registered-actions-only",
    "approval-gated-current-user-and-registered-host",
}
VALID_NETWORK_POLICIES = {"offline", "official-allowlist"}
REGISTERED_TOOL_REFS = frozenset(
    {
        "read_project",
        "query_knowledge",
        "inspect_host_read_only",
        "generate_specialist",
        "run_tests_in_worktree",
        "bash",
        "read",
        "write",
        "edit",
        "grep",
        "inspect_power_inventory",
        "inspect_packages",
        "read_local_docs",
        "official_docs_refresh_plan",
        "stage_registered_power_action",
        "power_inventory",
        "power_telemetry",
        "power_retrieve_evidence",
        "power_capabilities",
        "power_profile_plan",
        "power_profile_apply",
        "power_validate",
        "power_verify",
        "power_profile_rollback",
        "power_recovery_plan",
        "package_catalog",
        "package_search",
        "package_preview",
        "package_install",
        "package_remove",
        "package_recovery",
        "package_rollback",
        "health_inventory",
        "health_telemetry",
        "health_processes",
        "health_services",
        "health_storage",
        "health_logs",
        "operation_plan",
        "operation_result",
        "operation_recovery_plan",
        "development_toolchains",
        "development_project_inspect",
        "network_inventory",
        "security_inventory",
        "recovery_inventory",
        "recovery_plan",
    }
)


@dataclass(frozen=True)
class Specialist:
    id: str
    display_name: str
    version: str
    purpose: str
    prompt: str
    knowledge_kinds: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    mutations: str
    network: str
    status: str
    knowledge_sources: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    context_limit: int = 64_000
    retention: str = "bounded"
    selectable: bool = True
    source: str = ""

    def context_prompt(self) -> str:
        mutation_detail = (
            "Current-user-writable non-protected paths may be changed only through an exact "
            "reviewed operation and a fresh one-use user approval. Privileged changes require "
            "a registered target-specific helper and desktop authorization. Never request or "
            "treat session-wide approval as authority."
            if self.mutations == "approval-gated-current-user-and-registered-host"
            else self.mutations
        )
        return (
            f"Active JARVIS specialist: {self.display_name} ({self.version}).\n"
            f"Specialist purpose: {self.purpose}\n"
            f"Specialist instructions: {self.prompt}\n"
            f"Allowed tool classes: {list(self.allowed_tools)}\n"
            f"Knowledge sources: {list(self.knowledge_sources) or list(self.knowledge_kinds)}\n"
            f"Capabilities: {list(self.capabilities) or ['general conversation']}\n"
            f"Context policy: {self.retention}; limit={self.context_limit} characters\n"
            f"Mutation boundary: {self.mutations}. {mutation_detail}\n"
            f"Network boundary: {self.network}\n"
            "The user-selected specialist is authoritative; do not silently hand off to another specialist. "
            "If the request is outside this specialist's declared scope, explain the scope and ask the user "
            "to select an appropriate specialist."
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a complete editable definition without runtime-only source data."""
        return {
            "schema_version": 2,
            "id": self.id,
            "display_name": self.display_name,
            "version": self.version,
            "purpose": self.purpose,
            "prompt": self.prompt,
            "knowledge_kinds": list(self.knowledge_kinds),
            "knowledge_sources": list(self.knowledge_sources),
            "capabilities": list(self.capabilities),
            "allowed_tools": list(self.allowed_tools),
            "context_limit": self.context_limit,
            "retention": self.retention,
            "mutations": self.mutations,
            "network": self.network,
            "selectable": self.selectable,
            "status": self.status,
        }

    @classmethod
    def from_mapping(cls, value: dict[str, Any], *, source: str = "") -> Specialist:
        """Validate and load one descriptor from a plugin or active override."""
        if not isinstance(value, dict):
            raise ValueError("specialist descriptor must be an object")
        if value.get("schema_version") not in {1, 2}:
            raise ValueError("unsupported_or_disabled_specialist")
        required = {
            "id",
            "display_name",
            "version",
            "purpose",
            "prompt",
            "knowledge_kinds",
            "allowed_tools",
            "mutations",
            "network",
            "status",
        }
        if required - value.keys():
            raise ValueError("specialist descriptor is incomplete")
        if value.get("status") != "enabled":
            raise ValueError("unsupported_or_disabled_specialist")
        specialist_id = value.get("id")
        if not isinstance(specialist_id, str) or not specialist_id.startswith("jarvis-"):
            raise ValueError("specialist id is invalid")
        if any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for ch in specialist_id):
            raise ValueError("specialist id is invalid")
        display_name = value.get("display_name")
        purpose = value.get("purpose")
        prompt = value.get("prompt")
        if (
            not isinstance(display_name, str)
            or not display_name.strip()
            or len(display_name) > 160
            or not isinstance(purpose, str)
            or not purpose.strip()
            or len(purpose) > MAX_PURPOSE_CHARS
            or not isinstance(prompt, str)
            or not prompt.strip()
            or len(prompt) > MAX_PROMPT_CHARS
        ):
            raise ValueError("specialist descriptor exceeds bounds")
        knowledge_kinds = value.get("knowledge_kinds")
        allowed_tools = value.get("allowed_tools")
        if not isinstance(knowledge_kinds, list) or not all(
            isinstance(item, str) and item.strip() for item in knowledge_kinds
        ):
            raise ValueError("specialist knowledge kinds are invalid")
        if not isinstance(allowed_tools, list) or not all(
            isinstance(item, str) and item.strip() for item in allowed_tools
        ):
            raise ValueError("specialist tools are invalid")
        unknown_tools = sorted(set(allowed_tools) - REGISTERED_TOOL_REFS)
        if unknown_tools:
            raise ValueError("unregistered specialist tools: " + ", ".join(unknown_tools))
        if value.get("mutations") not in VALID_MUTATION_BOUNDARIES:
            raise ValueError("specialist mutation boundary is invalid")
        if value.get("network") not in VALID_NETWORK_POLICIES:
            raise ValueError("specialist network policy is invalid")
        knowledge_sources = value.get("knowledge_sources", [])
        capabilities = value.get("capabilities", [])
        if not isinstance(knowledge_sources, list) or not all(
            isinstance(item, str) and item.strip() for item in knowledge_sources
        ):
            raise ValueError("specialist knowledge sources are invalid")
        if not isinstance(capabilities, list) or not all(
            isinstance(item, str) and item.strip() for item in capabilities
        ):
            raise ValueError("specialist capabilities are invalid")
        context_limit = value.get("context_limit", 64_000)
        if (
            isinstance(context_limit, bool)
            or not isinstance(context_limit, int)
            or not 1_000 <= context_limit <= 64_000
        ):
            raise ValueError("specialist context limit is invalid")
        retention = value.get("retention", "bounded")
        if retention != "bounded":
            raise ValueError("specialist retention policy is invalid")
        selectable = value.get("selectable", True)
        if not isinstance(selectable, bool):
            raise ValueError("specialist selection policy is invalid")
        return cls(
            id=specialist_id,
            display_name=display_name.strip(),
            version=str(value["version"]),
            purpose=purpose.strip(),
            prompt=prompt.strip(),
            knowledge_kinds=tuple(knowledge_kinds),
            allowed_tools=tuple(allowed_tools),
            mutations=str(value["mutations"]),
            network=str(value["network"]),
            status="enabled",
            knowledge_sources=tuple(knowledge_sources),
            capabilities=tuple(capabilities),
            context_limit=context_limit,
            retention=retention,
            selectable=selectable,
            source=source,
        )


def _load(path: Path) -> Specialist:
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    return Specialist.from_mapping(value, source=str(path))


def load_specialists(bundle_root: Path) -> tuple[Specialist, ...]:
    found: list[Specialist] = []
    for path in sorted((bundle_root / "plugins").glob("*/specialist.json")):
        try:
            specialist = _load(path)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
        found.append(specialist)
    if not found:
        raise RuntimeError("no valid JARVIS specialist descriptors found")
    return tuple(sorted(found, key=lambda item: item.display_name.casefold()))
