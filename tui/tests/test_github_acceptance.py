from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis_tui import github_cli  # noqa: E402
from jarvis_tui.agent_registry import AgentRegistry  # noqa: E402


class GitHubAcceptanceTests(unittest.TestCase):
    def _repo(self) -> tempfile.TemporaryDirectory[str]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        subprocess.run(["/usr/bin/git", "init", str(root)], check=True, capture_output=True)
        (root / "README.md").write_text("# acceptance\n", encoding="utf-8")
        return temporary

    def test_agent_is_registered_with_required_tools(self) -> None:
        registry = AgentRegistry(ROOT.parent)
        agent = registry.get("jarvis-github-agent")
        self.assertIsNotNone(agent)
        assert agent is not None
        self.assertTrue(agent.selectable)
        self.assertEqual(
            set(agent.allowed_tools),
            {
                "github_inspect",
                "github_preflight",
                "github_remote_inspect",
                "github_operation_plan",
            },
        )

    def test_remote_view_catalog_uses_read_only_json_commands(self) -> None:
        payload = {"nameWithOwner": "rrvraygun/JARVIS"}
        with mock.patch.object(github_cli, "_gh", return_value="/usr/bin/gh"):
            with mock.patch.object(
                github_cli.subprocess,
                "run",
                return_value=SimpleNamespace(
                    returncode=0, stdout=json.dumps(payload), stderr=""
                ),
            ) as run:
                result = github_cli.inspect("rrvraygun/JARVIS", "repository")

        self.assertTrue(result["read_only"])
        self.assertEqual(result["data"], payload)
        argv = run.call_args.args[0]
        self.assertEqual(argv[1:3], ["repo", "view"])
        self.assertNotIn("api", argv)

    def test_remote_pull_request_verification_requires_readback(self) -> None:
        plan = {
            "id": "a" * 32,
            "digest": "b" * 64,
            "github_operation": "create_pull_request",
            "repository": "rrvraygun/JARVIS",
            "postconditions": ["remote_operation_receipt"],
        }
        result = {
            "status": "completed",
            "exit_code": 0,
            "stdout": "https://github.com/rrvraygun/JARVIS/pull/7\n",
        }
        with mock.patch.object(
            github_cli, "_readback", return_value={"number": 7, "state": "OPEN"}
        ) as readback:
            verification = github_cli.verify(plan, result)

        readback.assert_called_once()
        self.assertEqual(verification["verdict"], "pass")
        self.assertTrue(verification["checks"]["remote_operation_receipt"])

    def test_preflight_acceptance_blocks_sensitive_binary_and_large_files(self) -> None:
        with self._repo() as directory:
            root = Path(directory)
            (root / ".env").write_text("GITHUB_TOKEN=github_pat_example_value\n", encoding="utf-8")
            (root / "payload.bin").write_bytes(b"header\x00binary")
            (root / "large.dat").write_bytes(b"x" * (5 * 1024 * 1024 + 1))
            result = importlib.util.spec_from_file_location(
                "jarvis_github_tools_acceptance",
                ROOT.parent / "plugins/jarvis-github-agent/scripts/github_tools.py",
            )
            assert result and result.loader
            module = importlib.util.module_from_spec(result)
            result.loader.exec_module(module)
            preflight = module.github_preflight(directory)

        self.assertFalse(preflight["publication_ready"])
        self.assertTrue(preflight["secret_matches"])
        self.assertIn("payload.bin", preflight["binary_changed_files"])
        self.assertIn("large.dat", {item["path"] for item in preflight["large_changed_files"]})


if __name__ == "__main__":
    unittest.main()
