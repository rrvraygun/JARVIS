"""Bounded, current-user observation primitives; never an execution authority."""

from __future__ import annotations

import os
import selectors
import shutil
import signal
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .terminal_safety import sanitize_and_redact_terminal_text

SAFE_PATH = "/usr/sbin:/usr/bin:/sbin:/bin"


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def bounded_process(
    argv: tuple[str, ...],
    *,
    timeout: float = 5,
    limit: int = 8000,
    cwd: str = "/",
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """One subprocess attempt, bounded while reading, killing its group on overflow.

    Callers must authorize argv/cwd/env; this function does not classify commands.
    Partial output is withheld after overflow or timeout to avoid split secrets.
    """
    if not argv or not 0 < timeout <= 600 or not 1 <= limit <= 1_048_576:
        raise ValueError("invalid_process_limits")
    executable = shutil.which(argv[0], path=SAFE_PATH)
    base: dict[str, Any] = {
        "argv": list(argv),
        "observed_at": timestamp(),
        "attempts": 1,
        "output": "",
        "truncated": False,
    }
    if executable is None:
        return {**base, "status": "unavailable", "attempts": 0}
    started = time.monotonic()
    data = bytearray()
    status = "completed"
    with subprocess.Popen(
        [executable, *argv[1:]],
        cwd=cwd,
        env=env or {"PATH": SAFE_PATH, "LANG": "C.UTF-8", "LC_ALL": "C"},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    ) as process:
        assert process.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    status = "timeout"
                    break
                for key, _ in selector.select(min(remaining, 0.1)):
                    chunk = os.read(key.fd, min(4096, limit + 1 - len(data)))
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    data.extend(chunk)
                    if len(data) > limit:
                        status = "output_limit"
                        break
                if status != "completed":
                    break
        if status == "completed":
            try:
                process.wait(timeout=max(0.001, timeout - (time.monotonic() - started)))
            except subprocess.TimeoutExpired:
                status = "timeout"
        if status != "completed":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        code = process.returncode
    safe, changed = (
        sanitize_and_redact_terminal_text(data.decode("utf-8", errors="replace"))
        if status == "completed"
        else ("[incomplete output withheld]", True)
    )
    return {
        **base,
        "status": status if status != "completed" else ("completed" if code == 0 else "failed"),
        "exit_code": code,
        "output": safe,
        "redacted": changed,
        "truncated": status == "output_limit",
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def bounded_read(path: Path, limit: int = 8000) -> str:
    """Read fixed kernel evidence with a byte limit; no unbounded read_text."""
    try:
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            return "[oversized evidence withheld]"
        return sanitize_and_redact_terminal_text(data.decode("utf-8", errors="replace"))[0]
    except OSError:
        return ""


def open_project(root: Path) -> int:
    """Open an exact owned project directory without following any directory link."""
    if not root.is_absolute() or ".." in root.parts or len(root.parts) < 3:
        raise ValueError("project_root_invalid")
    if root.parts[1] in {
        "etc",
        "proc",
        "sys",
        "dev",
        "boot",
        "usr",
        "bin",
        "sbin",
        "root",
        "run",
        "var",
    }:
        raise ValueError("project_root_protected")
    if any(part.startswith(".") for part in root.parts[1:]):
        raise ValueError("project_root_hidden")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in root.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise ValueError("project_root_not_private_to_owner")
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_project_file(fd: int, name: str, limit: int = 32000) -> bytes:
    if "/" in name or name.startswith("."):
        raise ValueError("project_filename_invalid")
    child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        before = os.fstat(child)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_nlink != 1
        ):
            raise ValueError("project_file_unsafe")
        if before.st_size > limit:
            raise ValueError("project_file_oversized")
        data = os.read(child, limit + 1)
        after = os.fstat(child)
        if len(data) > limit or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ValueError("project_file_changed_or_oversized")
        return data
    finally:
        os.close(child)
