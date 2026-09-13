from __future__ import annotations

import dataclasses
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis_tui.normal_terminal import NormalTerminalWorkflow, execute_once


class NormalTerminalTests(unittest.TestCase):
    def test_inherits_stdio_and_runs_once_inside_visible_suspend(self):
        completed = type("Completed", (), {"returncode": 0})()
        with (
            patch("jarvis_tui.normal_terminal.available", return_value=True),
            patch("jarvis_tui.normal_terminal.subprocess.run", return_value=completed) as run,
        ):
            result = execute_once(
                ["/usr/bin/printf", "jarvis-terminal-smoke\\n"],
                cwd="/tmp",
                environment={"PATH": "/usr/bin"},
            )
        self.assertEqual(result["exit_code"], 0)
        self.assertFalse(result["goal_verified"])
        run.assert_called_once_with(
            ["/usr/bin/printf", "jarvis-terminal-smoke\\n"],
            cwd="/tmp",
            env=run.call_args.kwargs["env"],
            check=False,
        )

    def test_failure_is_indeterminate_and_never_retried(self):
        with (
            patch("jarvis_tui.normal_terminal.available", return_value=True),
            patch(
                "jarvis_tui.normal_terminal.subprocess.run", side_effect=OSError("fixture")
            ) as run,
        ):
            result = execute_once(["/usr/bin/true"], cwd="/tmp", environment={})
        self.assertEqual(result["status"], "indeterminate")
        self.assertEqual(result["attempts"], 1)
        run.assert_called_once()

    def test_rejects_nul_arguments(self):
        with self.assertRaises(ValueError):
            execute_once(["/usr/bin/printf", "bad\x00value"], cwd="/tmp", environment={})


class NormalTerminalApprovalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.flow = NormalTerminalWorkflow(self.root)

    def proposal(self):
        return self.flow.propose(
            ["/usr/bin/printf", "JARVIS terminal smoke\\n"], str(self.root), "a" * 32
        )

    def test_mode_has_its_own_digest_and_durable_one_use_reservation(self):
        plan = self.proposal()
        with self.assertRaises(ValueError):
            self.flow.approve(plan["id"], "a" * 64)
        approval = self.flow.approve(plan["id"], plan["digest"])

        def run(*args, **kwargs):
            self.assertTrue((self.flow.root / "reservations" / (plan["id"] + ".json")).is_file())
            return type("Completed", (), {"returncode": 0})()

        with (
            patch("jarvis_tui.normal_terminal.available", return_value=True),
            patch("jarvis_tui.normal_terminal.subprocess.run", side_effect=run) as invoke,
        ):
            result = self.flow.execute(approval)
            with self.assertRaises(ValueError):
                self.flow.execute(approval)
        self.assertEqual(result["execution_mode"], "normal-terminal")
        invoke.assert_called_once()
        self.assertTrue((self.flow.root / "results" / (plan["id"] + ".json")).is_file())

    def test_environment_values_are_not_persisted_and_drift_blocks_execution(self):
        with patch.dict(os.environ, {"JARVIS_TEST_ONLY_SECRET": "fictional-not-for-storage"}):
            plan = self.proposal()
            approval = self.flow.approve(plan["id"], plan["digest"])
        text = (self.flow.root / "proposals" / (plan["id"] + ".json")).read_text()
        self.assertNotIn("fictional-not-for-storage", text)
        self.assertNotIn("JARVIS_TEST_ONLY_SECRET", text)
        with (
            patch("jarvis_tui.normal_terminal.subprocess.run") as run,
            self.assertRaisesRegex(ValueError, "environment_drift"),
        ):
            self.flow.execute(approval)
        run.assert_not_called()

    def test_forged_or_headless_approval_never_launches(self):
        plan = self.proposal()
        approval = self.flow.approve(plan["id"], plan["digest"])
        with patch("jarvis_tui.normal_terminal.subprocess.run") as run:
            with self.assertRaises(ValueError):
                self.flow.execute(dataclasses.replace(approval))
            with self.assertRaises(ValueError):
                self.flow.execute(approval)
        run.assert_not_called()

    def test_interrupted_outcome_blocks_another_normal_terminal_operation(self):
        first = self.proposal()
        approval = self.flow.approve(first["id"], first["digest"])
        with (
            patch("jarvis_tui.normal_terminal.available", return_value=True),
            patch("jarvis_tui.normal_terminal.subprocess.run", side_effect=OSError("fixture")),
        ):
            self.assertEqual(self.flow.execute(approval)["status"], "indeterminate")
        second = self.proposal()
        approved = self.flow.approve(second["id"], second["digest"])
        with (
            patch("jarvis_tui.normal_terminal.available", return_value=True),
            patch("jarvis_tui.normal_terminal.subprocess.run") as run,
            self.assertRaisesRegex(ValueError, "previous_terminal_outcome_pending"),
        ):
            self.flow.execute(approved)
        run.assert_not_called()

    def test_headless_driver_cannot_launch_normal_terminal(self):
        plan = self.proposal()
        approval = self.flow.approve(plan["id"], plan["digest"])
        with (
            patch("jarvis_tui.normal_terminal.available", return_value=False),
            patch("jarvis_tui.normal_terminal.subprocess.run") as run,
            self.assertRaisesRegex(ValueError, "visible_terminal_required"),
        ):
            self.flow.execute(approval)
        run.assert_not_called()

    def test_expiry_is_rechecked_after_acquiring_execution_lock(self):
        with patch("jarvis_tui.normal_terminal.time.time", return_value=1000) as clock:
            plan = self.proposal()
            approval = self.flow.approve(plan["id"], plan["digest"])

            def delayed_lock(*args):
                clock.return_value = 1061

            with (
                patch("jarvis_tui.normal_terminal.available", return_value=True),
                patch("jarvis_tui.normal_terminal.fcntl.flock", side_effect=delayed_lock),
                patch("jarvis_tui.normal_terminal.subprocess.run") as run,
                self.assertRaises(ValueError),
            ):
                self.flow.execute(approval)
        run.assert_not_called()

    def test_decline_discards_ephemeral_environment(self):
        plan = self.proposal()
        self.flow.discard(plan["id"])
        with self.assertRaises(ValueError):
            self.flow.approve(plan["id"], plan["digest"])
        self.assertNotIn(plan["id"], self.flow._environments)

    def test_running_tui_as_root_cannot_use_normal_terminal_route(self):
        with (
            patch("jarvis_tui.normal_terminal.os.geteuid", return_value=0),
            self.assertRaisesRegex(ValueError, "nonroot_user"),
        ):
            self.proposal()
