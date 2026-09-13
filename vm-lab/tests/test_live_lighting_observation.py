from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import activation_authority as AUTH
import live_lighting_observation as LIVE
from restricted_fact_store import fact_scope_digest, load_approved_scope


class LiveLightingObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = Path(__file__).resolve().parents[1]
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "host"
        for relative in (
            "sys/class/backlight/intel_backlight",
            "sys/class/leds/kbd_backlight",
            "sys/class/drm/card0",
        ):
            (self.root / relative).mkdir(parents=True)
        values = {
            "sys/class/backlight/intel_backlight/brightness": "42\n",
            "sys/class/backlight/intel_backlight/actual_brightness": "42\n",
            "sys/class/backlight/intel_backlight/max_brightness": "100\n",
            "sys/class/backlight/intel_backlight/type": "raw\n",
            "sys/class/leds/kbd_backlight/brightness": "2\n",
            "sys/class/leds/kbd_backlight/max_brightness": "3\n",
            "sys/class/leds/kbd_backlight/trigger": "none\n",
        }
        for relative, value in values.items():
            path = self.root / relative
            path.write_text(value, encoding="utf-8")
        self.addCleanup(self.temp.cleanup)

    def _authorization(self) -> AUTH.UserAuthorization:
        scope = load_approved_scope(self.project / "enrollment/lighting-approved-fact-scope.json")
        facts = tuple(sorted({fact_id for entry in scope.entries for fact_id in entry.fact_ids}))
        return AUTH.UserAuthorization(
            authorization_id="lighting-auth-1",
            request_id="lighting-request-1",
            proposal_digest=scope.proposal_digest,
            source_catalog_digest=scope.source_catalog_digest,
            scope_digest=fact_scope_digest(scope),
            attestation_digest=LIVE.runtime_contract_digest(self.project),
            approved_group_ids=("graphics-display-input",),
            approved_fact_ids=facts,
            decision_digest="e" * 64,
            idempotency_key="lighting-idempotency-1",
            expires_at=(dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5))
            .isoformat()
            .replace("+00:00", "Z"),
        )

    def test_collects_ephemeral_observation_and_consumes_once(self) -> None:
        authorization = self._authorization()
        with tempfile.TemporaryDirectory() as directory:
            ledger = AUTH.ActivationAuthorityLedger(Path(directory) / "activation.sqlite3")
            ledger.record(authorization)
            result = LIVE.collect_lighting(
                ledger,
                authorization.authorization_id,
                expected_authorization=authorization,
                project_root=self.project,
                host_root=self.root,
            )
            self.assertEqual(result["status"], "host_observed_lighting")
            self.assertFalse(result["persistence_performed"])
            self.assertEqual(result["observation"]["backlights"][0]["brightness"], "42")
            with mock.patch.object(
                LIVE.observer,
                "collect_passive",
                side_effect=AssertionError("host read on replay"),
            ):
                with self.assertRaises(LIVE.LiveLightingObservationError):
                    LIVE.collect_lighting(
                        ledger,
                        authorization.authorization_id,
                        expected_authorization=authorization,
                        project_root=self.project,
                        host_root=self.root,
                    )
            ledger.close()

    def test_scope_mismatch_fails_before_observation(self) -> None:
        authorization = self._authorization()
        wrong = AUTH.UserAuthorization(
            **{**authorization.__dict__, "approved_group_ids": ("compute-summary",)}
        )
        with tempfile.TemporaryDirectory() as directory:
            ledger = AUTH.ActivationAuthorityLedger(Path(directory) / "activation.sqlite3")
            ledger.record(wrong)
            with self.assertRaises(LIVE.LiveLightingObservationError):
                LIVE.collect_lighting(
                    ledger,
                    wrong.authorization_id,
                    expected_authorization=wrong,
                    project_root=self.project,
                    host_root=self.root,
                )
            self.assertFalse(ledger.is_consumed(wrong.authorization_id, expected=wrong))
            ledger.close()

    def test_operation_extra_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "controller").mkdir()
            operation = json.loads(
                (self.project / "controller/lighting-observation-operation.json").read_text()
            )
            operation["unexpected"] = True
            (root / "controller/lighting-observation-operation.json").write_text(
                json.dumps(operation)
            )
            with self.assertRaises(LIVE.LiveLightingObservationError):
                LIVE._validate_operation(root)

    def test_registry_extra_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "controller").mkdir()
            shutil.copy2(
                self.project / "controller/lighting-observation-policy.json",
                root / "controller/lighting-observation-policy.json",
            )
            registry = json.loads(
                (self.project / "controller/lighting-observation-registry.json").read_text()
            )
            registry["unexpected"] = True
            (root / "controller/lighting-observation-registry.json").write_text(
                json.dumps(registry)
            )
            with self.assertRaises(LIVE.LiveLightingObservationError):
                LIVE._validate_policy(root)

    def test_runtime_contract_digest_mismatch_fails_before_observation(self) -> None:
        authorization = self._authorization()
        wrong = AUTH.UserAuthorization(**{**authorization.__dict__, "attestation_digest": "d" * 64})
        with tempfile.TemporaryDirectory() as directory:
            ledger = AUTH.ActivationAuthorityLedger(Path(directory) / "activation.sqlite3")
            ledger.record(wrong)
            with mock.patch.object(
                LIVE.observer,
                "collect_passive",
                side_effect=AssertionError("host read before binding"),
            ):
                with self.assertRaises(LIVE.LiveLightingObservationError):
                    LIVE.collect_lighting(
                        ledger,
                        wrong.authorization_id,
                        expected_authorization=wrong,
                        project_root=self.project,
                        host_root=self.root,
                    )
            ledger.close()

    def test_runtime_digest_covers_authorization_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in LIVE.CONTRACT_FILES:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.project / relative, target)
            original = LIVE.runtime_contract_digest(root)
            dependency = root / "scripts/activation_authority.py"
            dependency.write_bytes(dependency.read_bytes() + b"\n")
            self.assertNotEqual(original, LIVE.runtime_contract_digest(root))

    def test_failed_observation_reserves_the_only_attempt(self) -> None:
        authorization = self._authorization()
        with tempfile.TemporaryDirectory() as directory:
            ledger = AUTH.ActivationAuthorityLedger(Path(directory) / "activation.sqlite3")
            ledger.record(authorization)
            with (
                mock.patch.object(
                    LIVE.observer,
                    "collect_passive",
                    side_effect=LIVE.observer.LightingObservationError("fixture failure"),
                ),
                self.assertRaises(LIVE.LiveLightingObservationError),
            ):
                LIVE.collect_lighting(
                    ledger,
                    authorization.authorization_id,
                    expected_authorization=authorization,
                    project_root=self.project,
                    host_root=self.root,
                )
            with mock.patch.object(
                LIVE.observer,
                "collect_passive",
                side_effect=AssertionError("retry read"),
            ):
                with self.assertRaises(LIVE.LiveLightingObservationError):
                    LIVE.collect_lighting(
                        ledger,
                        authorization.authorization_id,
                        expected_authorization=authorization,
                        project_root=self.project,
                        host_root=self.root,
                    )
            ledger.close()


if __name__ == "__main__":
    unittest.main()
