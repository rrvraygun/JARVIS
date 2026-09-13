"""Broker-owned specialist scope. Model arguments cannot select an identity."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from uuid import uuid4

from . import private_records
from .specialists import Specialist

COMMON = frozenset(
    {
        "capabilities",
        "list_actions",
        "get_action",
        "evaluate_policy",
        "action_digest",
        "verify_ledger",
        "knowledge_status",
    }
)
FORBIDDEN = frozenset(
    {
        "activate_lesson",
        "verify_approval",
        "append_audit_event",
        "record_decision",
        "record_command_attempt",
        "promote_lesson_candidate",
    }
)


def package_query_terms(value: object) -> set[str]:
    """Bind package observations to requested search terms, not prose wording."""
    from .package_knowledge import QUERY_STOPWORDS

    if not isinstance(value, str):
        return set()
    ignored = QUERY_STOPWORDS | {
        "if",
        "in",
        "installed",
        "present",
        "system",
        "sytem",
        "whether",
        "want",
    }
    aliases = {"node": "nodejs", "node.js": "nodejs", "go": "golang"}
    words = {word.casefold().strip(".,:;!?()[]{}") for word in value.split()}
    return {aliases.get(word, word) for word in words if len(word) > 1 and word not in ignored}


def publish(
    bundle: Path,
    specialist: Specialist,
    task_id: str,
    scope_id: str,
    *,
    project_roots: tuple[str, ...] = (),
    evidence_tools: tuple[str, ...] = (),
    evidence_arguments: dict[str, object] | None = None,
) -> None:
    if len(scope_id) != 32 or any(c not in "0123456789abcdef" for c in scope_id):
        raise ValueError("invalid_scope_id")
    root = bundle / "runtime/tool-scope"
    name = uuid4().hex + ".json"
    private_records.write_once(
        root,
        name,
        {
            "generation": uuid4().hex,
            "controller_pid": os.getpid(),
            "controller_start": Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19],
            "project_root_digests": [
                hashlib.sha256(root.encode()).hexdigest() for root in project_roots
            ],
            "evidence_tools": list(evidence_tools),
            "evidence_argument_digests": {
                key: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
                for key, value in (evidence_arguments or {}).items()
            },
            "package_query_term_digests": sorted(
                hashlib.sha256(term.encode()).hexdigest()
                for term in package_query_terms((evidence_arguments or {}).get("query"))
            ),
            "specialist": specialist.id,
            "specialist_version": specialist.version,
            "network": specialist.network,
            "mutations": specialist.mutations,
            "specialist_digest": hashlib.sha256(
                json.dumps(specialist.to_dict(), sort_keys=True).encode()
            ).hexdigest(),
            "task_id": task_id,
            "expires_at": time.time() + 600,
            "allowed": sorted((set(specialist.allowed_tools) | COMMON) - FORBIDDEN),
        },
    )
    fd = private_records.directory(root)
    try:
        os.replace(name, scope_id + ".json", src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        os.close(fd)


def allowed(bundle: Path, scope_id: str) -> frozenset[str]:
    try:
        scope = private_records.read(bundle / "runtime/tool-scope", scope_id + ".json", 16000)
        if (
            not isinstance(scope.get("expires_at"), (float, int))
            or not time.time() < scope["expires_at"] <= time.time() + 601
        ):
            return frozenset()
        pid = scope.get("controller_pid")
        if not isinstance(pid, int) or pid <= 0:
            return frozenset()
        start = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
        if start != scope.get("controller_start"):
            return frozenset()
        names = scope.get("allowed")
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            return frozenset()
        return frozenset(names) - FORBIDDEN
    except (OSError, ValueError, IndexError):
        return frozenset()


def revoke(bundle: Path, scope_id: str) -> None:
    if not scope_id:
        return
    try:
        fd = private_records.directory(bundle / "runtime/tool-scope", create=False)
        try:
            os.unlink(scope_id + ".json", dir_fd=fd)
            os.fsync(fd)
        finally:
            os.close(fd)
    except FileNotFoundError:
        pass


def generation(bundle: Path, scope_id: str) -> str:
    if not allowed(bundle, scope_id):
        raise ValueError("observation_scope_expired")
    scope = private_records.read(bundle / "runtime/tool-scope", scope_id + ".json", 16000)
    value = scope.get("generation")
    if not isinstance(value, str) or len(value) != 32:
        raise ValueError("observation_generation_missing")
    return value


def note_observation(
    bundle: Path,
    scope_id: str,
    tool: str,
    arguments: dict[str, object] | None = None,
    *,
    expected_generation: str | None = None,
) -> None:
    scope = private_records.read(bundle / "runtime/tool-scope", scope_id + ".json", 16000)
    if expected_generation is not None and scope.get("generation") != expected_generation:
        raise ValueError("observation_generation_changed")
    if tool not in allowed(bundle, scope_id):
        raise ValueError("observation_scope_expired")
    actual = arguments or {}
    required_tools = scope.get("evidence_tools", [])
    if required_tools and tool not in required_tools:
        return
    for key, value in scope.get("evidence_argument_digests", {}).items():
        if (
            hashlib.sha256(json.dumps(actual.get(key), sort_keys=True).encode()).hexdigest()
            == value
        ):
            continue
        query_terms = {
            hashlib.sha256(term.encode()).hexdigest()
            for term in package_query_terms(actual.get(key))
        }
        if not (
            key == "query"
            and tool in {"package_search", "package_catalog", "inspect_packages"}
            and query_terms
            and query_terms == set(scope.get("package_query_term_digests", []))
        ):
            return
    if (
        tool in {"package_search", "package_catalog", "inspect_packages"}
        and actual.get("refresh", True) is not True
    ):
        return
    root = bundle / "runtime/tool-evidence"
    name = uuid4().hex + ".json"
    private_records.write_once(
        root,
        name,
        {
            "scope_id": scope_id,
            "generation": scope["generation"],
            "task_id": scope["task_id"],
            "tool": tool,
            "arguments_digest": hashlib.sha256(
                json.dumps(actual, sort_keys=True).encode()
            ).hexdigest(),
            "observed_at": time.time(),
        },
    )
    fd = private_records.directory(root)
    try:
        os.replace(name, scope_id + ".json", src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        os.close(fd)


def has_observation(bundle: Path, scope_id: str, task_id: str) -> bool:
    try:
        record = private_records.read(bundle / "runtime/tool-evidence", scope_id + ".json", 16000)
        return (
            record.get("scope_id") == scope_id
            and record.get("generation") == generation(bundle, scope_id)
            and record.get("task_id") == task_id
            and 0 <= time.time() - record["observed_at"] <= 600
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False
