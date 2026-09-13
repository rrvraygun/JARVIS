#!/usr/bin/env python3
"""Classify privacy-preserving restore mismatch tokens without file reads.

This tool traverses only the same five reviewed source mappings used by the
independent comparator.  It performs lstat, no-atime directory enumeration,
and SEEK_DATA/SEEK_HOLE probes.  It never prints or persists a path name.
"""

from __future__ import annotations

import argparse
import errno
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
TOKEN_PATTERN = re.compile(r"^[0-9a-f]{24}$")


def load_core() -> Any:
    path = Path(__file__).with_name("verify_restored_boundaries.py")
    spec = importlib.util.spec_from_file_location("jarvis_verify_restored_boundaries", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("verifier-module-loader-unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CORE = load_core()


class DiagnosisFatal(RuntimeError):
    def __init__(
        self,
        code: str,
        boundary: str = "input",
        token: str = "root",
        error_number: int | None = None,
    ):
        super().__init__(code)
        self.code = code
        self.boundary = boundary
        self.token = token
        self.error_number = error_number


def load_request(path: Path) -> list[dict[str, str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DiagnosisFatal(
            "diagnosis-spec-unreadable", error_number=getattr(exc, "errno", None)
        ) from None
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise DiagnosisFatal("diagnosis-spec-schema")
    items = value.get("tokens")
    if not isinstance(items, list) or not items:
        raise DiagnosisFatal("diagnosis-spec-tokens")
    allowed_boundaries = {"root", "home", "systemd_machines", "boot", "efi"}
    allowed_codes = {"missing-restored-entry", "mtime", "sparse-layout-not-preserved"}
    result: list[dict[str, str]] = []
    identities: set[tuple[str, str]] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"boundary", "code", "token"}:
            raise DiagnosisFatal("diagnosis-spec-token-shape")
        boundary = item.get("boundary")
        code = item.get("code")
        token = item.get("token")
        if boundary not in allowed_boundaries or code not in allowed_codes:
            raise DiagnosisFatal("diagnosis-spec-token-value")
        if not isinstance(token, str) or TOKEN_PATTERN.fullmatch(token) is None:
            raise DiagnosisFatal("diagnosis-spec-token-format")
        identity = (boundary, token)
        if identity in identities:
            raise DiagnosisFatal("diagnosis-spec-duplicate-token", boundary, token)
        identities.add(identity)
        result.append({"boundary": boundary, "code": code, "token": token})
    return result


def diagnose(boundaries: list[Any], requests: list[dict[str, str]]) -> dict[str, Any]:
    wanted: dict[str, dict[str, str]] = {}
    for item in requests:
        wanted[f"{item['boundary']}:{item['token']}"] = item["code"]
    found: dict[str, dict[str, Any]] = {}

    for boundary in boundaries:
        stack: list[tuple[Path, Path, tuple[str, ...]]] = [(boundary.source, boundary.restored, ())]
        while stack:
            source, restored, relative = stack.pop()
            token = CORE.path_token(boundary.boundary_id, relative)
            identity = f"{boundary.boundary_id}:{token}"
            try:
                source_stat = source.lstat()
            except OSError as exc:
                raise DiagnosisFatal(
                    "source-lstat-failed", boundary.boundary_id, token, exc.errno
                ) from None

            if identity in wanted:
                found[identity] = observe(
                    boundary.boundary_id,
                    wanted[identity],
                    token,
                    source,
                    restored,
                    source_stat,
                )

            if not CORE.stat.S_ISDIR(source_stat.st_mode):
                continue
            try:
                names = CORE.directory_names_noatime(
                    source,
                    boundary.boundary_id,
                    token,
                )
            except CORE.VerificationFatal as exc:
                raise DiagnosisFatal(exc.code, exc.boundary, exc.token, exc.error_number) from None
            if not relative and boundary.excluded_top_level:
                names.difference_update(boundary.excluded_top_level)
            for name in sorted(names, key=os.fsencode, reverse=True):
                stack.append((source / name, restored / name, relative + (name,)))

    missing_tokens = sorted(set(wanted) - set(found))
    if missing_tokens:
        boundary, token = missing_tokens[0].split(":", 1)
        raise DiagnosisFatal("requested-token-not-found", boundary, token)

    records = [found[key] for key in sorted(found)]
    type_counts: Counter[str] = Counter()
    code_counts: Counter[str] = Counter()
    restored_absence_counts: Counter[str] = Counter()
    for record in records:
        code_counts[record["code"]] += 1
        type_counts[f"{record['code']}:{record['source_type']}"] += 1
        if not record["restored_exists"]:
            restored_absence_counts[record["source_type"]] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "diagnosed-token-metadata",
        "mode": "read-only-noatime-lstat-seek-only",
        "privacy": "no-file-names-no-file-content",
        "requested_tokens": len(requests),
        "found_tokens": len(records),
        "summary": {
            "code_counts": dict(sorted(code_counts.items())),
            "code_and_source_type_counts": dict(sorted(type_counts.items())),
            "restored_absence_source_type_counts": dict(sorted(restored_absence_counts.items())),
        },
        "records": records,
    }


def observe(
    boundary: str,
    code: str,
    token: str,
    source: Path,
    restored: Path,
    source_stat: os.stat_result,
) -> dict[str, Any]:
    source_type = CORE.file_kind(source_stat.st_mode)
    try:
        restored_stat = restored.lstat()
    except FileNotFoundError:
        restored_stat = None
    except OSError as exc:
        if exc.errno in {errno.ENOENT, errno.ENOTDIR}:
            restored_stat = None
        else:
            raise DiagnosisFatal("restored-lstat-failed", boundary, token, exc.errno) from None

    record: dict[str, Any] = {
        "boundary": boundary,
        "code": code,
        "path_token": token,
        "source_type": source_type,
        "restored_exists": restored_stat is not None,
        "restored_type": CORE.file_kind(restored_stat.st_mode)
        if restored_stat is not None
        else None,
    }
    if restored_stat is not None:
        record["mtime_delta_ns_restored_minus_source"] = (
            restored_stat.st_mtime_ns - source_stat.st_mtime_ns
        )
    if source_type == "regular":
        record["logical_size"] = source_stat.st_size
        record["source_holes"] = hole_profile(source, source_stat, boundary, token, "source")
        record["restored_holes"] = (
            hole_profile(restored, restored_stat, boundary, token, "restored")
            if restored_stat is not None and CORE.file_kind(restored_stat.st_mode) == "regular"
            else None
        )
    return record


def hole_profile(
    path: Path,
    expected: os.stat_result,
    boundary: str,
    token: str,
    side: str,
) -> dict[str, Any]:
    flags = CORE.noatime_flags(
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise DiagnosisFatal(f"{side}-open-failed", boundary, token, exc.errno) from None
    try:
        opened = os.fstat(descriptor)
        if CORE.identity_tuple(opened) != CORE.identity_tuple(expected):
            raise DiagnosisFatal(f"{side}-changed-before-seek", boundary, token)
        profile = seek_hole_profile(descriptor, opened.st_size, boundary, token, side)
        after = os.fstat(descriptor)
        if CORE.identity_tuple(after) != CORE.identity_tuple(opened):
            raise DiagnosisFatal(f"{side}-changed-during-seek", boundary, token)
        return profile
    finally:
        os.close(descriptor)


def seek_hole_profile(
    descriptor: int,
    size: int,
    boundary: str,
    token: str,
    side: str,
) -> dict[str, Any]:
    if size == 0:
        return {
            "supported": True,
            "hole_count": 0,
            "hole_bytes": 0,
            "largest_hole_bytes": 0,
        }
    if not hasattr(os, "SEEK_DATA") or not hasattr(os, "SEEK_HOLE"):
        return {"supported": False}
    holes: list[tuple[int, int]] = []
    position = 0
    while position < size:
        try:
            data_position = os.lseek(descriptor, position, os.SEEK_DATA)
        except OSError as exc:
            if exc.errno == errno.ENXIO:
                holes.append((position, size))
                break
            if exc.errno in CORE.UNSUPPORTED_XATTR_ERRNOS or exc.errno == errno.EINVAL:
                return {"supported": False}
            raise DiagnosisFatal(f"{side}-seek-data-failed", boundary, token, exc.errno) from None
        if data_position > position:
            holes.append((position, min(data_position, size)))
        try:
            hole_position = os.lseek(descriptor, data_position, os.SEEK_HOLE)
        except OSError as exc:
            if exc.errno in CORE.UNSUPPORTED_XATTR_ERRNOS or exc.errno == errno.EINVAL:
                return {"supported": False}
            raise DiagnosisFatal(f"{side}-seek-hole-failed", boundary, token, exc.errno) from None
        if hole_position >= size:
            break
        if hole_position <= data_position:
            raise DiagnosisFatal(f"{side}-nonprogressing-hole-map", boundary, token)
        position = hole_position
    lengths = [end - start for start, end in holes if end > start]
    return {
        "supported": True,
        "hole_count": len(lengths),
        "hole_bytes": sum(lengths),
        "largest_hole_bytes": max(lengths, default=0),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify hashed restore-mismatch tokens without revealing paths or reading content."
    )
    parser.add_argument("--snapshot-set", type=Path, required=True)
    parser.add_argument("--restore-target", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        requests = load_request(args.spec)
        boundaries = CORE.build_machine_boundaries(args.snapshot_set, args.restore_target)
        CORE.validate_machine_container_shape(args.snapshot_set, args.restore_target)
        report = diagnose(boundaries, requests)
    except (DiagnosisFatal, CORE.VerificationFatal) as exc:
        output: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "status": "fatal",
            "code": exc.code,
            "boundary": exc.boundary,
            "path_token": exc.token,
        }
        if exc.error_number is not None:
            output["errno"] = exc.error_number
        print(json.dumps(output, sort_keys=True))
        return 4
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
