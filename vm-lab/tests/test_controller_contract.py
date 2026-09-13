#!/usr/bin/env python3
from __future__ import annotations

import ast
import copy
import importlib.util
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = LAB_ROOT / "scripts/controller_contract.py"
SPEC = importlib.util.spec_from_file_location("jarvis_controller_contract", SCRIPT)
assert SPEC and SPEC.loader
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)


class ControllerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.values = {
            name: contract.load(relative, LAB_ROOT) for name, relative in contract.FILES.items()
        }
        cls.result = contract.validate_all(LAB_ROOT)
        cls.states = contract.validate_state_machine(cls.values["state_machine"])
        cls.operations = contract.validate_operations(cls.values["operations"], cls.states)
        cls.sources = contract.validate_sources(cls.values["sources"])
        cls.source_catalog_digest = contract.file_digest(contract.FILES["sources"], LAB_ROOT)

    def new_simulator(self) -> object:
        return contract.ContractSimulator(
            self.operations,
            contract.file_digest(contract.FILES["policy"], LAB_ROOT),
            contract.file_digest(contract.FILES["proposal"], LAB_ROOT),
        )

    def test_contract_is_valid_and_h1_read_authority_is_narrow(self) -> None:
        self.assertTrue(self.result["valid"])
        self.assertTrue(self.result["operational_authority"])
        self.assertTrue(self.result["vm_controller_service_exists"])
        self.assertEqual(self.result["operations_executable"], 0)

    def test_enrollment_is_field_level_and_currently_disabled(self) -> None:
        enrollment = self.result["enrollment"]
        self.assertEqual(enrollment["sources"], 32)
        self.assertEqual(enrollment["groups"], 12)
        self.assertEqual(enrollment["facts"], 90)
        proposal = self.values["proposal"]
        self.assertFalse(proposal["execution_enabled"])
        self.assertFalse(proposal["approval_granted"])
        self.assertFalse(proposal["host_scan_performed"])
        self.assertIsNone(proposal["host_binding"])
        self.assertTrue(all(not group["current_enabled"] for group in proposal["groups"]))
        review = self.values["review"]
        self.assertEqual(review["status"], "pending")
        self.assertIsNone(review["decision"])
        self.assertEqual(review["current_authority"], "none")
        self.assertEqual(review["activated_tiers"], [])

    def test_controller_script_has_no_operational_import(self) -> None:
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        forbidden = {
            "asyncio",
            "libvirt",
            "os",
            "pty",
            "requests",
            "shlex",
            "socket",
            "subprocess",
            "urllib",
        }
        self.assertFalse(imported.intersection(forbidden))

    def test_every_future_operation_is_disabled(self) -> None:
        for operation in self.operations.values():
            self.assertFalse(operation["execution_enabled"])
        simulation = [
            operation
            for operation in self.operations.values()
            if operation["availability"] == "contract_simulation_only"
        ]
        self.assertEqual([item["id"] for item in simulation], ["profile.enrollment.prepare"])
        self.assertEqual(simulation[0]["effect_class"], "none")

    def test_every_observation_source_is_read_only_and_offline(self) -> None:
        for source in self.sources.values():
            self.assertFalse(source["network"])
            self.assertFalse(source["mutation"])
            self.assertTrue(source["future_adapter_required"])

    def test_tier_zero_contains_no_possible_effect_source(self) -> None:
        proposal = self.values["proposal"]
        tier_zero = [group for group in proposal["groups"] if group["tier"] == 0]
        self.assertTrue(tier_zero)
        for group in tier_zero:
            effects = {self.sources[item]["potential_effect"] for item in group["source_ids"]}
            self.assertEqual(effects, {"none"})

    def test_protected_and_device_waking_sources_are_per_probe(self) -> None:
        proposal = self.values["proposal"]
        tier_two = [group for group in proposal["groups"] if group["tier"] == 2]
        self.assertEqual(len(tier_two), 1)
        self.assertEqual(tier_two[0]["future_admission"], "per_probe_confirmation")
        effects = {self.sources[item]["potential_effect"] for item in tier_two[0]["source_ids"]}
        self.assertIn("protected_access", effects)
        self.assertIn("may_wake_device", effects)

    def test_virtualization_readiness_is_a_separate_l2_group(self) -> None:
        proposal = self.values["proposal"]
        l2 = [group for group in proposal["groups"] if group["phase"] == "L2"]
        self.assertEqual([group["id"] for group in l2], ["virtualization-readiness"])
        self.assertFalse(l2[0]["current_enabled"])
        self.assertTrue(proposal["completion_gate"]["L2_not_automatically_started"])

    def test_fixture_transition_has_no_effect_and_is_one_use(self) -> None:
        simulator = self.new_simulator()
        response = simulator.validate_request(copy.deepcopy(self.values["request"]))
        self.assertEqual(response, self.values["response"])
        self.assertFalse(response["effect_occurred"])
        with self.assertRaises(contract.ContractError):
            simulator.validate_request(copy.deepcopy(self.values["request"]))

    def test_rejects_unimplemented_operational_request(self) -> None:
        request = copy.deepcopy(self.values["request"])
        request["operation_id"] = "scenario.start"
        request["operation_revision"] = "1.0.0"
        with self.assertRaises(contract.ContractError):
            self.new_simulator().validate_request(request)

    def test_rejects_unknown_parameter_or_executable_field(self) -> None:
        request = copy.deepcopy(self.values["request"])
        request["parameters"]["unexpected"] = True
        with self.assertRaises(contract.ContractError):
            self.new_simulator().validate_request(request)
        with self.assertRaises(contract.ContractError):
            contract.reject_executable_fields("adversarial", {"nested": {"command": "do-not-run"}})

    def test_rejects_policy_or_proposal_digest_drift(self) -> None:
        request = copy.deepcopy(self.values["request"])
        request["identity_bindings"]["policy_digest"] = "0" * 64
        with self.assertRaises(contract.ContractError):
            self.new_simulator().validate_request(request)
        request = copy.deepcopy(self.values["request"])
        request["identity_bindings"]["proposal_digest"] = "0" * 64
        with self.assertRaises(contract.ContractError):
            self.new_simulator().validate_request(request)

    def test_rejects_false_host_scan_or_approval(self) -> None:
        proposal = copy.deepcopy(self.values["proposal"])
        proposal["host_scan_performed"] = True
        with self.assertRaises(contract.ContractError):
            contract.validate_proposal(proposal, self.sources, self.source_catalog_digest)
        proposal = copy.deepcopy(self.values["proposal"])
        proposal["approval_granted"] = True
        with self.assertRaises(contract.ContractError):
            contract.validate_proposal(proposal, self.sources, self.source_catalog_digest)

    def test_rejects_device_waking_source_in_tier_zero(self) -> None:
        proposal = copy.deepcopy(self.values["proposal"])
        group = next(item for item in proposal["groups"] if item["tier"] == 0)
        group["source_ids"].append("graphics.gpu-runtime-power")
        group["facts"].append(
            {
                "id": "adversarial.device_wake",
                "type": "string",
                "source_id": "graphics.gpu-runtime-power",
                "required": False,
                "transform": "state_only",
            }
        )
        with self.assertRaises(contract.ContractError):
            contract.validate_proposal(proposal, self.sources, self.source_catalog_digest)

    def test_rejects_source_catalog_digest_drift(self) -> None:
        proposal = copy.deepcopy(self.values["proposal"])
        proposal["source_catalog_binding"]["sha256"] = "0" * 64
        with self.assertRaises(contract.ContractError):
            contract.validate_proposal(proposal, self.sources, self.source_catalog_digest)

    def test_rejects_expiry_broadening(self) -> None:
        request = copy.deepcopy(self.values["request"])
        request["expires_at"] = "2026-08-06T13:00:00Z"
        with self.assertRaises(contract.ContractError):
            self.new_simulator().validate_request(request)


if __name__ == "__main__":
    unittest.main()
