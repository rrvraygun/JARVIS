#!/usr/bin/env python3
"""Minimal dependency-free stdio MCP control-plane server."""

from __future__ import annotations

import importlib.util
import json
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCOPE_ID = sys.argv[2] if len(sys.argv) == 3 and sys.argv[1] == "--scope-id" else ""
spec = importlib.util.spec_from_file_location("jarvisctl", ROOT / "scripts/jarvisctl.py")
ctl = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(ctl)
knowledge_spec = importlib.util.spec_from_file_location(
    "knowledge_store", ROOT / "scripts/knowledge_store.py"
)
knowledge = importlib.util.module_from_spec(knowledge_spec)
assert knowledge_spec.loader
knowledge_spec.loader.exec_module(knowledge)
power_spec = importlib.util.spec_from_file_location(
    "power_tools", ROOT.parent / "jarvis-power-expert/scripts/power_tools.py"
)
power_tools = importlib.util.module_from_spec(power_spec)
assert power_spec.loader
power_spec.loader.exec_module(power_tools)
health_spec = importlib.util.spec_from_file_location(
    "health_tools", ROOT / "scripts/health_tools.py"
)
health_tools = importlib.util.module_from_spec(health_spec)
assert health_spec.loader
health_spec.loader.exec_module(health_tools)
extended_spec = importlib.util.spec_from_file_location(
    "extended_tools", ROOT / "scripts/extended_tools.py"
)
extended_tools = importlib.util.module_from_spec(extended_spec)
assert extended_spec.loader
extended_spec.loader.exec_module(extended_tools)
github_spec = importlib.util.spec_from_file_location(
    "github_tools", ROOT.parent / "jarvis-github-agent/scripts/github_tools.py"
)
github_tools = importlib.util.module_from_spec(github_spec)
assert github_spec.loader
github_spec.loader.exec_module(github_tools)
sys.path.insert(0, str(ROOT.parent.parent / "tui/src"))
from jarvis_tui import private_records  # noqa: E402
from jarvis_tui.local_control import ReadOnlyLocalControl  # noqa: E402
from jarvis_tui.operation_workflow import OperationWorkflow  # noqa: E402
from jarvis_tui.recovery_plan import prepare as prepare_recovery_plan  # noqa: E402
from jarvis_tui.tool_scope import allowed as scoped_tools  # noqa: E402

package_reader = ReadOnlyLocalControl(ROOT.parent.parent)
operations = OperationWorkflow(ROOT.parent.parent)


