from __future__ import annotations

import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import activation_authority as AUTH


class ActivationAuthorityTests(unittest.TestCase):
    def _authorization(
        self, key: str = "idem-1", expires: str = "2099-01-01T00:00:00Z"
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

    def test_record_consume_is_durable_and_one_use(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.sqlite3"
            ledger = AUTH.ActivationAuthorityLedger(path)
            authorization = self._authorization()
            digest = ledger.record(authorization)
            self.assertEqual(len(digest), 64)
            self.assertFalse(
                ledger.is_consumed(authorization.authorization_id, expected=authorization)
            )
            consumed = ledger.consume(authorization.authorization_id)
            self.assertEqual(consumed.authorization_id, authorization.authorization_id)
            self.assertTrue(
                ledger.is_consumed(authorization.authorization_id, expected=authorization)
            )
            with self.assertRaisesRegex(AUTH.AuthorizationError, "already consumed"):
                ledger.consume(authorization.authorization_id)
            ledger.integrity_check()
            ledger.close()
            reopened = AUTH.ActivationAuthorityLedger(path)
            try:
                with self.assertRaisesRegex(AUTH.AuthorizationError, "already consumed"):
                    reopened.consume(authorization.authorization_id)
            finally:
                reopened.close()

    def test_duplicate_expired_and_invalid_scope_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.sqlite3"
            ledger = AUTH.ActivationAuthorityLedger(path)
            authorization = self._authorization()
            ledger.record(authorization)
            with self.assertRaisesRegex(AUTH.AuthorizationError, "duplicate"):
                ledger.record(authorization)
            expired = self._authorization("expired", "2020-01-01T00:00:00Z")
            with self.assertRaisesRegex(AUTH.AuthorizationError, "expired"):
                ledger.record(expired)
            unsorted = self._authorization("unsorted")
            unsorted = AUTH.UserAuthorization(
                **{
                    **unsorted.__dict__,
                    "approved_group_ids": ("platform-identity", "compute-summary"),
                }
            )
            with self.assertRaisesRegex(AUTH.AuthorizationError, "sorted and unique"):
                ledger.record(unsorted)
            ledger.close()

    def test_expiry_is_checked_at_consumption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.sqlite3"
            ledger = AUTH.ActivationAuthorityLedger(path)
            authorization = self._authorization()
            ledger.record(authorization)
            with self.assertRaisesRegex(AUTH.AuthorizationError, "expired"):
                ledger.consume(
                    authorization.authorization_id,
                    now=dt.datetime(2100, 1, 1, tzinfo=dt.timezone.utc),
                )
            ledger.close()

    def test_expected_binding_and_semantic_tamper_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.sqlite3"
            ledger = AUTH.ActivationAuthorityLedger(path)
            authorization = self._authorization("exact-1")
            ledger.record(authorization)
            wrong = AUTH.UserAuthorization(
                **{**authorization.__dict__, "decision_digest": "f" * 64}
            )
            with self.assertRaisesRegex(AUTH.AuthorizationError, "binding mismatch"):
                ledger.consume(authorization.authorization_id, expected=wrong)
            ledger.connection.execute(
                "UPDATE authorizations SET approved_group_ids = ? WHERE authorization_id = ?",
                ("not-json", authorization.authorization_id),
            )
            ledger.connection.commit()
            with self.assertRaisesRegex(
                AUTH.AuthorizationError, "malformed|sorted and unique|approved groups"
            ):
                ledger.consume(authorization.authorization_id)
            ledger.close()

    def test_consumption_runs_integrity_gate_before_update(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.sqlite3"
            ledger = AUTH.ActivationAuthorityLedger(path)
            authorization = self._authorization("integrity-1")
            ledger.record(authorization)
            original = ledger.integrity_check
            ledger.integrity_check = lambda: (_ for _ in ()).throw(
                AUTH.AuthorizationError("injected integrity failure")
            )
            with self.assertRaisesRegex(AUTH.AuthorizationError, "injected integrity failure"):
                ledger.consume(authorization.authorization_id, expected=authorization)
            ledger.integrity_check = original
            # The failed gate must not consume the authorization.
            ledger.consume(authorization.authorization_id, expected=authorization)
            ledger.close()

    def test_unconsumed_authorization_can_be_revoked_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.sqlite3"
            ledger = AUTH.ActivationAuthorityLedger(path)
            authorization = self._authorization("revoke-1")
            ledger.record(authorization)
            ledger.revoke_unconsumed(authorization.authorization_id, expected=authorization)
            with self.assertRaisesRegex(AUTH.AuthorizationError, "not found"):
                ledger.consume(authorization.authorization_id, expected=authorization)
            with self.assertRaisesRegex(AUTH.AuthorizationError, "not found"):
                ledger.revoke_unconsumed(authorization.authorization_id, expected=authorization)
            ledger.close()

    def test_consumed_authorization_cannot_be_revoked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.sqlite3"
            ledger = AUTH.ActivationAuthorityLedger(path)
            authorization = self._authorization("revoke-consumed")
            ledger.record(authorization)
            ledger.consume(authorization.authorization_id, expected=authorization)
            with self.assertRaisesRegex(AUTH.AuthorizationError, "consumed"):
                ledger.revoke_unconsumed(authorization.authorization_id, expected=authorization)
            ledger.close()

    def test_corrupt_database_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.sqlite3"
            ledger = AUTH.ActivationAuthorityLedger(path)
            ledger.close()
            path.write_bytes(b"not sqlite")
            with self.assertRaisesRegex(AUTH.AuthorizationError, "initialization failed"):
                AUTH.ActivationAuthorityLedger(path)

    def test_sqlite_connection_identity_matches_verified_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.sqlite3"
            ledger = AUTH.ActivationAuthorityLedger(path)
            database_path = Path(ledger.connection.execute("PRAGMA database_list").fetchone()[2])
            self.assertEqual(database_path.stat().st_ino, path.stat().st_ino)
            self.assertEqual(database_path.stat().st_dev, path.stat().st_dev)
            ledger.close()


if __name__ == "__main__":
    unittest.main()
