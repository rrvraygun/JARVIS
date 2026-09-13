#!/usr/bin/env python3
"""External monotonic-checkpoint contract and opt-in providers.

The fixture provider is in-memory and performs no host, network, privilege, or
persistence access. The TPM providers invoke only fixed tpm2-tools commands
when explicitly configured; importing this module does not access the TPM, and
the providers are not activated or wired into live observation by default.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Protocol


class CheckpointError(ValueError):
    """Raised when a checkpoint cannot be created or verified."""


_LEDGER_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _canonical(value: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CheckpointError("checkpoint value is not canonical JSON") from exc


def _hash(value: str, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise CheckpointError(f"invalid {label}")
    return value


def _ledger_id(value: str) -> str:
    if not isinstance(value, str) or not _LEDGER_ID.fullmatch(value):
        raise CheckpointError("invalid ledger id")
    return value


@dataclass(frozen=True)
class ExternalCheckpoint:
    schema_version: int
    ledger_id: str
    counter_value: int
    sequence: int
    head_hash: str
    authenticator_algorithm: str
    authenticator: str

    def unsigned_document(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ledger_id": self.ledger_id,
            "counter_value": self.counter_value,
            "sequence": self.sequence,
            "head_hash": self.head_hash,
            "authenticator_algorithm": self.authenticator_algorithm,
        }

    def document(self) -> dict[str, Any]:
        return {**self.unsigned_document(), "authenticator": self.authenticator}


class CheckpointProvider(Protocol):
    def advance_and_attest(
        self, ledger_id: str, sequence: int, head_hash: str
    ) -> ExternalCheckpoint: ...

    def verify(
        self,
        checkpoint: ExternalCheckpoint,
        ledger_id: str,
        sequence: int,
        head_hash: str,
    ) -> None: ...


class FixtureCheckpointProvider:
    """In-memory emulator for tests; never suitable for activation."""

    def __init__(self, secret: bytes) -> None:
        if not isinstance(secret, bytes) or len(secret) < 16:
            raise CheckpointError("fixture checkpoint secret must be at least 16 bytes")
        self._secret = secret
        self._counter = 0
        self._sequence = 0
        self._ledger_id: str | None = None
        self._head_hash = "0" * 64

    @property
    def counter_value(self) -> int:
        return self._counter

    def _authenticate(self, body: dict[str, Any]) -> str:
        return hmac.new(self._secret, _canonical(body), hashlib.sha256).hexdigest()

    def advance_and_attest(
        self, ledger_id: str, sequence: int, head_hash: str
    ) -> ExternalCheckpoint:
        ledger_id = _ledger_id(ledger_id)
        head_hash = _hash(head_hash, "head hash")
        if type(sequence) is not int or sequence != self._sequence + 1:
            raise CheckpointError("checkpoint sequence is not the next monotonic sequence")
        if self._ledger_id is not None and self._ledger_id != ledger_id:
            raise CheckpointError("checkpoint ledger identity changed")
        self._counter += 1
        checkpoint = ExternalCheckpoint(
            1, ledger_id, self._counter, sequence, head_hash, "fixture-hmac-sha256", ""
        )
        authenticator = self._authenticate(checkpoint.unsigned_document())
        checkpoint = ExternalCheckpoint(
            schema_version=checkpoint.schema_version,
            ledger_id=checkpoint.ledger_id,
            counter_value=checkpoint.counter_value,
            sequence=checkpoint.sequence,
            head_hash=checkpoint.head_hash,
            authenticator_algorithm=checkpoint.authenticator_algorithm,
            authenticator=authenticator,
        )
        self._ledger_id = ledger_id
        self._sequence = sequence
        self._head_hash = head_hash
        return checkpoint

    def verify(
        self,
        checkpoint: ExternalCheckpoint,
        ledger_id: str,
        sequence: int,
        head_hash: str,
    ) -> None:
        ledger_id = _ledger_id(ledger_id)
        head_hash = _hash(head_hash, "head hash")
        if type(sequence) is not int or sequence <= 0:
            raise CheckpointError("checkpoint sequence is invalid")
        if (
            checkpoint.document().keys()
            != ExternalCheckpoint(1, "x", 1, 1, "0" * 64, "x", "x").document().keys()
        ):
            raise CheckpointError("checkpoint fields are not exact")
        if (
            checkpoint.schema_version != 1
            or checkpoint.authenticator_algorithm != "fixture-hmac-sha256"
        ):
            raise CheckpointError("checkpoint algorithm or version is unsupported")
        if (
            type(checkpoint.counter_value) is not int
            or type(checkpoint.sequence) is not int
            or checkpoint.counter_value <= 0
        ):
            raise CheckpointError("checkpoint counter is invalid")
        if (
            checkpoint.ledger_id != ledger_id
            or checkpoint.sequence != sequence
            or checkpoint.head_hash != head_hash
        ):
            raise CheckpointError("checkpoint binding mismatch")
        expected = self._authenticate(checkpoint.unsigned_document())
        if not hmac.compare_digest(expected, checkpoint.authenticator):
            raise CheckpointError("checkpoint authenticator mismatch")
        if checkpoint.counter_value != self._counter or checkpoint.sequence != self._sequence:
            raise CheckpointError("checkpoint rollback or counter drift detected")

    def verify_current(self, checkpoint: ExternalCheckpoint) -> None:
        if self._ledger_id is None:
            raise CheckpointError("fixture checkpoint has no current ledger")
        self.verify(checkpoint, self._ledger_id, self._sequence, self._head_hash)


class Tpm2NvCounterProvider:
    """Read and advance a TPM 2.0 NV counter through fixed tpm2-tools calls.

    This is a hardware-bound monotonic counter provider, but deliberately does
    not claim a TPM-protected signing/HMAC key.  The authenticator is a digest
    over the counter bytes returned directly by the TPM.  A separate protected
    key provider remains required before H1 activation.
    """

    _AUTH_ALGORITHM = "tpm2-nv-counter-read-sha256"

    def __init__(
        self,
        nv_index: str,
        auth_file: str,
        *,
        runner: Any = subprocess.run,
        timeout_seconds: float = 5.0,
    ) -> None:
        if not isinstance(nv_index, str) or not re.fullmatch(r"0x[0-9a-fA-F]{1,8}", nv_index):
            raise CheckpointError("invalid TPM NV index")
        if not isinstance(auth_file, str) or not auth_file or not os.path.isabs(auth_file):
            raise CheckpointError("TPM authorization file must be an absolute path")
        try:
            canonical_auth = os.path.realpath(auth_file)
            stat = os.stat(canonical_auth)
        except OSError as exc:
            raise CheckpointError("TPM authorization file is unavailable") from exc
        if not os.path.isfile(canonical_auth) or stat.st_uid != os.getuid() or stat.st_mode & 0o077:
            raise CheckpointError("TPM authorization file must be user-owned and mode 600")
        self._nv_index = nv_index
        self._auth_file = canonical_auth
        self._runner = runner
        self._timeout = timeout_seconds

    def _run(self, executable: str, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        return self._run_with_input(executable, None, *arguments)

    def _run_with_input(
        self, executable: str, input_bytes: bytes | None, *arguments: str
    ) -> subprocess.CompletedProcess[bytes]:
        try:
            run_kwargs: dict[str, Any] = {
                "input": input_bytes,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "check": False,
                "timeout": self._timeout,
            }
            if input_bytes is None:
                run_kwargs["stdin"] = subprocess.DEVNULL
            result = self._runner([executable, "-Q", *arguments], **run_kwargs)
        except (OSError, subprocess.SubprocessError) as exc:
            raise CheckpointError("TPM command failed to start") from exc
        if result.returncode != 0:
            raise CheckpointError("TPM command failed")
        return result

    def _read_counter_bytes(self) -> bytes:
        result = self._run("tpm2_nvread", "-P", f"file:{self._auth_file}", self._nv_index)
        raw = bytes(result.stdout)
        if len(raw) != 8:
            raise CheckpointError("TPM NV counter returned an invalid size")
        return raw

    @staticmethod
    def _authenticator(unsigned_document: dict[str, Any], raw_counter: bytes) -> str:
        return hashlib.sha256(
            b"JARVIS-TPM2-NV-COUNTER\0" + raw_counter + _canonical(unsigned_document)
        ).hexdigest()

    def advance_and_attest(
        self, ledger_id: str, sequence: int, head_hash: str
    ) -> ExternalCheckpoint:
        ledger_id = _ledger_id(ledger_id)
        head_hash = _hash(head_hash, "head hash")
        if type(sequence) is not int or sequence <= 0:
            raise CheckpointError("checkpoint sequence is invalid")
        raw_before = self._read_counter_bytes()
        current_counter = int.from_bytes(raw_before, "big")
        if sequence != current_counter + 1:
            raise CheckpointError("checkpoint sequence is not the next monotonic sequence")
        self._run("tpm2_nvincrement", "-P", f"file:{self._auth_file}", self._nv_index)
        raw_counter = self._read_counter_bytes()
        counter_value = int.from_bytes(raw_counter, "big")
        if counter_value != current_counter + 1:
            raise CheckpointError("TPM NV counter advanced unexpectedly")
        unsigned = ExternalCheckpoint(
            1, ledger_id, counter_value, sequence, head_hash, self._AUTH_ALGORITHM, ""
        ).unsigned_document()
        return ExternalCheckpoint(
            1,
            ledger_id,
            counter_value,
            sequence,
            head_hash,
            self._AUTH_ALGORITHM,
            self._authenticator(unsigned, raw_counter),
        )

    def verify(
        self,
        checkpoint: ExternalCheckpoint,
        ledger_id: str,
        sequence: int,
        head_hash: str,
    ) -> None:
        ledger_id = _ledger_id(ledger_id)
        head_hash = _hash(head_hash, "head hash")
        if type(sequence) is not int or sequence <= 0:
            raise CheckpointError("checkpoint sequence is invalid")
        if (
            checkpoint.schema_version != 1
            or type(checkpoint.counter_value) is not int
            or type(checkpoint.sequence) is not int
            or checkpoint.authenticator_algorithm != self._AUTH_ALGORITHM
        ):
            raise CheckpointError("checkpoint algorithm or version is unsupported")
        if (
            checkpoint.ledger_id != ledger_id
            or checkpoint.sequence != sequence
            or checkpoint.head_hash != head_hash
        ):
            raise CheckpointError("checkpoint binding mismatch")
        raw_counter = self._read_counter_bytes()
        current_counter = int.from_bytes(raw_counter, "big")
        if checkpoint.counter_value != current_counter:
            raise CheckpointError("checkpoint rollback or counter drift detected")
        unsigned = checkpoint.unsigned_document()
        expected = self._authenticator(unsigned, raw_counter)
        raw_after_auth = self._read_counter_bytes()
        if raw_after_auth != raw_counter:
            raise CheckpointError("checkpoint rollback or counter drift detected")
        if not hmac.compare_digest(expected, checkpoint.authenticator):
            raise CheckpointError("checkpoint authenticator mismatch")


class Tpm2NvCounterHmacProvider(Tpm2NvCounterProvider):
    """TPM NV counter plus TPM-resident HMAC authenticator.

    The HMAC key is referenced by a persistent TPM handle and never leaves the
    TPM.  This provider is still construction-stage until the handle, key
    authorization, ledger integration, and independent review are complete.
    """

    _AUTH_ALGORITHM = "tpm2-nv-counter-hmac-sha256"

    def __init__(
        self,
        nv_index: str,
        auth_file: str,
        hmac_handle: str,
        hmac_auth_file: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(nv_index, auth_file, **kwargs)
        if not isinstance(hmac_handle, str) or not re.fullmatch(r"0x81[0-9a-fA-F]{6}", hmac_handle):
            raise CheckpointError("invalid persistent TPM HMAC handle")
        self._hmac_handle = hmac_handle
        self._hmac_auth_file = self._validate_auth_file(
            hmac_auth_file, "TPM HMAC authorization file"
        )

    @staticmethod
    def _validate_auth_file(path: str, label: str) -> str:
        if not isinstance(path, str) or not path or not os.path.isabs(path):
            raise CheckpointError(f"{label} must be an absolute path")
        try:
            canonical = os.path.realpath(path)
            value = os.stat(canonical)
        except OSError as exc:
            raise CheckpointError(f"{label} is unavailable") from exc
        if not os.path.isfile(canonical) or value.st_uid != os.getuid() or value.st_mode & 0o077:
            raise CheckpointError(f"{label} must be user-owned and mode 600")
        return canonical

    @staticmethod
    def _hmac_input(unsigned_document: dict[str, Any]) -> bytes:
        return b"JARVIS-TPM2-NV-HMAC\0" + _canonical(unsigned_document)

    def _authenticate(self, unsigned_document: dict[str, Any]) -> str:
        result = self._run_with_input(
            "tpm2_hmac",
            self._hmac_input(unsigned_document),
            "-c",
            self._hmac_handle,
            "-p",
            f"file:{self._hmac_auth_file}",
            "-g",
            "sha256",
            "--hex",
        )
        authenticator = result.stdout.decode("ascii", "strict").strip()
        if not re.fullmatch(r"[0-9a-fA-F]{64}", authenticator):
            raise CheckpointError("TPM HMAC returned an invalid authenticator")
        return authenticator.lower()

    def advance_and_attest(
        self, ledger_id: str, sequence: int, head_hash: str
    ) -> ExternalCheckpoint:
        ledger_id = _ledger_id(ledger_id)
        head_hash = _hash(head_hash, "head hash")
        if type(sequence) is not int or sequence <= 0:
            raise CheckpointError("checkpoint sequence is invalid")
        raw_before = self._read_counter_bytes()
        current_counter = int.from_bytes(raw_before, "big")
        if sequence != current_counter + 1:
            raise CheckpointError("checkpoint sequence is not the next monotonic sequence")
        self._run("tpm2_nvincrement", "-P", f"file:{self._auth_file}", self._nv_index)
        raw_counter = self._read_counter_bytes()
        counter_value = int.from_bytes(raw_counter, "big")
        if counter_value != current_counter + 1:
            raise CheckpointError("TPM NV counter advanced unexpectedly")
        unsigned = ExternalCheckpoint(
            1, ledger_id, counter_value, sequence, head_hash, self._AUTH_ALGORITHM, ""
        ).unsigned_document()
        return ExternalCheckpoint(
            1,
            ledger_id,
            counter_value,
            sequence,
            head_hash,
            self._AUTH_ALGORITHM,
            self._authenticate(unsigned),
        )

    def verify(
        self,
        checkpoint: ExternalCheckpoint,
        ledger_id: str,
        sequence: int,
        head_hash: str,
    ) -> None:
        ledger_id = _ledger_id(ledger_id)
        head_hash = _hash(head_hash, "head hash")
        if type(sequence) is not int or sequence <= 0:
            raise CheckpointError("checkpoint sequence is invalid")
        if (
            checkpoint.schema_version != 1
            or type(checkpoint.counter_value) is not int
            or type(checkpoint.sequence) is not int
            or checkpoint.authenticator_algorithm != self._AUTH_ALGORITHM
        ):
            raise CheckpointError("checkpoint algorithm or version is unsupported")
        if (
            checkpoint.ledger_id != ledger_id
            or checkpoint.sequence != sequence
            or checkpoint.head_hash != head_hash
        ):
            raise CheckpointError("checkpoint binding mismatch")
        raw_counter = self._read_counter_bytes()
        current_counter = int.from_bytes(raw_counter, "big")
        if checkpoint.counter_value != current_counter or checkpoint.sequence != current_counter:
            raise CheckpointError("checkpoint rollback or counter drift detected")
        expected = self._authenticate(checkpoint.unsigned_document())
        raw_after_auth = self._read_counter_bytes()
        if raw_after_auth != raw_counter:
            raise CheckpointError("checkpoint rollback or counter drift detected")
        if not hmac.compare_digest(expected, checkpoint.authenticator):
            raise CheckpointError("checkpoint authenticator mismatch")
