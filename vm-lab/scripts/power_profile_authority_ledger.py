#!/usr/bin/env python3
"""Descriptor-bound durable one-use ledger for power-profile approvals.

This is a prepared authority-ledger backend. It is not opened by a service or
connected to the TUI in the shipped state. The bridge consumes an exact row
only after all request, target, policy, expiry, and idempotency bindings pass.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import os
import sqlite3
import stat
from pathlib import Path

from power_profile_executor_bridge import (
    PowerProfileApproval,
    PowerProfileExecutorError,
)


class PowerProfileLedgerError(PowerProfileExecutorError):
    """Raised when the durable approval ledger cannot fail safely."""


_TABLE_SQL = """CREATE TABLE power_profile_approvals (
                    approval_id TEXT PRIMARY KEY,
                    operation_id TEXT NOT NULL,
                    operation_revision TEXT NOT NULL,
                    parameters_digest TEXT NOT NULL,
                    target_digest TEXT NOT NULL,
                    policy_digest TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    consumed_at TEXT
                )"""
_TABLE_INFO = (
    ("approval_id", "TEXT", 0, None, 1),
    ("operation_id", "TEXT", 1, None, 0),
    ("operation_revision", "TEXT", 1, None, 0),
    ("parameters_digest", "TEXT", 1, None, 0),
    ("target_digest", "TEXT", 1, None, 0),
    ("policy_digest", "TEXT", 1, None, 0),
    ("expires_at", "TEXT", 1, None, 0),
    ("idempotency_key", "TEXT", 1, None, 0),
    ("created_at", "TEXT", 1, None, 0),
    ("consumed_at", "TEXT", 0, None, 0),
)


class PowerProfileAuthorityLedger:
    """Owner-controlled SQLite ledger with atomic one-use consumption."""

    def __init__(self, path: Path) -> None:
        if not path.is_absolute() or path.resolve(strict=False) != path:
            raise PowerProfileLedgerError("ledger path must be absolute and canonical")
        try:
            parent = path.parent.lstat()
        except OSError as exc:
            raise PowerProfileLedgerError("ledger parent is unavailable") from exc
        if (
            not stat.S_ISDIR(parent.st_mode)
            or stat.S_ISLNK(parent.st_mode)
            or parent.st_uid != os.getuid()
            or stat.S_IMODE(parent.st_mode) & 0o077
        ):
            raise PowerProfileLedgerError("ledger parent is not owner-controlled")
        self.path = path
        self._parent_fd = self._open_parent(path.parent)
        try:
            self._db_fd, self._identity = self._open_database(path.name)
        except Exception:
            os.close(self._parent_fd)
            raise
        try:
            fcntl.flock(self._parent_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(self._db_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.connection = sqlite3.connect(path, isolation_level="IMMEDIATE", timeout=5)
            self._verify_identity()
            journal_mode = self.connection.execute("PRAGMA journal_mode=DELETE").fetchone()
            if journal_mode is None or str(journal_mode[0]).lower() != "delete":
                raise PowerProfileLedgerError("ledger journal mode is not DELETE")
            self.connection.execute("PRAGMA synchronous=FULL")
            synchronous = self.connection.execute("PRAGMA synchronous").fetchone()
            if synchronous is None or int(synchronous[0]) != 2:
                raise PowerProfileLedgerError("ledger synchronous mode is not FULL")
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS " + _TABLE_SQL[len("CREATE TABLE ") :]
            )
            self.connection.commit()
            self._verify_identity()
            self._verify_schema()
            self.integrity_check()
        except (OSError, sqlite3.Error, PowerProfileLedgerError) as exc:
            connection = getattr(self, "connection", None)
            if connection is not None:
                connection.close()
            os.close(self._db_fd)
            os.close(self._parent_fd)
            raise PowerProfileLedgerError("ledger initialization failed") from exc

    @staticmethod
    def _open_parent(parent: Path) -> int:
        try:
            return os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        except OSError as exc:
            raise PowerProfileLedgerError("ledger parent cannot be opened safely") from exc

    def _open_database(self, name: str) -> tuple[int, tuple[int, int]]:
        if not name or name in {".", ".."} or "/" in name:
            raise PowerProfileLedgerError("ledger database name is invalid")
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
                raise PowerProfileLedgerError("ledger database cannot be created safely") from exc
        except OSError as exc:
            raise PowerProfileLedgerError("ledger database cannot be opened safely") from exc
        try:
            value = os.fstat(fd)
            if (
                not stat.S_ISREG(value.st_mode)
                or value.st_uid != os.getuid()
                or stat.S_IMODE(value.st_mode) & 0o077
            ):
                raise PowerProfileLedgerError("ledger database is not owner-controlled")
            return fd, (value.st_dev, value.st_ino)
        except Exception:
            os.close(fd)
            raise

    def _verify_identity(self) -> None:
        path_stat = self.path.lstat()
        fd_stat = os.fstat(self._db_fd)
        if (
            not stat.S_ISREG(path_stat.st_mode)
            or (path_stat.st_dev, path_stat.st_ino) != self._identity
            or (fd_stat.st_dev, fd_stat.st_ino) != self._identity
        ):
            raise PowerProfileLedgerError("ledger database identity changed")

    def _verify_schema(self) -> None:
        try:
            table_row = self.connection.execute(
                "SELECT type, sql FROM sqlite_master WHERE name = ?",
                ("power_profile_approvals",),
            ).fetchone()
            if (
                table_row is None
                or table_row[0] != "table"
                or " ".join(table_row[1].lower().split()) != " ".join(_TABLE_SQL.lower().split())
            ):
                raise PowerProfileLedgerError("ledger schema is not the reviewed schema")
            columns = tuple(
                (row[1], row[2], row[3], row[4], row[5])
                for row in self.connection.execute(
                    "PRAGMA table_info(power_profile_approvals)"
                ).fetchall()
            )
            if columns != _TABLE_INFO:
                raise PowerProfileLedgerError("ledger columns are not the reviewed schema")
            indexes = self.connection.execute(
                "PRAGMA index_list(power_profile_approvals)"
            ).fetchall()
            observed: set[tuple[int, str, tuple[str, ...]]] = set()
            for index in indexes:
                if index[2] != 1 or index[3] not in {"pk", "u"}:
                    raise PowerProfileLedgerError("ledger indexes are not the reviewed schema")
                name = str(index[1]).replace('"', '""')
                info = tuple(
                    row[2]
                    for row in self.connection.execute(f'PRAGMA index_info("{name}")').fetchall()
                )
                observed.add((int(index[2]), str(index[3]), info))
            if observed != {
                (1, "pk", ("approval_id",)),
                (1, "u", ("idempotency_key",)),
            }:
                raise PowerProfileLedgerError("ledger indexes are not the reviewed schema")
        except sqlite3.Error as exc:
            raise PowerProfileLedgerError("ledger schema check failed") from exc

    def integrity_check(self) -> None:
        try:
            row = self.connection.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.Error as exc:
            raise PowerProfileLedgerError("ledger integrity check failed") from exc
        if row != ("ok",):
            raise PowerProfileLedgerError("ledger integrity check failed")

    def record(self, approval: PowerProfileApproval) -> None:
        approval.validate()
        created = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            self._verify_identity()
            with self.connection:
                self._verify_identity()
                self.connection.execute(
                    "INSERT INTO power_profile_approvals(approval_id, operation_id, operation_revision, parameters_digest, target_digest, policy_digest, expires_at, idempotency_key, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        approval.approval_id,
                        approval.operation_id,
                        approval.operation_revision,
                        approval.parameters_digest,
                        approval.target_digest,
                        approval.policy_digest,
                        approval.expires_at,
                        approval.idempotency_key,
                        created,
                    ),
                )
            self._verify_identity()
        except sqlite3.IntegrityError as exc:
            raise PowerProfileLedgerError("approval replay or duplicate") from exc
        except sqlite3.Error as exc:
            raise PowerProfileLedgerError("approval record failed atomically") from exc

    def consume(self, approval: PowerProfileApproval) -> None:
        approval.validate()
        now = dt.datetime.now(dt.timezone.utc)
        consumed = now.isoformat().replace("+00:00", "Z")
        try:
            self._verify_identity()
            with self.connection:
                self._verify_identity()
                self._verify_schema()
                self.integrity_check()
                row = self.connection.execute(
                    "SELECT approval_id, operation_id, operation_revision, parameters_digest, target_digest, policy_digest, expires_at, idempotency_key, consumed_at FROM power_profile_approvals WHERE approval_id = ?",
                    (approval.approval_id,),
                ).fetchone()
                if row is None:
                    raise PowerProfileLedgerError("approval not found")
                stored = PowerProfileApproval(*row[:8])
                stored.validate(now=now)
                if stored.document() != approval.document():
                    raise PowerProfileLedgerError("approval binding mismatch")
                if row[8] is not None:
                    raise PowerProfileLedgerError("approval already consumed")
                updated = self.connection.execute(
                    "UPDATE power_profile_approvals SET consumed_at = ? WHERE approval_id = ? AND consumed_at IS NULL AND idempotency_key = ?",
                    (consumed, approval.approval_id, approval.idempotency_key),
                ).rowcount
                if updated != 1:
                    raise PowerProfileLedgerError("approval replay or concurrent consumption")
            self._verify_identity()
        except PowerProfileLedgerError:
            raise
        except sqlite3.Error as exc:
            raise PowerProfileLedgerError("approval consumption failed atomically") from exc

    def close(self) -> None:
        connection = getattr(self, "connection", None)
        if connection is not None:
            connection.close()
        os.close(self._db_fd)
        os.close(self._parent_fd)
