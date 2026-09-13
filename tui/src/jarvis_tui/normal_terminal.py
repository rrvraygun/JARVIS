"""Separately reviewed ordinary commands with inherited terminal and environment."""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import secrets
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import private_records
from .operation_workflow import Approval, digest
from .terminal_safety import sanitize_and_redact_terminal_text


def available() -> bool:
    return all(
        stream is not None and stream.isatty()
        for stream in (sys.__stdin__, sys.__stdout__, sys.__stderr__)
    )


def _state(argv: list[str], cwd: str) -> dict[str, Any]:
    if os.geteuid() == 0:
        raise ValueError("normal_terminal_requires_nonroot_user")
    directory = Path(cwd)
    executable = Path(argv[0])
    if not directory.is_absolute() or not executable.is_absolute():
        raise ValueError("terminal_absolute_paths_required")
    if directory.resolve(strict=True) != directory or not directory.is_dir():
        raise ValueError("terminal_directory_ambiguous")
    resolved = executable.resolve(strict=True)
    info = resolved.stat()
    if not stat.S_ISREG(info.st_mode) or not os.access(resolved, os.X_OK):
        raise ValueError("terminal_executable_invalid")
    with resolved.open("rb") as stream:
        executable_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    directory_info = directory.stat()
    return {
        "uid": os.geteuid(),
        "gid": os.getegid(),
        "groups": sorted(os.getgroups()),
        "cwd_identity": [directory_info.st_dev, directory_info.st_ino],
        "executable": str(resolved),
        "executable_sha256": executable_hash,
    }


def execute_once(
    argv: list[str],
    *,
    cwd: str,
    environment: dict[str, str],
) -> dict[str, Any]:
    """Inherited stdio, no imposed runtime/resource timeout; called after reservation."""
    if not argv or not all(isinstance(item, str) and "\x00" not in item for item in argv):
        raise ValueError("terminal_argv_invalid")
    if not available():
        raise ValueError("visible_terminal_required")
    try:
        completed = subprocess.run(argv, cwd=cwd, env=environment, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "indeterminate", "attempts": 1, "error": type(exc).__name__}
    return {
        "status": "completed",
        "attempts": 1,
        "exit_code": completed.returncode,
        "goal_verified": False,
        "verification_scope": "foreground_process_exit_only",
    }


