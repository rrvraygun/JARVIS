from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from jarvis_tui.operation_workflow import OperationWorkflow


class GitHubOperationWorkflowTests(unittest.TestCase):
    def test_initialize_repository_requires_one_use_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            repository = bundle / "project"
            repository.mkdir()
            workflow = OperationWorkflow(bundle)

            plan = workflow.propose("github", "initialize_repository", str(repository), {})
            self.assertEqual(plan["risk"], 1)
            self.assertEqual(plan["network"], "denied")
            approval = workflow.approve(plan["id"], plan["digest"])
            result = workflow.execute(approval)

            self.assertEqual(result["status"], "completed")
            self.assertTrue(result["verified"])
            self.assertTrue((repository / ".git").exists())

    def test_commit_is_bound_to_reviewed_paths_and_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            repository = bundle / "project"
            repository.mkdir()
            subprocess.run(
                ["/usr/bin/git", "init", str(repository)], check=True, capture_output=True
            )
            subprocess.run(
                ["/usr/bin/git", "-C", str(repository), "config", "user.name", "Test User"],
                check=True,
            )
            subprocess.run(
                [
                    "/usr/bin/git",
                    "-C",
                    str(repository),
                    "config",
                    "user.email",
                    "test@example.invalid",
                ],
                check=True,
            )
            (repository / "README.md").write_text("hello\n", encoding="utf-8")
            workflow = OperationWorkflow(bundle)

            plan = workflow.propose(
                "github",
                "commit",
                str(repository),
                {"message": "Add README", "paths": ["README.md"]},
            )
            result = workflow.execute(workflow.approve(plan["id"], plan["digest"]))

            self.assertEqual(result["status"], "completed")
            self.assertTrue(result["verified"])
            commit = subprocess.run(
                ["/usr/bin/git", "-C", str(repository), "log", "-1", "--format=%s"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(commit.stdout.strip(), "Add README")

    def test_push_and_pull_are_network_risk_two_operations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "project"
            repository.mkdir()
            subprocess.run(
                ["/usr/bin/git", "init", str(repository)], check=True, capture_output=True
            )
            workflow = OperationWorkflow(Path(directory))
            for operation in ("pull", "push"):
                plan = workflow.propose(
                    "github",
                    operation,
                    str(repository),
                    {"remote": "origin", "ref": "main"},
                )
                self.assertEqual(plan["risk"], 2)
                self.assertIn("one Git network operation", plan["network"])

    def test_remote_github_operations_are_catalogued_but_blocked_without_connector(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "project"
            repository.mkdir()
            subprocess.run(
                ["/usr/bin/git", "init", str(repository)], check=True, capture_output=True
            )
            workflow = OperationWorkflow(Path(directory))
            plan = workflow.propose(
                "github",
                "modify_repository_settings",
                str(repository),
                {"requested_target": "owner/repo"},
            )
            self.assertIn("github_cli_unavailable", plan["blockers"])
            self.assertIn("github_operation_adapter_not_implemented", plan["blockers"])
            with self.assertRaises(ValueError):
                workflow.approve(plan["id"], plan["digest"])

    def test_clone_uses_ssh_without_requiring_github_cli(self) -> None:
        from jarvis_tui import github_cli

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "clone"
            plan = github_cli.prepare(
                "clone_repository",
                directory,
                "rrvraygun/JARVIS",
                {"destination": str(destination)},
            )

        self.assertEqual(plan["argv"][:3], ["/usr/bin/git", "clone", "--"])
        self.assertEqual(plan["blockers"], [])


if __name__ == "__main__":
    unittest.main()
