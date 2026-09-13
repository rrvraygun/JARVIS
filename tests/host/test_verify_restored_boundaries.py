#!/usr/bin/env python3
"""Adversarial tests for the independent restored-boundary verifier."""

from __future__ import annotations

import ast
import importlib.util
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "deployment/host/verify_restored_boundaries.py"
SPEC = importlib.util.spec_from_file_location("verify_restored_boundaries", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RestoredBoundaryVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        base = Path(self.temporary.name)
        self.source = base / "source"
        self.restored = base / "restored"
        self.source.mkdir()
        self.restored.mkdir()
        self._build_fixture(self.source)
        self._build_fixture(self.restored)
        self._match_tree_mtimes(self.source, self.restored)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _build_fixture(self, root: Path) -> None:
        (root / "directory").mkdir()
        (root / "directory" / "regular").write_bytes(b"verified-content\n")
        os.link(root / "directory" / "regular", root / "hardlink")
        os.symlink("directory/regular", root / "symlink")
        sparse = root / "sparse"
        with sparse.open("wb") as handle:
            handle.write(b"head")
            handle.seek(1024 * 1024)
            handle.write(b"tail")
        os.chmod(root / "directory" / "regular", 0o640)
        os.chmod(root / "directory", 0o750)
        try:
            os.setxattr(root / "directory" / "regular", "user.jarvis_fixture", b"xattr-value")
        except OSError:
            pass

    def _match_tree_mtimes(self, source: Path, restored: Path) -> None:
        for source_path in sorted(
            source.rglob("*"), key=lambda item: len(item.parts), reverse=True
        ):
            relative = source_path.relative_to(source)
            restored_path = restored / relative
            if not os.path.lexists(restored_path):
                continue
            source_stat = source_path.lstat()
            os.utime(
                restored_path,
                ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns),
                follow_symlinks=False,
            )
        source_stat = source.lstat()
        os.utime(restored, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))

    def verify(self):
        return MODULE.verify(
            [MODULE.Boundary("fixture", self.source, self.restored)],
            require_witnesses=False,
            progress_interval=0,
        )

    def test_identical_tree_passes_content_metadata_links_xattrs_and_sparse(
        self,
    ) -> None:
        result = self.verify()
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.mismatch_total, 0)
        self.assertEqual(result.source_manifest, result.restored_manifest)
        stats = result.boundaries["fixture"]
        self.assertEqual(stats.symlinks, 1)
        self.assertEqual(stats.hardlink_groups_witnessed, 1)
        self.assertEqual(stats.sparse_source_files, 1)

    def test_changed_content_is_detected_without_a_file_name(self) -> None:
        target = self.restored / "directory" / "regular"
        target.write_bytes(b"changed-content\n")
        source_stat = (self.source / "directory" / "regular").lstat()
        os.utime(target, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        result = self.verify()
        self.assertGreater(result.mismatch_counts["file-content-sha256"], 0)
        encoded = str(result.as_dict())
        self.assertNotIn(str(target), encoded)
        self.assertNotIn("changed-content", encoded)

    def test_missing_and_unexpected_entries_are_detected(self) -> None:
        (self.source / "source-only").write_bytes(b"source")
        (self.restored / "restored-only").write_bytes(b"restored")
        self._match_tree_mtimes(self.source, self.restored)
        result = self.verify()
        self.assertEqual(result.mismatch_counts["missing-restored-entry"], 1)
        self.assertEqual(result.mismatch_counts["unexpected-restored-entry"], 1)

    def test_symlink_target_change_is_detected_without_following_it(self) -> None:
        target = self.restored / "symlink"
        target.unlink()
        target.symlink_to("does-not-exist")
        source_stat = (self.source / "symlink").lstat()
        os.utime(
            target,
            ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns),
            follow_symlinks=False,
        )
        result = self.verify()
        self.assertEqual(result.mismatch_counts["symlink-target"], 1)

    def test_hardlink_split_is_detected(self) -> None:
        target = self.restored / "hardlink"
        content = target.read_bytes()
        target.unlink()
        target.write_bytes(content)
        source_stat = (self.source / "hardlink").lstat()
        os.chmod(target, source_stat.st_mode & 0o7777)
        os.utime(target, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        result = self.verify()
        self.assertEqual(result.mismatch_counts["hardlink-split"], 1)

    def test_sparse_allocation_difference_is_a_notice_not_content_failure(self) -> None:
        source = self.source / "sparse"
        restored = self.restored / "sparse"
        content = source.read_bytes()
        restored.write_bytes(content)
        source_stat = source.lstat()
        os.utime(restored, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        result = self.verify()
        self.assertEqual(result.mismatch_total, 0)
        self.assertEqual(
            result.boundaries["fixture"].sparse_source_files_without_restored_holes,
            1,
        )
        self.assertEqual(result.source_manifest, result.restored_manifest)

    def test_socket_omission_and_nested_btrfs_marker_detection_are_narrow(self) -> None:
        socket_stat = os.stat_result((stat.S_IFSOCK | 0o600, 1, 1, 1, 0, 0, 0, 0, 0, 0))
        nested_stub_stat = os.stat_result((stat.S_IFDIR | 0o755, 2, 1, 1, 0, 0, 0, 0, 0, 0))
        ordinary_dir_stat = os.stat_result((stat.S_IFDIR | 0o755, 3, 1, 1, 0, 0, 0, 0, 0, 0))
        self.assertTrue(MODULE.intentionally_ignored_source_socket(socket_stat))
        boundary = MODULE.Boundary(
            "fixture",
            self.source,
            self.restored,
            btrfs_snapshot=True,
        )
        self.assertTrue(
            MODULE.is_nested_btrfs_boundary_marker(boundary, ("stub",), nested_stub_stat)
        )
        self.assertFalse(MODULE.is_nested_btrfs_boundary_marker(boundary, (), nested_stub_stat))
        self.assertFalse(
            MODULE.is_nested_btrfs_boundary_marker(boundary, ("ordinary",), ordinary_dir_stat)
        )

    def test_top_level_exclusion_is_not_traversed(self) -> None:
        (self.source / "excluded").mkdir()
        (self.source / "excluded" / "source-secret-name").write_bytes(b"source")
        (self.restored / "excluded").mkdir()
        (self.restored / "excluded" / "different-restored-name").write_bytes(b"restored")
        self._match_tree_mtimes(self.source, self.restored)
        result = MODULE.verify(
            [
                MODULE.Boundary(
                    "fixture",
                    self.source,
                    self.restored,
                    excluded_top_level=frozenset({"excluded"}),
                )
            ],
            require_witnesses=False,
            progress_interval=0,
        )
        self.assertEqual(result.mismatch_total, 0)

    def test_witness_requirements_are_reported_as_gaps_not_false_failures(self) -> None:
        result = MODULE.verify(
            [MODULE.Boundary("fixture", self.source, self.restored)],
            require_witnesses=True,
            progress_interval=0,
        )
        self.assertEqual(result.mismatch_total, 0)
        self.assertIn("acl-unwitnessed", result.proof_gaps)
        self.assertEqual(result.status, "matched-with-unwitnessed-requirements")

    def test_verifier_has_no_network_subprocess_or_filesystem_mutation_primitive(
        self,
    ) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(
            imported.isdisjoint({"subprocess", "socket", "requests", "urllib", "ctypes"})
        )
        for token in ("O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND"):
            self.assertNotIn(token, source)
        for token in (
            ".unlink(",
            ".rename(",
            ".replace(",
            ".write_",
            "os.chmod(",
            "os.chown(",
            "os.setxattr(",
        ):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
