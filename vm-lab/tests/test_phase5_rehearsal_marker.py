from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from phase5_rehearsal_marker import (
    RehearsalMarkerAdapter,
    RehearsalMarkerError,
)


class RehearsalMarkerTests(unittest.TestCase):
    def test_present_then_absent_is_reversible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scratch").mkdir()
            with RehearsalMarkerAdapter(root, "scratch") as adapter:
                result = adapter.execute({"state": "present"})
                self.assertEqual(result["resulting_state"], "present")
                self.assertEqual(result["target_digest"], adapter.target_digest)
                self.assertTrue(adapter.marker_path.is_file())
                with self.assertRaisesRegex(RehearsalMarkerError, "already exists"):
                    adapter.execute({"state": "present"})
                self.assertEqual(adapter.execute({"state": "absent"})["resulting_state"], "absent")
                self.assertTrue(adapter.marker_path.exists())
                self.assertEqual(adapter.marker_path.read_bytes(), b"")
                self.assertEqual(
                    adapter.execute({"state": "present"})["resulting_state"], "present"
                )

    def test_absent_is_idempotent_but_parameters_are_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scratch").mkdir()
            with RehearsalMarkerAdapter(root, "scratch") as adapter:
                self.assertEqual(adapter.execute({"state": "absent"})["resulting_state"], "absent")
                for parameters in (
                    {},
                    {"state": "present", "extra": True},
                    {"state": "other"},
                ):
                    with self.assertRaises(RehearsalMarkerError):
                        adapter.execute(parameters)

    def test_symlink_marker_is_rejected(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.NamedTemporaryFile() as target,
        ):
            root = Path(directory)
            (root / "scratch").mkdir()
            with RehearsalMarkerAdapter(root, "scratch") as adapter:
                adapter.marker_path.symlink_to(target.name)
                with self.assertRaisesRegex(RehearsalMarkerError, "owner-controlled regular file"):
                    adapter.execute({"state": "absent"})

    def test_root_symlink_and_traversal_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            link = root / "link"
            link.symlink_to(root, target_is_directory=True)
            (root / "scratch").mkdir()
            with self.assertRaises(RehearsalMarkerError):
                RehearsalMarkerAdapter(link, "scratch")
            with self.assertRaises(RehearsalMarkerError):
                RehearsalMarkerAdapter(root / ".." / root.name, "scratch")

    def test_unexpected_marker_contents_are_not_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scratch").mkdir()
            with RehearsalMarkerAdapter(root, "scratch") as adapter:
                adapter.marker_path.write_text("unexpected", encoding="utf-8")
                with self.assertRaises(RehearsalMarkerError):
                    adapter.execute({"state": "absent"})
                self.assertTrue(adapter.marker_path.exists())

    def test_unexpected_sibling_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scratch = root / "scratch"
            scratch.mkdir()
            (scratch / "unexpected").write_text("x", encoding="utf-8")
            with RehearsalMarkerAdapter(root, "scratch") as adapter:
                with self.assertRaisesRegex(RehearsalMarkerError, "unexpected entries"):
                    adapter.execute({"state": "absent"})


if __name__ == "__main__":
    unittest.main()
