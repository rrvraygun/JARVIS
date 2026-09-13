from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis_tui.specialist_factory import build_specialist_proposal, write_proposal  # noqa: E402


class SpecialistFactoryTests(unittest.TestCase):
    def test_proposal_is_digest_bound_and_not_active(self) -> None:
        value = build_specialist_proposal(
            specialist_id="jarvis-test-specialist",
            display_name="Test Specialist",
            purpose="Inspect a bounded domain.",
            prompt="Use only local evidence and return sources.",
        )
        self.assertEqual(value["status"], "proposal")
        self.assertEqual(value["activation"], "requires_independent_review_and_user_approval")
        self.assertEqual(len(value["proposal_digest"]), 64)

    def test_unknown_tool_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowlist"):
            build_specialist_proposal(
                specialist_id="jarvis-test-specialist",
                display_name="Test Specialist",
                purpose="Inspect a bounded domain.",
                prompt="Use only local evidence.",
                allowed_tools=("terminal",),
            )

    def test_proposal_writes_private_runtime_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = build_specialist_proposal(
                specialist_id="jarvis-test-specialist",
                display_name="Test Specialist",
                purpose="Inspect a bounded domain.",
                prompt="Use only local evidence.",
            )
            path = write_proposal(root, value)
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