TOOLS = [
    {
        "name": "recovery_plan",
        "description": "Prepare a non-executable five-boundary Restic recovery plan bound to an observed external volume. It never opens, repairs or writes the repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_uuid": {"type": "string"},
                "mountpoint": {"type": "string"},
                "repository_prefix": {"type": "string"},
                "destination": {"type": "string"},
            },
            "required": ["device_uuid", "mountpoint", "repository_prefix", "destination"],
            "additionalProperties": False,
        },
    },
    {
        "name": "operation_plan",
        "description": "Prepare only; never execute or approve. Development: check/build/test/fmt/clippy "
        "on an absolute Cargo project, or dependencies with arguments.files "
        "(Cargo.toml/Cargo.lock text). Recovery: backup/restore of a text project to "
        "arguments.destination (new absolute directory). Health: restart/enable/disable of "
        "exact unit.service. Network: configure an observed connection UUID with "
        "arguments.dns (IPv4 list), or external_check of a canonical IP with "
        "arguments.port. Security: selinux restores one absolute file default label; "
        "firewall uses target zone/service and arguments.state present/absent. Updates and "
        "boot accept arguments.request with an exact separately root-reviewed helper request; without it they remain blocked. Root helpers must be installed and independently authorized with current R2 evidence. Development fetch_dependency reviews one locked package/version HTTPS download; Cargo operations may consume a complete verified downloads ID list offline. Development apply_dependencies accepts source_operation from a verified dependencies copy and reviews replacement of existing manifests in the original. Development command accepts arguments.argv with an exact /usr/bin executable and arguments, inside the same offline read-only project sandbox. A user-selected normal terminal requires a new review in the TUI. Review the returned ID in its TUI view.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "enum": ["development", "health", "network", "security", "recovery"],
                },
                "operation": {
                    "type": "string",
                    "enum": [
                        "check",
                        "build",
                        "test",
                        "fmt",
                        "clippy",
                        "dependencies",
                        "apply_dependencies",
                        "fetch_dependency",
                        "command",
                        "backup",
                        "restore",
                        "restart",
                        "enable",
                        "disable",
                        "configure",
                        "external_check",
                        "selinux",
                        "firewall",
                        "updates",
                        "boot",
                    ],
                },
                "target": {"type": "string"},
                "arguments": {
                    "type": "object",
                    "properties": {
                        "request": {
                            "type": "object",
                            "description": "Exact privileged request prepared and reviewed independently; root approval and R2 attestation are required outside model arguments.",
                        },
                        "package": {"type": "string"},
                        "version": {"type": "string"},
                        "downloads": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 64,
                        },
                        "source_operation": {"type": "string"},
                        "argv": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 128,
                        },
                        "files": {
                            "type": "object",
                            "properties": {
                                "Cargo.toml": {"type": "string"},
                                "Cargo.lock": {"type": "string"},
                            },
                            "additionalProperties": False,
                        },
                        "destination": {"type": "string"},
                        "dns": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                        "state": {"enum": ["present", "absent"]},
                        "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                    },
                    "additionalProperties": False,
                },
            },
            "required": ["domain", "operation", "target"],
            "additionalProperties": False,
        },
    },
    {
        "name": "operation_result",
        "description": "Read a stored operation result and independent verification record; does not assert current host state.",
        "inputSchema": {
            "type": "object",
            "properties": {"operation_id": {"type": "string"}},
            "required": ["operation_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "operation_recovery_plan",
        "description": "Prepare a separately reviewed exact Cargo-file recovery proposal. Does not restore anything.",
        "inputSchema": {
            "type": "object",
            "properties": {"operation_id": {"type": "string"}},
            "required": ["operation_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "network_inventory",
        "description": "Inspect local network interfaces, routes, DNS, NetworkManager, and listening sockets. Read-only; no external connections.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "security_inventory",
        "description": "Inspect bounded local SELinux, firewall, Secure Boot, listening-service, and failed-service evidence. Read-only.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "recovery_inventory",
        "description": "Inspect bounded local mounts, snapshots, Btrfs, Snapper, and boot history evidence. Read-only.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "health_inventory",
        "description": "Collect bounded Fedora workstation performance, service, storage, thermal, and local-network evidence. Read-only.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "health_telemetry",
        "description": "Read passive current load, memory pressure, and thermal telemetry. Read-only.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "health_processes",
        "description": "Collect bounded CPU/memory process evidence. Read-only.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "health_services",
        "description": "Inspect failed and running systemd services. Read-only.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "health_storage",
        "description": "Inspect bounded filesystems, mounts, and block devices. Read-only.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "health_logs",
        "description": "Read up to 100 sanitized journal lines for one exact systemd service. Read-only.",
        "inputSchema": {
            "type": "object",
            "required": ["service"],
            "properties": {"service": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "development_toolchains",
        "description": "Detect common compiler and runtime versions, including Rust and Cargo. Read-only.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "development_project_inspect",
        "description": "Inspect bounded project manifests and identify project languages/build systems. Read-only.",
        "inputSchema": {
            "type": "object",
            "required": ["project_root"],
            "properties": {"project_root": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "github_inspect",
        "description": "Inspect bounded local Git status, branch, diffs, ignored paths, conflicts, recent commits, and remotes. Read-only; no GitHub network access.",
        "inputSchema": {
            "type": "object",
            "required": ["project_root"],
            "properties": {"project_root": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "github_preflight",
        "description": "Inspect local publication risks: conflicts, changed paths, likely secret-bearing filenames, and large files. Read-only; file contents and GitHub network access are excluded.",
        "inputSchema": {
            "type": "object",
            "required": ["project_root"],
            "properties": {"project_root": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "github_operation_plan",
        "description": "Prepare one exact GitHub operation plan. It never executes, contacts GitHub, commits, pushes, merges, creates repositories, or changes settings.",
        "inputSchema": {
            "type": "object",
            "required": ["project_root", "operation"],
            "properties": {
                "project_root": {"type": "string"},
                "operation": {
                    "type": "string",
                    "enum": [
                        "initialize_repository",
                        "clone_repository",
                        "create_repository",
                        "create_branch",
                        "commit",
                        "pull",
                        "push",
                        "create_pull_request",
                        "merge_pull_request",
                        "create_issue",
                        "create_release",
                        "download_artifact",
                        "rerun_workflow",
                        "delete_branch",
                        "force_push",
                        "modify_repository_settings",
                        "delete_repository",
                    ],
                },
                "target": {"type": "string"},
                "arguments": {
                    "type": "object",
                    "properties": {
                        "branch": {"type": "string"},
                        "name": {"type": "string"},
                        "message": {"type": "string"},
                        "paths": {"type": "array", "items": {"type": "string"}, "maxItems": 100},
                        "remote": {"type": "string"},
                        "ref": {"type": "string"},
                        "set_upstream": {"type": "boolean"},
                        "visibility": {"enum": ["public", "private", "internal"]},
                        "description": {"type": "string"},
                        "push": {"type": "boolean"},
                        "destination": {"type": "string"},
                        "base": {"type": "string"},
                        "head": {"type": "string"},
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "draft": {"type": "boolean"},
                        "number": {"type": "string"},
                        "method": {"enum": ["merge", "squash", "rebase"]},
                        "delete_branch": {"type": "boolean"},
                        "labels": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
                        "tag": {"type": "string"},
                        "notes": {"type": "string"},
                        "assets": {"type": "array", "items": {"type": "string"}, "maxItems": 50},
                        "run_id": {"type": "string"},
                        "artifact": {"type": "string"},
                        "failed_only": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "package_catalog",
        "description": "Read the bounded installed and cached Fedora package catalog. This is read-only and never installs or removes packages.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "refresh": {"type": "boolean"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "package_search",
        "description": "Search bounded installed and cached Fedora package evidence and return structured matches. This is read-only.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}, "refresh": {"type": "boolean"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "inspect_packages",
        "description": "Compatibility alias for bounded installed and cached Fedora package inspection. This is read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "refresh": {"type": "boolean"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "power_inventory",
        "description": "Read the bounded sanitized Power inventory. This never mutates the host.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "inspect_power_inventory",
        "description": "Compatibility alias for the bounded sanitized Power inventory reader. This never mutates the host.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "power_telemetry",
        "description": "Read bounded passive Power telemetry. This never mutates the host.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "inspect_power_telemetry",
        "description": "Compatibility alias for bounded passive Power telemetry. This never mutates the host.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "power_retrieve_evidence",
        "description": "Retrieve bounded Power history and verified application evidence.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "power_capabilities",
        "description": "List reviewed Power controls and observed recommendation-only writable controls.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "power_profile_plan",
        "description": "Validate and create an exact paired AC/battery Power profile draft. This never applies it.",
        "inputSchema": {
            "type": "object",
            "required": ["name", "goal", "variants"],
            "properties": {
                "profile_id": {"type": "string"},
                "name": {"type": "string"},
                "goal": {"enum": ["battery", "performance", "quiet", "thermal", "balanced"]},
                "variants": {"type": "object"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "power_profile_apply",
        "description": "Validate an exact Power profile application proposal and return the approval requirements. It never bypasses Jarvis or OS authorization.",
        "inputSchema": {
            "type": "object",
            "required": ["profile_digest", "selected_variant", "pre_state", "requested"],
            "properties": {
                "profile_digest": {"type": "string"},
                "selected_variant": {"enum": ["ac", "battery"]},
                "pre_state": {"type": "object"},
                "requested": {"type": "object"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "power_validate",
        "description": "Refresh and validate an exact Power pre-state without mutating the host.",
        "inputSchema": {
            "type": "object",
            "required": ["pre_state", "requested"],
            "properties": {"pre_state": {"type": "object"}, "requested": {"type": "object"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "power_verify",
        "description": "Independently compare current Power values with requested values.",
        "inputSchema": {
            "type": "object",
            "required": ["requested"],
            "properties": {"requested": {"type": "object"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "power_profile_rollback",
        "description": "Prepare a recovery proposal for a Power profile result. It never executes rollback.",
        "inputSchema": {
            "type": "object",
            "required": ["record_digest"],
            "properties": {"record_digest": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "power_recovery_plan",
        "description": "Prepare bounded recovery guidance for a Power result; it never executes recovery.",
        "inputSchema": {
            "type": "object",
            "required": ["record_digest"],
            "properties": {"record_digest": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "stage_registered_power_action",
        "description": "Stage a registered Power action for exact Jarvis approval. It never executes an unregistered command.",
        "inputSchema": {
            "type": "object",
            "properties": {"action": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "capabilities",
        "description": "List registered Jarvis capabilities and safe defaults.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "list_actions",
        "description": "List versioned Jarvis catalog actions and their availability. This cannot execute an action.",
        "inputSchema": {
            "type": "object",
            "properties": {"capability": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_action",
        "description": "Read one exact Jarvis catalog action. This cannot execute an action.",
        "inputSchema": {
            "type": "object",
            "required": ["action_id"],
            "properties": {"action_id": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "evaluate_policy",
        "description": "Evaluate an exact administration action context without executing it.",
        "inputSchema": {
            "type": "object",
            "required": ["context"],
            "properties": {"context": {"type": "object"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "action_digest",
        "description": "Create the canonical redacted digest bound into an approval.",
        "inputSchema": {
            "type": "object",
            "required": ["context"],
            "properties": {"context": {"type": "object"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "verify_approval",
        "description": "Verify approval digest, targets, decision, and expiry against an action.",
        "inputSchema": {
            "type": "object",
            "required": ["context", "approval"],
            "properties": {
                "context": {"type": "object"},
                "approval": {"type": "object"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "append_audit_event",
        "description": "Redact and append an event to a hash-chained ledger under the configured store.",
        "inputSchema": {
            "type": "object",
            "required": ["event"],
            "properties": {"event": {"type": "object"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "verify_ledger",
        "description": "Verify the complete hash chain of the configured audit ledger.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "knowledge_status",
        "description": "Verify the local immutable knowledge database without inspecting the host.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "query_knowledge",
        "description": "Search current Fedora facts, documentation, attempts, errors, lessons, or decision summaries.",
        "inputSchema": {
            "type": "object",
            "required": ["kind", "text"],
            "properties": {
                "kind": {
                    "enum": [
                        "facts",
                        "sources",
                        "attempts",
                        "errors",
                        "lessons",
                        "decisions",
                    ]
                },
                "text": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "record_command_attempt",
        "description": "Redact and record exactly one command attempt and create an error observation for failure or unexpected behavior. This does not execute the command.",
        "inputSchema": {
            "type": "object",
            "required": ["attempt"],
            "properties": {"attempt": {"type": "object"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "record_decision",
        "description": "Record an auditable decision summary without private chain-of-thought. This does not execute an action.",
        "inputSchema": {
            "type": "object",
            "required": ["decision"],
            "properties": {"decision": {"type": "object"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "create_lesson_draft",
        "description": "Create an inactive lesson draft from reviewed evidence; this cannot activate the lesson.",
        "inputSchema": {
            "type": "object",
            "required": ["lesson"],
            "properties": {"lesson": {"type": "object"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "record_lesson_evidence",
        "description": "Add verified success or conflict evidence to a lesson; this cannot activate the lesson.",
        "inputSchema": {
            "type": "object",
            "required": ["evidence"],
            "properties": {"evidence": {"type": "object"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "revise_error",
        "description": "Append a diagnosis or resolution revision linked to a verified working attempt; never edits the original error.",
        "inputSchema": {
            "type": "object",
            "required": ["error_id", "revision"],
            "properties": {
                "error_id": {"type": "string"},
                "revision": {"type": "object"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "promote_lesson_candidate",
        "description": "Mark a draft lesson as a candidate only after the deterministic evidence threshold; user approval is still required for activation.",
        "inputSchema": {
            "type": "object",
            "required": ["lesson_id"],
            "properties": {"lesson_id": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "activate_lesson",
        "description": "Activate one promotion candidate. Codex configuration must force a direct user approval prompt for this tool.",
        "inputSchema": {
            "type": "object",
            "required": ["lesson_id", "decision_id"],
            "properties": {
                "lesson_id": {"type": "string"},
                "decision_id": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
]


def content(value: Any, error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(value, indent=2, sort_keys=True)}],
        "isError": error,
    }


def store_root() -> Path:
    import os

    configured = os.environ.get("JARVIS_STORE")
    if not configured:
        raise ValueError("JARVIS_STORE is required")
    path = Path(configured).resolve()
    ctl.init_store(path)
    return path


def knowledge_db() -> Path:
    path = store_root() / "knowledge/knowledge.db"
    knowledge.init_database(path)
    return path


def dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name not in scoped_tools(ROOT.parent.parent, SCOPE_ID):
        return content({"error": "tool_not_authorized_for_selected_specialist"}, True)
    definition = next((tool for tool in TOOLS if tool["name"] == name), None)
    if definition is None or not isinstance(args, dict):
        return content({"error": "invalid_tool_request"}, True)
    schema = definition["inputSchema"]
    if set(args) - set(schema.get("properties", {})) or set(schema.get("required", [])) - set(args):
        return content({"error": "invalid_tool_arguments"}, True)
    if name == "recovery_plan":
        try:
            return content(prepare_recovery_plan(**args))
        except (OSError, TypeError, ValueError):
            return content(
                {"error": "recovery_plan_unavailable", "execution_authorized": False}, True
            )

    project_target = (
        args.get("project_root")
        if name
        in {
            "development_project_inspect",
            "github_inspect",
            "github_preflight",
            "github_operation_plan",
        }
        else args.get("target")
        if name == "operation_plan" and args.get("domain") in {"development", "recovery"}
        else None
    )
    if project_target is not None:
        import hashlib

        scope = private_records.read(
            ROOT.parent.parent / "runtime/tool-scope", SCOPE_ID + ".json", 16000
        )
        if not isinstance(project_target, str) or hashlib.sha256(
            project_target.encode()
        ).hexdigest() not in scope.get("project_root_digests", []):
            return content(
                {"error": "project_outside_admitted_scope", "execution_authorized": False}, True
            )
    if name == "operation_plan":
        scope = private_records.read(
            ROOT.parent.parent / "runtime/tool-scope", SCOPE_ID + ".json", 16000
        )
        if (
            args.get("operation") in {"fetch_dependency", "external_check"}
            and scope.get("network") != "official-allowlist"
        ):
            return content({"error": "specialist_network_policy_blocks_operation"}, True)
        if args.get("operation") in {
            "apply_dependencies",
            "restart",
            "enable",
            "disable",
            "configure",
            "selinux",
            "firewall",
            "updates",
            "boot",
        } and scope.get("mutations") not in {
            "registered-actions-only",
            "approval-gated-current-user-and-registered-host",
        }:
            return content({"error": "specialist_mutation_policy_blocks_operation"}, True)
        domain = {
            "jarvis-cargo-builder": "development",
            "jarvis-system-health": "health",
            "jarvis-network-specialist": "network",
            "jarvis-security-specialist": "security",
            "jarvis-recovery-specialist": "recovery",
        }.get(scope.get("specialist"))
        if args.get("domain") != domain:
            return content({"error": "specialist_domain_mismatch"}, True)
        return content(
            operations.propose(
                args["domain"], args["operation"], args["target"], args.get("arguments")
            )
        )
    if name in {"operation_result", "operation_recovery_plan"}:
        plan = operations.load(args["operation_id"])
        if name == "operation_recovery_plan":
            return content(operations.recovery_proposal(plan["id"]))
        return content(operations.result(plan["id"]))
    if name in {"network_inventory", "security_inventory", "recovery_inventory"}:
        try:
            return content(getattr(extended_tools, name)())
        except (OSError, RuntimeError, TypeError, ValueError, TimeoutError):
            return content({"error": f"{name}_failed", "read_only": True}, True)
    if name in {
        "health_inventory",
        "health_telemetry",
        "health_processes",
        "health_services",
        "health_storage",
        "development_toolchains",
    }:
        try:
            reader = getattr(health_tools, name)
            return content(reader())
        except (OSError, RuntimeError, TypeError, ValueError, TimeoutError):
            return content({"error": f"{name}_failed", "read_only": True}, True)
    if name == "health_logs":
        service = args.get("service")
        if not isinstance(service, str):
            return content({"error": "invalid_service", "read_only": True}, True)
        try:
            return content(health_tools.health_logs(service))
        except (OSError, RuntimeError, TypeError, ValueError, TimeoutError):
            return content({"error": "health_logs_failed", "read_only": True}, True)
    if name == "development_project_inspect":
        root = args.get("project_root")
        if not isinstance(root, str):
            return content({"error": "invalid_project_root"}, True)
        try:
            return content(health_tools.development_project_inspect(root))
        except (OSError, RuntimeError, TypeError, ValueError, TimeoutError):
            return content({"error": "development_project_inspect_failed", "read_only": True}, True)
    if name in {"github_inspect", "github_preflight", "github_operation_plan"}:
        root = args.get("project_root")
        try:
            if name == "github_inspect":
                return content(github_tools.github_inspect(root))
            if name == "github_preflight":
                return content(github_tools.github_preflight(root))
            operation = args.get("operation")
            operation_target = str(Path(root).resolve())
            arguments = dict(args.get("arguments") or {})
            if args.get("target") is not None:
                arguments["requested_target"] = args.get("target")
            if not isinstance(operation, str) or not isinstance(arguments, dict):
                return content({"error": "invalid_github_operation_plan"}, True)
            return content(operations.propose("github", operation, operation_target, arguments))
        except (OSError, RuntimeError, TypeError, ValueError, TimeoutError):
            return content(
                {
                    "error": f"{name}_failed",
                    "read_only": name != "github_operation_plan",
                },
                True,
            )
    if name in {"package_catalog", "package_search", "inspect_packages"}:
        query = args.get("query", "")
        if not isinstance(query, str) or len(query) > 500:
            return content({"error": "invalid_package_query"}, True)
        refresh = args.get("refresh", True)
        if not isinstance(refresh, bool):
            return content({"error": "invalid_package_refresh"}, True)
        try:
            return content(package_reader.inspect_packages(query, refresh=refresh))
        except (OSError, RuntimeError, TypeError, ValueError, TimeoutError):
            return content({"error": "package_catalog_request_failed"}, True)
    if name in {
        "power_inventory",
        "inspect_power_inventory",
        "power_telemetry",
        "inspect_power_telemetry",
        "power_retrieve_evidence",
        "power_capabilities",
        "power_profile_plan",
        "power_profile_apply",
        "power_validate",
        "power_verify",
        "power_profile_rollback",
        "power_recovery_plan",
        "stage_registered_power_action",
    }:
        try:
            return content(power_tools.power_tool_call(name, args))
        except (OSError, TypeError, ValueError):
            return content({"error": "power_tool_request_failed"}, True)
    if name == "capabilities":
        return content({"capabilities": list(ctl.capabilities().values())})
    if name == "list_actions":
        items = list(ctl.actions().values())
        if args.get("capability"):
            items = [item for item in items if item.get("capability") == args["capability"]]
        return content({"actions": items})
    if name == "get_action":
        action = ctl.actions().get(args["action_id"])
        if action is None:
            return content({"error": "unknown_action", "action_id": args["action_id"]}, True)
        return content({"action": action})
    if name == "evaluate_policy":
        return content(ctl.policy(args["context"]))
    if name == "action_digest":
        return content({"action_digest": ctl.action_digest(args["context"])})
    if name == "verify_approval":
        result = ctl.verify_approval(args["context"], args["approval"])
        return content(result, not result["valid"])
    if name == "append_audit_event":
        root = store_root()
        event_path = root / "locks/pending-event.json"
        event_path.write_text(json.dumps(args["event"]), encoding="utf-8")
        try:
            result = ctl.append_event(event_path, root / "audit/events.jsonl")
        finally:
            event_path.unlink(missing_ok=True)
        return content(result)
    if name == "verify_ledger":
        ledger = store_root() / "audit/events.jsonl"
        if not ledger.exists():
            return content({"valid": True, "events": 0, "tail_hash": ctl.ZERO_HASH})
        valid, count, tail = ctl.verify_ledger(ledger)
        return content({"valid": valid, "events": count, "tail_hash": tail}, not valid)
    if name in {
        "knowledge_status",
        "query_knowledge",
        "record_command_attempt",
        "record_decision",
        "create_lesson_draft",
        "record_lesson_evidence",
        "revise_error",
        "promote_lesson_candidate",
        "activate_lesson",
    }:
        with closing(knowledge.connect(knowledge_db())) as connection, connection:
            if name == "knowledge_status":
                result = knowledge.verify(connection)
            elif name == "query_knowledge":
                result = {
                    "results": knowledge.query(
                        connection,
                        args["kind"],
                        args["text"],
                        int(args.get("limit", 20)),
                    )
                }
            elif name == "record_command_attempt":
                result = knowledge.add_attempt(connection, args["attempt"])
            elif name == "record_decision":
                result = knowledge.add_decision(connection, args["decision"])
            elif name == "create_lesson_draft":
                lesson = dict(args["lesson"])
                lesson["status"] = "draft"
                result = knowledge.append_lesson_revision(connection, lesson)
            elif name == "record_lesson_evidence":
                result = knowledge.add_lesson_evidence(connection, args["evidence"])
            elif name == "revise_error":
                result = knowledge.revise_error(connection, args["error_id"], args["revision"])
            elif name == "promote_lesson_candidate":
                result = knowledge.revise_lesson(
                    connection,
                    args["lesson_id"],
                    "candidate",
                    "automated evidence threshold met",
                )
            else:
                result = knowledge.revise_lesson(
                    connection,
                    args["lesson_id"],
                    "approved",
                    "explicit MCP user approval",
                    {
                        "decision_id": args["decision_id"],
                        "approver": "user",
                        "decision": "approved",
                    },
                )
            return content(result, isinstance(result, dict) and result.get("valid") is False)
    return content({"error": "unknown_tool"}, True)


def call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    from jarvis_tui.tool_scope import generation

    try:
        admitted_generation = generation(ROOT.parent.parent, SCOPE_ID)
        result = dispatch(name, args)
        if generation(ROOT.parent.parent, SCOPE_ID) != admitted_generation:
            raise ValueError("tool_scope_changed_during_call")
    except (OSError, ValueError, TypeError, KeyError, TimeoutError) as exc:
        import re

        reason = str(exc)
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,100}", reason):
            reason = type(exc).__name__
        return content(
            {"error": "tool_request_stopped", "reason": reason, "execution_authorized": False}, True
        )
    observation_tools = {
        "health_inventory",
        "health_telemetry",
        "health_processes",
        "health_services",
        "health_storage",
        "health_logs",
        "development_toolchains",
        "development_project_inspect",
        "github_inspect",
        "github_preflight",
        "network_inventory",
        "security_inventory",
        "recovery_inventory",
        "package_catalog",
        "package_search",
        "inspect_packages",
        "power_inventory",
        "inspect_power_inventory",
        "power_telemetry",
        "inspect_power_telemetry",
    }
    if name in observation_tools and not result.get("isError"):
        from jarvis_tui.tool_scope import note_observation

        payload = json.loads(result["content"][0]["text"])
        if (
            isinstance(payload, dict)
            and payload.get("stale") is not True
            and payload.get("available") is not False
            and not payload.get("error")
        ):
            try:
                note_observation(
                    ROOT.parent.parent,
                    SCOPE_ID,
                    name,
                    args,
                    expected_generation=admitted_generation,
                )
            except (OSError, ValueError):
                return content({"error": "observation_scope_changed"}, True)
    return result


def respond(identifier: Any, result: Any = None, error: Any = None) -> None:
    payload = {"jsonrpc": "2.0", "id": identifier}
    payload["error" if error is not None else "result"] = error if error is not None else result
    print(json.dumps(payload, separators=(",", ":")), flush=True)


while True:
    line = sys.stdin.readline(131073)
    if not line:
        break
    if len(line) > 131072:
        break
    try:
        request = json.loads(line)
        method = request.get("method")
        identifier = request.get("id")
        if method == "initialize":
            version = request.get("params", {}).get("protocolVersion", "2025-06-18")
            respond(
                identifier,
                {
                    "protocolVersion": version,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "jarvis-control", "version": "0.2.0"},
                },
            )
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            respond(
                identifier,
                {
                    "tools": [
                        tool
                        for tool in TOOLS
                        if tool["name"]
                        not in {
                            "activate_lesson",
                            "verify_approval",
                            "append_audit_event",
                            "record_decision",
                            "record_command_attempt",
                            "promote_lesson_candidate",
                        }
                    ]
                },
            )
        elif method == "tools/call":
            params = request.get("params", {})
            respond(identifier, call(params.get("name", ""), params.get("arguments", {})))
        elif identifier is not None:
            respond(identifier, error={"code": -32601, "message": "Method not found"})
    except Exception:
        if "identifier" in locals() and identifier is not None:
            respond(identifier, error={"code": -32000, "message": "request_failed"})
