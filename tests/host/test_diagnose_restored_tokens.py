#!/usr/bin/env python3
"""Tests for privacy-preserving restore mismatch classification."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "deployment/host/diagnose_restored_tokens.py"
SPEC = importlib.util.spec_from_file_location("diagnose_restored_tokens", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class DiagnoseRestoredTokensTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        base = Path(self.temporary.name)
        self.source = base / "source"
        self.restored = base / "restored"
        self.source.mkdir()
        self.restored.mkdir()

        self.missing_path = self.source / "private-missing-name"
        self.missing_path.write_bytes(b"missing-secret-payload")

        self.mtime_source = self.source / "private-mtime-name"
        self.mtime_restored = self.restored / "private-mtime-name"
        self.mtime_source.write_bytes(b"secret-payload")
        self.mtime_restored.write_bytes(b"secret-payload")
        source_stat = self.mtime_source.stat()
        os.utime(
            self.mtime_restored,
            ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns + 1_000_000_000),
        )

        self.sparse_source = self.source / "private-sparse-name"
        self.sparse_restored = self.restored / "private-sparse-name"
        with self.sparse_source.open("wb") as handle:
            handle.write(b"head")
            handle.seek(1024 * 1024)
            handle.write(b"tail")
        self.sparse_restored.write_bytes(self.sparse_source.read_bytes())

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_classifies_socket_mtime_and_sparse_without_paths_or_content(self) -> None:
        core = MODULE.CORE
        requests = [
            {
                "boundary": "fixture",
                "code": "missing-restored-entry",
                "token": core.path_token("fixture", (self.missing_path.name,)),
            },
            {
                "boundary": "fixture",
                "code": "mtime",
                "token": core.path_token("fixture", (self.mtime_source.name,)),
            },
            {
                "boundary": "fixture",
                "code": "sparse-layout-not-preserved",
                "token": core.path_token("fixture", (self.sparse_source.name,)),
            },
        ]
        report = MODULE.diagnose(
            [core.Boundary("fixture", self.source, self.restored)],
            requests,
        )
        self.assertEqual(report["found_tokens"], 3)
        self.assertEqual(
            report["summary"]["restored_absence_source_type_counts"],
            {"regular": 1},
        )
        mtime = next(item for item in report["records"] if item["code"] == "mtime")
        self.assertEqual(mtime["mtime_delta_ns_restored_minus_source"], 1_000_000_000)
        sparse = next(
            item for item in report["records"] if item["code"] == "sparse-layout-not-preserved"
        )
        self.assertGreater(sparse["source_holes"]["hole_bytes"], 0)
        encoded = json.dumps(report)
        for secret in (
            "private-missing-name",
            "private-mtime-name",
            "private-sparse-name",
            "missing-secret-payload",
            "secret-payload",
        ):
            self.assertNotIn(secret, encoded)

    def test_socket_mode_is_classified_without_opening_or_reading_the_path(
        self,
    ) -> None:
        socket_stat = os.stat_result((stat.S_IFSOCK | 0o600, 1, 1, 1, 0, 0, 0, 0, 0, 0))
        record = MODULE.observe(
            "fixture",
            "missing-restored-entry",
            "0" * 24,
            self.source / "unresolved-source-name",
            self.restored / "unresolved-restored-name",
            socket_stat,
        )
        self.assertEqual(record["source_type"], "socket")
        self.assertFalse(record["restored_exists"])

    def test_tool_has_no_network_subprocess_content_read_or_mutation_primitive(
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
        for token in (
            "O_WRONLY",
            "O_RDWR",
            "O_CREAT",
            "O_TRUNC",
            "O_APPEND",
            "os.read(",
        ):
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
