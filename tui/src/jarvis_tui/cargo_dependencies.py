"""Bind approved crate downloads to a project's existing Cargo.lock."""

from __future__ import annotations

import hashlib
import os
import tomllib
from pathlib import Path

from . import private_records
from .cargo_download import MAX_ARCHIVE, validate
from .observation_safety import open_project, read_project_file


def locked(project: Path) -> dict[tuple[str, str], str]:
    fd = open_project(project)
    try:
        value = tomllib.loads(read_project_file(fd, "Cargo.lock", 262144).decode())
    finally:
        os.close(fd)
    packages = value.get("package", [])
    if not isinstance(packages, list) or len(packages) > 200:
        raise ValueError("cargo_lock_package_limit")
    result = {}
    for package in packages:
        if "source" not in package:
            continue
        if package["source"] != "registry+https://github.com/rust-lang/crates.io-index":
            raise ValueError("cargo_source_not_supported")
        name, version, checksum = package["name"], package["version"], package["checksum"]
        validate(name, version, checksum)
        if (name, version) in result:
            raise ValueError("cargo_duplicate_identity")
        result[name, version] = checksum
    return result


def archive_digest(path: Path) -> str:
    fd = private_records.directory(path.parent, create=False)
    try:
        source = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            import stat

            info = os.fstat(source)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_nlink != 1
                or info.st_mode & 0o022
                or not 0 < info.st_size <= MAX_ARCHIVE
            ):
                raise ValueError("crate_archive_unsafe")
            with os.fdopen(os.dup(source), "rb") as stream:
                data = stream.read(MAX_ARCHIVE + 1)
            if len(data) > MAX_ARCHIVE:
                raise ValueError("crate_archive_limit")
            return hashlib.sha256(data).hexdigest()
        finally:
            os.close(source)
    finally:
        os.close(fd)
