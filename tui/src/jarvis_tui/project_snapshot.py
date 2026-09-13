"""Exact bounded source snapshots for isolated project operations."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from .observation_safety import open_project, read_project_file
from .terminal_safety import sanitize_and_redact_terminal_text

MAX_FILES = 2000
MAX_BYTES = 8 * 1024 * 1024


def inspect(root: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    fd = open_project(root)
    markers = ("Cargo.toml", "pyproject.toml", "package.json", "go.mod", "pom.xml", "Makefile")
    if not any((root / name).is_file() for name in markers):
        os.close(fd)
        raise ValueError("registered_text_project_marker_required")
    files: dict[str, bytes] = {}
    omitted: list[str] = []
    size = 0
    visited = 0

    def walk(parent: int, prefix: str, depth: int) -> None:
        nonlocal size, visited
        if depth > 8:
            raise ValueError("snapshot_depth_limit")
        with os.scandir(parent) as entries:
            for entry in entries:
                visited += 1
                if visited > MAX_FILES:
                    raise ValueError("snapshot_entry_limit")
                name = entry.name
                safe, changed = sanitize_and_redact_terminal_text(name)
                if changed or safe != name or name in {".", ".."}:
                    raise ValueError("snapshot_filename_unsafe")
                relative = prefix + name
                sensitive_name = re.search(
                    r"(?i)(password|passwd|passphrase|credential|secret|cookie|private[_-]?key|id_rsa|id_ed25519|contraseña|contrasena|(?:^|[._-])tokens?(?:[._-]|$))",
                    name,
                )
                if (
                    name.startswith(".")
                    or name in {"target", "node_modules", "runtime"}
                    or sensitive_name
                ):
                    omitted.append(relative)
                    continue
                info = entry.stat(follow_symlinks=False)
                if info.st_uid != os.geteuid() or info.st_mode & 0o022:
                    raise ValueError("snapshot_owner_or_permissions")
                if stat.S_ISDIR(info.st_mode):
                    child = os.open(
                        name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
                    )
                    try:
                        identity = os.fstat(child)
                        if (identity.st_dev, identity.st_ino) != (info.st_dev, info.st_ino):
                            raise ValueError("snapshot_directory_drift")
                        walk(child, relative + "/", depth + 1)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(info.st_mode):
                    data = read_project_file(parent, name, 1_048_576)
                    size += len(data)
                    if size > MAX_BYTES:
                        raise ValueError("snapshot_byte_limit")
                    text = data.decode("utf-8")
                    safe, changed = sanitize_and_redact_terminal_text(text)
                    if "\x00" in text or changed or safe != text:
                        raise ValueError("snapshot_sensitive_or_binary_file")
                    files[relative] = data
                else:
                    raise ValueError("snapshot_special_file_or_symlink")

    try:
        walk(fd, "", 0)
    finally:
        os.close(fd)
    hashes = {name: hashlib.sha256(value).hexdigest() for name, value in sorted(files.items())}
    material = {"files": hashes, "omitted": sorted(omitted), "bytes": size}
    material["digest"] = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()
    return files, material


def create(destination: Path, files: dict[str, bytes]) -> None:
    """Create only a new tree; never merge with or overwrite another directory."""
    parent = open_project(destination.parent)
    try:
        os.mkdir(destination.name, 0o700, dir_fd=parent)
        root = os.open(
            destination.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
        )
        try:
            for name, data in files.items():
                parts = Path(name).parts
                if Path(name).is_absolute() or any(p in {".", ".."} for p in parts):
                    raise ValueError("snapshot_path_invalid")
                fd = os.dup(root)
                try:
                    for part in parts[:-1]:
                        try:
                            os.mkdir(part, 0o700, dir_fd=fd)
                        except FileExistsError:
                            pass
                        child = os.open(
                            part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                        )
                        os.close(fd)
                        fd = child
                    output = os.open(
                        parts[-1],
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=fd,
                    )
                    try:
                        with os.fdopen(output, "wb", closefd=False) as stream:
                            stream.write(data)
                            stream.flush()
                            os.fsync(output)
                    finally:
                        os.close(output)
                    os.fsync(fd)
                finally:
                    os.close(fd)
            os.fsync(root)
        finally:
            os.close(root)
        os.fsync(parent)
    finally:
        os.close(parent)
