#!/usr/bin/env python3
"""Independently compare the five restored Fedora recovery boundaries.

The verifier is intentionally read-only.  It opens directories and regular
files with O_NOATIME, never follows symlinks, never invokes a subprocess, and
never prints file names or file contents.  Mismatches are represented by a
boundary identifier and a one-way path token.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import stat
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
CHUNK_SIZE = 1024 * 1024
MAX_FAILURE_EXAMPLES = 64
UNSUPPORTED_XATTR_ERRNOS = {
    value
    for value in (getattr(errno, "ENOTSUP", None), getattr(errno, "EOPNOTSUPP", None))
    if value is not None
}


class VerificationFatal(RuntimeError):
    """Raised when a complete, no-atime comparison cannot continue safely."""

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


@dataclass(frozen=True)
class Boundary:
    """One source-to-restore mapping with optional top-level exclusions."""

    boundary_id: str
    source: Path
    restored: Path
    excluded_top_level: frozenset[str] = frozenset()
    btrfs_snapshot: bool = False


@dataclass
class BoundaryStats:
    entries: int = 0
    directories: int = 0
    regular_files: int = 0
    logical_file_bytes: int = 0
    source_unique_bytes_hashed: int = 0
    restored_unique_bytes_hashed: int = 0
    symlinks: int = 0
    special_files: int = 0
    xattr_entries: int = 0
    paths_with_xattrs: int = 0
    acl_paths: int = 0
    selinux_label_paths: int = 0
    capability_paths: int = 0
    xattr_unsupported_source_paths: int = 0
    sparse_source_files: int = 0
    sparse_restored_files: int = 0
    sparse_source_files_without_restored_holes: int = 0
    hardlink_groups_witnessed: int = 0
    hardlink_paths_witnessed: int = 0
    source_sockets_intentionally_ignored: int = 0
    nested_btrfs_boundary_mtime_exemptions: int = 0

    def as_dict(self) -> dict[str, int]:
        return {key: int(value) for key, value in vars(self).items()}


@dataclass
class Result:
    boundaries: dict[str, BoundaryStats]
    mismatch_counts: Counter[str]
    boundary_mismatch_counts: dict[str, Counter[str]]
    failure_examples: list[dict[str, str]]
    source_manifest: str
    restored_manifest: str
    proof_gaps: list[str]
    proof_status: dict[str, str]

    @property
    def mismatch_total(self) -> int:
        return sum(self.mismatch_counts.values())

    @property
    def status(self) -> str:
        if self.mismatch_total:
            return "failed-mismatch"
        if self.proof_gaps:
            return "matched-with-unwitnessed-requirements"
        return "passed"

    def as_dict(self) -> dict[str, Any]:
        totals: Counter[str] = Counter()
        for value in self.boundaries.values():
            totals.update(value.as_dict())
        notices: list[dict[str, Any]] = []
        if totals["source_sockets_intentionally_ignored"]:
            notices.append(
                {
                    "code": "restic-intentionally-ignores-unix-sockets",
                    "count": totals["source_sockets_intentionally_ignored"],
                    "semantic_effect": "ephemeral-ipc-endpoints-not-recovery-data",
                }
            )
        if totals["sparse_source_files_without_restored_holes"]:
            notices.append(
                {
                    "code": "restic-does-not-store-exact-sparse-hole-layout",
                    "count": totals["sparse_source_files_without_restored_holes"],
                    "semantic_effect": "content-hash-and-logical-size-still-verified",
                }
            )
        if totals["nested_btrfs_boundary_mtime_exemptions"]:
            notices.append(
                {
                    "code": "nested-btrfs-boundary-marker-mtime-not-compared",
                    "count": totals["nested_btrfs_boundary_mtime_exemptions"],
                    "semantic_effect": "excluded-subvolume-boundary-not-production-directory-content",
                }
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "status": self.status,
            "mode": "read-only-noatime-full-sha256",
            "privacy": "no-file-names-no-file-content-hashed-path-tokens-only-on-failure",
            "boundaries": {key: value.as_dict() for key, value in sorted(self.boundaries.items())},
            "totals": dict(sorted(totals.items())),
            "manifests": {
                "algorithm": "sha256",
                "source": self.source_manifest,
                "restored": self.restored_manifest,
                "equal": self.source_manifest == self.restored_manifest,
            },
            "mismatch_total": self.mismatch_total,
            "mismatch_counts": dict(sorted(self.mismatch_counts.items())),
            "boundary_mismatch_counts": {
                boundary: dict(sorted(counts.items()))
                for boundary, counts in sorted(self.boundary_mismatch_counts.items())
                if counts
            },
            "failure_examples": self.failure_examples,
            "proof_status": dict(sorted(self.proof_status.items())),
            "proof_gaps": sorted(self.proof_gaps),
            "notices": notices,
        }


@dataclass
class _FileObservation:
    digest: str
    sparse: bool | None
    bytes_hashed: int


@dataclass
class _Verifier:
    boundaries: list[Boundary]
    require_witnesses: bool
    selinux_expectation: str
    progress_interval: int
    stats: dict[str, BoundaryStats] = field(default_factory=dict)
    mismatch_counts: Counter[str] = field(default_factory=Counter)
    boundary_mismatch_counts: dict[str, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    failure_examples: list[dict[str, str]] = field(default_factory=list)
    source_manifest: Any = field(default_factory=hashlib.sha256)
    restored_manifest: Any = field(default_factory=hashlib.sha256)
    source_file_cache: dict[tuple[str, int, int, int, int, int], _FileObservation] = field(
        default_factory=dict
    )
    restored_file_cache: dict[tuple[str, int, int, int, int, int], _FileObservation] = field(
        default_factory=dict
    )
    source_links: dict[tuple[str, int, int], list[tuple[str, tuple[int, int]]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    restored_links: dict[tuple[str, int, int], list[tuple[str, tuple[int, int]]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    processed_entries: int = 0

    def run(self) -> Result:
        for boundary in self.boundaries:
            if boundary.boundary_id in self.stats:
                raise VerificationFatal("duplicate-boundary-id", boundary.boundary_id)
            self.stats[boundary.boundary_id] = BoundaryStats()
            self._compare_boundary(boundary)
        self._verify_hardlinks()
        proof_status, proof_gaps = self._proofs()
        return Result(
            boundaries=self.stats,
            mismatch_counts=self.mismatch_counts,
            boundary_mismatch_counts=self.boundary_mismatch_counts,
            failure_examples=self.failure_examples,
            source_manifest=self.source_manifest.hexdigest(),
            restored_manifest=self.restored_manifest.hexdigest(),
            proof_gaps=proof_gaps,
            proof_status=proof_status,
        )

    def _compare_boundary(self, boundary: Boundary) -> None:
        stack: list[tuple[Path, Path, tuple[str, ...]]] = [(boundary.source, boundary.restored, ())]
        while stack:
            source, restored, relative = stack.pop()
            token = path_token(boundary.boundary_id, relative)
            source_stat = self._lstat(source, boundary.boundary_id, token, "source-lstat-failed")
            restored_stat = self._lstat(
                restored, boundary.boundary_id, token, "restored-lstat-failed"
            )
            kind = self._compare_entry(
                boundary,
                source,
                restored,
                relative,
                token,
                source_stat,
                restored_stat,
            )
            if kind != "directory":
                continue

            source_names = self._directory_names(
                source,
                source_stat,
                boundary.boundary_id,
                token,
                "source-directory-read-failed",
            )
            restored_names = self._directory_names(
                restored,
                restored_stat,
                boundary.boundary_id,
                token,
                "restored-directory-read-failed",
            )
            if not relative and boundary.excluded_top_level:
                source_names.difference_update(boundary.excluded_top_level)
                restored_names.difference_update(boundary.excluded_top_level)

            for name in sorted(source_names - restored_names, key=os.fsencode):
                missing_token = path_token(boundary.boundary_id, relative + (name,))
                missing_source = source / name
                missing_stat = self._lstat(
                    missing_source,
                    boundary.boundary_id,
                    missing_token,
                    "missing-source-lstat-failed",
                )
                if intentionally_ignored_source_socket(missing_stat):
                    self.stats[boundary.boundary_id].source_sockets_intentionally_ignored += 1
                else:
                    self._mismatch(
                        "missing-restored-entry",
                        boundary.boundary_id,
                        missing_token,
                    )
            for name in sorted(restored_names - source_names, key=os.fsencode):
                self._mismatch(
                    "unexpected-restored-entry",
                    boundary.boundary_id,
                    path_token(boundary.boundary_id, relative + (name,)),
                )
            for name in sorted(source_names & restored_names, key=os.fsencode, reverse=True):
                stack.append((source / name, restored / name, relative + (name,)))

    def _compare_entry(
        self,
        boundary: Boundary,
        source: Path,
        restored: Path,
        relative: tuple[str, ...],
        token: str,
        source_stat: os.stat_result,
        restored_stat: os.stat_result,
    ) -> str:
        boundary_stats = self.stats[boundary.boundary_id]
        boundary_stats.entries += 1
        self.processed_entries += 1
        if self.progress_interval and self.processed_entries % self.progress_interval == 0:
            print(
                f"progress entries={self.processed_entries} regular_files="
                f"{sum(item.regular_files for item in self.stats.values())}",
                file=sys.stderr,
                flush=True,
            )

        source_kind = file_kind(source_stat.st_mode)
        restored_kind = file_kind(restored_stat.st_mode)
        if source_kind != restored_kind:
            self._mismatch("file-type", boundary.boundary_id, token)
            self._update_manifests(
                boundary.boundary_id,
                token,
                metadata_record(source_stat, source_kind),
                metadata_record(restored_stat, restored_kind),
            )
            return "type-mismatch"

        if stat.S_IMODE(source_stat.st_mode) != stat.S_IMODE(restored_stat.st_mode):
            self._mismatch("mode", boundary.boundary_id, token)
        if source_stat.st_uid != restored_stat.st_uid:
            self._mismatch("uid", boundary.boundary_id, token)
        if source_stat.st_gid != restored_stat.st_gid:
            self._mismatch("gid", boundary.boundary_id, token)
        nested_boundary_mtime = (
            source_stat.st_mtime_ns != restored_stat.st_mtime_ns
            and is_nested_btrfs_boundary_marker(boundary, relative, source_stat)
        )
        if source_stat.st_mtime_ns != restored_stat.st_mtime_ns:
            if nested_boundary_mtime:
                boundary_stats.nested_btrfs_boundary_mtime_exemptions += 1
            else:
                self._mismatch("mtime", boundary.boundary_id, token)

        source_extra: dict[str, Any] = {}
        restored_extra: dict[str, Any] = {}
        if source_kind == "directory":
            boundary_stats.directories += 1
        elif source_kind == "regular":
            boundary_stats.regular_files += 1
            boundary_stats.logical_file_bytes += source_stat.st_size
            if source_stat.st_size != restored_stat.st_size:
                self._mismatch("file-size", boundary.boundary_id, token)
            source_observation = self._observe_file(
                source,
                source_stat,
                boundary.boundary_id,
                token,
                self.source_file_cache,
                "source",
            )
            restored_observation = self._observe_file(
                restored,
                restored_stat,
                boundary.boundary_id,
                token,
                self.restored_file_cache,
                "restored",
            )
            boundary_stats.source_unique_bytes_hashed += source_observation.bytes_hashed
            boundary_stats.restored_unique_bytes_hashed += restored_observation.bytes_hashed
            if source_observation.digest != restored_observation.digest:
                self._mismatch("file-content-sha256", boundary.boundary_id, token)
            if source_observation.sparse is True:
                boundary_stats.sparse_source_files += 1
                if restored_observation.sparse is True:
                    boundary_stats.sparse_restored_files += 1
                else:
                    boundary_stats.sparse_source_files_without_restored_holes += 1
            source_extra.update(
                content_sha256=source_observation.digest,
                size=source_stat.st_size,
            )
            restored_extra.update(
                content_sha256=restored_observation.digest,
                size=restored_stat.st_size,
            )
            source_link_key = (
                boundary.boundary_id,
                source_stat.st_dev,
                source_stat.st_ino,
            )
            restored_link_key = (
                boundary.boundary_id,
                restored_stat.st_dev,
                restored_stat.st_ino,
            )
            source_target = (restored_stat.st_dev, restored_stat.st_ino)
            restored_source = (source_stat.st_dev, source_stat.st_ino)
            self.source_links[source_link_key].append((token, source_target))
            self.restored_links[restored_link_key].append((token, restored_source))
        elif source_kind == "symlink":
            boundary_stats.symlinks += 1
            source_target = self._readlink(
                source, boundary.boundary_id, token, "source-readlink-failed"
            )
            restored_target = self._readlink(
                restored, boundary.boundary_id, token, "restored-readlink-failed"
            )
            if source_target != restored_target:
                self._mismatch("symlink-target", boundary.boundary_id, token)
            source_extra["target_sha256"] = hashlib.sha256(os.fsencode(source_target)).hexdigest()
            restored_extra["target_sha256"] = hashlib.sha256(
                os.fsencode(restored_target)
            ).hexdigest()
        else:
            boundary_stats.special_files += 1
            if source_kind in {"block-device", "character-device"}:
                if source_stat.st_rdev != restored_stat.st_rdev:
                    self._mismatch("device-identity", boundary.boundary_id, token)
                source_extra["rdev"] = source_stat.st_rdev
                restored_extra["rdev"] = restored_stat.st_rdev

        source_xattrs = self._xattrs(source, boundary.boundary_id, token, "source")
        restored_xattrs = self._xattrs(restored, boundary.boundary_id, token, "restored")
        if source_xattrs is None:
            boundary_stats.xattr_unsupported_source_paths += 1
            normalized_source_xattrs: list[tuple[str, str]] = []
            normalized_restored_xattrs: list[tuple[str, str]] = []
        else:
            if restored_xattrs is None:
                self._mismatch("restored-xattrs-unsupported", boundary.boundary_id, token)
                restored_xattrs = {}
            if source_xattrs != restored_xattrs:
                self._mismatch("xattr-set-or-value", boundary.boundary_id, token)
            normalized_source_xattrs = xattr_digest_records(source_xattrs)
            normalized_restored_xattrs = xattr_digest_records(restored_xattrs)
            if source_xattrs:
                boundary_stats.paths_with_xattrs += 1
                boundary_stats.xattr_entries += len(source_xattrs)
            if any(
                name in source_xattrs
                for name in ("system.posix_acl_access", "system.posix_acl_default")
            ):
                boundary_stats.acl_paths += 1
            if "security.selinux" in source_xattrs:
                boundary_stats.selinux_label_paths += 1
            if "security.capability" in source_xattrs:
                boundary_stats.capability_paths += 1

        source_record = metadata_record(source_stat, source_kind)
        restored_record = metadata_record(restored_stat, restored_kind)
        if nested_boundary_mtime:
            source_record["mtime_semantics"] = "excluded-nested-btrfs-boundary-marker"
            restored_record["mtime_semantics"] = "excluded-nested-btrfs-boundary-marker"
            restored_record["mtime_ns"] = source_record["mtime_ns"]
        source_record.update(source_extra, xattrs=normalized_source_xattrs)
        restored_record.update(restored_extra, xattrs=normalized_restored_xattrs)
        self._update_manifests(boundary.boundary_id, token, source_record, restored_record)
        return source_kind

    def _observe_file(
        self,
        path: Path,
        expected: os.stat_result,
        boundary: str,
        token: str,
        cache: dict[tuple[str, int, int, int, int, int], _FileObservation],
        side: str,
    ) -> _FileObservation:
        key = (
            boundary,
            expected.st_dev,
            expected.st_ino,
            expected.st_size,
            expected.st_mtime_ns,
            expected.st_ctime_ns,
        )
        if key in cache:
            cached = cache[key]
            return _FileObservation(cached.digest, cached.sparse, 0)
        flags = noatime_flags(
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise VerificationFatal(
                f"{side}-file-open-failed", boundary, token, exc.errno
            ) from None
        try:
            before = os.fstat(descriptor)
            if identity_tuple(before) != identity_tuple(expected):
                raise VerificationFatal(f"{side}-file-changed-before-read", boundary, token)
            digest = hashlib.sha256()
            bytes_hashed = 0
            while True:
                try:
                    chunk = os.read(descriptor, CHUNK_SIZE)
                except OSError as exc:
                    raise VerificationFatal(
                        f"{side}-file-read-failed", boundary, token, exc.errno
                    ) from None
                if not chunk:
                    break
                digest.update(chunk)
                bytes_hashed += len(chunk)
            sparse = self._sparse_state(descriptor, before.st_size, boundary, token, side)
            after = os.fstat(descriptor)
            if identity_tuple(after) != identity_tuple(before):
                raise VerificationFatal(f"{side}-file-changed-during-read", boundary, token)
        finally:
            os.close(descriptor)
        observation = _FileObservation(digest.hexdigest(), sparse, bytes_hashed)
        cache[key] = observation
        return observation

    def _sparse_state(
        self, descriptor: int, size: int, boundary: str, token: str, side: str
    ) -> bool | None:
        if size == 0:
            return False
        if not hasattr(os, "SEEK_DATA") or not hasattr(os, "SEEK_HOLE"):
            return None
        position = 0
        while position < size:
            try:
                data_position = os.lseek(descriptor, position, os.SEEK_DATA)
            except OSError as exc:
                if exc.errno == errno.ENXIO:
                    return True
                if exc.errno in UNSUPPORTED_XATTR_ERRNOS or exc.errno == errno.EINVAL:
                    return None
                raise VerificationFatal(
                    f"{side}-seek-data-failed", boundary, token, exc.errno
                ) from None
            if data_position > position:
                return True
            try:
                hole_position = os.lseek(descriptor, data_position, os.SEEK_HOLE)
            except OSError as exc:
                if exc.errno in UNSUPPORTED_XATTR_ERRNOS or exc.errno == errno.EINVAL:
                    return None
                raise VerificationFatal(
                    f"{side}-seek-hole-failed", boundary, token, exc.errno
                ) from None
            if hole_position < size:
                return True
            return False
        return False

    def _xattrs(self, path: Path, boundary: str, token: str, side: str) -> dict[str, bytes] | None:
        try:
            names = os.listxattr(path, follow_symlinks=False)
        except OSError as exc:
            if exc.errno in UNSUPPORTED_XATTR_ERRNOS:
                return None
            raise VerificationFatal(
                f"{side}-xattr-list-failed", boundary, token, exc.errno
            ) from None
        values: dict[str, bytes] = {}
        for name in sorted(names, key=os.fsencode):
            try:
                values[name] = os.getxattr(path, name, follow_symlinks=False)
            except OSError as exc:
                raise VerificationFatal(
                    f"{side}-xattr-read-failed", boundary, token, exc.errno
                ) from None
        return values

    def _directory_names(
        self,
        path: Path,
        expected: os.stat_result,
        boundary: str,
        token: str,
        fatal_code: str,
    ) -> set[str]:
        flags = noatime_flags(
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise VerificationFatal(fatal_code, boundary, token, exc.errno) from None
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
                raise VerificationFatal("directory-changed-before-read", boundary, token)
            try:
                with os.scandir(descriptor) as iterator:
                    return {entry.name for entry in iterator}
            except OSError as exc:
                raise VerificationFatal(fatal_code, boundary, token, exc.errno) from None
        finally:
            os.close(descriptor)

    def _lstat(self, path: Path, boundary: str, token: str, code: str) -> os.stat_result:
        try:
            return path.lstat()
        except OSError as exc:
            raise VerificationFatal(code, boundary, token, exc.errno) from None

    def _readlink(self, path: Path, boundary: str, token: str, code: str) -> str:
        try:
            return os.readlink(path)
        except OSError as exc:
            raise VerificationFatal(code, boundary, token, exc.errno) from None

    def _mismatch(self, code: str, boundary: str, token: str) -> None:
        self.mismatch_counts[code] += 1
        self.boundary_mismatch_counts[boundary][code] += 1
        if len(self.failure_examples) < MAX_FAILURE_EXAMPLES:
            self.failure_examples.append({"code": code, "boundary": boundary, "path_token": token})

    def _update_manifests(
        self,
        boundary: str,
        token: str,
        source_record: dict[str, Any],
        restored_record: dict[str, Any],
    ) -> None:
        prefix = {"boundary": boundary, "path_token": token}
        self.source_manifest.update(canonical_json_bytes(prefix | source_record))
        self.source_manifest.update(b"\n")
        self.restored_manifest.update(canonical_json_bytes(prefix | restored_record))
        self.restored_manifest.update(b"\n")

    def _verify_hardlinks(self) -> None:
        for (boundary, _device, _inode), records in self.source_links.items():
            if len(records) < 2:
                continue
            stats = self.stats[boundary]
            stats.hardlink_groups_witnessed += 1
            stats.hardlink_paths_witnessed += len(records)
            restored_inodes = {restored_inode for _token, restored_inode in records}
            if len(restored_inodes) != 1:
                self._mismatch("hardlink-split", boundary, group_token(boundary, records))
        for (boundary, _device, _inode), records in self.restored_links.items():
            if len(records) < 2:
                continue
            source_inodes = {source_inode for _token, source_inode in records}
            if len(source_inodes) != 1:
                self._mismatch(
                    "unexpected-hardlink-merge",
                    boundary,
                    group_token(boundary, records),
                )

    def _proofs(self) -> tuple[dict[str, str], list[str]]:
        total = Counter()
        for value in self.stats.values():
            total.update(value.as_dict())
        mismatch = self.mismatch_counts
        all_matched = not mismatch
        content_matched = not any(mismatch[key] for key in ("file-size", "file-content-sha256"))
        tree_matched = not any(
            mismatch[key]
            for key in (
                "file-type",
                "missing-restored-entry",
                "unexpected-restored-entry",
            )
        )
        ownership_matched = not any(mismatch[key] for key in ("mode", "uid", "gid"))
        xattrs_matched = not any(
            mismatch[key] for key in ("restored-xattrs-unsupported", "xattr-set-or-value")
        )
        proof_status = {
            "regular-file-content": passed_if(content_matched),
            "directory-tree": passed_if(tree_matched),
            "mode-owner-group": passed_if(ownership_matched),
            "timestamps": passed_if(mismatch["mtime"] == 0),
            "symlink": witness_status(total["symlinks"], mismatch["symlink-target"] == 0),
            "hard-link": witness_status(
                total["hardlink_groups_witnessed"],
                not any(mismatch[key] for key in ("hardlink-split", "unexpected-hardlink-merge")),
            ),
            "acl": witness_status(total["acl_paths"], xattrs_matched),
            "extended-attributes": witness_status(total["paths_with_xattrs"], xattrs_matched),
            "selinux-label": self._selinux_proof(total, xattrs_matched),
            "sparse-file": witness_status(total["sparse_restored_files"], True),
            "boot-files": boundary_witness_status(
                self.stats.get("boot"), not self.boundary_mismatch_counts.get("boot")
            ),
            "efi-files": boundary_witness_status(
                self.stats.get("efi"), not self.boundary_mismatch_counts.get("efi")
            ),
            "root-home-boundary-separation": passed_if(
                tree_matched and "root" in self.stats and "home" in self.stats
            ),
            "nested-subvolume-separation": passed_if(
                tree_matched and "systemd_machines" in self.stats
            ),
            "full-restore-to-nonproduction-target": passed_if(all_matched),
            "bootability-or-offline-reconstruction": "not-tested-by-file-comparator",
        }
        gaps: list[str] = []
        if self.require_witnesses:
            for proof in (
                "symlink",
                "hard-link",
                "acl",
                "extended-attributes",
                "selinux-label",
                "sparse-file",
                "boot-files",
                "efi-files",
            ):
                if proof_status[proof] in {
                    "unwitnessed",
                    "disabled-host-limitation-recorded",
                }:
                    if (
                        proof == "selinux-label"
                        and proof_status[proof] == "disabled-host-limitation-recorded"
                    ):
                        continue
                    gaps.append(f"{proof}-unwitnessed")
        return proof_status, gaps

    def _selinux_proof(self, total: Counter[str], all_matched: bool) -> str:
        if total["selinux_label_paths"]:
            return passed_if(all_matched and self.mismatch_counts["xattr-set-or-value"] == 0)
        if self.selinux_expectation == "disabled-reviewed":
            return "disabled-host-limitation-recorded"
        return "unwitnessed"


def noatime_flags(base: int) -> int:
    value = getattr(os, "O_NOATIME", None)
    if value is None:
        raise VerificationFatal("o-noatime-unavailable")
    return base | value


def identity_tuple(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def file_kind(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "regular"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISBLK(mode):
        return "block-device"
    if stat.S_ISCHR(mode):
        return "character-device"
    return "unknown"


def intentionally_ignored_source_socket(value: os.stat_result) -> bool:
    """Restic 0.19.1 intentionally omits Unix socket directory entries."""

    return stat.S_ISSOCK(value.st_mode)


def is_nested_btrfs_boundary_marker(
    boundary: Boundary,
    relative: tuple[str, ...],
    value: os.stat_result,
) -> bool:
    """Identify a descendant Btrfs subvolume root or snapshot stub.

    Btrfs subvolume roots use inode 256.  A nested subvolume represented inside
    a snapshot appears as an empty boundary marker with inode 2.  The mapping
    root itself is never exempted.
    """

    return (
        boundary.btrfs_snapshot
        and bool(relative)
        and stat.S_ISDIR(value.st_mode)
        and value.st_ino in {2, 256}
    )


def metadata_record(value: os.stat_result, kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "mode": stat.S_IMODE(value.st_mode),
        "uid": value.st_uid,
        "gid": value.st_gid,
        "mtime_ns": value.st_mtime_ns,
    }


def xattr_digest_records(values: dict[str, bytes]) -> list[tuple[str, str]]:
    return [
        (
            hashlib.sha256(os.fsencode(name)).hexdigest(),
            hashlib.sha256(value).hexdigest(),
        )
        for name, value in sorted(values.items(), key=lambda item: os.fsencode(item[0]))
    ]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def path_token(boundary: str, relative: Iterable[str]) -> str:
    digest = hashlib.sha256()
    digest.update(boundary.encode("ascii"))
    for part in relative:
        digest.update(b"\x00")
        digest.update(os.fsencode(part))
    return digest.hexdigest()[:24]


def group_token(boundary: str, records: list[tuple[str, tuple[int, int]]]) -> str:
    digest = hashlib.sha256(boundary.encode("ascii"))
    for token, _inode in sorted(records):
        digest.update(token.encode("ascii"))
    return digest.hexdigest()[:24]


def passed_if(condition: bool) -> str:
    return "passed" if condition else "failed"


def witness_status(count: int, matched: bool) -> str:
    if not count:
        return "unwitnessed"
    return "passed" if matched else "failed"


def boundary_witness_status(value: BoundaryStats | None, matched: bool) -> str:
    if value is None or value.regular_files == 0:
        return "unwitnessed"
    return "passed" if matched else "failed"


def verify(
    boundaries: list[Boundary],
    *,
    require_witnesses: bool = True,
    selinux_expectation: str = "required",
    progress_interval: int = 10_000,
) -> Result:
    """Compare mappings and return a privacy-preserving aggregate result."""

    return _Verifier(
        boundaries=boundaries,
        require_witnesses=require_witnesses,
        selinux_expectation=selinux_expectation,
        progress_interval=progress_interval,
    ).run()


def build_machine_boundaries(snapshot_set: Path, restore_target: Path) -> list[Boundary]:
    snapshot_set = validated_root(snapshot_set, "snapshot-set")
    restore_target = validated_root(restore_target, "restore-target")
    if restore_target.name != "data" or not restore_target.parent.name.startswith(
        "jarvis-r2-restore-"
    ):
        raise VerificationFatal("restore-target-not-approved-isolation-shape")
    if (
        snapshot_set == restore_target
        or snapshot_set in restore_target.parents
        or restore_target in snapshot_set.parents
    ):
        raise VerificationFatal("source-restore-overlap")
    sources = {
        "root": snapshot_set / "root",
        "home": snapshot_set / "home",
        "systemd_machines": snapshot_set / "machines",
        "boot": Path("/boot"),
        "efi": Path("/boot/efi"),
    }
    for boundary_id, source in sources.items():
        validated_root(source, f"source-{boundary_id}")
    for boundary_id in ("root", "home", "systemd_machines"):
        if sources[boundary_id].lstat().st_ino != 256:
            raise VerificationFatal(f"source-{boundary_id}-not-btrfs-subvolume-root")
    if restore_target.lstat().st_ino != 256:
        raise VerificationFatal("restore-target-not-btrfs-subvolume-root")
    return [
        Boundary(
            boundary_id=boundary_id,
            source=source,
            restored=restore_target / source.relative_to("/"),
            excluded_top_level=frozenset({"efi"}) if boundary_id == "boot" else frozenset(),
            btrfs_snapshot=boundary_id in {"root", "home", "systemd_machines"},
        )
        for boundary_id, source in sources.items()
    ]


def validate_machine_container_shape(snapshot_set: Path, restore_target: Path) -> None:
    """Reject a missing or unexpected sixth root outside the five mappings."""

    expected_directories = (
        (restore_target, (), {"boot", "var"}),
        (restore_target / "var", ("var",), {"lib"}),
        (restore_target / "var" / "lib", ("var", "lib"), {snapshot_set.name}),
        (
            restore_target / "var" / "lib" / snapshot_set.name,
            ("var", "lib", snapshot_set.name),
            {"root", "home", "machines"},
        ),
    )
    for directory, relative, expected in expected_directories:
        actual = directory_names_noatime(
            directory, "restore-container", path_token("restore-container", relative)
        )
        missing = expected - actual
        unexpected = actual - expected
        if missing:
            name = min(missing, key=os.fsencode)
            raise VerificationFatal(
                "restore-container-missing-entry",
                "restore-container",
                path_token("restore-container", relative + (name,)),
            )
        if unexpected:
            name = min(unexpected, key=os.fsencode)
            raise VerificationFatal(
                "restore-container-unexpected-entry",
                "restore-container",
                path_token("restore-container", relative + (name,)),
            )


def directory_names_noatime(path: Path, boundary: str, token: str) -> set[str]:
    try:
        expected = path.lstat()
    except OSError as exc:
        raise VerificationFatal(
            "container-directory-lstat-failed", boundary, token, exc.errno
        ) from None
    if not stat.S_ISDIR(expected.st_mode):
        raise VerificationFatal("container-entry-not-directory", boundary, token)
    flags = noatime_flags(
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise VerificationFatal(
            "container-directory-open-failed", boundary, token, exc.errno
        ) from None
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
            raise VerificationFatal("container-directory-changed-before-read", boundary, token)
        try:
            with os.scandir(descriptor) as iterator:
                return {entry.name for entry in iterator}
        except OSError as exc:
            raise VerificationFatal(
                "container-directory-read-failed", boundary, token, exc.errno
            ) from None
    finally:
        os.close(descriptor)


def validated_root(path: Path, code: str) -> Path:
    if not path.is_absolute():
        raise VerificationFatal(f"{code}-not-absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise VerificationFatal(f"{code}-unavailable", error_number=exc.errno) from None
    if resolved != path:
        raise VerificationFatal(f"{code}-symlink-or-noncanonical")
    try:
        value = path.lstat()
    except OSError as exc:
        raise VerificationFatal(f"{code}-lstat-failed", error_number=exc.errno) from None
    if not stat.S_ISDIR(value.st_mode):
        raise VerificationFatal(f"{code}-not-directory")
    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only, privacy-preserving comparison of the five Fedora recovery boundaries."
    )
    parser.add_argument("--snapshot-set", type=Path, required=True)
    parser.add_argument("--restore-target", type=Path, required=True)
    parser.add_argument(
        "--selinux-expectation",
        choices=("required", "disabled-reviewed"),
        default="required",
        help="Use disabled-reviewed only when separate host evidence has already established that limitation.",
    )
    parser.add_argument("--progress-interval", type=int, default=10_000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.progress_interval < 0:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "status": "fatal",
                    "code": "negative-progress-interval",
                }
            )
        )
        return 4
    try:
        boundaries = build_machine_boundaries(args.snapshot_set, args.restore_target)
        validate_machine_container_shape(args.snapshot_set, args.restore_target)
        result = verify(
            boundaries,
            require_witnesses=True,
            selinux_expectation=args.selinux_expectation,
            progress_interval=args.progress_interval,
        )
    except VerificationFatal as exc:
        report: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "status": "fatal",
            "code": exc.code,
            "boundary": exc.boundary,
            "path_token": exc.token,
        }
        if exc.error_number is not None:
            report["errno"] = exc.error_number
        print(json.dumps(report, sort_keys=True))
        return 4
    print(json.dumps(result.as_dict(), sort_keys=True))
    if result.mismatch_total:
        return 3
    if result.proof_gaps:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
