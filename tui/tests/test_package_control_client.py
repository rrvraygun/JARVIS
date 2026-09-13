from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis_tui.package_control_client import (
    apply_transaction,
    archive_transaction,
    authoritative_status,
    helper_matches_bundle,
    remove_transaction,
    undo_transaction,
)  # noqa: E402


class PackageControlClientTests(unittest.TestCase):
    def fake_helper(self) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "helper"
        path.write_text("helper")
        path.chmod(0o755)
        return path

    @mock.patch("jarvis_tui.package_control_client.helper_available", return_value=True)
    def test_apply_binds_preview_and_approval_digests(self, _available):
        runner = mock.Mock(return_value=mock.Mock(stdout='{"status":"passed","operation":"apply"}'))
        apply_transaction(("rust",), "a" * 64, "b" * 64, helper=self.fake_helper(), runner=runner)
        args = runner.call_args.args[0]
        self.assertIn("--preview-digest", args)
        self.assertIn("--approved-digest", args)
        self.assertIn("rust", args)

    @mock.patch("jarvis_tui.package_control_client.helper_available", return_value=True)
    def test_undo_requires_record_digest(self, _available):
        runner = mock.Mock(return_value=mock.Mock(stdout='{"status":"passed","operation":"undo"}'))
        undo_transaction("c" * 64, helper=self.fake_helper(), runner=runner)
        self.assertIn("--record-digest", runner.call_args.args[0])

    @mock.patch("jarvis_tui.package_control_client.helper_available", return_value=True)
    def test_archive_requires_record_digest(self, _available):
        runner = mock.Mock(
            return_value=mock.Mock(stdout='{"status":"passed","operation":"archive"}')
        )
        archive_transaction("c" * 64, helper=self.fake_helper(), runner=runner)
        self.assertEqual(runner.call_args.args[0][2:], ["archive", "--record-digest", "c" * 64])

    @mock.patch("jarvis_tui.package_control_client.helper_available", return_value=True)
    def test_remove_binds_exact_digests_and_names(self, _available):
        runner = mock.Mock(
            return_value=mock.Mock(stdout='{"status":"passed","operation":"remove"}')
        )
        remove_transaction(("demo",), "a" * 64, "b" * 64, helper=self.fake_helper(), runner=runner)
        self.assertEqual(
            runner.call_args.args[0][2:5],
            ["remove", "--preview-digest", "a" * 64],
        )
        self.assertEqual(runner.call_args.args[0][-1], "demo")

    @mock.patch("jarvis_tui.package_control_client.helper_available", return_value=True)
    def test_status_accepts_recovery_status(self, _available):
        runner = mock.Mock(
            return_value=mock.Mock(
                stdout='{"status":"passed","operation":"recovery-status","record_digest":"'
                + "d" * 64
                + '"}'
            )
        )
        value = authoritative_status(helper=self.fake_helper(), runner=runner)
        self.assertEqual(value["operation"], "recovery-status")

    @mock.patch("jarvis_tui.package_control_client.helper_available", return_value=True)
    def test_helper_match_requires_identical_reviewed_source(self, _available):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "vm-lab/scripts/jarvis_package_control.py"
            source.parent.mkdir(parents=True)
            source.write_text("reviewed helper")
            helper = root / "helper"
            helper.write_text("reviewed helper")
            helper.chmod(0o755)
            self.assertTrue(helper_matches_bundle(root, helper=helper))
            helper.write_text("stale helper")
            self.assertFalse(helper_matches_bundle(root, helper=helper))


if __name__ == "__main__":
    unittest.main()
