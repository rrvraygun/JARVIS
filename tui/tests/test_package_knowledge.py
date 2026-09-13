from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis_tui.package_inventory import PackageRecord, RepositoryPackageRecord  # noqa: E402
from jarvis_tui.package_knowledge import (
    package_context,
    read_catalog,
    search_catalog,
    write_catalog,
)  # noqa: E402
from jarvis_tui.local_control import ReadOnlyLocalControl  # noqa: E402


class PackageKnowledgeTests(unittest.TestCase):
    def test_catalog_persists_provenance_and_ranked_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            metadata = write_catalog(
                root,
                [
                    PackageRecord(
                        "rust",
                        "1",
                        "1",
                        "x86_64",
                        "Fedora",
                        "Rust compiler",
                        "development",
                        "Programming and development",
                        "rpmdb",
                    )
                ],
                [
                    RepositoryPackageRecord(
                        "cargo",
                        "0",
                        "2",
                        "1",
                        "x86_64",
                        "fedora",
                        "Fedora",
                        "MIT",
                        "Rust package manager",
                        "development",
                        "Programming and development",
                    )
                ],
            )
            payload = read_catalog(root)
            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertEqual(metadata["installed_count"], 1)
            self.assertEqual(metadata["available_count"], 1)
            matches = search_catalog(
                payload, "Which package should I install for Rust development?"
            )
            self.assertEqual(matches[0]["name"], "rust")
            self.assertEqual(matches[0]["origin"], "rpmdb")
            context = package_context(
                payload, "Which package should I install for Rust development?"
            )
            self.assertTrue(context[0]["documentation"]["packaged_docs"])
            self.assertEqual(context[0]["documentation"]["official_source_status"], "not_collected")
            self.assertEqual(payload["schema_version"], 2)

    def test_knowledge_status_reports_package_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_catalog(root, (), ())
            status = ReadOnlyLocalControl(root).knowledge_status()
            self.assertTrue(status["package_catalog"]["available"])
            self.assertEqual(status["package_catalog"]["installed_count"], 0)

    def test_go_alias_prefers_the_exact_fedora_toolchain_over_go_utilities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_catalog(
                root,
                [
                    PackageRecord(
                        "go-srpm-macros",
                        "1",
                        "1",
                        "noarch",
                        "Fedora",
                        "RPM macros for Go packages",
                        "development",
                        "Build tooling",
                        "rpmdb",
                    )
                ],
                [
                    RepositoryPackageRecord(
                        "golang",
                        "0",
                        "1",
                        "1",
                        "x86_64",
                        "fedora",
                        "Fedora",
                        "BSD",
                        "Go language compiler and toolchain",
                        "development",
                        "Programming language toolchain",
                    ),
                    RepositoryPackageRecord(
                        "go-task",
                        "0",
                        "1",
                        "1",
                        "x86_64",
                        "fedora",
                        "Fedora",
                        "MIT",
                        "Task runner",
                        "development",
                        "Task runner",
                    ),
                ],
            )
            payload = read_catalog(root)
            assert payload is not None
            self.assertEqual(search_catalog(payload, "Go language")[0]["name"], "golang")


if __name__ == "__main__":
    unittest.main()
