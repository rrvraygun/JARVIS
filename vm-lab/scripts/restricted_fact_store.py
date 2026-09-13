#!/usr/bin/env python3
"""Fail-closed restricted-fact storage and activation binding.

This module never handles encryption keys and never invents application-level
cryptography.  Persistence is admitted only when an external unlock/recovery
attestation is bound to the current LUKS device-mapper mount and to an
owner-controlled database path.  SQLite supplies transactional atomicity;
the mounted LUKS filesystem supplies encryption at rest.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import sqlite3
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class StorageGateError(ValueError):
    """Raised when restricted persistence lacks a required guarantee."""


@dataclass(frozen=True)
class StorageAttestation:
    """External user-unlock and recovery evidence bound to one database path."""

    attestation_id: str
    canonical_path: str
    owner_uid: int
    storage_class: str
    mount_id: int
    mount_source: str
    dm_uuid: str
    user_unlocked: bool
    encryption_verified: bool
    recovery_verified: bool
    recovery_evidence_sha256: str


@dataclass(frozen=True)
class ObservationBinding:
    """Immutable identity carried by one approved observation attempt."""

    request_id: str
    proposal_digest: str
    source_catalog_digest: str
    adapter_id: str
    adapter_version: str
    attestation_digest: str
    scope_digest: str
    idempotency_key: str
    expires_at: str


@dataclass(frozen=True)
class FactScopeEntry:
    adapter_id: str
    adapter_version: str
    source_id: str
    fact_ids: tuple[str, ...]


@dataclass(frozen=True)
class ApprovedFactScope:
    """Exact adapter/source/fact membership admitted by one proposal revision."""

    scope_id: str
    proposal_digest: str
    source_catalog_digest: str
    entries: tuple[FactScopeEntry, ...]

    def allows(self, adapter_id: str, adapter_version: str, source_id: str, fact_id: str) -> bool:
        return any(
            entry.adapter_id == adapter_id
            and entry.adapter_version == adapter_version
            and entry.source_id == source_id
            and fact_id in entry.fact_ids
            for entry in self.entries
        )


def canonical_scope_document(scope: ApprovedFactScope) -> str:
    document = {
        "scope_id": scope.scope_id,
        "proposal_digest": scope.proposal_digest,
        "source_catalog_digest": scope.source_catalog_digest,
        "entries": [
            {
                "adapter_id": entry.adapter_id,
                "adapter_version": entry.adapter_version,
                "source_id": entry.source_id,
                "fact_ids": list(entry.fact_ids),
            }
            for entry in scope.entries
        ],
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fact_scope_digest(scope: ApprovedFactScope) -> str:
    return hashlib.sha256(canonical_scope_document(scope).encode("utf-8")).hexdigest()


def load_approved_scope(path: Path) -> ApprovedFactScope:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        entries = tuple(
            FactScopeEntry(
                adapter_id=_safe_text(item["adapter_id"], "scope adapter id"),
                adapter_version=_safe_text(item["adapter_version"], "scope adapter version"),
                source_id=_safe_text(item["source_id"], "scope source id"),
                fact_ids=tuple(
                    _safe_text(value, "scope fact id", 128) for value in item["fact_ids"]
                ),
            )
            for item in document["entries"]
        )
        scope = ApprovedFactScope(
            scope_id=_safe_text(document["scope_id"], "scope id"),
            proposal_digest=_digest(document["proposal_digest"], "scope proposal digest"),
            source_catalog_digest=_digest(
                document["source_catalog_digest"], "scope catalog digest"
            ),
            entries=entries,
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise StorageGateError("approved fact scope is invalid") from exc
    return scope


class EncryptedFactBackend(Protocol):
    encrypted_at_rest: bool
    atomic_writes: bool
    recovery_verified: bool

    def consume_activation(self, binding: ObservationBinding) -> None: ...

    def put(self, fact: dict[str, Any], binding: ObservationBinding) -> None: ...


def _safe_text(value: Any, field_name: str, limit: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise StorageGateError(f"invalid {field_name}")
    if any(ord(char) < 0x20 for char in value):
        raise StorageGateError(f"invalid {field_name}")
    return value


def _digest(value: str, field_name: str) -> str:
    value = _safe_text(value, field_name, 128)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise StorageGateError(f"invalid {field_name}")
    return value


def canonical_attestation_document(attestation: StorageAttestation) -> str:
    """Canonical, key-free representation used for binding and audit."""

    document = {
        "attestation_id": attestation.attestation_id,
        "canonical_path": attestation.canonical_path,
        "owner_uid": attestation.owner_uid,
        "storage_class": attestation.storage_class,
        "mount_id": attestation.mount_id,
        "mount_source": attestation.mount_source,
        "dm_uuid": attestation.dm_uuid,
        "user_unlocked": attestation.user_unlocked,
        "encryption_verified": attestation.encryption_verified,
        "recovery_verified": attestation.recovery_verified,
        "recovery_evidence_sha256": attestation.recovery_evidence_sha256,
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def storage_attestation_digest(attestation: StorageAttestation) -> str:
    return hashlib.sha256(canonical_attestation_document(attestation).encode("utf-8")).hexdigest()


def _canonical_path(path: Path) -> Path:
    if not path.is_absolute():
        raise StorageGateError("restricted storage path must be absolute")
    resolved = path.resolve(strict=False)
    if resolved != path:
        raise StorageGateError("restricted storage path must be canonical")
    return path


def _unescape_mountinfo(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 3 < len(value):
            token = value[index + 1 : index + 4]
            if all(char in "01234567" for char in token):
                result.append(chr(int(token, 8)))
                index += 4
                continue
        result.append(value[index])
        index += 1
    return "".join(result)


def _mount_records(mountinfo_path: Path) -> list[tuple[int, Path, str, str]]:
    try:
        lines = mountinfo_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise StorageGateError("mount topology is unavailable") from exc
    records: list[tuple[int, Path, str, str]] = []
    for line in lines:
        if " - " not in line:
            continue
        left, right = line.split(" - ", 1)
        left_fields = left.split()
        right_fields = right.split()
        if len(left_fields) < 6 or len(right_fields) < 2:
            continue
        try:
            mount_id = int(left_fields[0])
        except ValueError:
            continue
        mount_point = Path(_unescape_mountinfo(left_fields[4]))
        filesystem = right_fields[0]
        source = _unescape_mountinfo(right_fields[1])
        records.append((mount_id, mount_point, filesystem, source))
    return records


class LuksStorageAttestor:
    """Verify a path is currently below the attested dm-crypt mount."""

    def __init__(
        self,
        *,
        mountinfo_path: Path = Path("/proc/self/mountinfo"),
        sysfs_root: Path = Path("/sys"),
    ) -> None:
        self.mountinfo_path = mountinfo_path
        self.sysfs_root = sysfs_root

    def _current_mount(self, path: Path) -> tuple[int, Path, str, str]:
        candidates = [
            record
            for record in _mount_records(self.mountinfo_path)
            if path == record[1] or record[1] in path.parents
        ]
        if not candidates:
            raise StorageGateError("database path is not below a known mount")
        return max(candidates, key=lambda record: len(record[1].parts))

    def _dm_uuid(self, source: str) -> str:
        if not source.startswith("/dev/mapper/"):
            raise StorageGateError("storage source is not a device-mapper path")
        resolved = os.path.realpath(source)
        block_name = os.path.basename(resolved) or os.path.basename(source)
        uuid_path = self.sysfs_root / "class" / "block" / block_name / "dm" / "uuid"
        try:
            value = uuid_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise StorageGateError("device-mapper identity is unavailable") from exc
        if not value.startswith("CRYPT-LUKS"):
            raise StorageGateError("storage source is not an unlocked LUKS mapping")
        return value

    def verify(self, attestation: StorageAttestation) -> None:
        path = _canonical_path(Path(attestation.canonical_path))
        if attestation.storage_class != "luks-backed-local":
            raise StorageGateError("storage attestation is not LUKS-backed local storage")
        if attestation.user_unlocked is not True:
            raise StorageGateError("restricted storage requires explicit user unlock")
        if attestation.encryption_verified is not True:
            raise StorageGateError("restricted storage encryption is not attested")
        if attestation.recovery_verified is not True:
            raise StorageGateError("restricted storage recovery is not verified")
        _digest(attestation.recovery_evidence_sha256, "recovery evidence digest")
        try:
            owner = path.parent.lstat().st_uid
        except OSError as exc:
            raise StorageGateError("restricted storage parent identity is unavailable") from exc
        if owner != attestation.owner_uid:
            raise StorageGateError("restricted storage parent owner changed")
        mount_id, mount_point, filesystem, source = self._current_mount(path.parent)
        if (
            mount_id != attestation.mount_id
            or str(mount_point) != attestation.mount_source.split("|", 1)[0]
        ):
            raise StorageGateError("storage mount identity changed")
        if source != attestation.mount_source.split("|", 1)[-1]:
            raise StorageGateError("storage mount source changed")
        if filesystem == "tmpfs":
            raise StorageGateError("restricted storage cannot use tmpfs")
        dm_uuid = self._dm_uuid(source)
        if dm_uuid != attestation.dm_uuid:
            raise StorageGateError("device-mapper identity changed")


def attest_luks_path(
    path: Path,
    *,
    attestation_id: str,
    owner_uid: int,
    user_unlocked: bool,
    encryption_verified: bool,
    recovery_verified: bool,
    recovery_evidence_sha256: str,
    attestor: LuksStorageAttestor | None = None,
) -> StorageAttestation:
    """Create a mount-bound attestation from current read-only topology."""

    path = _canonical_path(path)
    if not path.parent.is_dir():
        raise StorageGateError("restricted storage parent is unavailable")
    checker = attestor or LuksStorageAttestor()
    mount_id, mount_point, filesystem, source = checker._current_mount(path.parent)
    dm_uuid = checker._dm_uuid(source)
    if filesystem == "tmpfs":
        raise StorageGateError("restricted storage cannot use tmpfs")
    attestation = StorageAttestation(
        attestation_id=_safe_text(attestation_id, "attestation id"),
        canonical_path=str(path),
        owner_uid=owner_uid,
        storage_class="luks-backed-local",
        mount_id=mount_id,
        mount_source=f"{mount_point}|{source}",
        dm_uuid=dm_uuid,
        user_unlocked=user_unlocked,
        encryption_verified=encryption_verified,
        recovery_verified=recovery_verified,
        recovery_evidence_sha256=recovery_evidence_sha256,
    )
    checker.verify(attestation)
    return attestation


def _validate_binding(
    binding: ObservationBinding, expected_attestation_digest: str | None = None
) -> None:
    _safe_text(binding.request_id, "request id")
    _digest(binding.proposal_digest, "proposal digest")
    _digest(binding.source_catalog_digest, "source catalog digest")
    _safe_text(binding.adapter_id, "adapter id")
    _safe_text(binding.adapter_version, "adapter version")
    _digest(binding.attestation_digest, "attestation digest")
    _digest(binding.scope_digest, "scope digest")
    if (
        expected_attestation_digest is not None
        and binding.attestation_digest != expected_attestation_digest
    ):
        raise StorageGateError("observation binding attestation digest mismatch")
    _safe_text(binding.idempotency_key, "idempotency key")
    _safe_text(binding.expires_at, "binding expiry", 128)
    try:
        expires_at = dt.datetime.fromisoformat(binding.expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StorageGateError("invalid binding expiry") from exc
    if expires_at.tzinfo is None or expires_at <= dt.datetime.now(dt.timezone.utc):
        raise StorageGateError("observation binding expired")


class LuksSqliteFactBackend:
    """Atomic restricted-fact store on an attested LUKS-backed filesystem."""

    def __init__(
        self,
        path: Path,
        attestation: StorageAttestation,
        scope: ApprovedFactScope,
        *,
        attestor: LuksStorageAttestor | None = None,
    ) -> None:
        path = _canonical_path(path)
        if Path(attestation.canonical_path) != path:
            raise StorageGateError("storage path does not match attestation")
        checker = attestor or LuksStorageAttestor()
        checker.verify(attestation)
        _safe_text(scope.scope_id, "scope id")
        _digest(scope.proposal_digest, "scope proposal digest")
        _digest(scope.source_catalog_digest, "scope catalog digest")
        if not scope.entries:
            raise StorageGateError("approved fact scope has no entries")
        for entry in scope.entries:
            _safe_text(entry.adapter_id, "scope adapter id")
            _safe_text(entry.adapter_version, "scope adapter version")
            _safe_text(entry.source_id, "scope source id")
            if not entry.fact_ids:
                raise StorageGateError("approved fact scope entry has no fact ids")
            for fact_id in entry.fact_ids:
                _safe_text(fact_id, "scope fact id", 128)
        _digest(fact_scope_digest(scope), "scope digest")
        if not path.parent.is_dir():
            raise StorageGateError("restricted storage parent is unavailable")

        self.path = path
        self.attestation = attestation
        self.scope = scope
        self.scope_digest = fact_scope_digest(scope)
        self.encrypted_at_rest = True
        self.atomic_writes = True
        self.recovery_verified = True
        self._parent_fd = self._open_attested_parent(path.parent, attestation.owner_uid)
        self.attestation_digest = storage_attestation_digest(attestation)
        self._database_fd, self._db_identity = self._prepare_database(
            path.name, attestation.owner_uid
        )
        try:
            fcntl.flock(self._parent_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(self._database_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._connection = sqlite3.connect(path, isolation_level="IMMEDIATE", timeout=5)
            self._verify_open_identity()
            self._connection.execute("PRAGMA journal_mode=DELETE")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS activation_ledger (
                    request_id TEXT PRIMARY KEY,
                    proposal_digest TEXT NOT NULL,
                    source_catalog_digest TEXT NOT NULL,
                    adapter_id TEXT NOT NULL,
                    adapter_version TEXT NOT NULL,
                    attestation_digest TEXT NOT NULL,
                    scope_digest TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS restricted_facts (
                    record_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    proposal_digest TEXT NOT NULL,
                    source_catalog_digest TEXT NOT NULL,
                    adapter_id TEXT NOT NULL,
                    adapter_version TEXT NOT NULL,
                    attestation_digest TEXT NOT NULL,
                    scope_digest TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    fact_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    UNIQUE (idempotency_key, fact_id)
                )
                """
            )
            self._connection.commit()
            self._verify_open_identity()
        except (OSError, sqlite3.Error) as exc:
            connection = getattr(self, "_connection", None)
            if connection is not None:
                connection.close()
            os.close(self._database_fd)
            os.close(self._parent_fd)
            raise StorageGateError("restricted SQLite backend initialization failed") from exc

    @staticmethod
    def _open_attested_parent(parent: Path, owner_uid: int) -> int:
        parent_stat = parent.lstat()
        if not stat.S_ISDIR(parent_stat.st_mode) or stat.S_ISLNK(parent_stat.st_mode):
            raise StorageGateError("restricted storage parent is not a directory")
        if parent_stat.st_uid != owner_uid or stat.S_IMODE(parent_stat.st_mode) & 0o077:
            raise StorageGateError("restricted storage parent is not owner-controlled")
        try:
            return os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        except OSError as exc:
            raise StorageGateError("restricted storage parent cannot be opened safely") from exc

    def _prepare_database(self, name: str, owner_uid: int) -> tuple[int, tuple[int, int]]:
        if not name or name in {".", ".."} or "/" in name:
            raise StorageGateError("restricted database name is invalid")
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            fd = os.open(name, flags, dir_fd=self._parent_fd)
        except FileNotFoundError:
            try:
                fd = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                    0o600,
                    dir_fd=self._parent_fd,
                )
            except OSError as exc:
                raise StorageGateError("restricted database cannot be created safely") from exc
        except OSError as exc:
            raise StorageGateError("restricted database cannot be opened safely") from exc
        try:
            value = os.fstat(fd)
            if (
                not stat.S_ISREG(value.st_mode)
                or value.st_uid != owner_uid
                or stat.S_IMODE(value.st_mode) & 0o077
            ):
                raise StorageGateError("restricted database is not owner-controlled")
            return fd, (value.st_dev, value.st_ino)
        except Exception:
            os.close(fd)
            raise

    def _verify_open_identity(self) -> None:
        value = self.path.lstat()
        opened = os.fstat(self._database_fd)
        if (
            not stat.S_ISREG(value.st_mode)
            or (value.st_dev, value.st_ino) != self._db_identity
            or (opened.st_dev, opened.st_ino) != self._db_identity
        ):
            raise StorageGateError("restricted database identity changed during open")

    def consume_activation(self, binding: ObservationBinding) -> None:
        _validate_binding(binding, self.attestation_digest)
        if binding.scope_digest != self.scope_digest:
            raise StorageGateError("observation binding scope digest mismatch")
        if (
            binding.proposal_digest != self.scope.proposal_digest
            or binding.source_catalog_digest != self.scope.source_catalog_digest
        ):
            raise StorageGateError("observation binding proposal or catalog mismatch")
        consumed_at = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO activation_ledger(request_id, proposal_digest, source_catalog_digest, adapter_id, adapter_version, attestation_digest, scope_digest, idempotency_key, expires_at, consumed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        binding.request_id,
                        binding.proposal_digest,
                        binding.source_catalog_digest,
                        binding.adapter_id,
                        binding.adapter_version,
                        binding.attestation_digest,
                        binding.scope_digest,
                        binding.idempotency_key,
                        binding.expires_at,
                        consumed_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise StorageGateError("activation request replay or duplicate") from exc
        except sqlite3.Error as exc:
            raise StorageGateError("activation ledger atomic write failed") from exc

    def put(self, fact: dict[str, Any], binding: ObservationBinding) -> None:
        _validate_binding(binding, self.attestation_digest)
        if binding.scope_digest != self.scope_digest:
            raise StorageGateError("observation binding scope digest mismatch")
        if (
            binding.proposal_digest != self.scope.proposal_digest
            or binding.source_catalog_digest != self.scope.source_catalog_digest
        ):
            raise StorageGateError("observation binding proposal or catalog mismatch")
        if not isinstance(fact, dict):
            raise StorageGateError("restricted fact must be an object")
        fact_id = fact.get("fact_id")
        _safe_text(fact_id, "fact id", 128)
        source_id = fact.get("source_id")
        _safe_text(source_id, "source id", 128)
        if not self.scope.allows(binding.adapter_id, binding.adapter_version, source_id, fact_id):
            raise StorageGateError("fact is outside the approved adapter scope")
        try:
            payload = json.dumps(
                fact,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise StorageGateError("restricted fact is not canonical JSON") from exc
        payload_sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        record_id = hashlib.sha256(f"{binding.idempotency_key}\x00{fact_id}".encode()).hexdigest()
        observed_at = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            with self._connection:
                activation = self._connection.execute(
                    "SELECT 1 FROM activation_ledger WHERE request_id = ? AND idempotency_key = ? AND scope_digest = ?",
                    (binding.request_id, binding.idempotency_key, binding.scope_digest),
                ).fetchone()
                if activation is None:
                    raise StorageGateError("observation binding was not durably consumed")
                self._connection.execute(
                    "INSERT INTO restricted_facts(record_id, idempotency_key, request_id, proposal_digest, source_catalog_digest, adapter_id, adapter_version, attestation_digest, scope_digest, source_id, fact_id, observed_at, payload_json, payload_sha256) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record_id,
                        binding.idempotency_key,
                        binding.request_id,
                        binding.proposal_digest,
                        binding.source_catalog_digest,
                        binding.adapter_id,
                        binding.adapter_version,
                        binding.attestation_digest,
                        binding.scope_digest,
                        source_id,
                        fact_id,
                        observed_at,
                        payload,
                        payload_sha256,
                    ),
                )
        except StorageGateError:
            raise
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise StorageGateError("restricted fact duplicate or idempotency conflict") from exc
            raise StorageGateError("restricted fact atomic write failed") from exc
        except sqlite3.Error as exc:
            raise StorageGateError("restricted fact atomic write failed") from exc

    def verify_integrity(self) -> int:
        try:
            integrity = self._connection.execute("PRAGMA integrity_check").fetchone()
            if integrity != ("ok",):
                raise StorageGateError("restricted SQLite integrity check failed")
            rows = self._connection.execute(
                "SELECT payload_json, payload_sha256 FROM restricted_facts ORDER BY record_id"
            ).fetchall()
        except sqlite3.Error as exc:
            raise StorageGateError("restricted fact integrity read failed") from exc
        for payload, expected in rows:
            try:
                json.loads(payload)
            except json.JSONDecodeError as exc:
                raise StorageGateError("restricted fact payload is invalid JSON") from exc
            actual = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if actual != expected:
                raise StorageGateError("restricted fact payload hash mismatch")
        return len(rows)

    def close(self) -> None:
        self._connection.close()
        fcntl.flock(self._database_fd, fcntl.LOCK_UN)
        fcntl.flock(self._parent_fd, fcntl.LOCK_UN)
        os.close(self._database_fd)
        os.close(self._parent_fd)


def require_backend(backend: EncryptedFactBackend) -> EncryptedFactBackend:
    """Admit only a backend with all required independent attestations."""

    for name in ("encrypted_at_rest", "atomic_writes", "recovery_verified"):
        if getattr(backend, name, False) is not True:
            raise StorageGateError(f"restricted storage backend missing {name}")
    for name in ("consume_activation", "put"):
        if not callable(getattr(backend, name, None)):
            raise StorageGateError(f"restricted storage backend has no {name} operation")
    return backend


@dataclass
class EphemeralCandidateStore:
    """Memory-only candidate store; it intentionally has no persistence API."""

    _facts: list[dict[str, Any]] = field(default_factory=list)

    def add(self, fact: dict[str, Any]) -> None:
        if fact.get("synthetic") is not True:
            raise StorageGateError("only synthetic candidate facts may remain ephemeral")
        self._facts.append(dict(fact))

    def snapshot(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(fact) for fact in self._facts)

    def persist(
        self, backend: EncryptedFactBackend, binding: ObservationBinding | None = None
    ) -> None:
        admitted = require_backend(backend)
        if binding is None:
            raise StorageGateError("observation binding is required for persistence")
        for fact in self._facts:
            admitted.put(dict(fact), binding)


def persistence_status(backend: EncryptedFactBackend | None = None) -> dict[str, Any]:
    """Return a safe status projection without exposing backend internals."""

    if backend is None:
        return {"available": False, "reason": "encrypted_backend_not_supplied"}
    try:
        require_backend(backend)
    except StorageGateError as exc:
        return {"available": False, "reason": str(exc)}
    return {"available": True, "encrypted_at_rest": True, "recovery_verified": True}
