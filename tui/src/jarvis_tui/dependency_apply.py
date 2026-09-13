"""Exact existing-manifest replacement, retaining every displaced original."""

from __future__ import annotations

import ctypes
import hashlib
import os
import stat
from pathlib import Path
from typing import Any

from . import private_records, project_snapshot
from .observation_safety import open_project, read_project_file


def identity(info: os.stat_result) -> list[int]:
    return [
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    ]


def metadata(descriptor: int) -> dict[str, Any]:
    info = os.fstat(descriptor)
    attributes = os.listxattr(descriptor)
    if len(attributes) > 128:
        raise ValueError("manifest_metadata_limit")
    return {
        "uid": info.st_uid,
        "gid": info.st_gid,
        "mode": stat.S_IMODE(info.st_mode),
        "xattrs": {
            name: hashlib.sha256(os.getxattr(descriptor, name)).hexdigest() for name in attributes
        },
    }


def file_metadata(fd: int, name: str) -> dict[str, Any]:
    child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        if not stat.S_ISREG(os.fstat(child).st_mode):
            raise ValueError("manifest_not_regular")
        return metadata(child)
    finally:
        os.close(child)


def prepare(target: Path, source: dict[str, Any]) -> dict[str, Any]:
    if (
        source["domain"] != "development"
        or source["operation"] != "dependencies"
        or source["target"] != str(target)
    ):
        raise ValueError("dependency_source_not_bound")
    if project_snapshot.inspect(target)[1] != source["source_tree"]:
        raise ValueError("dependency_original_drift")
    expected = dict(source["source_tree"]["files"])
    expected.update(
        {
            name: hashlib.sha256(text.encode()).hexdigest()
            for name, text in source["arguments"]["files"].items()
        }
    )
    if project_snapshot.inspect(Path(source["destination"]))[1]["files"] != expected:
        raise ValueError("reviewed_dependency_workspace_drift")
    fd = open_project(target)
    identities = {}
    metadata_by_file = {}
    try:
        for name in source["arguments"]["files"]:
            # New manifests require a separate create workflow, never an overwrite fallback.
            read_project_file(fd, name, 262144)
            identities[name] = identity(os.stat(name, dir_fd=fd, follow_symlinks=False))
            metadata_by_file[name] = file_metadata(fd, name)
    finally:
        os.close(fd)
    return {
        "files": dict(source["arguments"]["files"]),
        "file_identities": identities,
        "file_metadata": metadata_by_file,
        "expected_files": expected,
        "source_operation": source["id"],
        "diff": source["diff"],
    }


def exchange(fd: int, staged: str, target: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    call = libc.renameat2
    call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    call.restype = ctypes.c_int
    if call(fd, staged.encode(), fd, target.encode(), 2) != 0:
        error = ctypes.get_errno()
        raise OSError(error, "atomic manifest exchange failed")


def retained_digest(fd: int, name: str) -> str:
    if not name.startswith(".jarvis-dependency-") or "/" in name:
        raise ValueError("retained_name_invalid")
    child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        info = os.fstat(child)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_nlink != 1
            or info.st_size > 262144
        ):
            raise ValueError("retained_file_unsafe")
        with os.fdopen(os.dup(child), "rb") as stream:
            data = stream.read(262145)
        if len(data) > 262144:
            raise ValueError("retained_file_oversized")
        return hashlib.sha256(data).hexdigest()
    finally:
        os.close(child)


