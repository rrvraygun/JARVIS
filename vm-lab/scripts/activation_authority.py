#!/usr/bin/env python3
"""Durable, exact-scope user-decision ledger for future H1 activation.

This module records and consumes one explicit authorization without granting
host capabilities itself.  It has no shell, privilege, network, service, or
host-observation interface.  A separate reviewed broker must still enforce the
same binding before any observation is attempted.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import sqlite3
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AuthorizationError(ValueError):
    """Raised when an authorization cannot be admitted or consumed."""


def _text(value: Any, label: str, limit: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise AuthorizationError(f"invalid {label}")
    if any(ord(char) < 0x20 for char in value):
        raise AuthorizationError(f"invalid {label}")
    return value


def _digest(value: Any, label: str) -> str:
    value = _text(value, label, 128)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise AuthorizationError(f"invalid {label}")
    return value


def _expiry(value: str) -> dt.datetime:
    _text(value, "expiry", 128)
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuthorizationError("invalid expiry") from exc
    if parsed.tzinfo is None:
        raise AuthorizationError("expiry requires timezone")
    return parsed.astimezone(dt.timezone.utc)


def _canonical(value: dict[str, Any]) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


@dataclass(frozen=True)
class UserAuthorization:
    authorization_id: str
    request_id: str
    proposal_digest: str
    source_catalog_digest: str
    scope_digest: str
    attestation_digest: str
    approved_group_ids: tuple[str, ...]
    approved_fact_ids: tuple[str, ...]
    decision_digest: str
    idempotency_key: str
    expires_at: str

    def document(self) -> dict[str, Any]:
        return {
            "authorization_id": self.authorization_id,
            "request_id": self.request_id,
            "proposal_digest": self.proposal_digest,
            "source_catalog_digest": self.source_catalog_digest,
            "scope_digest": self.scope_digest,
            "attestation_digest": self.attestation_digest,
            "approved_group_ids": list(self.approved_group_ids),
            "approved_fact_ids": list(self.approved_fact_ids),
            "decision_digest": self.decision_digest,
            "idempotency_key": self.idempotency_key,
            "expires_at": self.expires_at,
        }

    def binding_digest(self) -> str:
        return hashlib.sha256(_canonical(self.document()).encode("utf-8")).hexdigest()


def validate_authorization(authorization: UserAuthorization, *, check_expiry: bool = True) -> None:
    for value, label in (
        (authorization.authorization_id, "authorization id"),
        (authorization.request_id, "request id"),
        (authorization.idempotency_key, "idempotency key"),
    ):
        _text(value, label)
    for value, label in (
        (authorization.proposal_digest, "proposal digest"),
        (authorization.source_catalog_digest, "source catalog digest"),
        (authorization.scope_digest, "scope digest"),
        (authorization.attestation_digest, "attestation digest"),
        (authorization.decision_digest, "decision digest"),
    ):
        _digest(value, label)
    if not authorization.approved_group_ids:
        raise AuthorizationError("authorization has no approved groups")
    if not authorization.approved_fact_ids:
        raise AuthorizationError("authorization has no approved facts")
    for group_id in authorization.approved_group_ids:
        _text(group_id, "approved group id", 128)
    for fact_id in authorization.approved_fact_ids:
        _text(fact_id, "approved fact id", 128)
    if tuple(sorted(set(authorization.approved_group_ids))) != authorization.approved_group_ids:
        raise AuthorizationError("approved groups must be sorted and unique")
    if tuple(sorted(set(authorization.approved_fact_ids))) != authorization.approved_fact_ids:
        raise AuthorizationError("approved facts must be sorted and unique")
    if check_expiry and _expiry(authorization.expires_at) <= dt.datetime.now(dt.timezone.utc):
        raise AuthorizationError("authorization expired")


class ActivationAuthorityLedger:
    """SQLite-backed immutable decision and one-use consumption ledger."""

    def __init__(self, path: Path) -> None:
        if not path.is_absolute() or path.resolve(strict=False) != path:
            raise AuthorizationError("authorization ledger path must be absolute and canonical")
        try:
            parent_stat = path.parent.lstat()
        except OSError as exc:
            raise AuthorizationError("authorization ledger parent is unavailable") from exc
        if (
            not stat.S_ISDIR(parent_stat.st_mode)
            or stat.S_ISLNK(parent_stat.st_mode)
            or parent_stat.st_uid != os.getuid()
            or stat.S_IMODE(parent_stat.st_mode) & 0o077
        ):
            raise AuthorizationError("authorization ledger parent is not owner-controlled")
        if path.exists() and (path.is_symlink() or not path.is_file()):
            raise AuthorizationError("authorization ledger target is not a regular file")
        if path.exists():
            try:
                ledger_stat = path.lstat()
            except OSError as exc:
                raise AuthorizationError("authorization ledger identity is unavailable") from exc
            if ledger_stat.st_uid != os.getuid() or stat.S_IMODE(ledger_stat.st_mode) & 0o077:
                raise AuthorizationError("authorization ledger is not owner-controlled")
        if not path.parent.is_dir():
            raise AuthorizationError("authorization ledger parent is unavailable")
        self.path = path
        self._parent_fd = self._open_parent(path.parent)
        created = not path.exists()
        self._database_fd, self._db_identity = self._prepare_database(path.name, created)
        try:
            fcntl.flock(self._parent_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(self._database_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Python's sqlite3 API reopens by pathname and may create journal
            # sidecars by pathname. Owner/mode checks, held descriptors,
            # advisory locks, and post-open identity checks reduce the risk,
            # but a same-UID rename race remains a documented limitation until
            # a descriptor-aware SQLite VFS is provided.
            self.connection = sqlite3.connect(path, isolation_level="IMMEDIATE", timeout=5)
            self._verify_open_identity()
            self.connection.execute("PRAGMA journal_mode=DELETE")
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS authorizations (
                    authorization_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    proposal_digest TEXT NOT NULL,
                    source_catalog_digest TEXT NOT NULL,
                    scope_digest TEXT NOT NULL,
                    attestation_digest TEXT NOT NULL,
                    approved_group_ids TEXT NOT NULL,
                    approved_fact_ids TEXT NOT NULL,
                    decision_digest TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    consumed_at TEXT
                )
                """
            )
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS authorization_attempts (
                    authorization_id TEXT PRIMARY KEY,
                    attempted_at TEXT NOT NULL
                )
                """
            )
            self.connection.commit()
            self._verify_open_identity()
            self.integrity_check()
        except (AuthorizationError, OSError, sqlite3.Error) as exc:
            connection = getattr(self, "connection", None)
            if connection is not None:
                connection.close()
            os.close(self._database_fd)
            os.close(self._parent_fd)
            raise AuthorizationError("authorization ledger initialization failed") from exc

    def _open_parent(self, parent: Path) -> int:
        try:
            return os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        except OSError as exc:
            raise AuthorizationError("authorization ledger parent cannot be opened safely") from exc

    def _prepare_database(self, name: str, created: bool) -> tuple[int, tuple[int, int]]:
        if not name or name in {".", ".."} or "/" in name:
            raise AuthorizationError("authorization ledger database name is invalid")
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self._parent_fd)
        except FileNotFoundError:
            try:
                fd = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                    0o600,
                    dir_fd=self._parent_fd,
                )
            except OSError as exc:
                raise AuthorizationError(
                    "authorization ledger database cannot be created safely"
                ) from exc
        except OSError as exc:
            raise AuthorizationError(
                "authorization ledger database cannot be opened safely"
            ) from exc
        try:
            value = os.fstat(fd)
            if (
                not stat.S_ISREG(value.st_mode)
                or value.st_uid != os.getuid()
                or stat.S_IMODE(value.st_mode) & 0o077
            ):
                raise AuthorizationError("authorization ledger database is not owner-controlled")
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
            raise AuthorizationError("authorization ledger identity changed during open")

    def record(self, authorization: UserAuthorization) -> str:
        validate_authorization(authorization)
        created_at = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            with self.connection:
                self.connection.execute(
                    """
                    INSERT INTO authorizations(
                        authorization_id, request_id, proposal_digest,
                        source_catalog_digest, scope_digest, attestation_digest,
                        approved_group_ids, approved_fact_ids, decision_digest,
                        idempotency_key, expires_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        authorization.authorization_id,
                        authorization.request_id,
                        authorization.proposal_digest,
                        authorization.source_catalog_digest,
                        authorization.scope_digest,
                        authorization.attestation_digest,
                        _canonical(list(authorization.approved_group_ids)),
                        _canonical(list(authorization.approved_fact_ids)),
                        authorization.decision_digest,
                        authorization.idempotency_key,
                        authorization.expires_at,
                        created_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise AuthorizationError("authorization replay or duplicate") from exc
        except sqlite3.Error as exc:
            raise AuthorizationError("authorization record failed atomically") from exc
        return authorization.binding_digest()

    def begin_attempt(
        self,
        authorization_id: str,
        *,
        expected: UserAuthorization | None = None,
        now: dt.datetime | None = None,
    ) -> UserAuthorization:
        """Irreversibly reserve the one allowed observation attempt."""
        authorization_id = _text(authorization_id, "authorization id")
        if expected is not None and expected.authorization_id != authorization_id:
            raise AuthorizationError("expected authorization identity mismatch")
        current = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
        attempted_at = current.isoformat().replace("+00:00", "Z")
        try:
            with self.connection:
                self.integrity_check()
                row = self.connection.execute(
                    """
                    SELECT authorization_id, request_id, proposal_digest,
                           source_catalog_digest, scope_digest, attestation_digest,
                           approved_group_ids, approved_fact_ids, decision_digest,
                           idempotency_key, expires_at, consumed_at
                    FROM authorizations WHERE authorization_id = ?
                    """,
                    (authorization_id,),
                ).fetchone()
                if row is None:
                    raise AuthorizationError("authorization not found")
                if row[-1] is not None:
                    raise AuthorizationError("authorization already consumed")
                if _expiry(row[10]) <= current:
                    raise AuthorizationError("authorization expired")
                row_authorization = self._authorization_from_row(row)
                validate_authorization(row_authorization)
                if expected is not None and row_authorization.document() != expected.document():
                    raise AuthorizationError("authorization binding mismatch")
                self.connection.execute(
                    "INSERT INTO authorization_attempts(authorization_id, attempted_at) VALUES (?, ?)",
                    (authorization_id, attempted_at),
                )
        except AuthorizationError:
            raise
        except sqlite3.IntegrityError as exc:
            raise AuthorizationError("authorization attempt already recorded") from exc
        except sqlite3.Error as exc:
            raise AuthorizationError("authorization attempt failed atomically") from exc
        return row_authorization

    def consume(
        self,
        authorization_id: str,
        *,
        expected: UserAuthorization | None = None,
        now: dt.datetime | None = None,
    ) -> UserAuthorization:
        authorization_id = _text(authorization_id, "authorization id")
        if expected is not None and expected.authorization_id != authorization_id:
            raise AuthorizationError("expected authorization identity mismatch")
        current = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
        consumed_at = current.isoformat().replace("+00:00", "Z")
        try:
            with self.connection:
                self.integrity_check()
                row = self.connection.execute(
                    """
                    SELECT authorization_id, request_id, proposal_digest,
                           source_catalog_digest, scope_digest, attestation_digest,
                           approved_group_ids, approved_fact_ids, decision_digest,
                           idempotency_key, expires_at, consumed_at
                    FROM authorizations
                    WHERE authorization_id = ?
                    """,
                    (authorization_id,),
                ).fetchone()
                if row is None:
                    raise AuthorizationError("authorization not found")
                if row[-1] is not None:
                    raise AuthorizationError("authorization already consumed")
                if _expiry(row[10]) <= current:
                    raise AuthorizationError("authorization expired")
                row_authorization = self._authorization_from_row(row)
                validate_authorization(row_authorization)
                if expected is not None and row_authorization.document() != expected.document():
                    raise AuthorizationError("authorization binding mismatch")
                updated = self.connection.execute(
                    """
                    UPDATE authorizations SET consumed_at = ?
                    WHERE authorization_id = ? AND consumed_at IS NULL
                      AND request_id = ? AND proposal_digest = ?
                      AND source_catalog_digest = ? AND scope_digest = ?
                      AND attestation_digest = ? AND approved_group_ids = ?
                      AND approved_fact_ids = ? AND decision_digest = ?
                      AND idempotency_key = ? AND expires_at = ?
                    """,
                    (
                        consumed_at,
                        authorization_id,
                        row_authorization.request_id,
                        row_authorization.proposal_digest,
                        row_authorization.source_catalog_digest,
                        row_authorization.scope_digest,
                        row_authorization.attestation_digest,
                        _canonical(list(row_authorization.approved_group_ids)),
                        _canonical(list(row_authorization.approved_fact_ids)),
                        row_authorization.decision_digest,
                        row_authorization.idempotency_key,
                        row_authorization.expires_at,
                    ),
                ).rowcount
                if updated != 1:
                    raise AuthorizationError("authorization replay or concurrent consumption")
        except AuthorizationError:
            raise
        except sqlite3.Error as exc:
            raise AuthorizationError("authorization consumption failed atomically") from exc
        return row_authorization

    def revoke_unconsumed(
        self,
        authorization_id: str,
        *,
        expected: UserAuthorization | None = None,
    ) -> None:
        """Remove exactly one still-unconsumed authorization during rollback."""
        authorization_id = _text(authorization_id, "authorization id")
        if expected is not None and expected.authorization_id != authorization_id:
            raise AuthorizationError("expected authorization identity mismatch")
        try:
            with self.connection:
                self.integrity_check()
                row = self.connection.execute(
                    """
                    SELECT authorization_id, request_id, proposal_digest,
                           source_catalog_digest, scope_digest, attestation_digest,
                           approved_group_ids, approved_fact_ids, decision_digest,
                           idempotency_key, expires_at, consumed_at
                    FROM authorizations WHERE authorization_id = ?
                    """,
                    (authorization_id,),
                ).fetchone()
                if row is None:
                    raise AuthorizationError("authorization not found")
                if row[-1] is not None:
                    raise AuthorizationError("cannot revoke consumed authorization")
                row_authorization = self._authorization_from_row(row)
                validate_authorization(row_authorization, check_expiry=False)
                if expected is not None and row_authorization.document() != expected.document():
                    raise AuthorizationError("authorization binding mismatch")
                deleted = self.connection.execute(
                    "DELETE FROM authorizations WHERE authorization_id = ? AND consumed_at IS NULL",
                    (authorization_id,),
                ).rowcount
                if deleted != 1:
                    raise AuthorizationError("authorization revoke race")
        except AuthorizationError:
            raise
        except sqlite3.Error as exc:
            raise AuthorizationError("authorization revoke failed atomically") from exc

    def is_consumed(
        self,
        authorization_id: str,
        *,
        expected: UserAuthorization | None = None,
    ) -> bool:
        """Read durable consumption state and verify the full binding."""
        authorization_id = _text(authorization_id, "authorization id")
        if expected is not None and expected.authorization_id != authorization_id:
            raise AuthorizationError("expected authorization identity mismatch")
        try:
            self.integrity_check()
            row = self.connection.execute(
                """
                SELECT authorization_id, request_id, proposal_digest,
                       source_catalog_digest, scope_digest, attestation_digest,
                       approved_group_ids, approved_fact_ids, decision_digest,
                       idempotency_key, expires_at, consumed_at
                FROM authorizations WHERE authorization_id = ?
                """,
                (authorization_id,),
            ).fetchone()
            if row is None:
                raise AuthorizationError("authorization not found")
            row_authorization = self._authorization_from_row(row)
            validate_authorization(row_authorization, check_expiry=False)
            if expected is not None and row_authorization.document() != expected.document():
                raise AuthorizationError("authorization binding mismatch")
            return row[-1] is not None
        except AuthorizationError:
            raise
        except sqlite3.Error as exc:
            raise AuthorizationError("authorization state read failed") from exc

    @staticmethod
    def _authorization_from_row(row: tuple[Any, ...]) -> UserAuthorization:
        try:
            groups = json.loads(row[6])
            facts = json.loads(row[7])
            if not isinstance(groups, list) or not isinstance(facts, list):
                raise ValueError("authorization arrays are not lists")
            return UserAuthorization(
                authorization_id=row[0],
                request_id=row[1],
                proposal_digest=row[2],
                source_catalog_digest=row[3],
                scope_digest=row[4],
                attestation_digest=row[5],
                approved_group_ids=tuple(groups),
                approved_fact_ids=tuple(facts),
                decision_digest=row[8],
                idempotency_key=row[9],
                expires_at=row[10],
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AuthorizationError("authorization row is malformed") from exc

    def integrity_check(self) -> None:
        try:
            result = self.connection.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.Error as exc:
            raise AuthorizationError("authorization ledger integrity read failed") from exc
        if result != ("ok",):
            raise AuthorizationError("authorization ledger integrity check failed")

    def close(self) -> None:
        self.connection.close()
        fcntl.flock(self._database_fd, fcntl.LOCK_UN)
        fcntl.flock(self._parent_fd, fcntl.LOCK_UN)
        os.close(self._database_fd)
        os.close(self._parent_fd)
