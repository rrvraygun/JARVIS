#!/usr/bin/env python3
"""Adversarial tests for the prepared Fedora R2 recovery-set plan."""

from __future__ import annotations

import ast
import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "deployment/host/validate_recovery_set.py"
SPEC = importlib.util.spec_from_file_location("validate_recovery_set", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RecoverySetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = MODULE.load()

    def test_prepared_plan_is_valid_but_not_executed(self) -> None:
        report = MODULE.validate(copy.deepcopy(self.plan))
        self.assertEqual(report["boundaries"], 5)
        self.assertEqual(
            report["current_claim"],
            "minimal-restic-mechanism-verified-system-set-not-created",
        )

    def test_missing_boundary_is_rejected(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["boundaries"].pop()
        with self.assertRaisesRegex(MODULE.RecoverySetError, "boundary"):
            MODULE.validate(plan)

    def test_cross_subvolume_atomicity_cannot_be_claimed(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["consistency_model"]["cross_subvolume_atomicity"] = True
        with self.assertRaisesRegex(MODULE.RecoverySetError, "atomicity"):
            MODULE.validate(plan)

    def test_unencrypted_repository_is_rejected(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["repository"]["encryption_initialized"] = False
        with self.assertRaisesRegex(MODULE.RecoverySetError, "encryption"):
            MODULE.validate(plan)

    def test_password_file_cannot_replace_interactive_handling(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["repository"]["password_handling"] = "password-file"
        with self.assertRaisesRegex(MODULE.RecoverySetError, "password"):
            MODULE.validate(plan)

    def test_system_artifact_cannot_be_claimed_before_execution(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["repository"]["system_recovery_set_present"] = True
        with self.assertRaisesRegex(MODULE.RecoverySetError, "falsely claimed"):
            MODULE.validate(plan)

    def test_required_exclusions_cannot_be_removed(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["explicit_exclusions"].remove("LUKS header and recovery material")
        with self.assertRaisesRegex(MODULE.RecoverySetError, "exclusion"):
            MODULE.validate(plan)

    def test_automatic_retry_or_rollback_is_rejected(self) -> None:
        for key in ("automatic_retry", "automatic_rollback"):
            plan = copy.deepcopy(self.plan)
            plan["approval_policy"][key] = True
            with self.assertRaisesRegex(MODULE.RecoverySetError, "automation"):
                MODULE.validate(plan)

    def test_full_restore_cannot_be_marked_passed(self) -> None:
        plan = copy.deepcopy(self.plan)
        proof = next(
            item
            for item in plan["proof_matrix"]
            if item["id"] == "full-restore-to-nonproduction-target"
        )
        proof["status"] = "passed"
        with self.assertRaisesRegex(MODULE.RecoverySetError, "full restore"):
            MODULE.validate(plan)

    def test_a3_floor_cannot_be_opened(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["claims"]["r2_sufficient_for_a3"] = True
        with self.assertRaisesRegex(MODULE.RecoverySetError, "falsely claimed"):
            MODULE.validate(plan)

    def test_validator_has_no_operational_imports(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(
            imported.isdisjoint({"os", "subprocess", "shlex", "socket", "requests", "ctypes"})
        )


if __name__ == "__main__":
    unittest.main()
