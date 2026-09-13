"""Private append-only broker event journal used to recover TUI state."""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import re
import stat
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

ZERO_HASH = "0" * 64
SENSITIVE = re.compile(
    r"(?i)(password|passwd|secret|token|private[_-]?key|api[_-]?key|credential|cookie|authorization)"
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if SENSITIVE.search(str(key)) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


class JournalIntegrityError(ValueError):
    def __init__(self, reason: str, count: int) -> None:
        super().__init__(reason)
        self.reason = reason
        self.count = count


@dataclass
class _JournalHead:
    identity: tuple[int, int]
    size: int
    mtime_ns: int
    ctime_ns: int
    verified_offset: int
    sequence: int
    last_hash: str
    prefix_hasher: Any
    records: list[dict[str, Any]] = field(default_factory=list)
    idempotency: dict[str, dict[str, Any]] = field(default_factory=dict)


class EventJournal:
    """Hash-linked JSONL with one verified prefix scan and incremental appends."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._head: _JournalHead | None = None
        self._thread_lock = threading.RLock()
        self.full_scan_count = 0
        self.incremental_scan_count = 0
        self.cache_parsed_line_count = 0
        self.verification_scan_count = 0

    def _open(self) -> BinaryIO:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        parent_info = self.path.parent.lstat()
        if not stat.S_ISDIR(parent_info.st_mode):
            raise JournalIntegrityError("unsafe_parent", 0)
        flags = os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(self.path, flags, 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            os.close(fd)
            raise JournalIntegrityError("special_file", 0)
        if stat.S_IMODE(info.st_mode) != 0o600:
            os.fchmod(fd, 0o600)
        return os.fdopen(fd, "r+b", buffering=0)

    @staticmethod
    def _identity(info: os.stat_result) -> tuple[int, int]:
        return int(info.st_dev), int(info.st_ino)

    @staticmethod
    def _parse_line(line: bytes, count: int) -> dict[str, Any]:
        if not line.endswith(b"\n"):
            raise JournalIntegrityError("truncated_record", count)
        try:
            value = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JournalIntegrityError("invalid_json", count) from exc
        if not isinstance(value, dict):
            raise JournalIntegrityError("invalid_record_shape", count)
        return value

    @staticmethod
    def _verify_record(
        original: dict[str, Any], previous: str, expected_sequence: int, count: int
    ) -> str:
        event = dict(original)
        supplied = event.pop("event_hash", None)
        if event.get("sequence") != expected_sequence:
            raise JournalIntegrityError("sequence_mismatch", count)
        if event.get("previous_hash") != previous:
            raise JournalIntegrityError("previous_hash_mismatch", count)
        expected = hashlib.sha256(previous.encode() + _canonical(event)).hexdigest()
        if supplied != expected:
            raise JournalIntegrityError("event_hash_mismatch", count)
        return str(supplied)

    def _scan_full_locked(self, handle: BinaryIO) -> None:
        self.full_scan_count += 1
        handle.seek(0)
        records: list[dict[str, Any]] = []
        idempotency: dict[str, dict[str, Any]] = {}
        previous = ZERO_HASH
        prefix_hasher = hashlib.sha256()
        count = 0
        while line := handle.readline():
            prefix_hasher.update(line)
            value = self._parse_line(line, count)
            previous = self._verify_record(value, previous, count + 1, count)
            records.append(value)
            key = value.get("details", {}).get("idempotency_key")
            if isinstance(key, str) and key:
                idempotency.setdefault(key, value)
            count += 1
            self.cache_parsed_line_count += 1
        offset = handle.tell()
        info = os.fstat(handle.fileno())
        if offset != info.st_size:
            raise JournalIntegrityError("size_changed_during_scan", count)
        self._head = _JournalHead(
            identity=self._identity(info),
            size=int(info.st_size),
            mtime_ns=int(info.st_mtime_ns),
            ctime_ns=int(info.st_ctime_ns),
            verified_offset=offset,
            sequence=count,
            last_hash=previous,
            prefix_hasher=prefix_hasher,
            records=records,
            idempotency=idempotency,
        )

    def _scan_suffix_locked(self, handle: BinaryIO, info: os.stat_result) -> None:
        assert self._head is not None
        self.incremental_scan_count += 1
        handle.seek(self._head.verified_offset)
        previous = self._head.last_hash
        sequence = self._head.sequence
        additions: list[dict[str, Any]] = []
        candidate_hasher = self._head.prefix_hasher.copy()
        while line := handle.readline():
            value = self._parse_line(line, sequence)
            previous = self._verify_record(value, previous, sequence + 1, sequence)
            additions.append(value)
            candidate_hasher.update(line)
            sequence += 1
            self.cache_parsed_line_count += 1
        offset = handle.tell()
        final_info = os.fstat(handle.fileno())
        if offset != final_info.st_size or final_info.st_size < info.st_size:
            raise JournalIntegrityError("size_changed_during_scan", sequence)
        for value in additions:
            key = value.get("details", {}).get("idempotency_key")
            if isinstance(key, str) and key:
                self._head.idempotency.setdefault(key, value)
        self._head.records.extend(additions)
        self._head.identity = self._identity(final_info)
        self._head.size = int(final_info.st_size)
        self._head.mtime_ns = int(final_info.st_mtime_ns)
        self._head.ctime_ns = int(final_info.st_ctime_ns)
        self._head.verified_offset = offset
        self._head.sequence = sequence
        self._head.last_hash = previous
        self._head.prefix_hasher = candidate_hasher

    def _cached_prefix_matches_locked(self, handle: BinaryIO) -> bool:
        """Hash the verified prefix when another writer changed the inode.

        This is intentionally not JSON parsing. It runs only after external
        modification evidence; appends made through this instance update the
        cached hash state incrementally.
        """
        assert self._head is not None
        remaining = self._head.verified_offset
        observed = hashlib.sha256()
        handle.seek(0)
        while remaining:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                return False
            observed.update(chunk)
            remaining -= len(chunk)
        return bool(observed.digest() == self._head.prefix_hasher.digest())

    def _sync_locked(self, handle: BinaryIO) -> None:
        info = os.fstat(handle.fileno())
        head = self._head
        if (
            head is None
            or self._identity(info) != head.identity
            or info.st_size < head.verified_offset
        ):
            self._scan_full_locked(handle)
            return
        if info.st_size == head.verified_offset:
            if info.st_mtime_ns != head.mtime_ns or info.st_ctime_ns != head.ctime_ns:
                self._scan_full_locked(handle)
            return
        if (
            info.st_mtime_ns != head.mtime_ns or info.st_ctime_ns != head.ctime_ns
        ) and not self._cached_prefix_matches_locked(handle):
            self._scan_full_locked(handle)
            return
        self._scan_suffix_locked(handle, info)

    def append(
        self,
        event_type: str,
        actor: str,
        status: str,
        details: dict[str, Any],
        task_id: str | None = None,
    ) -> dict[str, Any]:
        with self._thread_lock, self._open() as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                self._sync_locked(handle)
                return copy.deepcopy(
                    self._append_locked(handle, event_type, actor, status, details, task_id)
                )
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def append_once(
        self,
        idempotency_key: str,
        event_type: str,
        actor: str,
        status: str,
        details: dict[str, Any],
        task_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Atomically reserve an operation key with O(1) lookup after initialization."""
        with self._thread_lock, self._open() as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                self._sync_locked(handle)
                assert self._head is not None
                existing = self._head.idempotency.get(idempotency_key)
                if existing is not None:
                    return copy.deepcopy(existing), False
                safe_details = dict(details)
                safe_details["idempotency_key"] = idempotency_key
                event = self._append_locked(
                    handle, event_type, actor, status, safe_details, task_id
                )
                self._head.idempotency[idempotency_key] = event
                return copy.deepcopy(event), True
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _append_locked(
        self,
        handle: BinaryIO,
        event_type: str,
        actor: str,
        status: str,
        details: dict[str, Any],
        task_id: str | None,
    ) -> dict[str, Any]:
        assert self._head is not None
        previous = self._head.last_hash
        event = {
            "schema_version": 1,
            "sequence": self._head.sequence + 1,
            "id": f"evt_{uuid4().hex}",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event_type": event_type,
            "actor": actor,
            "status": status,
            "task_id": task_id,
            "details": _redact(details),
            "previous_hash": previous,
        }
        event["event_hash"] = hashlib.sha256(previous.encode() + _canonical(event)).hexdigest()
        encoded = _canonical(event) + b"\n"
        handle.seek(0, os.SEEK_END)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
        info = os.fstat(handle.fileno())
        self._head.identity = self._identity(info)
        self._head.size = int(info.st_size)
        self._head.mtime_ns = int(info.st_mtime_ns)
        self._head.ctime_ns = int(info.st_ctime_ns)
        self._head.verified_offset = int(info.st_size)
        self._head.sequence += 1
        self._head.last_hash = str(event["event_hash"])
        self._head.prefix_hasher.update(encoded)
        self._head.records.append(event)
        return event

    def verify(self) -> tuple[bool, int, str]:
        """Perform a full independent chain scan without trusting the cached head."""
        with self._thread_lock, self._open() as handle:
            fcntl.flock(handle, fcntl.LOCK_SH)
            previous = ZERO_HASH
            count = 0
            self.verification_scan_count += 1
            try:
                handle.seek(0)
                while line := handle.readline():
                    value = self._parse_line(line, count)
                    previous = self._verify_record(value, previous, count + 1, count)
                    count += 1
                if handle.tell() != os.fstat(handle.fileno()).st_size:
                    raise JournalIntegrityError("size_changed_during_scan", count)
                return True, count, previous
            except JournalIntegrityError as exc:
                return False, exc.count, exc.reason
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def read(self) -> tuple[dict[str, Any], ...]:
        with self._thread_lock, self._open() as handle:
            fcntl.flock(handle, fcntl.LOCK_SH)
            try:
                self._sync_locked(handle)
                assert self._head is not None
                return tuple(copy.deepcopy(self._head.records))
            except JournalIntegrityError as exc:
                raise ValueError(f"broker event journal is invalid: {exc.reason}") from exc
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
