#!/usr/bin/env python3
"""Adversarial tests for fixture-only L2 readiness parsers."""

from __future__ import annotations

import ast
import importlib.util
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = LAB_ROOT / "scripts/readiness_contract.py"
SPEC = importlib.util.spec_from_file_location("readiness_contract", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReadinessContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry, cls.plan = MODULE.validate_contract()

    def test_all_eighteen_checks_are_bound_and_synthetic(self) -> None:
        response = MODULE.simulate(self.registry, self.plan)
        self.assertEqual(len(response["candidate_results"]), 18)
        self.assertEqual(
            {item["check_id"] for item in response["candidate_results"]},
            {item["id"] for item in self.plan["checks"]},
        )
        self.assertTrue(all(item["synthetic"] for item in response["candidate_results"]))

    def test_response_has_no_operational_or_host_claim(self) -> None:
        response = MODULE.simulate(self.registry, self.plan)
        self.assertFalse(response["execution_performed"])
        self.assertFalse(response["host_observed"])
        self.assertFalse(response["effect_occurred"])
        self.assertFalse(response["persistence_performed"])
        self.assertEqual(response["attempts"], 1)

    def test_registry_and_plan_have_no_live_backend(self) -> None:
        self.assertFalse(self.registry["execution_enabled"])
        self.assertFalse(self.registry["host_observation_enabled"])
        self.assertFalse(self.registry["live_backend_implemented"])
        self.assertFalse(self.plan["live_observation_backend_complete"])
        self.assertFalse(self.plan["host_scan_performed"])
        self.assertTrue(all(not check["live_backend_implemented"] for check in self.plan["checks"]))

    def test_all_new_parsers_are_tier_one_no_effect(self) -> None:
        for adapter in self.registry["adapters"]:
            self.assertEqual(adapter["maturity_level"], 1)
            self.assertFalse(adapter["execution_enabled"])
            self.assertEqual(
                adapter["risk"],
                {
                    "tier": 1,
                    "privilege": False,
                    "network": False,
                    "mutation": False,
                    "device_wake": False,
                },
            )
            self.assertEqual(adapter["bounds"]["attempt_limit"], 1)

    def test_virtualization_parser_rejects_extra_field(self) -> None:
        value = MODULE.load(self.registry["fixture_set"]["files"]["virtualization_summary"])
        value["guest_names"] = ["private"]
        with self.assertRaisesRegex(MODULE.ReadinessError, "unexpected or missing"):
            MODULE.parse_virtualization(value)

    def test_package_parser_rejects_untyped_or_active_version(self) -> None:
        for value in (
            {"status": "installed", "version": "$(bad)"},
            {"status": "absent", "version": "1.0"},
            {"status": "installed", "version": 10},
        ):
            with self.assertRaises(MODULE.ReadinessError):
                MODULE.parse_package(value, "package")

    def test_storage_parser_rejects_unknown_fields_and_values(self) -> None:
        for value in (
            {
                "capacity_class": "infinite",
                "filesystem_capability": "supports_sparse_qcow2_and_atomic_rename",
            },
            {
                "capacity_class": "meets_minimum",
                "filesystem_capability": "limited",
                "path": "/home/user",
            },
        ):
            with self.assertRaises(MODULE.ReadinessError):
                MODULE.parse_storage(value)

    def test_selinux_parser_rejects_hostile_policy_text(self) -> None:
        with self.assertRaises(MODULE.ReadinessError):
            MODULE.parse_selinux({"mode": "enforcing", "policy_class": "targeted\x1b[31m"})

    def test_terminal_controls_and_active_shell_syntax_are_rejected(self) -> None:
        for value in ({"x": "bad\x00value"}, {"x": "bad\x7fvalue"}, {"x": "$(bad)"}):
            with self.assertRaises(MODULE.ReadinessError):
                MODULE.reject_unsafe_text(value, "hostile")

    def test_fixture_references_are_confined(self) -> None:
        allowed = (LAB_ROOT / "fixtures/readiness").resolve()
        for reference in self.registry["fixture_set"]["files"].values():
            self.assertTrue((LAB_ROOT / reference).resolve().is_relative_to(allowed))

    def test_digest_bindings_are_exact(self) -> None:
        expected = {
            "source_catalog_sha256": MODULE.digest(MODULE.FILES["sources"]),
            "proposal_sha256": MODULE.digest(MODULE.FILES["proposal"]),
            "tier0_adapter_registry_sha256": MODULE.digest(MODULE.FILES["tier0_registry"]),
            "readiness_plan_sha256": MODULE.digest(MODULE.FILES["plan"]),
        }
        self.assertEqual(self.registry["bindings"], expected)

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


if __name__ == "__main__":
    unittest.main()
