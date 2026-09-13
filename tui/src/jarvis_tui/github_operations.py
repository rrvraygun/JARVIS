"""Exact, one-use Git operations prepared by GitHub Agent."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from . import github_cli

MAX_MESSAGE_CHARS = 500
MAX_PATHS = 100
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
REMOTE_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
REF_RE = re.compile(r"^[A-Za-z0-9._/@-]{1,300}$")
SENSITIVE_NAMES = frozenset(
    {".env", ".env.local", "credentials", "credentials.json", "id_ed25519", "id_rsa"}
)
SENSITIVE_SUFFIXES = (".key", ".pem", ".p12", ".pfx")
SUPPORTED_OPERATIONS = frozenset(
    {
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
    }
)
REMOTE_CONNECTOR_OPERATIONS = github_cli.REMOTE_OPERATIONS


def _run(root: Path, argv: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update({"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
    return subprocess.run(
        argv,
        cwd=root,
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=environment,
    )


def _safe(value: str, limit: int = 4000) -> str:
    return "".join(ch for ch in value if ch in "\n\t" or 32 <= ord(ch) != 127)[:limit]


def _git(root: Path, *args: str) -> str:
    result = _run(root, ["/usr/bin/git", *args], timeout=8)
    if result.returncode != 0:
        raise ValueError("github_git_command_failed")
    return _safe(result.stdout)


def _repo(root: object, *, allow_uninitialized: bool = False) -> Path:
    if not isinstance(root, str) or not root.strip() or len(root) > 4096:
        raise ValueError("invalid_project_root")
    path = Path(root).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError("project_root_is_not_directory")
    if allow_uninitialized:
        return path
    top = Path(_git(path, "rev-parse", "--show-toplevel").strip()).resolve(strict=True)
    if top != path:
        raise ValueError("project_root_must_be_repository_root")
    return path


def _state(root: Path, *, allow_uninitialized: bool = False) -> dict[str, str]:
    if allow_uninitialized and not (root / ".git").exists():
        return {"git_head": "uninitialized", "status_digest": "uninitialized"}
    status = _git(root, "status", "--porcelain=v1", "--branch", "--ignored")
    head_value = _git_optional(root, "rev-parse", "HEAD")
    head = head_value.strip() if head_value else "unborn"
    return {
        "git_head": head,
        "status_digest": hashlib.sha256(status.encode("utf-8")).hexdigest(),
    }


def _git_optional(root: Path, *args: str) -> str:
    try:
        return _git(root, *args)
    except ValueError:
        return ""


def _sensitive(path: str) -> bool:
    name = Path(path).name.casefold()
    return name in SENSITIVE_NAMES or name.endswith(SENSITIVE_SUFFIXES)


def _paths(value: object) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_PATHS:
        raise ValueError("github_commit_paths_invalid")
    result: list[str] = []
    for item in value:
        if (
            not isinstance(item, str)
            or not item
            or len(item) > 500
            or item.startswith("/")
            or "\x00" in item
            or Path(item).is_absolute()
            or ".." in Path(item).parts
            or _sensitive(item)
        ):
            raise ValueError("github_commit_path_rejected")
        result.append(item)
    if len(set(result)) != len(result):
        raise ValueError("github_commit_paths_duplicate")
    return result


def _name(value: object, pattern: re.Pattern[str], error: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(error)
    return value


def prepare(bundle: Path, operation: str, target: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if operation not in SUPPORTED_OPERATIONS:
        raise ValueError("github_operation_not_implemented")
    root = _repo(
        target,
        allow_uninitialized=operation in {"initialize_repository", "clone_repository"},
    )
    args = dict(arguments)
    requested_target = args.pop("requested_target", "")
    if not isinstance(requested_target, str) or len(requested_target) > 500:
        raise ValueError("github_operation_target_invalid")
    proposal: dict[str, Any] = {
        "cwd": str(root),
        "argv": [],
        "environment": {"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        "network": "denied",
        "privilege": "current-user",
        "risk": 1,
        "attempt_limit": 1,
        "pre_state": _state(
            root, allow_uninitialized=operation in {"initialize_repository", "clone_repository"}
        ),
        "postconditions": ["repository_state_recorded"],
        "expected_effect": "",
        "rollback": "No automatic rollback. A separate reviewed inverse operation is required.",
        "blockers": [],
        "requested_target": requested_target,
    }
    if operation in REMOTE_CONNECTOR_OPERATIONS:
        proposal.update(github_cli.prepare(operation, str(root), requested_target, args))
    elif operation == "initialize_repository":
        if args:
            branch = _name(args.pop("branch", "main"), BRANCH_RE, "github_branch_invalid")
        else:
            branch = "main"
        if (root / ".git").exists():
            raise ValueError("repository_already_initialized")
        proposal.update(
            argv=["/usr/bin/git", "init", "--initial-branch", branch, str(root)],
            expected_effect=f"Initialize one local repository with branch {branch}.",
            postconditions=["repository_exists", "repository_state_recorded"],
        )
    elif operation == "create_branch":
        branch = _name(args.pop("branch", args.pop("name", "")), BRANCH_RE, "github_branch_invalid")
        if args or _git_optional(root, "show-ref", "--verify", f"refs/heads/{branch}"):
            raise ValueError("github_branch_already_exists_or_arguments_invalid")
        proposal.update(
            argv=["/usr/bin/git", "switch", "-c", branch],
            expected_effect=f"Create and select local branch {branch}.",
            postconditions=["branch_selected", "repository_state_recorded"],
        )
    elif operation == "commit":
        message = args.pop("message", "")
        if not isinstance(message, str) or not message.strip() or len(message) > MAX_MESSAGE_CHARS:
            raise ValueError("github_commit_message_invalid")
        safe_message = _safe(message, MAX_MESSAGE_CHARS)
        if safe_message != message or "\n" in message or "\r" in message:
            raise ValueError("github_commit_message_unreviewable")
        paths = _paths(args.pop("paths", None))
        if args:
            raise ValueError("github_commit_arguments_invalid")
        if _git(root, "diff", "--name-only", "--diff-filter=U").strip():
            raise ValueError("github_conflicts_present")
        proposal.update(
            argv=["/usr/bin/git", "commit", "-m", safe_message, "--", *paths],
            commit_paths=paths,
            commit_message=safe_message,
            expected_effect=f"Create one local commit containing only the reviewed paths: {', '.join(paths)}.",
            postconditions=["commit_created", "repository_state_recorded"],
        )
    else:
        remote = _name(args.pop("remote", "origin"), REMOTE_RE, "github_remote_invalid")
        ref = _name(args.pop("ref", ""), REF_RE, "github_ref_invalid")
        set_upstream = args.pop("set_upstream", False)
        if not isinstance(set_upstream, bool):
            raise ValueError("github_set_upstream_invalid")
        if args or not ref:
            raise ValueError("github_remote_arguments_invalid")
        proposal["network"] = "one Git network operation to the reviewed remote and ref"
        proposal["risk"] = 2
        if operation == "pull":
            proposal.update(
                argv=["/usr/bin/git", "pull", "--ff-only", remote, ref],
                expected_effect=f"Fast-forward the local branch from {remote}/{ref}.",
                postconditions=["pull_completed", "repository_state_recorded"],
            )
        else:
            if set_upstream:
                proposal["argv"] = ["/usr/bin/git", "push", "--set-upstream", remote, ref]
            else:
                proposal["argv"] = ["/usr/bin/git", "push", remote, ref]
            proposal.update(
                expected_effect=f"Push the current reviewed state to {remote} ref {ref}.",
                postconditions=["push_completed", "repository_state_recorded"],
            )
    if args:
        raise ValueError("github_operation_arguments_invalid")
    proposal["github_operation"] = operation
    proposal["target"] = str(root)
    proposal["digest_material"] = {
        "operation": operation,
        "target": str(root),
        "arguments": arguments,
        "pre_state": proposal["pre_state"],
    }
    proposal["github_plan_version"] = 1
    return proposal


def apply(bundle: Path, plan: dict[str, Any]) -> dict[str, Any]:
    root = _repo(
        plan.get("target"),
        allow_uninitialized=plan.get("github_operation")
        in {"initialize_repository", "clone_repository"},
    )
    if _state(
        root,
        allow_uninitialized=plan.get("github_operation")
        in {"initialize_repository", "clone_repository"},
    ) != plan.get("pre_state"):
        raise ValueError("github_pre_state_drift")
    operation = plan.get("github_operation")
    if operation in github_cli.REMOTE_OPERATIONS:
        return github_cli.execute(plan)
    if operation == "commit":
        paths = plan.get("commit_paths")
        staged = _run(root, ["/usr/bin/git", "add", "--", *paths], timeout=15)
        if staged.returncode != 0:
            raise ValueError("github_stage_failed")
        command = ["/usr/bin/git", "commit", "-m", plan["commit_message"], "--", *paths]
    else:
        command = list(plan["argv"])
    result = _run(root, command, timeout=60 if plan.get("network") != "denied" else 30)
    return {
        "status": "completed" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "stdout": _safe(result.stdout),
        "stderr": _safe(result.stderr),
        "attempts": 1,
        "post_state": _state(root, allow_uninitialized=False)
        if operation != "initialize_repository" or result.returncode == 0
        else {"git_head": "uninitialized", "status_digest": "uninitialized"},
    }


def verify(plan: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    if plan.get("github_operation") in github_cli.REMOTE_OPERATIONS:
        return github_cli.verify(plan, result)
    passed = result.get("status") == "completed" and result.get("exit_code") == 0
    return {
        "verdict": "pass" if passed else "fail",
        "id": plan.get("id"),
        "digest": plan.get("digest"),
        "checks": {name: passed for name in plan.get("postconditions", ())},
    }
