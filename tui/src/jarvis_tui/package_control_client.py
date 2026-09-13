"""Client for the reviewed root-owned package transaction helper."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

HELPER_PATH = Path("/usr/libexec/jarvis-package-control")
PKEXEC_PATH = Path("/usr/bin/pkexec")
MAX_OUTPUT = 65_536


class PackageControlClientError(ValueError):
    pass


def helper_available(path: Path = HELPER_PATH) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISREG(info.st_mode)
        and os.access(path, os.X_OK)
        and info.st_uid == 0
        and not info.st_mode & 0o022
    )


def helper_matches_bundle(bundle_root: Path, *, helper: Path = HELPER_PATH) -> bool:
    """Require the deployed root helper to match this reviewed checkout."""
    source = bundle_root.resolve() / "vm-lab/scripts/jarvis_package_control.py"
    if not helper_available(helper):
        return False
    try:
        source_info = source.lstat()
        helper_info = helper.lstat()
        if not stat.S_ISREG(source_info.st_mode) or not stat.S_ISREG(helper_info.st_mode):
            return False
        if source_info.st_size > MAX_OUTPUT or helper_info.st_size > MAX_OUTPUT:
            return False
        return (
            hashlib.sha256(source.read_bytes()).digest()
            == hashlib.sha256(helper.read_bytes()).digest()
        )
    except OSError:
        return False


def _invoke(
    argv: list[str],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    try:
        result = runner(argv, check=True, capture_output=True, text=True, timeout=180, shell=False)
    except subprocess.CalledProcessError as exc:
        raw = (exc.stdout or exc.stderr or "").strip()
        detail = raw
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict) and payload.get("error"):
                detail = str(payload["error"])
        except json.JSONDecodeError:
            pass
        suffix = f": {detail[:500]}" if detail else ""
        raise PackageControlClientError(
            f"authorized package operation failed (exit {exc.returncode}){suffix}"
        ) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise PackageControlClientError(
            "authorized package operation failed or was cancelled"
        ) from exc
    if len(result.stdout.encode()) > MAX_OUTPUT:
        raise PackageControlClientError("package helper response exceeded limit")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PackageControlClientError("package helper response is invalid") from exc
    if not isinstance(value, dict) or value.get("status") != "passed":
        raise PackageControlClientError("package helper did not verify the operation")
    return value


def authoritative_status(
    *,
    helper: Path = HELPER_PATH,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    if not helper_available(helper):
        raise PackageControlClientError("root-owned package helper is not deployed")
    value = _invoke([str(PKEXEC_PATH), str(helper), "status"], runner)
    if (
        value.get("operation") not in {"status", "recovery-status"}
        or len(str(value.get("record_digest", ""))) != 64
    ):
        raise PackageControlClientError("authoritative package status is invalid")
    return value


def apply_transaction(
    names: tuple[str, ...],
    preview_digest: str,
    approved_digest: str,
    *,
    helper: Path = HELPER_PATH,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    if not helper_available(helper):
        raise PackageControlClientError("root-owned package helper is not deployed")
    if len(preview_digest) != 64 or len(approved_digest) != 64:
        raise PackageControlClientError("package approval digest is invalid")
    return _invoke(
        [
            str(PKEXEC_PATH),
            str(helper),
            "apply",
            "--preview-digest",
            preview_digest,
            "--approved-digest",
            approved_digest,
            *names,
        ],
        runner,
    )


def remove_transaction(
    names: tuple[str, ...],
    preview_digest: str,
    approved_digest: str,
    *,
    helper: Path = HELPER_PATH,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    if not helper_available(helper):
        raise PackageControlClientError("root-owned package helper is not deployed")
    if len(preview_digest) != 64 or len(approved_digest) != 64:
        raise PackageControlClientError("package approval digest is invalid")
    return _invoke(
        [
            str(PKEXEC_PATH),
            str(helper),
            "remove",
            "--preview-digest",
            preview_digest,
            "--approved-digest",
            approved_digest,
            *names,
        ],
        runner,
    )


def undo_transaction(
    record_digest: str,
    *,
    helper: Path = HELPER_PATH,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    if not helper_available(helper):
        raise PackageControlClientError("root-owned package helper is not deployed")
    if len(record_digest) != 64 or any(char not in "0123456789abcdef" for char in record_digest):
        raise PackageControlClientError("package record digest is invalid")
    return _invoke(
        [str(PKEXEC_PATH), str(helper), "undo", "--record-digest", record_digest],
        runner,
    )


def archive_transaction(
    record_digest: str,
    *,
    helper: Path = HELPER_PATH,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    if not helper_available(helper):
        raise PackageControlClientError("root-owned package helper is not deployed")
    if len(record_digest) != 64 or any(char not in "0123456789abcdef" for char in record_digest):
        raise PackageControlClientError("package record digest is invalid")
    return _invoke(
        [str(PKEXEC_PATH), str(helper), "archive", "--record-digest", record_digest],
        runner,
    )