class NormalTerminalWorkflow:
    """Normal mode gets a new digest and a durable one-use reservation."""

    def __init__(self, bundle: Path):
        self.root = bundle / "runtime/normal-terminal"
        self._approvals: dict[str, Approval] = {}
        self._environments: dict[str, dict[str, str]] = {}
        self._environment_key = secrets.token_bytes(32)

    def _environment_digest(self, environment: dict[str, str]) -> str:
        return hmac.new(
            self._environment_key, json.dumps(environment, sort_keys=True).encode(), hashlib.sha256
        ).hexdigest()

    def propose(self, argv: list[str], cwd: str, source_operation: str) -> dict[str, Any]:
        if len(self._environments) >= 32:
            raise ValueError("too_many_pending_terminal_reviews")
        if (
            not isinstance(argv, list)
            or not 1 <= len(argv) <= 128
            or not all(isinstance(item, str) and "\x00" not in item for item in argv)
            or sum(len(item.encode()) for item in argv) > 16000
        ):
            raise ValueError("terminal_argv_invalid")
        for item in [*argv, cwd]:
            safe, changed = sanitize_and_redact_terminal_text(item)
            if changed or safe != item:
                raise ValueError("terminal_review_contains_sensitive_data")
        state = _state(argv, cwd)
        identity = uuid4().hex
        environment = dict(os.environ)
        plan: dict[str, Any] = {
            "id": identity,
            "domain": "development",
            "operation": "normal_terminal",
            "execution_mode": "normal-terminal",
            "source_operation": source_operation,
            "argv": list(argv),
            "cwd": cwd,
            "target": cwd,
            "pre_state": state,
            "environment": "Inherited user environment; values never persisted. Changes require a new review.",
            "environment_digest": self._environment_digest(environment),
            "privilege": "current operating-system user",
            "network": "Normal host connectivity; no network sandbox is imposed.",
            "isolation": "None. This command can access the user's files and normal environment.",
            "resource_limits": "No application-imposed runtime or resource limit.",
            "expected_effect": "Run exactly the displayed command with inherited terminal input/output. Child processes may outlive it; only foreground exit is recorded.",
            "rollback": "No automatic rollback. Host changes and background processes require their own reviewed recovery.",
            "postconditions": ["foreground_exit_observed"],
            "blockers": [],
            "expires_at": time.time() + 600,
        }
        plan["digest"] = digest(plan)
        private_records.write_once(self.root / "proposals", identity + ".json", plan)
        self._environments[identity] = environment
        return plan

    def discard(self, identity: str) -> None:
        self._environments.pop(identity, None)
        self._approvals.pop(identity, None)

    def load(self, identity: str) -> dict[str, Any]:
        if len(identity) != 32 or any(c not in "0123456789abcdef" for c in identity):
            raise ValueError("terminal_operation_id_invalid")
        plan = private_records.read(self.root / "proposals", identity + ".json")
        if plan.get("id") != identity or plan.get("digest") != digest(
            {k: v for k, v in plan.items() if k != "digest"}
        ):
            raise ValueError("terminal_proposal_drift")
        if plan.get("execution_mode") != "normal-terminal":
            raise ValueError("terminal_mode_mismatch")
        return plan

    def approve(self, identity: str, reviewed_digest: str) -> Approval:
        plan = self.load(identity)
        if (
            plan["digest"] != reviewed_digest
            or time.time() >= plan["expires_at"]
            or identity not in self._environments
        ):
            raise ValueError("terminal_approval_invalid_or_expired")
        approval = Approval(identity, reviewed_digest, min(time.time() + 60, plan["expires_at"]))
        self._approvals[identity] = approval
        return approval

    def execute(self, approval: Approval) -> dict[str, Any]:
        issued = self._approvals.pop(approval.operation_id, None)
        environment = self._environments.pop(approval.operation_id, None)
        if issued is not approval or environment is None or time.time() >= approval.expires_at:
            raise ValueError("terminal_approval_consumed_or_expired")
        plan = self.load(approval.operation_id)
        if (
            plan["digest"] != approval.digest
            or time.time() >= plan["expires_at"]
            or _state(plan["argv"], plan["cwd"]) != plan["pre_state"]
            or self._environment_digest(dict(os.environ)) != plan["environment_digest"]
        ):
            raise ValueError("terminal_pre_state_or_environment_drift")
        if not available():
            raise ValueError("visible_terminal_required")
        parent = private_records.directory(self.root)
        try:
            lock = os.open(
                "execution.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=parent
            )
        finally:
            os.close(parent)
        try:
            info = os.fstat(lock)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077
            ):
                raise ValueError("terminal_lock_unsafe")
            fcntl.flock(lock, fcntl.LOCK_EX)
            reservations = self.root / "reservations"
            directory = private_records.directory(reservations)
            try:
                with os.scandir(directory) as entries:
                    for count, entry in enumerate(entries):
                        if count >= 256:
                            raise ValueError("terminal_history_requires_review")
                        try:
                            prior = private_records.read(self.root / "results", entry.name)
                        except FileNotFoundError:
                            raise ValueError("previous_terminal_outcome_pending") from None
                        if prior.get("status") != "completed":
                            raise ValueError("previous_terminal_outcome_pending")
            finally:
                os.close(directory)
            if (
                time.time() >= approval.expires_at
                or time.time() >= plan["expires_at"]
                or _state(plan["argv"], plan["cwd"]) != plan["pre_state"]
                or self._environment_digest(dict(os.environ)) != plan["environment_digest"]
            ):
                raise ValueError("terminal_pre_state_or_environment_drift")
            private_records.write_once(
                reservations, plan["id"] + ".json", {"digest": plan["digest"]}
            )
        finally:
            os.close(lock)
        result = execute_once(plan["argv"], cwd=plan["cwd"], environment=environment)
        result.update(id=plan["id"], digest=plan["digest"], execution_mode="normal-terminal")
        private_records.write_once(self.root / "results", plan["id"] + ".json", result)
        return result
