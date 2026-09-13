from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import h1_activation_contract as H1


class H1ActivationContractTests(unittest.TestCase):
    def test_current_runtime_contract_is_valid_without_new_activation(self) -> None:
        result = H1.validate_current_runtime(Path(__file__).resolve().parents[1])
        self.assertEqual(result, {"status": "valid_h1_runtime", "host_activation_performed": True})

    def test_policy_rejects_privilege_or_persistence(self) -> None:
        root = Path(__file__).resolve().parents[1]
        policy = H1._load(root / "controller" / "h1-promotion-policy.template.json")
        policy["privilege_enabled"] = True
        with self.assertRaisesRegex(H1.H1ContractError, "forbidden capability"):
            H1.validate_policy(policy)
        policy["privilege_enabled"] = False
        policy["persistence_enabled"] = True
        with self.assertRaisesRegex(H1.H1ContractError, "persistence"):
            H1.validate_policy(policy)

    def test_transport_rejects_network_or_broad_peer(self) -> None:
        root = Path(__file__).resolve().parents[1]
        transport = H1._load(root / "controller" / "private-transport.template.json")
        transport["network_listener"] = True
        with self.assertRaisesRegex(H1.H1ContractError, "network"):
            H1.validate_transport(transport)
        transport["network_listener"] = False
        transport["allowed_peer"] = "any-user"
        with self.assertRaisesRegex(H1.H1ContractError, "peer"):
            H1.validate_transport(transport)

    def test_transport_must_remain_prepared_and_unbound(self) -> None:
        root = Path(__file__).resolve().parents[1]
        transport = H1._load(root / "controller" / "private-transport.template.json")
        transport["status"] = "bound"
        with self.assertRaisesRegex(H1.H1ContractError, "installed or bound"):
            H1.validate_transport(transport)

    def test_current_policies_are_live_tier0_read_only(self) -> None:
        root = Path(__file__).resolve().parents[1]
        controller = H1._load(root / "controller" / "policy.json")
        broker = H1._load(root / "observation" / "broker-policy.json")
        H1.validate_current_controller_policy(controller)
        H1.validate_current_broker_policy(broker)

        controller["execution_enabled"] = True
        with self.assertRaisesRegex(H1.H1ContractError, "unsafe capability"):
            H1.validate_current_controller_policy(controller)
        broker["mutation_enabled"] = True
        with self.assertRaisesRegex(H1.H1ContractError, "unsafe capability"):
            H1.validate_current_broker_policy(broker)
        controller["execution_enabled"] = False
        controller["mutation_enabled"] = True
        with self.assertRaisesRegex(H1.H1ContractError, "unsafe capability"):
            H1.validate_current_controller_policy(controller)

    def test_identity_and_socket_bindings_are_exact(self) -> None:
        root = Path(__file__).resolve().parents[1]
        identity = H1._load(root / "controller" / "service-identity.template.json")
        transport = H1._load(root / "controller" / "private-transport.template.json")
        identity["user_binding"] = "any-user"
        with self.assertRaisesRegex(H1.H1ContractError, "user binding"):
            H1.validate_service_identity(identity)
        transport["socket_template"] = "/tmp/jarvis.sock"
        with self.assertRaisesRegex(H1.H1ContractError, "socket location"):
            H1.validate_transport(transport)
        transport["socket_template"] = "/run/user/%UID%/jarvis/jarvisd.sock"
        transport["protocol_version"] = "jarvis-control-v0"
        with self.assertRaisesRegex(H1.H1ContractError, "protocol"):
            H1.validate_transport(transport)

    def test_unexpected_contract_fields_are_rejected(self) -> None:
        root = Path(__file__).resolve().parents[1]
        policy = H1._load(root / "controller" / "h1-promotion-policy.template.json")
        identity = H1._load(root / "controller" / "service-identity.template.json")
        transport = H1._load(root / "controller" / "private-transport.template.json")
        policy["unexpected_execution_directive"] = "forbidden"
        with self.assertRaisesRegex(H1.H1ContractError, "policy fields"):
            H1.validate_policy(policy)
        identity["unexpected_write_path"] = "/tmp"
        with self.assertRaisesRegex(H1.H1ContractError, "identity fields"):
            H1.validate_service_identity(identity)
        identity.pop("unexpected_write_path")
        identity["allowed_read_interfaces"].append("/etc/shadow")
        with self.assertRaisesRegex(H1.H1ContractError, "read-interface"):
            H1.validate_service_identity(identity)
        transport["unexpected_retry"] = True
        with self.assertRaisesRegex(H1.H1ContractError, "transport fields"):
            H1.validate_transport(transport)

    def test_trusted_artifact_digests_are_pinned(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(
            H1._sha256(
                root.parent / "runtime" / "reports" / "2026-08-07-h1-user-decision-packet.json"
            ),
            H1.TRUSTED_USER_DECISION_PACKET_SHA256,
        )
        self.assertEqual(
            H1._sha256(root / "controller" / "policy.json"),
            H1.TRUSTED_CURRENT_CONTROLLER_POLICY_SHA256,
        )
        self.assertEqual(
            H1._sha256(root / "observation" / "broker-policy.json"),
            H1.TRUSTED_CURRENT_BROKER_POLICY_SHA256,
        )
        self.assertEqual(
            H1._sha256(root / "scripts" / "jarvisd_service.py"),
            H1.TRUSTED_SERVICE_SHA256,
        )
        self.assertEqual(
            H1._sha256(root / "controller" / "jarvisd.service.template"),
            H1.TRUSTED_UNIT_SHA256,
        )
        for filename, digest in H1.TRUSTED_RUNTIME_DEPENDENCY_SHA256.items():
            self.assertEqual(H1._sha256(root / "scripts" / filename), digest)

    def test_runtime_dependency_drift_is_rejected(self) -> None:
        root = Path(__file__).resolve().parents[1]
        original = H1.TRUSTED_RUNTIME_DEPENDENCY_SHA256["live_tier0_observation.py"]
        H1.TRUSTED_RUNTIME_DEPENDENCY_SHA256["live_tier0_observation.py"] = "0" * 64
        try:
            with self.assertRaisesRegex(H1.H1ContractError, "runtime dependency artifact drift"):
                H1.validate_current_runtime(root)
        finally:
            H1.TRUSTED_RUNTIME_DEPENDENCY_SHA256["live_tier0_observation.py"] = original


if __name__ == "__main__":
    unittest.main()
