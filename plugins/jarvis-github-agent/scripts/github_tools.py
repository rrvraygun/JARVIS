"""Bounded local Git evidence and non-executable GitHub operation planning."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

MAX_OUTPUT_CHARS = 24_000
MAX_ITEMS = 200
MAX_PATH_CHARS = 4096
LARGE_FILE_BYTES = 5 * 1024 * 1024
SENSITIVE_BASENAMES = frozenset(
    {
        ".env",
        ".env.local",
        "credentials",
        "credentials.json",
        "id_ed25519",
        "id_rsa",
        "secrets.json",
    }
)
SENSITIVE_SUFFIXES = (".key", ".pem", ".p12", ".pfx")
OPERATIONS = frozenset(
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
DESTRUCTIVE_OPERATIONS = frozenset(
    {"delete_branch", "force_push", "modify_repository_settings", "delete_repository"}
)
REMOTE_WRITE_OPERATIONS = OPERATIONS - {"clone_repository", "download_artifact", "pull"}


class GitHubEvidenceError(ValueError):
    """Raised when local repository evidence cannot be safely collected."""


def _safe_text(value: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    cleaned = "".join(
        character for character in value if character in "\n\t" or 32 <= ord(character) != 127
    )
    return cleaned[:limit]


def _path(value: object) -> Path:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_PATH_CHARS:
        raise GitHubEvidenceError("invalid_project_root")
    candidate = Path(value).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise GitHubEvidenceError("project_root_unavailable") from exc
    if not resolved.is_dir():
        raise GitHubEvidenceError("project_root_is_not_directory")
    return resolved


def _run(root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["/usr/bin/git", "-C", str(root), *arguments],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitHubEvidenceError("git_inspection_unavailable") from exc
    if result.returncode != 0:
        raise GitHubEvidenceError("not_a_git_repository")
    return _safe_text(result.stdout)


def _repository_root(root: Path) -> Path:
    value = _run(root, "rev-parse", "--show-toplevel").strip()
    try:
        repository = Path(value).resolve(strict=True)
    except OSError as exc:
        raise GitHubEvidenceError("repository_root_unavailable") from exc
    if repository != root:
        raise GitHubEvidenceError("project_root_must_be_repository_root")
    return repository


def _lines(value: str, *, limit: int = MAX_ITEMS) -> list[str]:
    return [_safe_text(item, 512) for item in value.splitlines() if item][:limit]


def _optional_run(root: Path, *arguments: str) -> str:
    try:
        return _run(root, *arguments)
    except GitHubEvidenceError:
        return ""


def _redact_remote(value: str) -> str:
    return re.sub(r"(https?://)[^/@\\s]+@", r"\\1***@", value)


def _status(root: Path) -> dict[str, Any]:
    repository = _repository_root(root)
    porcelain = _lines(_run(repository, "status", "--porcelain=v1", "--branch", "--ignored"))
    branch = ""
    entries: list[str] = []
    ignored: list[str] = []
    for line in porcelain:
        if line.startswith("## "):
            branch = line[3:]
        elif line.startswith("!! "):
            ignored.append(line[3:])
        else:
            entries.append(line)
    return {
        "repository_root": str(repository),
        "branch": branch or "detached_or_unknown",
        "changes": entries,
        "ignored_paths": ignored,
        "conflicts": _lines(_run(repository, "diff", "--name-only", "--diff-filter=U")),
        "unstaged_diff_stat": _safe_text(_run(repository, "diff", "--stat"), 6_000),
        "staged_diff_stat": _safe_text(_run(repository, "diff", "--cached", "--stat"), 6_000),
        "recent_commits": _lines(
            _optional_run(repository, "log", "--format=%h %s", "-n", "20"), limit=20
        ),
        "remotes": [
            _redact_remote(item) for item in _lines(_run(repository, "remote", "-v"), limit=40)
        ],
    }


def github_inspect(project_root: object) -> dict[str, Any]:
    """Return bounded local Git metadata without network access or writes."""
    root = _path(project_root)
    result = _status(root)
    result.update(
        {
            "available": True,
            "read_only": True,
            "network_accessed": False,
            "git_version": _safe_text(
                subprocess.run(
                    ["/usr/bin/git", "--version"],
                    check=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=4,
                    env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
                ).stdout,
                200,
            ).strip(),
            "github_cli_available": shutil.which("gh") is not None,
        }
    )
    return result


def _changed_paths(root: Path) -> list[str]:
    values = (
        _lines(_run(root, "diff", "--name-only"), limit=MAX_ITEMS)
        + _lines(_run(root, "diff", "--cached", "--name-only"), limit=MAX_ITEMS)
        + _lines(_run(root, "ls-files", "--others", "--exclude-standard"), limit=MAX_ITEMS)
    )
    return list(dict.fromkeys(values))[:MAX_ITEMS]


def _sensitive_path(path: str) -> bool:
    name = Path(path).name.casefold()
    return name in SENSITIVE_BASENAMES or name.endswith(SENSITIVE_SUFFIXES)


def github_preflight(project_root: object) -> dict[str, Any]:
    """Inspect publication-risk metadata without reading file contents."""
    root = _path(project_root)
    evidence = _status(root)
    repository = Path(evidence["repository_root"])
    changed = _changed_paths(repository)
    sensitive = list(
        dict.fromkeys(
            path for path in [*changed, *evidence["ignored_paths"]] if _sensitive_path(path)
        )
    )
    large: list[dict[str, Any]] = []
    for relative in changed:
        candidate = repository / relative
        try:
            info = candidate.lstat()
        except OSError:
            continue
        if info.st_size > LARGE_FILE_BYTES:
            large.append({"path": relative, "bytes": info.st_size})
    return {
        "available": True,
        "read_only": True,
        "network_accessed": False,
        "repository_root": evidence["repository_root"],
        "branch": evidence["branch"],
        "changed_paths": changed,
        "conflicts": evidence["conflicts"],
        "ignored_paths": evidence["ignored_paths"],
        "sensitive_filename_candidates": sensitive,
        "large_changed_files": large,
        "limitations": [
            "No file contents or credentials were read.",
            "Secret detection is filename-based in this phase.",
            "Remote GitHub checks, CI, and Actions require a separately approved capability.",
        ],
        "publication_ready": not evidence["conflicts"] and not sensitive and not large,
    }


def github_operation_plan(
    project_root: object, operation: object, target: object = ""
) -> dict[str, Any]:
    """Prepare a non-executable operation requiring a fresh exact approval."""
    root = _path(project_root)
    repository = _repository_root(root)
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise GitHubEvidenceError("unsupported_github_operation")
    if not isinstance(target, str) or len(target) > 500:
        raise GitHubEvidenceError("invalid_operation_target")
    return {
        "operation": operation,
        "target": _safe_text(target, 500),
        "repository_root": str(repository),
        "approval_required": True,
        "execution_authorized": False,
        "network_required": operation in REMOTE_WRITE_OPERATIONS
        or operation in {"clone_repository", "download_artifact", "pull"},
        "destructive": operation in DESTRUCTIVE_OPERATIONS,
        "required_checks": [
            "github_inspect",
            "github_preflight",
            "fresh exact user approval",
        ],
        "availability": {
            "git": True,
            "github_cli": shutil.which("gh") is not None,
            "github_mcp": False,
        },
        "next_step": "Review this plan in the GitHub Agent conversation; it does not execute.",
    }
