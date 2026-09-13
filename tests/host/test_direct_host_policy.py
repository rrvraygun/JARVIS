#!/usr/bin/env python3
"""Adversarial tests for the static direct-host deployment policy."""

from __future__ import annotations

import ast
import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "deployment/host/validate_policy.py"
SPEC = importlib.util.spec_from_file_location("validate_host_policy", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DirectHostPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = MODULE.load()

    def test_policy_is_fixture_only_and_unenrolled(self) -> None:
        report = MODULE.validate(copy.deepcopy(self.policy))
        self.assertEqual(report["current_mode"], "fixture")
        self.assertFalse(report["host_observed"])
        self.assertFalse(report["mutation_performed"])
        self.assertEqual(report["next_gate"], "H1_bounded_read_only_enrollment")

    def test_any_current_authority_is_rejected(self) -> None:
        for key in self.policy["current_authority"]:
            policy = copy.deepcopy(self.policy)
            policy["current_authority"][key] = True
            with self.assertRaisesRegex(MODULE.HostPolicyError, "authority"):
                MODULE.validate(policy)

    def test_vm_cannot_be_promoted_to_physical_proof(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["laboratory_relationship"]["vm_success_proves_physical_hardware_behavior"] = True
        with self.assertRaisesRegex(MODULE.HostPolicyError, "VM overclaim"):
            MODULE.validate(policy)

    def test_local_snapshot_cannot_be_called_backup(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["backend_selection"]["same_device_snapshot_is_backup"] = True
        with self.assertRaisesRegex(MODULE.HostPolicyError, "mislabeled backup"):
            MODULE.validate(policy)

    def test_default_fedora_layout_cannot_be_assumed(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["backend_selection"]["never_assume_default_fedora_layout"] = False
        with self.assertRaisesRegex(MODULE.HostPolicyError, "layout assumed"):
            MODULE.validate(policy)

    def test_recovery_floor_cannot_be_weakened(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["action_classes"][3]["minimum_recovery_level"] = "R1_local_filesystem_snapshot"
        with self.assertRaisesRegex(MODULE.HostPolicyError, "recovery floors"):
            MODULE.validate(policy)

    def test_never_positive_action_cannot_be_approved(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["action_classes"][-1]["approval"] = "per_command"
        with self.assertRaisesRegex(MODULE.HostPolicyError, "never-positive"):
            MODULE.validate(policy)

    def test_automatic_retry_and_rollback_are_rejected(self) -> None:
        for key in ("automatic_retry", "automatic_rollback"):
            policy = copy.deepcopy(self.policy)
            policy["transaction_invariants"][key] = True
            with self.assertRaises(MODULE.HostPolicyError):
                MODULE.validate(policy)

    def test_downstream_gate_cannot_open(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["gates"][4]["status"] = "complete"
        with self.assertRaisesRegex(MODULE.HostPolicyError, "downstream"):
            MODULE.validate(policy)

    def test_executable_interface_field_is_rejected(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["command"] = "anything"
        with self.assertRaisesRegex(MODULE.HostPolicyError, "executable field"):
            MODULE.validate(policy)

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
                    "shlex",
                    "socket",
                    "subprocess",
                    "urllib",
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
