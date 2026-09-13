from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS_PATH = ROOT.parent / "plugins/jarvis-github-agent/scripts/github_tools.py"
spec = importlib.util.spec_from_file_location("jarvis_github_tools", TOOLS_PATH)
assert spec and spec.loader
github_tools = importlib.util.module_from_spec(spec)
sys.modules["jarvis_github_tools"] = github_tools
spec.loader.exec_module(github_tools)


class GitHubToolsTests(unittest.TestCase):
    def _repository(self) -> tempfile.TemporaryDirectory[str]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        subprocess.run(["/usr/bin/git", "init", str(root)], check=True, capture_output=True)
        (root / "README.md").write_text("# fixture\n", encoding="utf-8")
        return temporary

    def test_inspection_is_local_and_bounded(self) -> None:
        with self._repository() as directory:
            result = github_tools.github_inspect(directory)

        self.assertTrue(result["available"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["network_accessed"])
        self.assertIn("README.md", "\n".join(result["changes"]))
        self.assertIn("git version", result["git_version"])

    def test_preflight_reports_sensitive_filename_without_reading_contents(self) -> None:
        with self._repository() as directory:
            root = Path(directory)
            (root / ".gitignore").write_text(".env\n", encoding="utf-8")
            (root / ".env").write_text("GITHUB_TOKEN=github_pat_example_value\n", encoding="utf-8")
            result = github_tools.github_preflight(directory)

        self.assertIn(".env", result["sensitive_filename_candidates"])
        self.assertIn(".env", result["ignored_paths"])
        self.assertEqual(result["secret_matches"][0]["path"], ".env")
        self.assertNotIn("github_pat_example_value", str(result))
        self.assertFalse(result["publication_ready"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["network_accessed"])

    def test_operation_plan_never_authorizes_execution(self) -> None:
        with self._repository() as directory:
            result = github_tools.github_operation_plan(directory, "push", "origin/main")

        self.assertTrue(result["approval_required"])
        self.assertFalse(result["execution_authorized"])
        self.assertTrue(result["network_required"])

    def test_remote_inspection_is_read_only_and_bounded(self) -> None:
        from jarvis_tui import github_cli

        with mock.patch.object(github_cli, "_gh", return_value="/usr/bin/gh"):
            with mock.patch.object(
                github_cli.subprocess,
                "run",
                return_value=SimpleNamespace(
                    returncode=0,
                    stdout='{"nameWithOwner":"rrvraygun/JARVIS"}',
                    stderr="",
                ),
            ):
                result = github_cli.inspect("rrvraygun/JARVIS", "repository")

        self.assertTrue(result["read_only"])
        self.assertTrue(result["network_accessed"])
        self.assertEqual(result["data"]["nameWithOwner"], "rrvraygun/JARVIS")

    def test_preflight_reports_binary_archive_lfs_and_repository_metadata(self) -> None:
        with self._repository() as directory:
            root = Path(directory)
            (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "ci.yml").write_text("name: CI\n", encoding="utf-8")
            (root / "image.bin").write_bytes(b"header\x00binary")
            (root / "bundle.zip").write_bytes(b"archive")
            (root / "large.lfs").write_text(
                "version https://git-lfs.github.com/spec/v1\n", encoding="utf-8"
            )
            result = github_tools.github_preflight(directory)

        self.assertIn("image.bin", result["binary_changed_files"])
        self.assertIn("bundle.zip", result["archive_changed_files"])
        self.assertIn("large.lfs", result["lfs_pointer_files"])
        self.assertTrue(result["repository_files"]["license_present"])
        self.assertEqual(result["repository_files"]["workflow_files"], [".github/workflows/ci.yml"])

    def test_subdirectory_is_rejected_as_repository_root(self) -> None:
        with self._repository() as directory:
            nested = Path(directory) / "nested"
            nested.mkdir()
            with self.assertRaises(github_tools.GitHubEvidenceError):
                github_tools.github_inspect(str(nested))


if __name__ == "__main__":
    unittest.main()
