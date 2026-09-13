from __future__ import annotations

import os
import stat
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from external_checkpoint import (
    CheckpointError,
    FixtureCheckpointProvider,
    Tpm2NvCounterHmacProvider,
    Tpm2NvCounterProvider,
)


class ExternalCheckpointTests(unittest.TestCase):
    def test_monotonic_attestation_and_binding(self) -> None:
        provider = FixtureCheckpointProvider(b"fixture-secret-for-tests")
        first = provider.advance_and_attest("jarvis-authority", 1, "1" * 64)
        provider.verify(first, "jarvis-authority", 1, "1" * 64)
        second = provider.advance_and_attest("jarvis-authority", 2, "2" * 64)
        provider.verify_current(second)
        with self.assertRaisesRegex(CheckpointError, "rollback"):
            provider.verify(first, "jarvis-authority", 1, "1" * 64)

    def test_sequence_and_ledger_rebinding_are_rejected(self) -> None:
        provider = FixtureCheckpointProvider(b"fixture-secret-for-tests")
        provider.advance_and_attest("jarvis-authority", 1, "1" * 64)
        with self.assertRaisesRegex(CheckpointError, "sequence"):
            provider.advance_and_attest("jarvis-authority", 3, "3" * 64)
        with self.assertRaisesRegex(CheckpointError, "ledger identity"):
            provider.advance_and_attest("other-ledger", 2, "2" * 64)

    def test_authenticator_tamper_and_wrong_head_fail_closed(self) -> None:
        provider = FixtureCheckpointProvider(b"fixture-secret-for-tests")
        checkpoint = provider.advance_and_attest("jarvis-authority", 1, "1" * 64)
        tampered = checkpoint.__class__(**{**checkpoint.__dict__, "head_hash": "2" * 64})
        with self.assertRaisesRegex(CheckpointError, "binding mismatch|authenticator"):
            provider.verify(tampered, "jarvis-authority", 1, "2" * 64)
        with self.assertRaisesRegex(CheckpointError, "secret"):
            FixtureCheckpointProvider(b"short")

    def test_fixture_is_not_live_tpm(self) -> None:
        provider = FixtureCheckpointProvider(b"fixture-secret-for-tests")
        self.assertEqual(provider.counter_value, 0)

    def test_tpm_provider_binds_counter_and_rejects_drift(self) -> None:
        with self.subTest("hardware provider"):
            fake_stat = __import__("types").SimpleNamespace(
                st_uid=os.getuid(), st_mode=stat.S_IFREG | 0o600
            )
            with (
                patch(
                    "external_checkpoint.os.path.realpath",
                    return_value="/tmp/jarvis-test-auth",
                ),
                patch("external_checkpoint.os.stat", return_value=fake_stat),
                patch("external_checkpoint.os.path.isfile", return_value=True),
            ):
                counter = {"value": 0}
                calls = []

                def runner(argv, **kwargs):
                    calls.append(argv)
                    if argv[0] == "tpm2_nvincrement":
                        counter["value"] += 1
                        return __import__("subprocess").CompletedProcess(argv, 0, b"", b"")
                    if argv[0] == "tpm2_nvread":
                        return __import__("subprocess").CompletedProcess(
                            argv, 0, counter["value"].to_bytes(8, "big"), b""
                        )
                    raise AssertionError(argv)

                provider = Tpm2NvCounterProvider(
                    "0x1500010", "/tmp/jarvis-test-auth", runner=runner
                )
                checkpoint = provider.advance_and_attest("jarvis-authority", 1, "1" * 64)
                provider.verify(checkpoint, "jarvis-authority", 1, "1" * 64)
                self.assertEqual(checkpoint.counter_value, 1)
                self.assertTrue(all("shell" not in call for call in calls))
                with self.assertRaisesRegex(CheckpointError, "next monotonic sequence"):
                    provider.advance_and_attest("jarvis-authority", 3, "3" * 64)
                counter["value"] = 2
                with self.assertRaisesRegex(CheckpointError, "drift"):
                    provider.verify(checkpoint, "jarvis-authority", 1, "1" * 64)

    def test_tpm_hmac_provider_keeps_authenticator_key_out_of_process(self) -> None:
        fake_stat = __import__("types").SimpleNamespace(
            st_uid=os.getuid(), st_mode=stat.S_IFREG | 0o600
        )
        with (
            patch("external_checkpoint.os.path.realpath", side_effect=lambda value: value),
            patch("external_checkpoint.os.stat", return_value=fake_stat),
            patch("external_checkpoint.os.path.isfile", return_value=True),
        ):
            counter = {"value": 0}
            key = b"tpm-only-test-key"

            def runner(argv, **kwargs):
                self.assertFalse(
                    kwargs.get("stdin") is not None and kwargs.get("input") is not None
                )
                if argv[0] == "tpm2_nvincrement":
                    counter["value"] += 1
                    return __import__("subprocess").CompletedProcess(argv, 0, b"", b"")
                if argv[0] == "tpm2_nvread":
                    return __import__("subprocess").CompletedProcess(
                        argv, 0, counter["value"].to_bytes(8, "big"), b""
                    )
                if argv[0] == "tpm2_hmac":
                    digest = (
                        __import__("hmac")
                        .new(key, kwargs["input"], __import__("hashlib").sha256)
                        .hexdigest()
                        .encode()
                    )
                    return __import__("subprocess").CompletedProcess(argv, 0, digest, b"")
                raise AssertionError(argv)

            provider = Tpm2NvCounterHmacProvider(
                "0x1500010",
                "/tmp/nv-auth",
                "0x81000010",
                "/tmp/hmac-auth",
                runner=runner,
            )
            checkpoint = provider.advance_and_attest("jarvis-authority", 1, "1" * 64)
            provider.verify(checkpoint, "jarvis-authority", 1, "1" * 64)
            self.assertEqual(checkpoint.authenticator_algorithm, "tpm2-nv-counter-hmac-sha256")
            tampered = checkpoint.__class__(**{**checkpoint.__dict__, "sequence": 2})
            with self.assertRaisesRegex(CheckpointError, "drift"):
                provider.verify(tampered, "jarvis-authority", 2, "1" * 64)

    def test_tpm_hmac_provider_rejects_counter_drift_during_authentication(
        self,
    ) -> None:
        fake_stat = __import__("types").SimpleNamespace(
            st_uid=os.getuid(), st_mode=stat.S_IFREG | 0o600
        )
        with (
            patch("external_checkpoint.os.path.realpath", side_effect=lambda value: value),
            patch("external_checkpoint.os.stat", return_value=fake_stat),
            patch("external_checkpoint.os.path.isfile", return_value=True),
        ):
            counter = {"value": 0, "drift_during_hmac": False}
            key = b"tpm-only-test-key"

            def runner(argv, **kwargs):
                if argv[0] == "tpm2_nvincrement":
                    counter["value"] += 1
                    return __import__("subprocess").CompletedProcess(argv, 0, b"", b"")
                if argv[0] == "tpm2_nvread":
                    return __import__("subprocess").CompletedProcess(
                        argv, 0, counter["value"].to_bytes(8, "big"), b""
                    )
                if argv[0] == "tpm2_hmac":
                    digest = (
                        __import__("hmac")
                        .new(key, kwargs["input"], __import__("hashlib").sha256)
                        .hexdigest()
                        .encode()
                    )
                    if counter["drift_during_hmac"]:
                        counter["value"] += 1
                        counter["drift_during_hmac"] = False
                    return __import__("subprocess").CompletedProcess(argv, 0, digest, b"")
                raise AssertionError(argv)

            provider = Tpm2NvCounterHmacProvider(
                "0x1500010",
                "/tmp/nv-auth",
                "0x81000010",
                "/tmp/hmac-auth",
                runner=runner,
            )
            checkpoint = provider.advance_and_attest("jarvis-authority", 1, "1" * 64)
            counter["drift_during_hmac"] = True
            with self.assertRaisesRegex(CheckpointError, "drift"):
                provider.verify(checkpoint, "jarvis-authority", 1, "1" * 64)


if __name__ == "__main__":
    unittest.main()
