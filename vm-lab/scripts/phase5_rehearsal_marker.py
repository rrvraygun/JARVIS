"""Disposable-scratch-only Phase 5 rehearsal adapter.

This adapter is deliberately not registered with Jarvis. It exercises a
bounded reversible filesystem effect in a caller-owned temporary directory;
it has no host-service, shell, privilege, network, device, or policy path.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any


class RehearsalMarkerError(ValueError):
    pass


class RehearsalMarkerAdapter:
    operation_id = "jarvis.rehearsal.marker"
    revision = "1.0.0"
    _marker_name = ".jarvis-rehearsal-marker"
    _marker_contents = b"jarvis-rehearsal-marker-v1\n"

    def __init__(self, rehearsal_root: Path, scratch_name: str) -> None:
        raw_boundary = Path(rehearsal_root)
        if not raw_boundary.is_absolute() or ".." in raw_boundary.parts:
            raise RehearsalMarkerError("rehearsal root must be absolute and traversal-free")
        if not scratch_name or scratch_name in {".", ".."} or "/" in scratch_name:
            raise RehearsalMarkerError("scratch name must be a single path component")
        self.rehearsal_root = raw_boundary
        self.scratch_name = scratch_name
        self.scratch_root = raw_boundary / scratch_name
        self._boundary_fd = self._open_path_without_symlinks(raw_boundary)
        self._root_fd = None
        try:
            self._validate_directory(self._boundary_fd, "rehearsal root")
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
            self._root_fd = os.open(scratch_name, flags, dir_fd=self._boundary_fd)
            self._validate_root()
        except Exception:
            if self._root_fd is not None:
                os.close(self._root_fd)
            os.close(self._boundary_fd)
            raise

    def _open_path_without_symlinks(self, path: Path) -> int:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(os.sep, flags)
        try:
            for component in path.parts[1:]:
                child = os.open(component, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            return descriptor
        except OSError as exc:
            os.close(descriptor)
            raise RehearsalMarkerError("scratch root is unavailable or contains a symlink") from exc

    @staticmethod
    def _validate_directory(descriptor: int, label: str) -> None:
        try:
            value = os.fstat(descriptor)
        except OSError as exc:
            raise RehearsalMarkerError(f"{label} is unavailable") from exc
        if (
            not stat.S_ISDIR(value.st_mode)
            or value.st_uid != os.getuid()
            or stat.S_IMODE(value.st_mode) & 0o022
        ):
            raise RehearsalMarkerError(f"{label} is not an owner-controlled directory")

    def _validate_root(self) -> None:
        if self._root_fd is None:
            raise RehearsalMarkerError("scratch root is closed")
        self._validate_directory(self._root_fd, "scratch root")

    @property
    def marker_path(self) -> Path:
        return self.scratch_root / self._marker_name

    @property
    def target_digest(self) -> str:
        encoded = json.dumps(
            {
                "rehearsal_root": str(self.rehearsal_root),
                "scratch_name": self.scratch_name,
                "marker": self._marker_name,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def close(self) -> None:
        if self._root_fd is not None:
            os.close(self._root_fd)
            self._root_fd = None
        if self._boundary_fd is not None:
            os.close(self._boundary_fd)
            self._boundary_fd = None

    def __enter__(self) -> RehearsalMarkerAdapter:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(parameters, dict) or set(parameters) != {"state"}:
            raise RehearsalMarkerError("parameters must contain only state")
        state = parameters["state"]
        if state not in {"present", "absent"}:
            raise RehearsalMarkerError("state must be present or absent")
        self._validate_root()
        fcntl.flock(self._root_fd, fcntl.LOCK_EX)
        try:
            return self._execute_locked(state)
        finally:
            fcntl.flock(self._root_fd, fcntl.LOCK_UN)

    def _execute_locked(self, state: str) -> dict[str, Any]:
        try:
            entries = os.listdir(self._root_fd)
        except OSError as exc:
            raise RehearsalMarkerError("scratch directory inspection failed") from exc
        if any(name != self._marker_name for name in entries):
            raise RehearsalMarkerError("scratch directory contains unexpected entries")
        if state == "present":
            self._create_marker()
            resulting = "present"
        else:
            self._remove_marker()
            resulting = "absent"
        return {
            "operation_id": self.operation_id,
            "revision": self.revision,
            "target_digest": self.target_digest,
            "resulting_state": resulting,
        }

    def _create_marker(self) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(self._marker_name, flags, 0o600, dir_fd=self._root_fd)
        except FileExistsError:
            try:
                descriptor = os.open(
                    self._marker_name,
                    os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=self._root_fd,
                )
                value = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(value.st_mode)
                    or value.st_uid != os.getuid()
                    or stat.S_IMODE(value.st_mode) != 0o600
                    or value.st_nlink != 1
                    or os.read(descriptor, len(self._marker_contents) + 1) != b""
                ):
                    os.close(descriptor)
                    raise RehearsalMarkerError("marker already exists; stale state requires review")
                os.lseek(descriptor, 0, os.SEEK_SET)
            except RehearsalMarkerError:
                raise
            except OSError as open_exc:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                raise RehearsalMarkerError(
                    "marker already exists; stale state requires review"
                ) from open_exc
        except OSError as exc:
            raise RehearsalMarkerError("marker creation failed") from exc
        try:
            remaining = memoryview(self._marker_contents)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise RehearsalMarkerError("marker write made no progress")
                remaining = remaining[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self._sync_root()

    def _remove_marker(self) -> None:
        try:
            value = os.stat(self._marker_name, dir_fd=self._root_fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise RehearsalMarkerError("marker inspection failed") from exc
        if (
            not stat.S_ISREG(value.st_mode)
            or value.st_uid != os.getuid()
            or stat.S_IMODE(value.st_mode) != 0o600
            or value.st_nlink != 1
        ):
            raise RehearsalMarkerError("marker is not an owner-controlled regular file")
        flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self._marker_name, flags, dir_fd=self._root_fd)
        except OSError as exc:
            raise RehearsalMarkerError("marker inspection failed") from exc
        try:
            opened = os.fstat(descriptor)
            if (
                opened.st_dev != value.st_dev
                or opened.st_ino != value.st_ino
                or os.read(descriptor, len(self._marker_contents) + 1)
                not in {b"", self._marker_contents}
            ):
                raise RehearsalMarkerError("marker contents or identity are stale")
            os.ftruncate(descriptor, 0)
            os.fsync(descriptor)
        except RehearsalMarkerError:
            raise
        except OSError as exc:
            raise RehearsalMarkerError("marker clearing failed") from exc
        finally:
            os.close(descriptor)
        self._sync_root()

    def _sync_root(self) -> None:
        os.fsync(self._root_fd)
