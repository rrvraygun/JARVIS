from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import power_profile_authority_ledger as LEDGER
import power_profile_executor_bridge as BRIDGE


class PowerProfileAuthorityLedgerTests(unittest.TestCase):
    def approval(
        self, *, approval_id: str = "approval-1", idempotency_key: str = "idem-1"
    ) -> BRIDGE.PowerProfileApproval:
        parameters = {
            "requested_profile": "performance",
            "pre_profile": "balanced",
            "tui_confirmed": True,
            "active_session": True,
            "on_battery": False,
            "thermal_degraded": False,
        }
        target = dict(BRIDGE.TARGET)
        return BRIDGE.PowerProfileApproval(
            approval_id=approval_id,
            operation_id=BRIDGE.OPERATION_ID,
            operation_revision=BRIDGE.OPERATION_REVISION,
            parameters_digest=BRIDGE.PreparedPowerProfileExecutor.parameters_digest(parameters),
            target_digest=BRIDGE.PreparedPowerProfileExecutor.target_digest(target),
            policy_digest=BRIDGE.current_policy_digest(),
            expires_at=(datetime.now(timezone.utc) + timedelta(seconds=30))
            .isoformat()
            .replace("+00:00", "Z"),
            idempotency_key=idempotency_key,
        )

    def test_record_consume_and_reopen_rejects_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "power-profile-approvals.sqlite3"
            approval = self.approval()
            ledger = LEDGER.PowerProfileAuthorityLedger(path)
            self.assertEqual(
                ledger.connection.execute("PRAGMA journal_mode").fetchone(), ("delete",)
            )
            self.assertEqual(ledger.connection.execute("PRAGMA synchronous").fetchone(), (2,))
            ledger.record(approval)
            ledger.consume(approval)
            ledger.close()
            reopened = LEDGER.PowerProfileAuthorityLedger(path)
            with self.assertRaisesRegex(LEDGER.PowerProfileLedgerError, "already consumed"):
                reopened.consume(approval)
            reopened.close()

    def test_reopen_preserves_unconsumed_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "power-profile-approvals.sqlite3"
            approval = self.approval()
            ledger = LEDGER.PowerProfileAuthorityLedger(path)
            ledger.record(approval)
            ledger.close()
            reopened = LEDGER.PowerProfileAuthorityLedger(path)
            reopened.consume(approval)
            reopened.close()

    def test_duplicate_idempotency_and_binding_mismatch_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "power-profile-approvals.sqlite3"
            approval = self.approval()
            ledger = LEDGER.PowerProfileAuthorityLedger(path)
            ledger.record(approval)
            with self.assertRaisesRegex(LEDGER.PowerProfileLedgerError, "replay or duplicate"):
                ledger.record(self.approval(approval_id="approval-2"))
            wrong = self.approval(approval_id="approval-1", idempotency_key="idem-2")
            with self.assertRaisesRegex(LEDGER.PowerProfileLedgerError, "binding mismatch"):
                ledger.consume(wrong)
            ledger.consume(approval)
            ledger.close()

    def test_corrupt_schema_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "power-profile-approvals.sqlite3"
            approval = self.approval()
            ledger = LEDGER.PowerProfileAuthorityLedger(path)
            ledger.record(approval)
            ledger.connection.execute("DROP TABLE power_profile_approvals")
            ledger.connection.commit()
            with self.assertRaisesRegex(LEDGER.PowerProfileLedgerError, "schema"):
                ledger.consume(approval)
            ledger.close()

    def test_existing_schema_without_idempotency_unique_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "power-profile-approvals.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute(
                """CREATE TABLE power_profile_approvals (
                    approval_id TEXT PRIMARY KEY,
                    operation_id TEXT NOT NULL,
                    operation_revision TEXT NOT NULL,
                    parameters_digest TEXT NOT NULL,
                    target_digest TEXT NOT NULL,
                    policy_digest TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    consumed_at TEXT
                )"""
            )
            connection.commit()
            connection.close()
            path.chmod(0o600)
            with self.assertRaisesRegex(LEDGER.PowerProfileLedgerError, "initialization failed"):
                LEDGER.PowerProfileAuthorityLedger(path)


if __name__ == "__main__":
    unittest.main()
