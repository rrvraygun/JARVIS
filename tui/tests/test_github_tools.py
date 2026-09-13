from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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
            (root / ".env").write_text("not-inspected\n", encoding="utf-8")
            result = github_tools.github_preflight(directory)

        self.assertIn(".env", result["sensitive_filename_candidates"])
        self.assertIn(".env", result["ignored_paths"])
        self.assertFalse(result["publication_ready"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["network_accessed"])

    def test_operation_plan_never_authorizes_execution(self) -> None:
        with self._repository() as directory:
            result = github_tools.github_operation_plan(directory, "push", "origin/main")

        self.assertTrue(result["approval_required"])
        self.assertFalse(result["execution_authorized"])
        self.assertTrue(result["network_required"])

    def test_subdirectory_is_rejected_as_repository_root(self) -> None:
        with self._repository() as directory:
            nested = Path(directory) / "nested"
            nested.mkdir()
            with self.assertRaises(github_tools.GitHubEvidenceError):
                github_tools.github_inspect(str(nested))


if __name__ == "__main__":
    unittest.main()
