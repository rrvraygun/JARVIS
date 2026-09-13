from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import activation_authority as AUTH
import descriptor_bound_authority as DBA
from descriptor_bound_authority import DescriptorBoundActivationLedger
from external_checkpoint import CheckpointError, FixtureCheckpointProvider


class DescriptorBoundAuthorityTests(unittest.TestCase):
    def _authorization(
        self, key: str = "descriptor-1", expires: str = "2099-01-01T00:00:00Z"
    ) -> AUTH.UserAuthorization:
        return AUTH.UserAuthorization(
            authorization_id=f"auth-{key}",
            request_id=f"request-{key}",
            proposal_digest="a" * 64,
            source_catalog_digest="b" * 64,
            scope_digest="c" * 64,
            attestation_digest="d" * 64,
            approved_group_ids=("compute-summary", "platform-identity"),
            approved_fact_ids=("cpu.architecture", "memory.total_bytes"),
            decision_digest="e" * 64,
            idempotency_key=key,
            expires_at=expires,
        )

    def test_record_consume_reopen_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.log"
            ledger = DescriptorBoundActivationLedger(path)
            authorization = self._authorization()
            ledger.record(authorization)
            consumed = ledger.consume(authorization.authorization_id, expected=authorization)
            self.assertEqual(consumed.authorization_id, authorization.authorization_id)
            ledger.close()
            reopened = DescriptorBoundActivationLedger(path)
            try:
                with self.assertRaisesRegex(AUTH.AuthorizationError, "already consumed"):
                    reopened.consume(authorization.authorization_id)
            finally:
                reopened.close()

    def test_duplicate_and_binding_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = DescriptorBoundActivationLedger(Path(directory) / "authority.log")
            authorization = self._authorization()
            ledger.record(authorization)
            with self.assertRaisesRegex(AUTH.AuthorizationError, "duplicate"):
                ledger.record(authorization)
            wrong = AUTH.UserAuthorization(
                **{**authorization.__dict__, "decision_digest": "f" * 64}
            )
            with self.assertRaisesRegex(AUTH.AuthorizationError, "binding mismatch"):
                ledger.consume(authorization.authorization_id, expected=wrong)
            ledger.close()

    def test_truncated_or_tampered_frame_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.log"
            ledger = DescriptorBoundActivationLedger(path)
            ledger.record(self._authorization())
            ledger.close()
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaisesRegex(AUTH.AuthorizationError, "incomplete frame|hash chain"):
                DescriptorBoundActivationLedger(path)

    def test_complete_prefix_rollback_fails_checkpoint_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.log"
            ledger = DescriptorBoundActivationLedger(path)
            authorization = self._authorization("rollback")
            ledger.record(authorization)
            ledger.consume(authorization.authorization_id)
            ledger.close()
            with path.open("r+b") as handle:
                handle.truncate(DBA.DATA_OFFSET)
            with self.assertRaisesRegex(AUTH.AuthorizationError, "checkpoint mismatch"):
                DescriptorBoundActivationLedger(path)

    def test_open_descriptor_survives_path_rename_for_existing_handle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.log"
            replacement = Path(directory) / "replacement.log"
            ledger = DescriptorBoundActivationLedger(path)
            path.rename(replacement)
            ledger.record(self._authorization("renamed"))
            ledger.integrity_check()
            ledger.close()
            self.assertTrue(replacement.exists())
            self.assertFalse(path.exists())

    def test_expired_record_remains_structurally_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.log"
            ledger = DescriptorBoundActivationLedger(path)
            expired = self._authorization("expired", "2020-01-01T00:00:00Z")
            ledger._append({"type": "record", "authorization": expired.document()})
            ledger.close()
            reopened = DescriptorBoundActivationLedger(path)
            try:
                with self.assertRaisesRegex(AUTH.AuthorizationError, "expired"):
                    reopened.consume(expired.authorization_id)
            finally:
                reopened.close()

    def test_record_rescans_before_append_after_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.log"
            ledger = DescriptorBoundActivationLedger(path)
            ledger.record(self._authorization())
            with path.open("r+b") as handle:
                handle.truncate(1)
            with self.assertRaisesRegex(AUTH.AuthorizationError, "magic|incomplete"):
                ledger.record(self._authorization("tampered"))
            ledger.close()

    def test_shared_instance_serializes_concurrent_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = DescriptorBoundActivationLedger(Path(directory) / "authority.log")
            failures: list[Exception] = []

            def add(index: int) -> None:
                try:
                    ledger.record(self._authorization(f"thread-{index}"))
                except Exception as exc:  # pragma: no cover - diagnostic assertion
                    failures.append(exc)

            threads = [threading.Thread(target=add, args=(index,)) for index in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(failures, [])
            ledger.integrity_check()
            ledger.close()

    def test_external_checkpoint_is_persisted_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.log"
            provider = FixtureCheckpointProvider(b"fixture-checkpoint-secret")
            ledger = DescriptorBoundActivationLedger(
                path, checkpoint_provider=provider, ledger_id="jarvis-authority"
            )
            authorization = self._authorization("external")
            ledger.record(authorization)
            self.assertIsNotNone(ledger._external_checkpoint)
            ledger.close()

            reopened = DescriptorBoundActivationLedger(
                path, checkpoint_provider=provider, ledger_id="jarvis-authority"
            )
            try:
                reopened.integrity_check()
                self.assertEqual(reopened._sequence, 1)
                self.assertIsNotNone(reopened._external_checkpoint)
            finally:
                reopened.close()

    def test_external_checkpoint_requires_provider_on_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.log"
            provider = FixtureCheckpointProvider(b"fixture-checkpoint-secret")
            ledger = DescriptorBoundActivationLedger(path, checkpoint_provider=provider)
            ledger.record(self._authorization("requires-provider"))
            ledger.close()
            with self.assertRaisesRegex(
                AUTH.AuthorizationError, "external checkpoint requires a provider"
            ):
                DescriptorBoundActivationLedger(path)

    def test_external_checkpoint_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.log"
            provider = FixtureCheckpointProvider(b"fixture-checkpoint-secret")
            ledger = DescriptorBoundActivationLedger(path, checkpoint_provider=provider)
            ledger.record(self._authorization("external-tamper"))
            ledger.close()
            with path.open("r+b") as handle:
                handle.seek(len(DBA.MAGIC) + DBA.CHECKPOINT_SLOT_BYTES + DBA.CHECKPOINT_STRUCT.size)
                value = handle.read(1)
                handle.seek(len(DBA.MAGIC) + DBA.CHECKPOINT_SLOT_BYTES + DBA.CHECKPOINT_STRUCT.size)
                handle.write(bytes([value[0] ^ 1]))
            with self.assertRaisesRegex(AUTH.AuthorizationError, "checkpoint"):
                DescriptorBoundActivationLedger(path, checkpoint_provider=provider)

    def test_event_without_external_checkpoint_fails_closed(self) -> None:
        class FailingProvider:
            def advance_and_attest(self, ledger_id: str, sequence: int, head_hash: str):
                raise CheckpointError("simulated provider failure")

            def verify(self, checkpoint, ledger_id: str, sequence: int, head_hash: str) -> None:
                raise CheckpointError("simulated provider failure")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.log"
            ledger = DescriptorBoundActivationLedger(path, checkpoint_provider=FailingProvider())
            with self.assertRaisesRegex(AUTH.AuthorizationError, "advancement failed"):
                ledger.record(self._authorization("external-failure"))
            ledger.close()
            with self.assertRaisesRegex(AUTH.AuthorizationError, "checkpoint mismatch"):
                DescriptorBoundActivationLedger(
                    path,
                    checkpoint_provider=FixtureCheckpointProvider(b"fixture-checkpoint-secret"),
                )

    def test_invalid_provider_checkpoint_is_not_committed(self) -> None:
        class InvalidProvider(FixtureCheckpointProvider):
            def advance_and_attest(self, ledger_id: str, sequence: int, head_hash: str):
                checkpoint = super().advance_and_attest(ledger_id, sequence, head_hash)
                return checkpoint.__class__(**{**checkpoint.__dict__, "authenticator": "0" * 64})

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.log"
            provider = InvalidProvider(b"fixture-checkpoint-secret")
            ledger = DescriptorBoundActivationLedger(path, checkpoint_provider=provider)
            with self.assertRaisesRegex(
                AUTH.AuthorizationError, "verification failed before commit"
            ):
                ledger.record(self._authorization("invalid-provider"))
            ledger.close()
            with self.assertRaisesRegex(AUTH.AuthorizationError, "checkpoint mismatch"):
                DescriptorBoundActivationLedger(
                    path,
                    checkpoint_provider=FixtureCheckpointProvider(b"fixture-checkpoint-secret"),
                )


if __name__ == "__main__":
    unittest.main()
