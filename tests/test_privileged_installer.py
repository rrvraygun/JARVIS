from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "installer",
    Path(__file__).resolve().parents[1] / "deployment/host/install_privileged_controls.py",
)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def test_directory_or_receipt_failure_rolls_back_all_new_objects(self):
        for failure in ("directory", "receipt"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                target, files = self.fixture(root)
                original_mkdir = Path.mkdir

                def mkdir(path, *args, **kwargs):
                    if failure == "directory" and path.name == "results":
                        raise OSError("fixture directory failure")
                    return original_mkdir(path, *args, **kwargs)

                with (
                    patch.object(installer, "BUNDLE", root),
                    patch.object(installer, "FILES", files),
                    patch.object(installer, "STATE", root / "state"),
                    patch.object(installer, "safe_directory"),
                    patch.object(installer, "verify"),
                    patch.object(Path, "mkdir", mkdir),
                    patch.object(
                        installer.json, "dump", side_effect=OSError("fixture receipt failure")
                    ),
                    self.assertRaises(OSError),
                ):
                    installer.install(1000)
                self.assertFalse(target.exists())
                self.assertFalse((root / "state").exists())

    def fixture(self, root):
        source = root / "source"
        source.write_bytes(b"fixture")
        target = root / "installed"
        files = (("source", str(target), 0o644, hashlib.sha256(b"fixture").hexdigest()),)
        return target, files

    def test_source_drift_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target, files = self.fixture(root)
            (root / "source").write_bytes(b"changed")
            with (
                patch.object(installer, "BUNDLE", root),
                patch.object(installer, "FILES", files),
                patch.object(installer, "STATE", root / "state"),
                self.assertRaises(ValueError),
            ):
                installer.install(1000)
            self.assertFalse(target.exists())
            self.assertFalse((root / "state").exists())

    def test_existing_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target, files = self.fixture(root)
            target.write_bytes(b"old")
            with (
                patch.object(installer, "BUNDLE", root),
                patch.object(installer, "FILES", files),
                patch.object(installer, "STATE", root / "state"),
                patch.object(installer, "safe_directory"),
                self.assertRaises(ValueError),
            ):
                installer.install(1000)
            self.assertEqual(target.read_bytes(), b"old")
            self.assertFalse((root / "state").exists())

    def test_verification_failure_removes_only_new_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target, files = self.fixture(root)
            with (
                patch.object(installer, "BUNDLE", root),
                patch.object(installer, "FILES", files),
                patch.object(installer, "STATE", root / "state"),
                patch.object(installer, "safe_directory"),
                patch.object(installer, "verify", side_effect=ValueError("fixture")),
                self.assertRaises(ValueError),
            ):
                installer.install(1000)
            self.assertFalse(target.exists())
            self.assertEqual((root / "source").read_bytes(), b"fixture")
            self.assertFalse((root / "state").exists())


if __name__ == "__main__":
    unittest.main()
