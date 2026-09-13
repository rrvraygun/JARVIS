#!/usr/bin/env python3
"""Adversarial tests for the fixture-only observation contract."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = LAB_ROOT / "scripts/observation_contract.py"
SPEC = importlib.util.spec_from_file_location("observation_contract", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

BROKER_PATH = LAB_ROOT / "scripts/observation_broker.py"
BROKER_SPEC = importlib.util.spec_from_file_location("observation_broker", BROKER_PATH)
assert BROKER_SPEC and BROKER_SPEC.loader
BROKER = importlib.util.module_from_spec(BROKER_SPEC)
import sys

sys.modules["observation_contract"] = MODULE
BROKER_SPEC.loader.exec_module(BROKER)

STORE_PATH = LAB_ROOT / "scripts/restricted_fact_store.py"
STORE_SPEC = importlib.util.spec_from_file_location("restricted_fact_store", STORE_PATH)
assert STORE_SPEC and STORE_SPEC.loader
STORE = importlib.util.module_from_spec(STORE_SPEC)
sys.modules["restricted_fact_store"] = STORE
STORE_SPEC.loader.exec_module(STORE)


class ObservationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry, cls.policy = MODULE.validate_contract()
        cls.request = MODULE.load_json(MODULE.FILES["request"])

    def test_expected_simulation_is_exact_and_has_no_host_claim(self) -> None:
        result = MODULE.simulate(copy.deepcopy(self.request), self.registry, self.policy)
        expected = MODULE.load_json(MODULE.FILES["response"])
        self.assertEqual(result, expected)
        self.assertFalse(result["execution_performed"])
        self.assertFalse(result["host_observed"])
        self.assertFalse(result["effect_occurred"])
        self.assertFalse(result["persistence_performed"])
        self.assertTrue(all(item["synthetic"] for item in result["candidate_facts"]))

    def test_all_adapters_are_tier_zero_parser_only(self) -> None:
        for adapter in self.registry["adapters"]:
            self.assertEqual(adapter["maturity_level"], 1)
            self.assertFalse(adapter["execution_enabled"])
            self.assertEqual(
                adapter["risk"],
                {
                    "tier": 0,
                    "privilege": False,
                    "network": False,
                    "mutation": False,
                    "device_wake": False,
                },
            )
            self.assertEqual(adapter["bounds"]["attempt_limit"], 1)

    def test_live_state_is_read_only_tier_zero(self) -> None:
        self.assertEqual(self.registry["implementation_status"], "tier0_live_read_enabled")
        self.assertTrue(self.registry["host_observation_enabled"])
        self.assertFalse(self.registry["execution_enabled"])
        self.assertFalse(self.policy["persistence_enabled"])
        self.assertFalse(self.policy["mutation_enabled"])

    def test_parser_module_has_no_operational_imports(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(
            imported.isdisjoint(
                {
                    "asyncio",
                    "ctypes",
                    "libvirt",
                    "os",
                    "pty",
                    "requests",
                    "shlex",
                    "socket",
                    "subprocess",
                    "urllib",
                }
            )
        )

    def test_request_rejects_unknown_fields_and_parameters(self) -> None:
        for mutation in (
            lambda request: request.update({"host_path": "/etc/os-release"}),
            lambda request: request["parameters"].update({"anything": "value"}),
            lambda request: request["adapters"].append({"id": "unknown", "version": "1.0.0"}),
        ):
            request = copy.deepcopy(self.request)
            mutation(request)
            with self.assertRaises(MODULE.ObservationError):
                MODULE.validate_request(request, self.registry, self.policy)

    def test_request_rejects_digest_drift(self) -> None:
        request = copy.deepcopy(self.request)
        request["bindings"]["adapter_registry_sha256"] = "0" * 64
        with self.assertRaisesRegex(MODULE.ObservationError, "binding drift"):
            MODULE.validate_request(request, self.registry, self.policy)

    def test_request_replay_is_rejected(self) -> None:
        seen: set[str] = set()
        MODULE.simulate(
            copy.deepcopy(self.request),
            self.registry,
            self.policy,
            seen_request_ids=seen,
        )
        with self.assertRaisesRegex(MODULE.ObservationError, "replay"):
            MODULE.simulate(
                copy.deepcopy(self.request),
                self.registry,
                self.policy,
                seen_request_ids=seen,
            )

    def test_os_release_rejects_duplicate_and_active_syntax(self) -> None:
        duplicate = (
            "ID=fedora\nID=fedora\nVERSION_ID=44\nVARIANT_ID=workstation\nPRETTY_NAME=Fedora\n"
        )
        active = 'ID=fedora\nVERSION_ID=44\nVARIANT_ID=workstation\nPRETTY_NAME="$(bad)"\n'
        for text in (duplicate, active):
            with self.assertRaises(MODULE.ObservationError):
                MODULE.parse_os_release({"os_release": text})

    def test_terminal_controls_are_rejected(self) -> None:
        for text in ("safe\x1b[31m", "safe\x00bad", "safe\x7fbad"):
            with self.assertRaisesRegex(MODULE.ObservationError, "control character"):
                MODULE.reject_terminal_controls(text, "hostile")

    def test_kernel_identity_requires_exact_fields(self) -> None:
        payload = json.dumps(
            {"release": "6.0.fc44.x86_64", "machine": "x86_64", "serial": "secret"}
        )
        with self.assertRaisesRegex(MODULE.ObservationError, "unexpected or missing"):
            MODULE.parse_kernel_identity({"kernel_identity": payload})

    def test_cpu_topology_mismatch_and_duplicate_cpu_fields_fail(self) -> None:
        topology = json.dumps(
            {
                "architecture": "x86_64",
                "physical_core_count": 1,
                "logical_thread_count": 2,
            }
        )
        one_cpu = "processor : 0\nvendor_id : GenuineIntel\nmodel name : Synthetic\nflags : vmx\n"
        with self.assertRaisesRegex(MODULE.ObservationError, "logical count mismatch"):
            MODULE.parse_cpu_summary({"cpu_info": one_cpu, "cpu_topology": topology})
        duplicate = one_cpu + "processor : 1\n"
        with self.assertRaises(MODULE.ObservationError):
            MODULE.parse_cpu_summary({"cpu_info": duplicate, "cpu_topology": topology})

    def test_memory_rejects_duplicate_or_untyped_values(self) -> None:
        topology = json.dumps({"node_count": 1})
        for meminfo in ("MemTotal: 1 kB\nMemTotal: 2 kB\n", "MemTotal: unknown kB\n"):
            with self.assertRaises(MODULE.ObservationError):
                MODULE.parse_memory_summary({"memory_info": meminfo, "numa_topology": topology})

    def test_registry_fixture_references_remain_below_fixture_root(self) -> None:
        allowed = (LAB_ROOT / "fixtures/observations").resolve()
        for fixture_set in self.registry["fixture_sets"]:
            self.assertTrue(fixture_set["synthetic"])
            self.assertFalse(fixture_set["represents_host"])
            for reference in fixture_set["files"].values():
                self.assertTrue((LAB_ROOT / reference).resolve().is_relative_to(allowed))

    def test_typed_broker_prepares_and_simulates_minimal_tier0_scope(self) -> None:
        request = BROKER.prepare_minimal_request(
            "minimal-preview",
            "2099-01-01T00:00:00Z",
        )
        result = BROKER.simulate_minimal(request, seen_request_ids=set())
        self.assertEqual(result["status"], "fixture_simulated")
        self.assertFalse(result["host_observed"])
        self.assertEqual(len(result["candidate_facts"]), 14)

    def test_typed_broker_rejects_expiry_replay_and_live_mode(self) -> None:
        request = BROKER.prepare_minimal_request("expiry-preview", "2099-01-01T00:00:00Z")
        seen: set[str] = set()
        BROKER.simulate_minimal(request, seen_request_ids=seen)
        with self.assertRaisesRegex(MODULE.ObservationError, "replay"):
            BROKER.simulate_minimal(request, seen_request_ids=seen)
        with self.assertRaisesRegex(MODULE.ObservationError, "expired"):
            BROKER.simulate_minimal(
                request,
                now=__import__("datetime").datetime(
                    2100, 1, 1, tzinfo=__import__("datetime").timezone.utc
                ),
            )
        with self.assertRaisesRegex(MODULE.ObservationError, "live host observation"):
            BROKER.run_live()

    def test_restricted_store_keeps_candidates_ephemeral_until_attested_backend(
        self,
    ) -> None:
        store = STORE.EphemeralCandidateStore()
        store.add({"fact_id": "os.id", "value": "fedora", "synthetic": True})
        self.assertEqual(len(store.snapshot()), 1)
        self.assertEqual(
            STORE.persistence_status(),
            {"available": False, "reason": "encrypted_backend_not_supplied"},
        )

        class PlainBackend:
            encrypted_at_rest = False
            atomic_writes = True
            recovery_verified = True

            def put(self, fact: dict[str, object]) -> None:
                raise AssertionError("must not be called")

        with self.assertRaisesRegex(STORE.StorageGateError, "encrypted_at_rest"):
            store.persist(PlainBackend())

    def test_luks_backend_requires_explicit_unlock_and_recovery_attestation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.sqlite3"
            incomplete = STORE.StorageAttestation(
                attestation_id="unlock-1",
                canonical_path=str(path),
                owner_uid=os.getuid(),
                storage_class="luks-backed-local",
                mount_id=99,
                mount_source=f"{directory}|/dev/mapper/dm-0",
                dm_uuid="CRYPT-LUKS2-test",
                user_unlocked=False,
                encryption_verified=True,
                recovery_verified=True,
                recovery_evidence_sha256="a" * 64,
            )
            attestor = STORE.LuksStorageAttestor()
            with self.assertRaisesRegex(STORE.StorageGateError, "explicit user unlock"):
                STORE.LuksSqliteFactBackend(path, incomplete, self._scope(), attestor=attestor)

    def _attestor_and_attestation(self, directory: str, path: Path) -> tuple[object, object]:
        mountinfo = Path(directory) / "mountinfo"
        mountinfo.write_text(
            f"99 1 0:1 / {directory} rw,relatime - btrfs /dev/mapper/dm-0 rw\n",
            encoding="utf-8",
        )
        sysfs = Path(directory) / "sys"
        uuid_path = sysfs / "class" / "block" / "dm-0" / "dm"
        uuid_path.mkdir(parents=True)
        (uuid_path / "uuid").write_text("CRYPT-LUKS2-test\n", encoding="utf-8")
        attestor = STORE.LuksStorageAttestor(mountinfo_path=mountinfo, sysfs_root=sysfs)
        attestation = STORE.StorageAttestation(
            attestation_id="unlock-valid",
            canonical_path=str(path),
            owner_uid=os.getuid(),
            storage_class="luks-backed-local",
            mount_id=99,
            mount_source=f"{directory}|/dev/mapper/dm-0",
            dm_uuid="CRYPT-LUKS2-test",
            user_unlocked=True,
            encryption_verified=True,
            recovery_verified=True,
            recovery_evidence_sha256="b" * 64,
        )
        return attestor, attestation

    def _scope(self) -> object:
        return STORE.ApprovedFactScope(
            scope_id="test-scope-v1",
            proposal_digest="c" * 64,
            source_catalog_digest="d" * 64,
            entries=(
                STORE.FactScopeEntry(
                    adapter_id="fedora.platform.os-release",
                    adapter_version="1.0.0",
                    source_id="platform.os-release",
                    fact_ids=(
                        "platform.os",
                        "not-activated",
                        "nan",
                        "safe",
                        "rollback",
                    ),
                ),
            ),
        )

    def _binding(
        self,
        key: str = "idempotency-1",
        attestation: object | None = None,
        scope: object | None = None,
    ) -> object:
        selected_scope = scope or self._scope()
        return STORE.ObservationBinding(
            request_id=f"request-{key}",
            proposal_digest="c" * 64,
            source_catalog_digest="d" * 64,
            adapter_id="fedora.platform.os-release",
            adapter_version="1.0.0",
            attestation_digest=(
                STORE.storage_attestation_digest(attestation)
                if attestation is not None
                else "e" * 64
            ),
            scope_digest=STORE.fact_scope_digest(selected_scope),
            idempotency_key=key,
            expires_at="2099-01-01T00:00:00Z",
        )

    def test_luks_backend_writes_canonical_facts_transactionally(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.sqlite3"
            attestor, attestation = self._attestor_and_attestation(directory, path)
            backend = STORE.LuksSqliteFactBackend(
                path, attestation, self._scope(), attestor=attestor
            )
            try:
                store = STORE.EphemeralCandidateStore()
                store.add(
                    {
                        "fact_id": "platform.os",
                        "source_id": "platform.os-release",
                        "value": "fedora",
                        "synthetic": True,
                    }
                )
                binding = self._binding(attestation=attestation)
                backend.consume_activation(binding)
                store.persist(backend, binding)
                self.assertEqual(STORE.persistence_status(backend)["available"], True)
                self.assertEqual(backend.verify_integrity(), 1)
            finally:
                backend.close()
            connection = sqlite3.connect(path)
            try:
                row = connection.execute(
                    "SELECT fact_id, payload_json, payload_sha256, request_id, proposal_digest FROM restricted_facts"
                ).fetchone()
            finally:
                connection.close()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "platform.os")
            self.assertIn('"synthetic":true', row[1])
            self.assertEqual(len(row[2]), 64)
            self.assertEqual(row[3], "request-idempotency-1")
            self.assertEqual(row[4], "c" * 64)

    def test_luks_backend_rejects_replay_and_unconsumed_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.sqlite3"
            attestor, attestation = self._attestor_and_attestation(directory, path)
            backend = STORE.LuksSqliteFactBackend(
                path, attestation, self._scope(), attestor=attestor
            )
            try:
                binding = self._binding("replay-1", attestation)
                backend.consume_activation(binding)
                with self.assertRaisesRegex(STORE.StorageGateError, "replay"):
                    backend.consume_activation(binding)
                with self.assertRaisesRegex(STORE.StorageGateError, "not durably consumed"):
                    backend.put(
                        {
                            "fact_id": "not-activated",
                            "source_id": "platform.os-release",
                            "value": True,
                        },
                        self._binding("never-consumed", attestation),
                    )
            finally:
                backend.close()

    def test_luks_backend_rejects_tampered_payload_and_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.sqlite3"
            attestor, attestation = self._attestor_and_attestation(directory, path)
            backend = STORE.LuksSqliteFactBackend(
                path, attestation, self._scope(), attestor=attestor
            )
            try:
                binding = self._binding("tamper-1", attestation)
                backend.consume_activation(binding)
                with self.assertRaisesRegex(STORE.StorageGateError, "canonical JSON"):
                    backend.put(
                        {
                            "fact_id": "nan",
                            "source_id": "platform.os-release",
                            "value": float("nan"),
                        },
                        binding,
                    )
                backend.put(
                    {
                        "fact_id": "safe",
                        "source_id": "platform.os-release",
                        "value": "ok",
                    },
                    binding,
                )
                backend._connection.execute(
                    "UPDATE restricted_facts SET payload_json = ? WHERE fact_id = ?",
                    ('{"fact_id":"safe","value":"tampered"}', "safe"),
                )
                backend._connection.commit()
                with self.assertRaisesRegex(STORE.StorageGateError, "hash mismatch"):
                    backend.verify_integrity()
            finally:
                backend.close()

    def test_luks_backend_binds_attestation_digest_and_rejects_after_restart(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.sqlite3"
            attestor, attestation = self._attestor_and_attestation(directory, path)
            backend = STORE.LuksSqliteFactBackend(
                path, attestation, self._scope(), attestor=attestor
            )
            try:
                wrong = self._binding("digest-wrong")
                with self.assertRaisesRegex(STORE.StorageGateError, "attestation digest mismatch"):
                    backend.consume_activation(wrong)
                binding = self._binding("restart-1", attestation)
                backend.consume_activation(binding)
                self.assertEqual(
                    backend._connection.execute("PRAGMA journal_mode").fetchone(),
                    ("delete",),
                )
                self.assertEqual(backend._connection.execute("PRAGMA synchronous").fetchone(), (2,))
            finally:
                backend.close()

            reopened = STORE.LuksSqliteFactBackend(
                path, attestation, self._scope(), attestor=attestor
            )
            try:
                with self.assertRaisesRegex(STORE.StorageGateError, "replay"):
                    reopened.consume_activation(binding)
            finally:
                reopened.close()

    def test_luks_backend_rolls_back_failed_insert_and_rejects_corrupt_database(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.sqlite3"
            attestor, attestation = self._attestor_and_attestation(directory, path)
            backend = STORE.LuksSqliteFactBackend(
                path, attestation, self._scope(), attestor=attestor
            )
            try:
                binding = self._binding("rollback-1", attestation)
                backend.consume_activation(binding)
                backend._connection.execute(
                    "CREATE TRIGGER reject_fact BEFORE INSERT ON restricted_facts BEGIN SELECT RAISE(ABORT, 'injected failure'); END;"
                )
                backend._connection.commit()
                with self.assertRaisesRegex(STORE.StorageGateError, "atomic write failed"):
                    backend.put(
                        {
                            "fact_id": "rollback",
                            "source_id": "platform.os-release",
                            "value": True,
                        },
                        binding,
                    )
                self.assertEqual(
                    backend._connection.execute("SELECT COUNT(*) FROM restricted_facts").fetchone(),
                    (0,),
                )
            finally:
                backend.close()

            path.write_bytes(b"not a sqlite database")
            with self.assertRaisesRegex(STORE.StorageGateError, "initialization failed"):
                STORE.LuksSqliteFactBackend(path, attestation, self._scope(), attestor=attestor)

    def test_luks_attestor_rejects_mount_identity_drift_and_unsafe_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.sqlite3"
            attestor, attestation = self._attestor_and_attestation(directory, path)
            Path(directory, "mountinfo").write_text(
                f"100 1 0:1 / {directory} rw,relatime - btrfs /dev/mapper/other rw\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                STORE.StorageGateError, "mount identity changed|mount source changed"
            ):
                STORE.LuksSqliteFactBackend(path, attestation, self._scope(), attestor=attestor)

        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "open-parent"
            parent.mkdir(mode=0o755)
            path = parent / "facts.sqlite3"
            attestor, attestation = self._attestor_and_attestation(directory, path)
            with self.assertRaisesRegex(STORE.StorageGateError, "owner-controlled"):
                STORE.LuksSqliteFactBackend(path, attestation, self._scope(), attestor=attestor)

    def test_luks_backend_enforces_approved_fact_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "facts.sqlite3"
            attestor, attestation = self._attestor_and_attestation(directory, path)
            backend = STORE.LuksSqliteFactBackend(
                path, attestation, self._scope(), attestor=attestor
            )
            try:
                binding = self._binding("scope-1", attestation)
                backend.consume_activation(binding)
                with self.assertRaisesRegex(
                    STORE.StorageGateError, "outside the approved adapter scope"
                ):
                    backend.put(
                        {
                            "fact_id": "not-approved",
                            "source_id": "platform.os-release",
                            "value": True,
                        },
                        binding,
                    )
                with self.assertRaisesRegex(
                    STORE.StorageGateError, "outside the approved adapter scope"
                ):
                    backend.put(
                        {
                            "fact_id": "safe",
                            "source_id": "different-source",
                            "value": True,
                        },
                        binding,
                    )
                wrong_scope = STORE.ApprovedFactScope(
                    scope_id="different-scope",
                    proposal_digest="c" * 64,
                    source_catalog_digest="d" * 64,
                    entries=self._scope().entries,
                )
                with self.assertRaisesRegex(STORE.StorageGateError, "scope digest mismatch"):
                    backend.consume_activation(self._binding("scope-2", attestation, wrong_scope))
            finally:
                backend.close()


if __name__ == "__main__":
    unittest.main()