def apply(root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    fd = open_project(Path(plan["target"]))
    completed: list[str] = []
    retained: dict[str, str] = {}
    file_states = {name: "not_started" for name in plan["files"]}
    stage = "precheck"
    try:
        for name, expected in plan["file_identities"].items():
            data = read_project_file(fd, name, 262144)
            if (
                identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) != expected
                or hashlib.sha256(data).hexdigest() != plan["source_tree"]["files"][name]
            ):
                raise ValueError("dependency_original_drift")
        for name, text in plan["files"].items():
            stage = "staging"
            file_states[name] = "staging"
            retained[name] = ".jarvis-dependency-" + plan["id"] + "-" + name
            output = os.open(
                retained[name],
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=fd,
            )
            original = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                info = os.fstat(original)
                if identity(info) != plan["file_identities"][name]:
                    raise ValueError("dependency_original_drift")
                with os.fdopen(os.dup(output), "wb") as stream:
                    stream.write(text.encode())
                    stream.flush()
                    os.fsync(stream.fileno())
                os.fchown(output, -1, info.st_gid)
                os.fchmod(output, stat.S_IMODE(info.st_mode))
                if metadata(original) != plan["file_metadata"][name]:
                    raise ValueError("manifest_metadata_drift")
                source_attributes = os.listxattr(original)
                for attribute in set(os.listxattr(output)) - set(source_attributes):
                    os.removexattr(output, attribute)
                for attribute in source_attributes:
                    value = os.getxattr(original, attribute)
                    try:
                        existing = os.getxattr(output, attribute)
                    except OSError:
                        existing = None
                    if existing != value:
                        os.setxattr(output, attribute, value)
                if metadata(output) != plan["file_metadata"][name]:
                    raise ValueError("manifest_metadata_not_preserved")
                os.fsync(output)
                file_states[name] = "prepared"
            finally:
                os.close(original)
                os.close(output)
            if (
                identity(os.stat(name, dir_fd=fd, follow_symlinks=False))
                != plan["file_identities"][name]
            ):
                raise ValueError("dependency_original_drift")
            stage = "exchange_requested"
            file_states[name] = "exchange_requested"
            private_records.write_once(
                root / "file-attempts",
                plan["id"] + "-" + name + ".json",
                {
                    "id": plan["id"],
                    "file": name,
                    "retained": retained[name],
                    "digest": plan["digest"],
                },
            )
            exchange(fd, retained[name], name)
            os.fsync(fd)
            completed.append(name)
            displaced = os.stat(retained[name], dir_fd=fd, follow_symlinks=False)
            # rename changes ctime. Compare identity and content without deleting a raced edit.
            expected = plan["file_identities"][name]
            if [
                displaced.st_dev,
                displaced.st_ino,
                displaced.st_mode,
                displaced.st_size,
                displaced.st_mtime_ns,
            ] != expected[:5]:
                raise ValueError("concurrent_edit_retained")
            if retained_digest(fd, retained[name]) != plan["source_tree"]["files"][name]:
                raise ValueError("concurrent_edit_retained")
            if file_metadata(fd, retained[name]) != plan["file_metadata"][name]:
                raise ValueError("concurrent_metadata_edit_retained")
            stage = "exchanged"
            file_states[name] = "applied_original_retained"
        return {
            "status": "applied_unverified",
            "completed_files": completed,
            "file_states": file_states,
            "retained_originals": retained,
            "original_unchanged": False,
        }
    except (OSError, ValueError) as exc:
        return {
            "status": "indeterminate"
            if completed or stage == "exchange_requested"
            else "stopped_before_replacement",
            "error": type(exc).__name__,
            "stage": stage,
            "completed_files": completed,
            "file_states": file_states,
            "retained_files": retained,
            "automatic_recovery": False,
        }
    finally:
        os.close(fd)


def recovery(plan: dict[str, Any]) -> dict[str, Any]:
    """Describe an inverse copy plan only when current changes are still attributable."""
    current = project_snapshot.inspect(Path(plan["target"]))[1]
    saved, saved_tree = project_snapshot.inspect(Path(plan["snapshot"]))
    if saved_tree != plan["snapshot_tree"]:
        raise ValueError("dependency_recovery_snapshot_drift")
    before = plan["source_tree"]["files"]
    expected = plan["expected_files"]
    if set(current["files"]) != set(before):
        raise ValueError("dependency_recovery_project_drift")
    fd = open_project(Path(plan["target"]))
    try:
        for name, digest in current["files"].items():
            if digest not in {before[name], expected[name]}:
                raise ValueError("dependency_recovery_user_edit")
            if name in plan["files"] and file_metadata(fd, name) != plan["file_metadata"][name]:
                raise ValueError("dependency_recovery_metadata_drift")
    finally:
        os.close(fd)
    files = {
        name: saved[name].decode("utf-8")
        for name in plan["files"]
        if current["files"][name] != before[name]
    }
    if not files:
        return {"status": "original_manifest_contents_present", "execution_authorized": False}
    return {
        "status": "inverse_copy_plan_available",
        "execution_authorized": False,
        "next_plan": {
            "domain": "development",
            "operation": "dependencies",
            "target": plan["target"],
            "arguments": {"files": files},
        },
        "next_step": "Review and execute this new dependency-copy proposal; after separate verification, review an apply_dependencies proposal bound to that new copy. Existing files are never restored automatically.",
    }
