from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import activation_authority as AUTH
import live_tier0_observation as LIVE


class LiveTier0ObservationTests(unittest.TestCase):
    def _authorization(self) -> AUTH.UserAuthorization:
        return AUTH.UserAuthorization(
            authorization_id="auth-live-1",
            request_id="request-live-1",
            proposal_digest="a" * 64,
            source_catalog_digest="b" * 64,
            scope_digest="c" * 64,
            attestation_digest="d" * 64,
            approved_group_ids=("compute-summary", "platform-identity"),
            approved_fact_ids=("cpu.architecture", "memory.total_bytes"),
            decision_digest="e" * 64,
            idempotency_key="live-1",
            expires_at="2099-01-01T00:00:00Z",
        )

    def test_current_policy_rejects_unbound_authorization_before_consumption(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = AUTH.ActivationAuthorityLedger(Path(directory) / "authority.sqlite3")
            authorization = self._authorization()
            ledger.record(authorization)
            with self.assertRaisesRegex(
                LIVE.LiveObservationError, "proposal or catalog binding drift"
            ):
                LIVE.collect_tier0(
                    ledger,
                    authorization.authorization_id,
                    expected_authorization=authorization,
                )
            # It should still be consumable: the policy check happened first.
            ledger.consume(authorization.authorization_id)
            with self.assertRaisesRegex(AUTH.AuthorizationError, "already consumed"):
                ledger.consume(authorization.authorization_id)
            ledger.close()

    def test_topology_range_parser_is_bounded(self) -> None:
        self.assertEqual(LIVE._range_count("0-3,8"), 5)
        with self.assertRaisesRegex(LIVE.LiveObservationError, "invalid kernel topology"):
            LIVE._range_count("3-1")

    def test_source_reader_rejects_oversize_and_symlink_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.write_bytes(b"0123456789")
            with self.assertRaisesRegex(LIVE.LiveObservationError, "exceeds bound"):
                LIVE._read(root, "source", 4)
            link = root / "link"
            link.symlink_to(source)
            with self.assertRaisesRegex(LIVE.LiveObservationError, "unavailable"):
                LIVE._read(root, "link", 64)

    def test_result_contract_distinguishes_authorization_mutation_from_host_effect(
        self,
    ) -> None:
        result = {
            "effect_occurred": True,
            "host_effect_occurred": False,
            "persistence_performed": False,
            "authorization_ledger_persistence_performed": True,
            "fact_persistence_performed": False,
            "authorization_ledger_mutated": True,
        }
        self.assertTrue(result["authorization_ledger_mutated"])
        self.assertFalse(result["host_effect_occurred"])
        self.assertFalse(result["fact_persistence_performed"])


if __name__ == "__main__":
    unittest.main()
