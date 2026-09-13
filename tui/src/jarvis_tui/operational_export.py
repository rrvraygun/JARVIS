"""Explicit, local delivery for the Phase 6 redacted operational report.

The presentation layer only builds an in-memory payload.  This module is an
opt-in delivery boundary for a caller that already has an explicit destination
chosen by the user.  It never creates parent directories, overwrites an
existing file, follows a destination symlink, or contacts a remote sink.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_EXPORT_BYTES = 32_000


@dataclass(frozen=True)
class ExportDeliveryResult:
    path: str
    bytes_written: int
    mode: int
    remote_sink_used: bool = False


class ExportDeliveryError(ValueError):
    """Raised when an explicit export destination cannot be safely used."""


def validate_redacted_payload(payload: str) -> bytes:
    """Validate the presentation payload before any filesystem operation."""
    if not isinstance(payload, str):
        raise ExportDeliveryError("export payload must be text")
    encoded = payload.encode("utf-8")
    if len(encoded) > MAX_EXPORT_BYTES:
        raise ExportDeliveryError("export payload exceeds bounded size")
    try:
        value: Any = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ExportDeliveryError("export payload is not valid JSON") from exc
    if not isinstance(value, dict) or value.get("kind") != "jarvis.phase6.operational-report":
        raise ExportDeliveryError("export payload kind is not approved")
    capabilities = value.get("capabilities")
    if not isinstance(capabilities, dict) or any(capabilities.values()):
        raise ExportDeliveryError("export payload carries authority")
    return encoded


def deliver_redacted_export(payload: str, destination: Path) -> ExportDeliveryResult:
    """Write one user-selected report atomically with mode 0600.

    The parent directory must already exist and be a directory.  Creation uses
    ``O_EXCL|O_NOFOLLOW`` so a repeated export or symlink target fails closed.
    """
    encoded = validate_redacted_payload(payload)
    target = Path(destination)
    if not target.is_absolute():
        raise ExportDeliveryError("export destination must be absolute")
    parent_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        parent_flags |= os.O_NOFOLLOW
    try:
        parent_fd = os.open(target.parent, parent_flags)
    except OSError as exc:
        raise ExportDeliveryError("export destination parent is unavailable") from exc
    try:
        parent = os.fstat(parent_fd)
        if (
            not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) & 0o022
        ):
            raise ExportDeliveryError("export destination parent is unsafe")
    except ExportDeliveryError:
        os.close(parent_fd)
        raise
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd: int | None = None
    try:
        fd = os.open(target.name, flags, 0o600, dir_fd=parent_fd)
    except OSError as exc:
        os.close(parent_fd)
        raise ExportDeliveryError("export destination was not created") from exc
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.fchmod(fd, 0o600)
        os.close(fd)
        os.close(parent_fd)
    except OSError as exc:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.close(parent_fd)
        except OSError:
            pass
        try:
            target.unlink()
        except OSError:
            pass
        raise ExportDeliveryError("export delivery failed closed") from exc
    return ExportDeliveryResult(str(target), len(encoded), 0o600)
