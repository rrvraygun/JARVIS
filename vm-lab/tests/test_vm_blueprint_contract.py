#!/usr/bin/env python3
"""Tests for the non-operational full Fedora Workstation VM blueprint."""

from __future__ import annotations

import ast
import copy
import importlib.util
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = LAB_ROOT / "scripts/vm_blueprint_contract.py"
SPEC = importlib.util.spec_from_file_location("vm_blueprint_contract", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VMBlueprintContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.blueprint = MODULE.load(MODULE.FILES["blueprint"])
        cls.gates = MODULE.load(MODULE.FILES["gates"])
        cls.readiness = MODULE.load(MODULE.FILES["readiness"])
        cls.sources = MODULE.load(MODULE.FILES["sources"])
        cls.image_lock = MODULE.load(MODULE.FILES["image_lock"])

    def test_complete_contract_is_valid_and_non_operational(self) -> None:
        report = MODULE.validate_all()
        self.assertEqual(report["status"], "valid")
        self.assertFalse(report["execution_performed"])
        self.assertFalse(report["host_observed"])
        self.assertFalse(report["vm_exists"])
        self.assertEqual(report["boot_profiles"], 2)
        self.assertEqual(report["readiness_checks"], 18)
        self.assertEqual(report["provisioning_gates"], 8)

    def test_headless_profile_cannot_become_reduced_guest(self) -> None:
        blueprint = copy.deepcopy(self.blueprint)
        blueprint["boot_profiles"][0]["installed_payload"] = "server_minimal"
        with self.assertRaisesRegex(MODULE.BlueprintError, "reduced guest"):
            MODULE.validate_blueprint(blueprint, self.image_lock)

    def test_graphical_and_headless_profiles_remain_distinct(self) -> None:
        blueprint = copy.deepcopy(self.blueprint)
        blueprint["boot_profiles"][1]["boot_goal"] = "multi_user"
        with self.assertRaisesRegex(MODULE.BlueprintError, "graphical profile"):
            MODULE.validate_blueprint(blueprint, self.image_lock)

    def test_passthrough_network_shares_and_model_shell_are_rejected(self) -> None:
        mutations = (
            lambda value: value["virtual_hardware"].update({"physical_GPU_passthrough": True}),
            lambda value: value["isolation"].update({"runtime_network": "default_nat"}),
            lambda value: value["isolation"].update({"host_filesystem_shares": "home"}),
            lambda value: value["control_and_evidence"].update(
                {"arbitrary_shell_from_model": True}
            ),
        )
        for mutation in mutations:
            blueprint = copy.deepcopy(self.blueprint)
            mutation(blueprint)
            with self.assertRaises(MODULE.BlueprintError):
                MODULE.validate_blueprint(blueprint, self.image_lock)

    def test_resources_cannot_be_guessed_before_readiness(self) -> None:
        blueprint = copy.deepcopy(self.blueprint)
        blueprint["resource_policy"]["selected_vcpus"] = 8
        with self.assertRaisesRegex(MODULE.BlueprintError, "was guessed"):
            MODULE.validate_blueprint(blueprint, self.image_lock)

    def test_readiness_plan_cannot_claim_adapter_or_scan(self) -> None:
        for mutation in (
            lambda value: value.update({"host_scan_performed": True}),
            lambda value: value.update({"live_observation_backend_complete": True}),
            lambda value: value["checks"][0].update({"live_backend_implemented": True}),
            lambda value: value["authority"].update({"network": True}),
        ):
            readiness = copy.deepcopy(self.readiness)
            mutation(readiness)
            with self.assertRaises(MODULE.BlueprintError):
                MODULE.validate_readiness(readiness, self.sources)

    def test_readiness_uses_only_declared_nonmutating_sources(self) -> None:
        source_index = {item["id"]: item for item in self.sources["sources"]}
        for check in self.readiness["checks"]:
            source = source_index[check["source_id"]]
            self.assertFalse(source["network"])
            self.assertFalse(source["mutation"])
            self.assertIn(source["potential_effect"], {"none", "none_expected"})

    def test_p0_complete_and_p1_requires_user_authorization(self) -> None:
        self.assertEqual(self.gates["gates"][0]["current_status"], "completed")
        self.assertEqual(
            self.gates["gates"][1]["current_status"],
            "next_blocked_on_user_authorization",
        )
        self.assertTrue(
            all(item["current_status"] == "blocked" for item in self.gates["gates"][2:])
        )
        gates = copy.deepcopy(self.gates)
        gates["gates"][3]["current_status"] = "next"
        with self.assertRaisesRegex(MODULE.BlueprintError, "downstream gate"):
            MODULE.validate_gates(gates)

    def test_machine_assets_have_no_executable_interface_keys(self) -> None:
        for label, value in (
            ("blueprint", self.blueprint),
            ("gates", self.gates),
            ("readiness", self.readiness),
        ):
            MODULE.reject_executable_fields(label, value)

    def test_validator_has_no_operational_imports(self) -> None:
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
                    "socket",
                    "subprocess",
                    "urllib",
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
