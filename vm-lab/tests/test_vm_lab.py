#!/usr/bin/env python3
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = LAB_ROOT / "scripts/labctl.py"
SPEC = importlib.util.spec_from_file_location("jarvis_vm_labctl", SCRIPT)
assert SPEC and SPEC.loader
labctl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(labctl)


class VmLabContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validated = labctl.load_and_validate(LAB_ROOT)
        cls.report = labctl.build_coverage_report(cls.validated)

    def test_fixture_mode_has_no_operational_authority(self) -> None:
        policy = self.validated["loaded"]["policy/lab-policy.json"]
        self.assertEqual(policy["mode"], "fixture_only")
        self.assertTrue(policy["authority"])
        self.assertTrue(all(value is False for value in policy["authority"].values()))

    def test_labctl_has_no_process_network_or_virtualization_import(self) -> None:
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

    def test_machine_assets_expose_no_executable_interface_keys(self) -> None:
        for relative in labctl.MACHINE_FILES:
            payload = json.loads((LAB_ROOT / relative).read_text(encoding="utf-8"))
            keys = {key for _path, key in labctl.iter_keys(payload)}
            self.assertFalse(
                keys.intersection(labctl.FORBIDDEN_MACHINE_KEYS),
                msg=relative,
            )

    def test_system_twin_is_explicitly_unobserved(self) -> None:
        profile = self.validated["loaded"]["profiles/fedora-workstation-template.json"]
        self.assertEqual(profile["status"], "unobserved_template")
        self.assertFalse(profile["enrollment"]["host_scan_performed"])
        self.assertIsNone(profile["enrollment"]["host_binding"])
        self.assertEqual(
            profile["fidelity_layers"][-1]["current_evidence"],
            "unrepresentable_by_default_vm",
        )

    def test_image_and_guest_are_not_resolved_or_created(self) -> None:
        image = self.validated["loaded"]["images/fedora-workstation-image-lock.template.json"]
        self.assertEqual(image["status"], "unresolved")
        self.assertFalse(image["acquisition_enabled"])
        self.assertEqual(image["baseline"]["state"], "not_created")
        self.assertFalse(image["virtualization"]["device_passthrough"])

    def test_curated_regressions_all_match_their_oracles(self) -> None:
        results = self.validated["curated"]
        self.assertEqual(len(results), 37)
        self.assertTrue(all(item["passed"] for item in results))

    def test_declared_state_spaces_and_digests_are_pinned(self) -> None:
        reports = {item["matrix_id"]: item for item in self.report["matrices"]}
        self.assertEqual(reports["lighting-controls"]["evaluated_state_cases"], 64512)
        self.assertEqual(reports["lighting-controls"]["logical_declared_cases"], 258048)
        self.assertEqual(reports["sysadmin-control-plane"]["evaluated_state_cases"], 60480)
        self.assertEqual(reports["sysadmin-control-plane"]["logical_declared_cases"], 1028160)
        for report in reports.values():
            self.assertEqual(report["pair_coverage_percent"], 100)
            self.assertTrue(all(count > 0 for count in report["oracle_counts"].values()))
            self.assertRegex(report["state_space_digest"], r"^[a-f0-9]{64}$")

    def test_fixture_evidence_cannot_promote_past_stage_one(self) -> None:
        self.assertEqual(self.report["promotion_ceiling"], 1)
        self.assertEqual(self.report["physical_gaps_open"], 10)
        self.assertTrue(
            self.validated["loaded"]["policy/lab-policy.json"]["promotion_gates"][
                "stage_2_requires_real_disposable_guest"
            ]
        )

    def test_scope_excludes_gaming_and_networking_vpn(self) -> None:
        policy_scope = self.validated["loaded"]["policy/lab-policy.json"]["scope"]
        self.assertEqual(set(policy_scope["excluded_domains"]), {"gaming", "networking_vpn"})
        domains = self.validated["matrices"]["sysadmin-control-plane"]["context_dimensions"][
            "capability_domain"
        ]
        self.assertNotIn("gaming", domains)
        self.assertNotIn("networking_vpn", domains)

    def test_every_oracle_disables_automatic_retry(self) -> None:
        for matrix in self.validated["matrices"].values():
            for rule in matrix["oracle_rules"]:
                self.assertFalse(rule["expected"]["automatic_retry"])

    def test_rejects_any_operational_authority_activation(self) -> None:
        policy = copy.deepcopy(self.validated["loaded"]["policy/lab-policy.json"])
        policy["authority"]["guest_start_enabled"] = True
        with self.assertRaises(labctl.LabValidationError):
            labctl.validate_policy(policy)

    def test_rejects_false_host_enrollment(self) -> None:
        profile = copy.deepcopy(
            self.validated["loaded"]["profiles/fedora-workstation-template.json"]
        )
        profile["enrollment"]["host_scan_performed"] = True
        with self.assertRaises(labctl.LabValidationError):
            labctl.validate_profile(profile)

    def test_rejects_executable_interface_field(self) -> None:
        with self.assertRaises(labctl.LabValidationError):
            labctl.validate_machine_key_boundary(
                "adversarial.json", {"nested": {"argv": ["unsafe"]}}
            )

    def test_rejects_automatic_retry_oracle(self) -> None:
        matrix = copy.deepcopy(self.validated["matrices"]["sysadmin-control-plane"])
        matrix["oracle_rules"][-1]["expected"]["automatic_retry"] = True
        with self.assertRaises(labctl.LabValidationError):
            labctl.validate_matrix(matrix)

    def test_rejects_curated_oracle_drift(self) -> None:
        catalog = copy.deepcopy(self.validated["loaded"]["scenarios/catalog.json"])
        catalog["scenarios"][0]["expected_decision"] = "execute_anything"
        with self.assertRaises(labctl.LabValidationError):
            labctl.validate_curated_catalog(catalog, self.validated["matrices"])

    def test_rejects_coverage_digest_drift(self) -> None:
        expected = copy.deepcopy(self.validated["loaded"]["coverage/expected.json"])
        expected["matrices"][0]["state_space_digest"] = "0" * 64
        with self.assertRaises(labctl.LabValidationError):
            labctl.validate_coverage_expectations(
                expected,
                self.validated["matrix_reports"],
                len(self.validated["curated"]),
                self.validated["physical_count"],
            )


if __name__ == "__main__":
    unittest.main()
