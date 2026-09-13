"""Allowlisted GitHub CLI plans and single-attempt execution."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

REMOTE_OPERATIONS = frozenset(
    {
        "clone_repository",
        "create_repository",
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
REMOTE_VIEWS = frozenset({"repository", "pull_requests", "issues", "runs", "releases"})
DESTRUCTIVE = frozenset({"merge_pull_request", "delete_branch", "delete_repository"})
SLUG_RE = re.compile(r"^(?:github\.com/)?[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")


class GitHubConnectorUnavailable(ValueError):
    """Raised when GitHub CLI is not installed or cannot be used."""


def _gh() -> str:
    path = shutil.which("gh")
    if path is None or not Path(path).is_file():
        raise GitHubConnectorUnavailable("github_cli_unavailable")
    return path


def _safe(value: object, limit: int = 4_000) -> str:
    if not isinstance(value, str):
        raise ValueError("github_text_invalid")
    if len(value) > limit or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValueError("github_text_invalid")
    return value


def _slug(value: object) -> str:
    value = _safe(value, 300)
    if not SLUG_RE.fullmatch(value):
        raise ValueError("github_repository_slug_invalid")
    return value.removeprefix("github.com/")


def _name(value: object, error: str) -> str:
    value = _safe(value, 200)
    if not NAME_RE.fullmatch(value):
        raise ValueError(error)
    return value


def _branch(value: object, error: str = "github_branch_invalid") -> str:
    value = _safe(value, 300)
    if not BRANCH_RE.fullmatch(value) or ".." in value or value.endswith(("/", ".")):
        raise ValueError(error)
    return value


def _tag(value: object) -> str:
    value = _safe(value, 300)
    if not TAG_RE.fullmatch(value) or ".." in value or value.endswith(("/", ".")):
        raise ValueError("github_tag_invalid")
    return value


def _absolute_directory(value: object) -> str:
    value = _safe(value, 4096)
    raw = Path(value).expanduser()
    if raw.is_symlink():
        raise ValueError("github_destination_invalid")
    path = raw.resolve(strict=True)
    if not path.is_dir():
        raise ValueError("github_destination_invalid")
    return str(path)


def _clone_destination(value: object) -> str:
    value = _safe(value, 4096)
    raw = Path(value).expanduser()
    if raw.is_symlink() or raw.parent.is_symlink():
        raise ValueError("github_clone_destination_invalid")
    path = raw.resolve(strict=False)
    if path.exists() or not path.parent.is_dir():
        raise ValueError("github_clone_destination_invalid")
    return str(path)


def _asset_paths(value: object) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= 50:
        raise ValueError("github_assets_invalid")
    paths: list[str] = []
    for item in value:
        raw = _safe(item, 4096)
        source = Path(raw).expanduser()
        if source.is_symlink():
            raise ValueError("github_asset_invalid")
        path = source.resolve(strict=True)
        if not path.is_file():
            raise ValueError("github_asset_invalid")
        paths.append(str(path))
    return paths


def _common(
    operation: str,
    repository_root: str,
    requested_target: str,
    argv: list[str],
    *,
    risk: int,
    expected_effect: str,
    blockers: list[str] | None = None,
    network: str = "GitHub CLI network request; exact approval required.",
) -> dict[str, Any]:
    return {
        "argv": argv,
        "cwd": repository_root,
        "network": network,
        "privilege": "current-user GitHub profile",
        "risk": risk,
        "blockers": list(blockers or []),
        "requested_target": requested_target,
        "github_operation": operation,
        "expected_effect": expected_effect,
        "rollback": "Remote changes cannot be automatically undone; prepare a separate reviewed inverse operation.",
        "postconditions": ["remote_operation_receipt"],
    }


def prepare(
    operation: str,
    repository_root: str,
    requested_target: object,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    target = _safe(requested_target, 500)
    args = dict(arguments)
    if operation not in REMOTE_OPERATIONS:
        raise ValueError("github_remote_operation_not_registered")
    blockers: list[str] = []
    try:
        executable = _gh()
    except GitHubConnectorUnavailable:
        executable = "/usr/bin/gh"
        blockers.append("github_cli_unavailable")

    if operation in {"force_push", "modify_repository_settings"}:
        plan = _common(
            operation,
            repository_root,
            target,
            [],
            risk=4,
            expected_effect=f"Prepare the exact {operation} request after a dedicated adapter is reviewed.",
            blockers=[*blockers, "github_operation_adapter_not_implemented"],
        )
    elif operation == "clone_repository":
        repository = _slug(target)
        destination = _clone_destination(args.pop("destination"))
        argv = ["/usr/bin/git", "clone", "--", f"git@github.com:{repository}.git", destination]
        plan = _common(
            operation,
            repository_root,
            target,
            argv,
            risk=2,
            expected_effect=f"Clone {repository} into the reviewed destination over SSH.",
            blockers=[],
        )
    elif operation == "create_repository":
        repository = _safe(target, 300)
        if "/" in repository:
            repository = _slug(repository)
        else:
            repository = _name(repository, "github_repository_name_invalid")
        visibility = args.pop("visibility", None)
        if visibility not in {"public", "private", "internal"}:
            raise ValueError("github_visibility_required")
        argv = [
            executable,
            "repo",
            "create",
            repository,
            f"--{visibility}",
            "--source",
            repository_root,
        ]
        description = args.pop("description", None)
        if description is not None:
            argv.extend(["--description", _safe(description, 1_000)])
        if args.pop("push", False):
            argv.append("--push")
        plan = _common(
            operation,
            repository_root,
            target,
            argv,
            risk=2,
            expected_effect=f"Create the {visibility} repository {repository} from the reviewed local source.",
            blockers=blockers,
        )
    elif operation == "create_pull_request":
        repository = _slug(target)
        base = _branch(args.pop("base", "main"))
        head = _branch(args.pop("head", ""))
        title = _safe(args.pop("title"), 500)
        body = _safe(args.pop("body", ""), 10_000)
        if not head or not title.strip():
            raise ValueError("github_pull_request_fields_required")
        argv = [
            executable,
            "pr",
            "create",
            "--repo",
            repository,
            "--base",
            base,
            "--head",
            head,
            "--title",
            title,
            "--body",
            body,
        ]
        if args.pop("draft", False):
            argv.append("--draft")
        plan = _common(
            operation,
            repository_root,
            target,
            argv,
            risk=2,
            expected_effect=f"Create one pull request in {repository} from {head} into {base}.",
            blockers=blockers,
        )
    elif operation == "merge_pull_request":
        repository = _slug(target)
        number = _safe(args.pop("number"), 20)
        if not number.isdigit() or not 1 <= int(number) <= 2_000_000_000:
            raise ValueError("github_pull_request_number_invalid")
        method = args.pop("method", "squash")
        if method not in {"merge", "squash", "rebase"}:
            raise ValueError("github_merge_method_invalid")
        argv = [executable, "pr", "merge", number, "--repo", repository, f"--{method}"]
        if args.pop("delete_branch", False):
            argv.append("--delete-branch")
        plan = _common(
            operation,
            repository_root,
            target,
            argv,
            risk=3,
            expected_effect=f"Merge pull request {number} in {repository}.",
            blockers=blockers,
        )
        plan["pull_number"] = number
    elif operation == "create_issue":
        repository = _slug(target)
        title = _safe(args.pop("title"), 500)
        body = _safe(args.pop("body", ""), 10_000)
        if not title.strip():
            raise ValueError("github_issue_title_required")
        argv = [
            executable,
            "issue",
            "create",
            "--repo",
            repository,
            "--title",
            title,
            "--body",
            body,
        ]
        labels = args.pop("labels", [])
        if not isinstance(labels, list) or len(labels) > 20:
            raise ValueError("github_issue_labels_invalid")
        for label in labels:
            argv.extend(["--label", _name(label, "github_issue_label_invalid")])
        plan = _common(
            operation,
            repository_root,
            target,
            argv,
            risk=2,
            expected_effect=f"Create one issue in {repository}.",
            blockers=blockers,
        )
    elif operation == "create_release":
        repository = _slug(target)
        tag = _tag(args.pop("tag"))
        title = _safe(args.pop("title", tag), 500)
        notes = _safe(args.pop("notes", ""), 20_000)
        argv = [
            executable,
            "release",
            "create",
            tag,
            "--repo",
            repository,
            "--verify-tag",
            "--title",
            title,
            "--notes",
            notes,
        ]
        assets = _asset_paths(args.pop("assets", [])) if "assets" in arguments else []
        argv.extend(assets)
        plan = _common(
            operation,
            repository_root,
            target,
            argv,
            risk=3,
            expected_effect=f"Create release {tag} in {repository} from an existing verified tag.",
            blockers=blockers,
        )
        plan["tag"] = tag
    elif operation == "download_artifact":
        repository = _slug(target)
        run_id = _safe(args.pop("run_id"), 30)
        if not run_id.isdigit() or not 1 <= int(run_id) <= 2_000_000_000:
            raise ValueError("github_run_id_invalid")
        destination = _absolute_directory(args.pop("destination"))
        argv = [executable, "run", "download", run_id, "--repo", repository, "--dir", destination]
        artifact = args.pop("artifact", None)
        if artifact is not None:
            argv.extend(["--name", _name(artifact, "github_artifact_name_invalid")])
        plan = _common(
            operation,
            repository_root,
            target,
            argv,
            risk=2,
            expected_effect=f"Download one reviewed Actions artifact from run {run_id} into the existing destination.",
            blockers=blockers,
        )
    elif operation == "delete_branch":
        branch = _branch(args.pop("branch"))
        plan = _common(
            operation,
            repository_root,
            target,
            [],
            risk=3,
            expected_effect=f"Delete branch {branch} from the reviewed repository.",
            blockers=[*blockers, "github_branch_delete_adapter_not_implemented"],
        )
    else:
        repository = _slug(target)
        run_id = _safe(args.pop("run_id"), 30)
        if not run_id.isdigit() or not 1 <= int(run_id) <= 2_000_000_000:
            raise ValueError("github_run_id_invalid")
        argv = [executable, "run", "rerun", run_id, "--repo", repository]
        if args.pop("failed_only", False):
            argv.append("--failed")
        plan = _common(
            operation,
            repository_root,
            target,
            argv,
            risk=3,
            expected_effect=f"Request one rerun of Actions run {run_id} in {repository}.",
            blockers=blockers,
        )
    if operation not in {"force_push", "modify_repository_settings", "delete_branch"}:
        plan["repository"] = repository
    if operation in {"clone_repository", "download_artifact"}:
        plan["destination"] = destination
    if operation in {"create_pull_request", "create_issue", "create_release"}:
        plan["result_kind"] = operation
    if args:
        raise ValueError("github_operation_arguments_invalid")
    return plan


def execute(plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("blockers"):
        raise ValueError("github_operation_blocked")
    result = subprocess.run(
        plan["argv"],
        cwd=plan["cwd"],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env={**os.environ, "GH_PROMPT_DISABLED": "1", "LC_ALL": "C"},
    )
    return {
        "status": "completed" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "stdout": _safe(result.stdout),
        "stderr": _safe(result.stderr),
        "attempts": 1,
    }


def inspect(repository: object, view: object = "repository") -> dict[str, Any]:
    """Read bounded GitHub metadata through allowlisted gh commands."""
    repo = _slug(repository)
    if not isinstance(view, str) or view not in REMOTE_VIEWS:
        raise ValueError("github_remote_view_invalid")
    executable = _gh()
    commands = {
        "repository": [
            "repo",
            "view",
            repo,
            "--json",
            "nameWithOwner,isPrivate,defaultBranchRef,url,description",
        ],
        "pull_requests": [
            "pr",
            "list",
            "--repo",
            repo,
            "--limit",
            "50",
            "--json",
            "number,title,state,headRefName,baseRefName,isDraft,url",
        ],
        "issues": [
            "issue",
            "list",
            "--repo",
            repo,
            "--limit",
            "50",
            "--json",
            "number,title,state,url",
        ],
        "runs": [
            "run",
            "list",
            "--repo",
            repo,
            "--limit",
            "50",
            "--json",
            "databaseId,name,status,conclusion,headBranch,url",
        ],
        "releases": [
            "release",
            "list",
            "--repo",
            repo,
            "--limit",
            "50",
            "--json",
            "tagName,name,isDraft,isLatest,url",
        ],
    }
    result = subprocess.run(
        [executable, *commands[view]],
        check=False,
        cwd=None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        env={**os.environ, "GH_PROMPT_DISABLED": "1", "LC_ALL": "C"},
    )
    if result.returncode != 0:
        return {
            "available": True,
            "read_only": True,
            "network_accessed": True,
            "repository": repo,
            "view": view,
            "error": "github_remote_read_failed",
        }
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("github_remote_response_invalid") from exc
    return {
        "available": True,
        "read_only": True,
        "network_accessed": True,
        "repository": repo,
        "view": view,
        "data": data,
    }


def _readback(arguments: list[str]) -> dict[str, Any] | None:
    result = subprocess.run(
        [_gh(), *arguments],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        env={**os.environ, "GH_PROMPT_DISABLED": "1", "LC_ALL": "C"},
    )
    if result.returncode != 0:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def verify(plan: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    # Remote state is read back with one allowlisted command after the mutation.
    passed = result.get("status") == "completed" and result.get("exit_code") == 0
    operation = plan.get("github_operation")
    repository = plan.get("repository")
    command_completed = passed
    checks = {name: False for name in plan.get("postconditions", ())}
    readback: dict[str, Any] = {}
    try:
        if operation == "create_repository":
            readback = inspect(repository, "repository")
            data = readback.get("data", {})
            checks["remote_operation_receipt"] = data.get("nameWithOwner") == repository
        elif operation == "create_pull_request":
            output = result.get("stdout", "")
            urls = re.findall(
                r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:pull|issues|releases/tag)/[^\s]+",
                output,
            )
            readback = (
                _readback(
                    ["pr", "view", urls[0], "--json", "number,state,headRefName,baseRefName,url"]
                )
                if urls
                else None
            )
            checks["remote_operation_receipt"] = bool(readback) and command_completed
        elif operation == "create_issue":
            output = result.get("stdout", "")
            urls = re.findall(
                r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/[^\s]+",
                output,
            )
            readback = (
                _readback(["issue", "view", urls[0], "--json", "number,state,url"])
                if urls
                else None
            )
            checks["remote_operation_receipt"] = bool(readback) and command_completed
        elif operation == "create_release":
            readback = _readback(
                [
                    "release",
                    "view",
                    plan.get("tag", ""),
                    "--repo",
                    repository,
                    "--json",
                    "tagName,isDraft,url",
                ]
            )
            checks["remote_operation_receipt"] = bool(readback) and command_completed
        elif operation == "merge_pull_request":
            readback = _readback(
                [
                    "pr",
                    "view",
                    plan.get("pull_number", ""),
                    "--repo",
                    repository,
                    "--json",
                    "state,mergedAt,url",
                ]
            )
            checks["remote_operation_receipt"] = (
                bool(readback) and readback.get("state") == "MERGED" if readback else False
            )
        elif operation == "clone_repository":
            destination = plan.get("destination")
            readback = {
                "destination_exists": isinstance(destination, str) and Path(destination).is_dir()
            }
            checks["remote_operation_receipt"] = (
                readback["destination_exists"] and command_completed
            )
        elif operation == "download_artifact":
            destination = plan.get("destination")
            readback = {
                "destination_exists": isinstance(destination, str) and Path(destination).is_dir()
            }
            checks["remote_operation_receipt"] = (
                readback["destination_exists"] and command_completed
            )
        elif operation == "rerun_workflow":
            readback = {"command_completed": command_completed}
        elif operation == "delete_repository":
            readback = inspect(repository, "repository")
            checks["remote_operation_receipt"] = (
                readback.get("error") == "github_remote_read_failed"
            )
    except (OSError, ValueError, TypeError, KeyError):
        readback = {"verification": "unavailable"}
    return {
        "verdict": "pass" if all(checks.values()) and checks else "unknown",
        "id": plan.get("id"),
        "digest": plan.get("digest"),
        "checks": checks,
        "command_completed": passed,
        "readback": readback,
        "limitation": "Some operations expose command completion only until a resource-specific readback is available.",
    }
