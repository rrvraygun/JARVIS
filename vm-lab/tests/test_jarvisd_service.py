from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import jarvisd_service as SERVICE


class JarvisdServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.ledger = Path("/tmp/jarvisd-test-ledger.sqlite3").resolve()

    def test_health_is_bounded(self) -> None:
        result = SERVICE.handle_request(
            {"method": "health.read", "request_id": "health-1"},
            project_root=self.root,
            ledger_path=self.ledger,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["service"], "jarvisd-user-service-v1")

    def test_unknown_method_and_extra_fields_fail(self) -> None:
        with self.assertRaisesRegex(SERVICE.JarvisdError, "not registered"):
            SERVICE.handle_request(
                {"method": "shell.exec", "request_id": "x"},
                project_root=self.root,
                ledger_path=self.ledger,
            )
        with self.assertRaisesRegex(SERVICE.JarvisdError, "unexpected request fields"):
            SERVICE.handle_request(
                {"method": "health.read", "request_id": "x", "extra": True},
                project_root=self.root,
                ledger_path=self.ledger,
            )

    def test_status_reports_live_read_only_current_policy(self) -> None:
        result = SERVICE.handle_request(
            {"method": "activation.status", "request_id": "status-1"},
            project_root=self.root,
            ledger_path=self.ledger,
        )
        self.assertTrue(result["activation"]["controller_host_observation_enabled"])
        self.assertTrue(result["activation"]["broker_host_observation_enabled"])

    def test_observation_prepare_fails_closed_before_enablement(self) -> None:
        authorization = {
            "authorization_id": "auth-test",
            "request_id": "observe-1",
            "proposal_digest": "a" * 64,
            "source_catalog_digest": "b" * 64,
            "scope_digest": "c" * 64,
            "attestation_digest": "d" * 64,
            "approved_group_ids": ["compute-summary", "platform-identity"],
            "approved_fact_ids": ["cpu.architecture", "memory.total_bytes"],
            "decision_digest": "e" * 64,
            "idempotency_key": "idempotency-test",
            "expires_at": "2099-01-01T00:00:00Z",
        }
        with self.assertRaisesRegex(SERVICE.JarvisdError, "failed closed"):
            SERVICE.handle_request(
                {
                    "method": "observation.prepare",
                    "request_id": "observe-1",
                    "authorization_id": "auth-test",
                    "authorization": authorization,
                },
                project_root=self.root,
                ledger_path=self.ledger,
            )

    def test_observation_prepare_binds_request_identity(self) -> None:
        authorization = {
            "authorization_id": "auth-test",
            "request_id": "bound-request",
            "proposal_digest": "a" * 64,
            "source_catalog_digest": "b" * 64,
            "scope_digest": "c" * 64,
            "attestation_digest": "d" * 64,
            "approved_group_ids": ["compute-summary", "platform-identity"],
            "approved_fact_ids": ["cpu.architecture", "memory.total_bytes"],
            "decision_digest": "e" * 64,
            "idempotency_key": "idempotency-test",
            "expires_at": "2099-01-01T00:00:00Z",
        }
        with self.assertRaisesRegex(SERVICE.JarvisdError, "request identity"):
            SERVICE.handle_request(
                {
                    "method": "observation.prepare",
                    "request_id": "different-request",
                    "authorization_id": "auth-test",
                    "authorization": authorization,
                },
                project_root=self.root,
                ledger_path=self.ledger,
            )


if __name__ == "__main__":
    unittest.main()
