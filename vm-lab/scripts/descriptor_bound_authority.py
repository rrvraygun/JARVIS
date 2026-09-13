#!/usr/bin/env python3
"""Sidecar-free, descriptor-bound one-use authorization ledger.

This backend is a construction-stage alternative to the SQLite ledger. It
stores a hash-chained sequence of framed JSON events in one owner-controlled
regular file. No journal, WAL, shared-memory, or other pathname-based sidecar
is created. It is not wired into live collection or activation until reviewed.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import stat
import struct
import threading
from pathlib import Path
from typing import Any

from activation_authority import (
    AuthorizationError,
    UserAuthorization,
    _canonical,
    _expiry,
    _text,
    validate_authorization,
)
from external_checkpoint import CheckpointError, CheckpointProvider, ExternalCheckpoint

MAGIC = b"JARVIS-AUTH-LEDGER-V3\n"
MAX_FRAME_BYTES = 1 << 20
ZERO_DIGEST = b"\0" * 32
CHECKPOINT_SLOT_BYTES = 512
CHECKPOINT_STRUCT = struct.Struct(">QQ32s32sH")
DATA_OFFSET = len(MAGIC) + (2 * CHECKPOINT_SLOT_BYTES)


class DescriptorBoundActivationLedger:
    """Durable one-use ledger with all writes bound to one verified fd."""

    def __init__(
        self,
        path: Path,
        *,
        checkpoint_provider: CheckpointProvider | None = None,
        ledger_id: str = "jarvis-authority",
    ) -> None:
        if not path.is_absolute() or path.resolve(strict=False) != path:
            raise AuthorizationError("descriptor ledger path must be absolute and canonical")
        try:
            parent = path.parent.lstat()
        except OSError as exc:
            raise AuthorizationError("descriptor ledger parent is unavailable") from exc
        if (
            not stat.S_ISDIR(parent.st_mode)
            or stat.S_ISLNK(parent.st_mode)
            or parent.st_uid != os.getuid()
            or stat.S_IMODE(parent.st_mode) & 0o077
        ):
            raise AuthorizationError("descriptor ledger parent is not owner-controlled")
        self.path = path
        self._checkpoint_provider = checkpoint_provider
        self._ledger_id = ledger_id
        self._mutex = threading.RLock()
        try:
            self._parent_fd = os.open(
                path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            )
            self._ledger_fd = os.open(
                path.name,
                os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=self._parent_fd,
            )
            value = os.fstat(self._ledger_fd)
            if (
                not stat.S_ISREG(value.st_mode)
                or value.st_uid != os.getuid()
                or stat.S_IMODE(value.st_mode) & 0o077
            ):
                raise AuthorizationError("descriptor ledger is not owner-controlled")
            self._identity = (value.st_dev, value.st_ino)
            fcntl.flock(self._parent_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(self._ledger_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._state: dict[str, tuple[UserAuthorization, str | None]] = {}
            self._idempotency: set[str] = set()
            self._sequence = 0
            self._last_digest = ZERO_DIGEST
            self._checkpoint_generation = 0
            self._checkpoint_slot = 0
            if os.fstat(self._ledger_fd).st_size == 0:
                self._write_all(
                    MAGIC
                    + self._checkpoint_bytes(0, 0, ZERO_DIGEST, None)
                    + (b"\0" * CHECKPOINT_SLOT_BYTES)
                )
                os.fsync(self._ledger_fd)
            self.integrity_check()
        except (OSError, AuthorizationError) as exc:
            for fd_name in ("_ledger_fd", "_parent_fd"):
                fd = getattr(self, fd_name, None)
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            if isinstance(exc, AuthorizationError):
                raise
            raise AuthorizationError("descriptor ledger initialization failed") from exc

    def _write_all(self, data: bytes) -> None:
        offset = 0
        while offset < len(data):
            try:
                offset += os.write(self._ledger_fd, data[offset:])
            except OSError as exc:
                raise AuthorizationError("descriptor ledger write failed") from exc

    @staticmethod
    def _checkpoint_bytes(
        generation: int,
        sequence: int,
        digest: bytes,
        external: ExternalCheckpoint | None,
    ) -> bytes:
        external_bytes = (
            b"" if external is None else _canonical(external.document()).encode("utf-8")
        )
        if len(external_bytes) > CHECKPOINT_SLOT_BYTES - CHECKPOINT_STRUCT.size:
            raise AuthorizationError("external checkpoint exceeds checkpoint slot")
        body = struct.pack(">QQ32s", generation, sequence, digest)
        checksum = hashlib.sha256(
            body + struct.pack(">H", len(external_bytes)) + external_bytes
        ).digest()
        header = CHECKPOINT_STRUCT.pack(generation, sequence, digest, checksum, len(external_bytes))
        return (
            header
            + external_bytes
            + (b"\0" * (CHECKPOINT_SLOT_BYTES - len(header) - len(external_bytes)))
        )

    @staticmethod
    def _external_from_document(document: Any) -> ExternalCheckpoint:
        if not isinstance(document, dict) or set(document) != set(
            ExternalCheckpoint.__dataclass_fields__
        ):
            raise AuthorizationError("descriptor ledger external checkpoint fields are invalid")
        try:
            return ExternalCheckpoint(**document)
        except (TypeError, ValueError) as exc:
            raise AuthorizationError("descriptor ledger external checkpoint is malformed") from exc

    @staticmethod
    def _from_document(document: dict[str, Any]) -> UserAuthorization:
        try:
            value = UserAuthorization(
                authorization_id=document["authorization_id"],
                request_id=document["request_id"],
                proposal_digest=document["proposal_digest"],
                source_catalog_digest=document["source_catalog_digest"],
                scope_digest=document["scope_digest"],
                attestation_digest=document["attestation_digest"],
                approved_group_ids=tuple(document["approved_group_ids"]),
                approved_fact_ids=tuple(document["approved_fact_ids"]),
                decision_digest=document["decision_digest"],
                idempotency_key=document["idempotency_key"],
                expires_at=document["expires_at"],
            )
            validate_authorization(value, check_expiry=False)
            _expiry(value.expires_at)
            return value
        except (KeyError, TypeError, ValueError, AuthorizationError) as exc:
            raise AuthorizationError("descriptor ledger authorization event is malformed") from exc

    def _scan(
        self,
    ) -> tuple[
        dict[str, tuple[UserAuthorization, str | None]],
        set[str],
        int,
        bytes,
        int,
        int,
        ExternalCheckpoint | None,
    ]:
        file_size = os.fstat(self._ledger_fd).st_size
        header = os.pread(self._ledger_fd, len(MAGIC), 0)
        if header != MAGIC:
            raise AuthorizationError("descriptor ledger magic or header is invalid")
        if file_size < DATA_OFFSET:
            raise AuthorizationError("descriptor ledger checkpoint header is incomplete")
        checkpoints: list[tuple[int, int, bytes, int, ExternalCheckpoint | None]] = []
        for slot in range(2):
            raw_checkpoint = os.pread(
                self._ledger_fd,
                CHECKPOINT_SLOT_BYTES,
                len(MAGIC) + slot * CHECKPOINT_SLOT_BYTES,
            )
            if (
                len(raw_checkpoint) != CHECKPOINT_SLOT_BYTES
                or raw_checkpoint == b"\0" * CHECKPOINT_SLOT_BYTES
            ):
                continue
            (
                generation,
                checkpoint_sequence,
                checkpoint_digest,
                checksum,
                external_length,
            ) = CHECKPOINT_STRUCT.unpack(raw_checkpoint[: CHECKPOINT_STRUCT.size])
            if external_length > CHECKPOINT_SLOT_BYTES - CHECKPOINT_STRUCT.size:
                raise AuthorizationError("descriptor ledger external checkpoint length is invalid")
            external: ExternalCheckpoint | None = None
            raw_external = raw_checkpoint[
                CHECKPOINT_STRUCT.size : CHECKPOINT_STRUCT.size + external_length
            ]
            if external_length:
                try:
                    external_document = json.loads(raw_external.decode("utf-8"))
                    if _canonical(external_document).encode("utf-8") != raw_external:
                        raise AuthorizationError(
                            "descriptor ledger external checkpoint is not canonical JSON"
                        )
                    external = self._external_from_document(external_document)
                except (UnicodeDecodeError, ValueError) as exc:
                    raise AuthorizationError(
                        "descriptor ledger external checkpoint is invalid JSON"
                    ) from exc
            body = struct.pack(">QQ32s", generation, checkpoint_sequence, checkpoint_digest)
            if (
                hashlib.sha256(body + struct.pack(">H", external_length) + raw_external).digest()
                == checksum
            ):
                checkpoints.append(
                    (generation, checkpoint_sequence, checkpoint_digest, slot, external)
                )
        if not checkpoints:
            raise AuthorizationError("descriptor ledger has no valid terminal checkpoint")
        (
            checkpoint_generation,
            checkpoint_sequence,
            checkpoint_digest,
            checkpoint_slot,
            external_checkpoint,
        ) = max(checkpoints)
        if checkpoint_sequence == 0 and external_checkpoint is not None:
            raise AuthorizationError(
                "descriptor ledger has an external checkpoint at sequence zero"
            )
        if (
            checkpoint_sequence > 0
            and external_checkpoint is None
            and self._checkpoint_provider is not None
        ):
            raise AuthorizationError("descriptor ledger external checkpoint is unavailable")
        if external_checkpoint is not None:
            if self._checkpoint_provider is None:
                raise AuthorizationError(
                    "descriptor ledger external checkpoint requires a provider"
                )
            try:
                self._checkpoint_provider.verify(
                    external_checkpoint,
                    self._ledger_id,
                    checkpoint_sequence,
                    checkpoint_digest.hex(),
                )
            except (CheckpointError, ValueError, TypeError) as exc:
                raise AuthorizationError(
                    "descriptor ledger external checkpoint verification failed"
                ) from exc
        offset = DATA_OFFSET
        state: dict[str, tuple[UserAuthorization, str | None]] = {}
        idempotency: set[str] = set()
        sequence = 0
        previous = ZERO_DIGEST
        while offset < file_size:
            frame_header = os.pread(self._ledger_fd, 8, offset)
            if len(frame_header) != 8:
                raise AuthorizationError("descriptor ledger has an incomplete frame header")
            length = struct.unpack(">Q", frame_header)[0]
            offset += 8
            if length <= 0 or length > MAX_FRAME_BYTES or file_size - offset < length + 32:
                raise AuthorizationError("descriptor ledger has an incomplete frame")
            payload = os.pread(self._ledger_fd, length, offset)
            if len(payload) != length:
                raise AuthorizationError("descriptor ledger has an incomplete frame payload")
            offset += length
            digest = os.pread(self._ledger_fd, 32, offset)
            if len(digest) != 32:
                raise AuthorizationError("descriptor ledger has an incomplete frame digest")
            offset += 32
            expected_digest = hashlib.sha256(previous + payload).digest()
            if digest != expected_digest:
                raise AuthorizationError("descriptor ledger hash chain is invalid")
            try:
                text = payload.decode("utf-8")
                event = json.loads(text, object_pairs_hook=self._pairs_without_duplicates)
            except (UnicodeDecodeError, ValueError) as exc:
                raise AuthorizationError("descriptor ledger event is invalid JSON") from exc
            if not isinstance(event, dict) or _canonical(event).encode("utf-8") != payload:
                raise AuthorizationError("descriptor ledger event is not canonical JSON")
            if not isinstance(event, dict) or event.get("sequence") != sequence + 1:
                raise AuthorizationError("descriptor ledger sequence is invalid")
            event_type = event.get("type")
            if event_type == "record":
                if set(event) != {
                    "sequence",
                    "type",
                    "authorization",
                } or not isinstance(event.get("authorization"), dict):
                    raise AuthorizationError("descriptor ledger record fields are invalid")
                if set(event["authorization"]) != set(UserAuthorization.__dataclass_fields__):
                    raise AuthorizationError("descriptor ledger authorization fields are invalid")
                authorization = self._from_document(event.get("authorization", {}))
                if (
                    authorization.authorization_id in state
                    or authorization.idempotency_key in idempotency
                ):
                    raise AuthorizationError("descriptor ledger contains a duplicate authorization")
                state[authorization.authorization_id] = (authorization, None)
                idempotency.add(authorization.idempotency_key)
            elif event_type == "consume":
                if set(event) != {
                    "sequence",
                    "type",
                    "authorization_id",
                    "consumed_at",
                }:
                    raise AuthorizationError("descriptor ledger consumption fields are invalid")
                authorization_id = _text(event.get("authorization_id"), "authorization id")
                existing = state.get(authorization_id)
                if existing is None or existing[1] is not None:
                    raise AuthorizationError("descriptor ledger contains an invalid consumption")
                consumed_at = _text(event.get("consumed_at"), "consumed at", 128)
                _expiry(consumed_at)
                state[authorization_id] = (existing[0], consumed_at)
            else:
                raise AuthorizationError("descriptor ledger event type is invalid")
            sequence += 1
            previous = digest
        if sequence != checkpoint_sequence or previous != checkpoint_digest:
            raise AuthorizationError("descriptor ledger terminal checkpoint mismatch")
        return (
            state,
            idempotency,
            sequence,
            previous,
            checkpoint_generation,
            checkpoint_slot,
            external_checkpoint,
        )

    @staticmethod
    def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def integrity_check(self) -> None:
        with self._mutex:
            state, idempotency, sequence, digest, generation, slot, external = self._scan()
            self._state, self._idempotency, self._sequence, self._last_digest = (
                state,
                idempotency,
                sequence,
                digest,
            )
            self._checkpoint_generation, self._checkpoint_slot = generation, slot
            self._external_checkpoint = external

    def _append(self, event: dict[str, Any]) -> None:
        event = {"sequence": self._sequence + 1, **event}
        payload = _canonical(event).encode("utf-8")
        if len(payload) > MAX_FRAME_BYTES:
            raise AuthorizationError("descriptor ledger event exceeds bound")
        digest = hashlib.sha256(self._last_digest + payload).digest()
        os.lseek(self._ledger_fd, 0, os.SEEK_END)
        self._write_all(struct.pack(">Q", len(payload)) + payload + digest)
        os.fsync(self._ledger_fd)
        external: ExternalCheckpoint | None = None
        if self._checkpoint_provider is not None:
            try:
                external = self._checkpoint_provider.advance_and_attest(
                    self._ledger_id, event["sequence"], digest.hex()
                )
            except (CheckpointError, ValueError, TypeError) as exc:
                raise AuthorizationError("external checkpoint advancement failed") from exc
            if (
                not isinstance(external, ExternalCheckpoint)
                or external.sequence != event["sequence"]
                or external.head_hash != digest.hex()
            ):
                raise AuthorizationError("external checkpoint binding mismatch")
            try:
                self._checkpoint_provider.verify(
                    external, self._ledger_id, event["sequence"], digest.hex()
                )
            except (CheckpointError, ValueError, TypeError) as exc:
                raise AuthorizationError(
                    "external checkpoint verification failed before commit"
                ) from exc
        self._sequence += 1
        self._last_digest = digest
        next_generation = self._checkpoint_generation + 1
        next_slot = 1 - self._checkpoint_slot
        checkpoint_offset = len(MAGIC) + next_slot * CHECKPOINT_SLOT_BYTES
        checkpoint = self._checkpoint_bytes(
            next_generation, self._sequence, self._last_digest, external
        )
        if os.pwrite(self._ledger_fd, checkpoint, checkpoint_offset) != len(checkpoint):
            raise AuthorizationError("descriptor ledger checkpoint write failed")
        os.fsync(self._ledger_fd)
        self._checkpoint_generation, self._checkpoint_slot = next_generation, next_slot
        self._external_checkpoint = external

    def record(self, authorization: UserAuthorization) -> str:
        with self._mutex:
            validate_authorization(authorization)
            self.integrity_check()
            if (
                authorization.authorization_id in self._state
                or authorization.idempotency_key in self._idempotency
            ):
                raise AuthorizationError("authorization replay or duplicate")
            self._append({"type": "record", "authorization": authorization.document()})
            self._state[authorization.authorization_id] = (authorization, None)
            self._idempotency.add(authorization.idempotency_key)
            return authorization.binding_digest()

    def consume(
        self,
        authorization_id: str,
        *,
        expected: UserAuthorization | None = None,
        now: dt.datetime | None = None,
    ) -> UserAuthorization:
        with self._mutex:
            authorization_id = _text(authorization_id, "authorization id")
            self.integrity_check()
            existing = self._state.get(authorization_id)
            if existing is None:
                raise AuthorizationError("authorization not found")
            authorization, consumed_at = existing
            if consumed_at is not None:
                raise AuthorizationError("authorization already consumed")
            current = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
            if _expiry(authorization.expires_at) <= current:
                raise AuthorizationError("authorization expired")
            if expected is not None and authorization.document() != expected.document():
                raise AuthorizationError("authorization binding mismatch")
            stamp = current.isoformat().replace("+00:00", "Z")
            self._append(
                {
                    "type": "consume",
                    "authorization_id": authorization_id,
                    "consumed_at": stamp,
                }
            )
            self._state[authorization_id] = (authorization, stamp)
            return authorization

    def close(self) -> None:
        fcntl.flock(self._ledger_fd, fcntl.LOCK_UN)
        fcntl.flock(self._parent_fd, fcntl.LOCK_UN)
        os.close(self._ledger_fd)
        os.close(self._parent_fd)
