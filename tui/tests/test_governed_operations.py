from __future__ import annotations

import dataclasses
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis_tui import private_records
from jarvis_tui.observation_safety import bounded_process, open_project, read_project_file
from jarvis_tui.operation_workflow import OperationWorkflow
from jarvis_tui.outcome_verification import verify
from jarvis_tui.specialists import Specialist
from jarvis_tui.terminal_safety import sanitize_and_redact_terminal_text
from jarvis_tui.tool_scope import allowed, publish

BUNDLE = Path(__file__).resolve().parents[2]


class GovernedOperationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir(mode=0o700)
        (self.project / "Cargo.toml").write_text('[package]\nname="demo"\nversion="0.1.0"\n')
        self.workflow = OperationWorkflow(self.root)

    def test_host_recovery_does_not_claim_original_unchanged(self):
        with patch.object(
            self.workflow,
            "load",
            return_value={"id": "fixture", "domain": "health", "operation": "restart"},
        ):
            result = self.workflow.recovery_proposal("fixture")
        self.assertFalse(result["original_unchanged_by_design"])
        self.assertFalse(result["execution_authorized"])
        self.assertIn("current target state", result["message"])

    def test_late_observation_cannot_unlock_new_turn(self):
        from jarvis_tui.tool_scope import generation, has_observation, note_observation

        spec = Specialist.from_mapping(
            json.loads((BUNDLE / "plugins/jarvis-system-health/specialist.json").read_text())
        )
        scope = "a" * 32
        publish(self.root, spec, "turn-a", scope)
        admitted = generation(self.root, scope)
        publish(self.root, spec, "turn-b", scope)
        with self.assertRaisesRegex(ValueError, "generation_changed"):
            note_observation(self.root, scope, "health_inventory", {}, expected_generation=admitted)
        self.assertFalse(has_observation(self.root, scope, "turn-b"))
        note_observation(
            self.root,
            scope,
            "health_inventory",
            {},
            expected_generation=generation(self.root, scope),
        )
        self.assertTrue(has_observation(self.root, scope, "turn-b"))

    def test_result_and_transcript_agree_on_verified_receipt(self):
        plan = self.workflow.propose(
            "development",
            "dependencies",
            str(self.project),
            {"files": {"Cargo.toml": '[package]\nname="new"\n'}},
        )
        report = {
            "id": plan["id"],
            "digest": plan["digest"],
            "verdict": "pass",
            "checks": {
                key: True for key in plan["postconditions"] if key != "independent_verifier"
            },
        }
        with (
            patch(
                "jarvis_tui.operation_workflow.bounded_process",
                return_value={"status": "completed", "output": json.dumps(report)},
            ),
            patch("jarvis_tui.operation_workflow.append_transcript") as transcript,
        ):
            result = self.workflow.execute(self.workflow.approve(plan["id"], plan["digest"]))
        self.assertTrue(result["verified"])
        self.assertTrue(self.workflow.result(plan["id"])["verified"])
        self.assertTrue(transcript.call_args.args[3]["verified"])

    def test_general_command_requires_exact_safe_argv(self):
        for argv in (
            "echo hi",
            ["python3", "-c", "print(1)"],
            ["/bin/sh", "-c", "true"],
            ["/usr/bin/python3", "\x00"],
        ):
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                self.workflow.propose("development", "command", str(self.project), {"argv": argv})
        plan = self.workflow.propose(
            "development",
            "command",
            str(self.project),
            {"argv": ["/usr/bin/python3", "-I", "-c", "print(2 + 2)"]},
        )
        self.assertEqual(plan["network"], "denied")
        self.assertIn("execution_settled", plan["postconditions"])
        self.assertIn("executable", plan)

    def test_pending_command_reservation_blocks_next_command(self):
        args = {"argv": ["/usr/bin/python3", "-I", "-c", "print(2 + 2)"]}
        first = self.workflow.propose("development", "command", str(self.project), args)
        private_records.write_once(
            self.workflow.root / "reservations", first["id"] + ".json", {"digest": first["digest"]}
        )
        second = self.workflow.propose("development", "command", str(self.project), args)
        with self.assertRaisesRegex(ValueError, "prior_command_outcome_pending"):
            self.workflow.approve(second["id"], second["digest"])

    def test_transcripts_remain_readable_for_seven_days(self):
        from jarvis_tui.transcript_store import append, read

        with patch("jarvis_tui.transcript_store.time.time", return_value=1000):
            identity = append(self.root, "operation_result", "fixture", {"status": "completed"})
        with patch("jarvis_tui.transcript_store.time.time", return_value=1000 + 6 * 86400):
            self.assertIn("payload", read(self.root, identity))
        with patch("jarvis_tui.transcript_store.time.time", return_value=1000 + 8 * 86400):
            self.assertEqual(read(self.root, identity)["status"], "expired")

    def test_concurrent_isolated_reservations_are_serialized(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor

        args = {"argv": ["/usr/bin/python3", "-I", "-c", "print(2 + 2)"]}
        plans = [
            self.workflow.propose("development", "command", str(self.project), args),
            self.workflow.propose("development", "check", str(self.project)),
        ]
        barrier = threading.Barrier(2)

        def reserve(plan):
            barrier.wait()
            try:
                OperationWorkflow(self.root)._reserve(plan)
                return "reserved"
            except ValueError as exc:
                return str(exc)

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(reserve, plans))
        self.assertCountEqual(results, ["reserved", "prior_command_outcome_pending"])

    def test_settlement_requires_empty_bound_cgroup(self):
        from jarvis_tui.isolated_execution import settled

        plan = {
            "id": "a" * 32,
            "digest": "b" * 64,
            "unit": "jarvis-build-" + "a" * 32,
            "settlement_version": 1,
        }
        group_name = "/app.slice/" + plan["unit"] + ".service"
        cgroups = self.root / "cgroups"
        group = cgroups / group_name.lstrip("/")
        group.mkdir(parents=True)
        info = group.stat()
        private_records.write_once(
            self.workflow.root / "launches", plan["id"] + ".json", {"digest": plan["digest"]}
        )
        private_records.write_once(
            self.workflow.root / "starts",
            plan["id"] + ".json",
            {
                "id": plan["id"],
                "digest": plan["digest"],
                "cgroup": group_name,
                "identity": [info.st_dev, info.st_ino],
                "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            },
        )
        (group / "cgroup.events").write_text("populated 1\nfrozen 0\n")
        self.assertFalse(settled(self.workflow.root, plan, cgroup_root=cgroups))
        (group / "cgroup.events").write_text("populated 0\nfrozen 0\n")
        self.assertTrue(settled(self.workflow.root, plan, cgroup_root=cgroups))

    def _verified_dependency_copy(self, files):
        plan = self.workflow.propose(
            "development", "dependencies", str(self.project), {"files": files}
        )

        def verifier(argv, **kwargs):
            return {"status": "completed", "output": json.dumps(verify(self.root, argv[-1]))}

        with patch("jarvis_tui.operation_workflow.bounded_process", side_effect=verifier):
            result = self.workflow.execute(self.workflow.approve(plan["id"], plan["digest"]))
        self.assertTrue(result["verified"])
        return plan

    def test_apply_dependency_copy_retains_original_and_verifies(self):
        os.setxattr(self.project / "Cargo.toml", "user.jarvis_fixture", b"preserve-this-attribute")
        before = (self.project / "Cargo.toml").read_bytes()
        source = self._verified_dependency_copy(
            {"Cargo.toml": '[package]\nname="new"\nversion="0.1.0"\n'}
        )
        plan = self.workflow.propose(
            "development",
            "apply_dependencies",
            str(self.project),
            {"source_operation": source["id"]},
        )
        with patch(
            "jarvis_tui.operation_workflow.bounded_process",
            side_effect=lambda argv, **kw: {
                "status": "completed",
                "output": json.dumps(verify(self.root, argv[-1])),
            },
        ):
            result = self.workflow.execute(self.workflow.approve(plan["id"], plan["digest"]))
        self.assertTrue(result["verified"])
        self.assertEqual(
            (self.project / result["retained_originals"]["Cargo.toml"]).read_bytes(), before
        )
        self.assertFalse(
            self.workflow.recovery_proposal(plan["id"])["original_unchanged_by_design"]
        )
        self.assertEqual(
            os.getxattr(self.project / "Cargo.toml", "user.jarvis_fixture"),
            b"preserve-this-attribute",
        )
        os.chmod(self.project / "Cargo.toml", 0o640)
        self.assertFalse(verify(self.root, plan["id"])["checks"]["dependency_metadata_exact"])
        os.chmod(self.project / result["retained_originals"]["Cargo.toml"], 0o640)
        self.assertFalse(verify(self.root, plan["id"])["checks"]["retained_originals_exact"])

    def test_apply_dependency_copy_rejects_drift_after_review(self):
        source = self._verified_dependency_copy({"Cargo.toml": '[package]\nname="new"\n'})
        plan = self.workflow.propose(
            "development",
            "apply_dependencies",
            str(self.project),
            {"source_operation": source["id"]},
        )
        approval = self.workflow.approve(plan["id"], plan["digest"])
        (self.project / "Cargo.toml").write_text('[package]\nname="user-edit"\n')
        result = self.workflow.execute(approval)
        self.assertFalse(result["verified"])
        self.assertIn("user-edit", (self.project / "Cargo.toml").read_text())
        self.assertFalse(list(self.project.glob(".jarvis-dependency-*")))

    def test_partial_dependency_application_never_auto_rolls_back(self):
        from jarvis_tui import dependency_apply

        (self.project / "Cargo.lock").write_text("version=3\n")
        before = (self.project / "Cargo.toml").read_bytes()
        source = self._verified_dependency_copy(
            {"Cargo.toml": '[package]\nname="new"\n', "Cargo.lock": "version=4\n"}
        )
        plan = self.workflow.propose(
            "development",
            "apply_dependencies",
            str(self.project),
            {"source_operation": source["id"]},
        )
        real = dependency_apply.exchange
        attempts = []

        def exchange(fd, staged, target):
            attempts.append(target)
            if len(attempts) == 2:
                raise OSError("fixture exchange failure")
            return real(fd, staged, target)

        with patch.object(dependency_apply, "exchange", side_effect=exchange):
            result = self.workflow.execute(self.workflow.approve(plan["id"], plan["digest"]))
        self.assertEqual(result["status"], "indeterminate")
        self.assertFalse(result["verified"])
        first = attempts[0]
        self.assertEqual(
            (self.project / result["retained_files"][first]).read_bytes(),
            b"version=3\n" if first == "Cargo.lock" else before,
        )
        self.assertEqual(len(attempts), 2)

    def test_dependency_recovery_is_separately_reviewed_and_preserves_user_edits(self):
        before = (self.project / "Cargo.toml").read_bytes()
        source = self._verified_dependency_copy({"Cargo.toml": '[package]\nname="new"\n'})
        apply = self.workflow.propose(
            "development",
            "apply_dependencies",
            str(self.project),
            {"source_operation": source["id"]},
        )

        def verifier(argv, **kw):
            return {"status": "completed", "output": json.dumps(verify(self.root, argv[-1]))}

        with patch("jarvis_tui.operation_workflow.bounded_process", side_effect=verifier):
            outcome = self.workflow.execute(self.workflow.approve(apply["id"], apply["digest"]))
        self.assertTrue(outcome["verified"])
        recovery = self.workflow.recovery_proposal(apply["id"])["recovery"]
        self.assertFalse(recovery["execution_authorized"])
        self.assertNotEqual((self.project / "Cargo.toml").read_bytes(), before)
        inverse = self.workflow.propose(**recovery["next_plan"])
        with patch("jarvis_tui.operation_workflow.bounded_process", side_effect=verifier):
            self.assertTrue(
                self.workflow.execute(self.workflow.approve(inverse["id"], inverse["digest"]))[
                    "verified"
                ]
            )
        restore = self.workflow.propose(
            "development",
            "apply_dependencies",
            str(self.project),
            {"source_operation": inverse["id"]},
        )
        with patch("jarvis_tui.operation_workflow.bounded_process", side_effect=verifier):
            self.assertTrue(
                self.workflow.execute(self.workflow.approve(restore["id"], restore["digest"]))[
                    "verified"
                ]
            )
        self.assertEqual((self.project / "Cargo.toml").read_bytes(), before)
        (self.project / "Cargo.toml").write_text('[package]\nname="user-new-work"\n')
        blocked = self.workflow.recovery_proposal(apply["id"])["recovery"]
        self.assertEqual(blocked["status"], "blocked_current_state_requires_review")
        self.assertNotIn("next_plan", blocked)

    def test_output_overflow_stops_and_withholds_partial_secrets(self):
        result = bounded_process(("/usr/bin/python3", "-c", 'print("a" * 9000)'), limit=64)
        self.assertEqual(result["status"], "output_limit")
        self.assertNotIn("aaaa", result["output"])
        self.assertEqual(result["attempts"], 1)

    def test_timeout_is_one_attempt(self):
        result = bounded_process(
            ("/usr/bin/python3", "-c", "import time; time.sleep(2)"), timeout=0.05
        )
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["attempts"], 1)

    def test_manifest_symlinks_and_oversize_are_rejected(self):
        (self.project / "Cargo.lock").symlink_to(self.project / "Cargo.toml")
        fd = open_project(self.project)
        try:
            with self.assertRaises(OSError):
                read_project_file(fd, "Cargo.lock")
            with self.assertRaises(ValueError):
                read_project_file(fd, "Cargo.toml", 2)
        finally:
            os.close(fd)
        linked = self.root / "linked"
        linked.symlink_to(self.project)
        with self.assertRaises(OSError):
            open_project(linked)

    def test_json_and_incomplete_pem_are_redacted(self):
        for value, secret in [
            ('"token": "not-for-storage"', "not-for-storage"),
            ("-----BEGIN PRIVATE KEY-----\nkey-material", "key-material"),
            ("https://alice:private-value@example.test", "private-value"),
        ]:
            safe, _ = sanitize_and_redact_terminal_text(value)
            self.assertNotIn(secret, safe)

    def test_forged_and_duplicate_approvals_fail(self):
        plan = self.workflow.propose(
            "development",
            "dependencies",
            str(self.project),
            {"files": {"Cargo.toml": '[package]\nname="new"\nversion="0.1.0"\n'}},
        )
        approval = self.workflow.approve(plan["id"], plan["digest"])
        with self.assertRaises(ValueError):
            self.workflow.execute(dataclasses.replace(approval))
        # A forged attempt consumes the pending decision: it cannot be replayed.
        with self.assertRaises(ValueError):
            self.workflow.execute(approval)

    def test_dependency_application_and_independent_check(self):
        # Verification here calls the pure reader directly; subprocess integration
        # is separately exercised against a source-bearing bundle.
        plan = self.workflow.propose(
            "development",
            "dependencies",
            str(self.project),
            {"files": {"Cargo.toml": '[package]\nname="new"\nversion="0.1.0"\n'}},
        )
        approval = self.workflow.approve(plan["id"], plan["digest"])
        result = self.workflow.execute(approval)
        self.assertEqual(result["status"], "prepared_workspace")
        self.assertEqual(verify(self.root, plan["id"])["verdict"], "pass")
        with self.assertRaises(ValueError):
            self.workflow.execute(approval)
        # A later edit invalidates both independent success and recovery planning.
        (self.project / "Cargo.toml").write_text('[package]\nname="later"\n')
        self.assertEqual(verify(self.root, plan["id"])["verdict"], "fail")
        self.assertFalse(self.workflow.recovery_proposal(plan["id"])["execution_authorized"])

    def test_stale_prestate_does_not_write(self):
        plan = self.workflow.propose(
            "development",
            "dependencies",
            str(self.project),
            {"files": {"Cargo.toml": '[package]\nname="new"\n'}},
        )
        approval = self.workflow.approve(plan["id"], plan["digest"])
        (self.project / "Cargo.toml").write_text('[package]\nname="concurrent"\n')
        result = self.workflow.execute(approval)
        self.assertEqual(result["status"], "indeterminate")
        self.assertIn("concurrent", (self.project / "Cargo.toml").read_text())
        with self.assertRaises(FileExistsError):
            other = OperationWorkflow(self.root)
            other.execute(other.approve(plan["id"], plan["digest"]))

    def test_host_proposals_cannot_execute(self):
        for domain, operation in [
            ("security", "updates"),
        ]:
            plan = self.workflow.propose(domain, operation, "exact-target")
            self.assertTrue(plan["blockers"])
            with self.assertRaises(ValueError):
                self.workflow.approve(plan["id"], plan["digest"])

    def test_private_records_reject_symlinks_and_second_reservation(self):
        root = self.root / "records"
        private_records.write_once(root, "a.json", {"a": 1})
        with self.assertRaises(FileExistsError):
            private_records.write_once(root, "a.json", {"a": 2})
        (root / "b.json").symlink_to(root / "a.json")
        with self.assertRaises(OSError):
            private_records.read(root, "b.json")

    def test_specialist_scope_excludes_activation_and_unselected_tools(self):
        spec = Specialist.from_mapping(
            json.loads((BUNDLE / "plugins/jarvis-system-health/specialist.json").read_text())
        )
        publish(self.root, spec, "fixture-task", "a" * 32)
        self.assertIn("health_inventory", allowed(self.root, "a" * 32))
        self.assertNotIn("security_inventory", allowed(self.root, "a" * 32))
        self.assertNotIn("activate_lesson", allowed(self.root, "a" * 32))
        with patch("jarvis_tui.tool_scope.time.time", return_value=10**12):
            self.assertEqual(allowed(self.root, "a" * 32), frozenset())

    def test_tree_change_after_review_blocks_execution(self):
        (self.project / "build.rs").write_text("fn main() {}")
        plan = self.workflow.propose("development", "check", str(self.project))
        approval = self.workflow.approve(plan["id"], plan["digest"])
        (self.project / "build.rs").write_text('fn main() { panic!("changed"); }')
        with patch.object(self.workflow, "_cargo") as cargo:
            result = self.workflow.execute(approval)
        cargo.assert_not_called()
        self.assertEqual(result["status"], "indeterminate")

    def test_removed_secret_never_enters_a_proposal_diff(self):
        (self.project / "Cargo.toml").write_text('[package]\ntoken="fixture-only-secret"\n')
        with self.assertRaises(ValueError):
            self.workflow.propose(
                "development",
                "dependencies",
                str(self.project),
                {"files": {"Cargo.toml": '[package]\nname="clean"\n'}},
            )
        self.assertFalse((self.workflow.root / "proposals").exists())

    def test_backup_and_restore_never_overwrite(self):
        destination = self.root / "backup"
        plan = self.workflow.propose(
            "recovery", "backup", str(self.project), {"destination": str(destination)}
        )
        result = self.workflow.execute(self.workflow.approve(plan["id"], plan["digest"]))
        self.assertEqual(result["status"], "prepared_workspace")
        self.assertEqual(verify(self.root, plan["id"])["verdict"], "pass")
        with self.assertRaises(ValueError):
            self.workflow.propose(
                "recovery", "restore", str(destination), {"destination": str(self.project)}
            )
        restored = self.root / "restored"
        restore = self.workflow.propose(
            "recovery", "restore", str(destination), {"destination": str(restored)}
        )
        self.workflow.execute(self.workflow.approve(restore["id"], restore["digest"]))
        self.assertEqual(
            (restored / "Cargo.toml").read_bytes(), (self.project / "Cargo.toml").read_bytes()
        )

    def test_runtime_profile_rejects_extra_mcp_and_accepts_explicit_full_access(self):
        import tomllib

        from jarvis_tui.runtime_profile import render, validate

        config = tomllib.loads(render(self.root))
        validate(config, self.root)
        config["mcp_servers"]["untrusted"] = {"command": "anything"}
        with self.assertRaises(ValueError):
            validate(config, self.root)
        config = tomllib.loads(render(self.root))
        config["sandbox_mode"] = "danger-full-access"
        config["approval_policy"] = "on-request"
        config["features"]["plugins"] = True
        config["features"]["hooks"] = True
        validate(config, self.root)

    def test_transcript_rejects_reasoning_and_redacts_output(self):
        from jarvis_tui.transcript_store import append, read

        with self.assertRaises(ValueError):
            append(self.root, "operation_result", "fixture", {"reasoning": "not retained"})
        identity = append(
            self.root, "operation_result", "fixture", {"output": 'token="fixture-secret"'}
        )
        self.assertNotIn("fixture-secret", str(read(self.root, identity)))

    def test_resource_guard_fails_without_effective_limits(self):
        from jarvis_tui.resource_guard import check_limits

        limits = self.root / "cgroup"
        limits.mkdir()
        (limits / "memory.max").write_text("max")
        (limits / "pids.max").write_text("32")
        (limits / "cpu.max").write_text("100000 100000")
        self.assertFalse(check_limits(limits))
        (limits / "memory.max").write_text("1073741824")
        self.assertTrue(check_limits(limits))

    def test_reading_missing_record_does_not_create_directories(self):
        root = self.root / "must-not-exist"
        with self.assertRaises(FileNotFoundError):
            private_records.read(root, "missing.json")
        self.assertFalse(root.exists())

    def test_external_check_requires_ip_and_exact_port_and_one_use(self):
        with self.assertRaises(ValueError):
            self.workflow.propose("network", "external_check", "example.test", {"port": 443})
        with self.assertRaises(ValueError):
            self.workflow.propose("network", "external_check", "192.0.2.1", {"port": True})
        plan = self.workflow.propose("network", "external_check", "192.0.2.1", {"port": 443})
        self.assertIn("cannot be undone", plan["rollback"])
        with patch("jarvis_tui.operation_workflow.socket.socket") as factory:
            result = self.workflow.execute(self.workflow.approve(plan["id"], plan["digest"]))
            factory.return_value.__enter__.return_value.connect.assert_called_once_with(
                ("192.0.2.1", 443)
            )
        self.assertTrue(result["connected"])
        self.assertEqual(verify(self.root, plan["id"])["verdict"], "pass")

    def test_scope_is_per_process_and_revoked(self):
        from jarvis_tui.tool_scope import revoke

        spec = Specialist.from_mapping(
            json.loads((BUNDLE / "plugins/jarvis-system-health/specialist.json").read_text())
        )
        publish(self.root, spec, "task-a", "b" * 32)
        self.assertIn("health_inventory", allowed(self.root, "b" * 32))
        self.assertEqual(allowed(self.root, "c" * 32), frozenset())
        revoke(self.root, "b" * 32)
        self.assertEqual(allowed(self.root, "b" * 32), frozenset())

    def test_observation_evidence_cannot_cross_tasks(self):
        from jarvis_tui.tool_scope import has_observation, note_observation

        spec = Specialist.from_mapping(
            json.loads((BUNDLE / "plugins/jarvis-system-health/specialist.json").read_text())
        )
        publish(self.root, spec, "task-a", "d" * 32)
        note_observation(self.root, "d" * 32, "health_inventory")
        self.assertTrue(has_observation(self.root, "d" * 32, "task-a"))
        self.assertFalse(has_observation(self.root, "d" * 32, "task-b"))

    def test_nested_sensitive_transcript_keys_are_rejected(self):
        from jarvis_tui.transcript_store import sanitized

        for key in (
            "password",
            "passwd",
            "passphrase",
            "secret",
            "api-key",
            "api_key",
            "authorization",
            "cookie",
            "session_id",
            "contraseña",
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                sanitized({"output": [{"nested": {key: "fictional-secret"}}]})

    def test_package_freshness_cannot_be_unlocked_by_telemetry_or_cached_read(self):
        from jarvis_tui.tool_scope import has_observation, note_observation

        spec = Specialist.from_mapping(
            json.loads((BUNDLE / "plugins/jarvis-power-expert/specialist.json").read_text())
        )
        scope = "f" * 32
        publish(
            self.root,
            spec,
            "package-task",
            scope,
            evidence_tools=("inspect_packages", "package_search"),
        )
        note_observation(self.root, scope, "power_telemetry", {})
        self.assertFalse(has_observation(self.root, scope, "package-task"))
        note_observation(self.root, scope, "inspect_packages", {"refresh": False})
        self.assertFalse(has_observation(self.root, scope, "package-task"))
        note_observation(self.root, scope, "inspect_packages", {"refresh": True})
        self.assertTrue(has_observation(self.root, scope, "package-task"))

    def test_evidence_query_must_match_and_is_not_stored_in_plaintext(self):
        from jarvis_tui.tool_scope import has_observation, note_observation

        spec = Specialist.from_mapping(
            json.loads((BUNDLE / "plugins/jarvis-power-expert/specialist.json").read_text())
        )
        scope = "e" * 32
        publish(
            self.root,
            spec,
            "package-query",
            scope,
            evidence_tools=("inspect_packages",),
            evidence_arguments={"query": "fixture request text"},
        )
        self.assertNotIn(
            "fixture request text", (self.root / "runtime/tool-scope" / f"{scope}.json").read_text()
        )
        note_observation(
            self.root, scope, "inspect_packages", {"query": "unrelated", "refresh": True}
        )
        self.assertFalse(has_observation(self.root, scope, "package-query"))
        note_observation(
            self.root, scope, "inspect_packages", {"query": "fixture request text", "refresh": True}
        )
        self.assertTrue(has_observation(self.root, scope, "package-query"))

    def test_runtime_profile_rejects_an_explicit_app_override(self):
        import tomllib

        from jarvis_tui.runtime_profile import render, validate

        config = tomllib.loads(render(self.root))
        config["apps"]["extra_app"] = {"enabled": True}
        with self.assertRaises(ValueError):
            validate(config, self.root)

    def test_package_alias_accepts_relevant_query_but_rejects_unrelated_and_stale(self):
        from jarvis_tui.tool_scope import allowed, has_observation, note_observation

        spec = Specialist.from_mapping(
            json.loads(
                (BUNDLE / "plugins/jarvis-installation-specialist/specialist.json").read_text()
            )
        )
        scope = "f" * 32
        publish(
            self.root,
            spec,
            "node-task",
            scope,
            evidence_tools=("inspect_packages",),
            evidence_arguments={"query": "check if node is present n the sytem"},
        )
        self.assertIn("inspect_packages", allowed(self.root, scope))
        note_observation(self.root, scope, "inspect_packages", {"query": "rust", "refresh": True})
        self.assertFalse(has_observation(self.root, scope, "node-task"))
        note_observation(
            self.root, scope, "inspect_packages", {"query": "nodejs", "refresh": False}
        )
        self.assertFalse(has_observation(self.root, scope, "node-task"))
        note_observation(self.root, scope, "inspect_packages", {"query": "node", "refresh": True})
        self.assertTrue(has_observation(self.root, scope, "node-task"))
        publish(
            self.root,
            spec,
            "multi-package-task",
            scope,
            evidence_tools=("inspect_packages",),
            evidence_arguments={"query": "check node and python"},
        )
        note_observation(self.root, scope, "inspect_packages", {"query": "node", "refresh": True})
        self.assertFalse(has_observation(self.root, scope, "multi-package-task"))
        note_observation(
            self.root, scope, "inspect_packages", {"query": "python nodejs", "refresh": True}
        )
        self.assertTrue(has_observation(self.root, scope, "multi-package-task"))

    def test_effective_profile_accepts_only_the_observed_local_transport(self):
        import tomllib

        from jarvis_tui.runtime_profile import render, validate_effective

        config = tomllib.loads(render(self.root))
        scope = "a" * 32
        server = config["mcp_servers"]["jarvis_control"]
        server["args"] += ["--scope-id", scope]
        server.update(enabled=True, environment_id="local", tool_timeout_sec=None)
        validate_effective({"config": config}, self.root, scope)
        server["environment_id"] = "remote"
        with self.assertRaises(ValueError):
            validate_effective({"config": config}, self.root, scope)

    def test_backup_excludes_sensitive_names_before_reading_content(self):
        from jarvis_tui.project_snapshot import inspect

        (self.project / "passwords.txt").write_text("fictional-unlabelled-value")
        files, tree = inspect(self.project)
        self.assertNotIn("passwords.txt", files)
        self.assertIn("passwords.txt", tree["omitted"])
        no_project = self.root / "documents"
        no_project.mkdir()
        with self.assertRaises(ValueError):
            inspect(no_project)

    def test_removed_knowledge_tool_is_not_restored_by_control_scope(self):
        spec = Specialist.from_mapping(
            json.loads((BUNDLE / "plugins/jarvis-system-health/specialist.json").read_text())
        )
        narrowed = dataclasses.replace(
            spec,
            allowed_tools=tuple(tool for tool in spec.allowed_tools if tool != "query_knowledge"),
        )
        publish(self.root, narrowed, "narrowed-task", "c" * 32)
        self.assertNotIn("query_knowledge", allowed(self.root, "c" * 32))
        record = private_records.read(self.root / "runtime/tool-scope", "c" * 32 + ".json")
        self.assertIn("specialist_digest", record)
