import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis_tui.package_inventory import (
    advisories,
    enrich_package,
    package_documentation,
    parse_dependency_output,
    parse_file_output,
)


class PackageInventoryEnrichmentTests(unittest.TestCase):
    def test_dependency_and_file_parsers_are_bounded(self):
        self.assertEqual(parse_dependency_output("z\na\na\n"), ("a", "z"))
        self.assertEqual(
            parse_file_output("/usr/bin/a\n/usr/share/doc/a\n"), ("/usr/bin/a", "/usr/share/doc/a")
        )

    @mock.patch("jarvis_tui.package_inventory._fixed_query")
    def test_enrichment_uses_fixed_local_queries(self, query):
        query.side_effect = ["libc\n", "app\n", "/usr/bin/app\n"]
        result = enrich_package("app")
        self.assertEqual(result["requires"], ("libc",))
        self.assertFalse(result["network_used"])
        self.assertEqual(query.call_args_list[0].args[0][:3], ["rpm", "-q", "--requires"])

    def test_advisories_require_explicit_network(self):
        with self.assertRaises(PermissionError):
            advisories()

    def test_package_name_cannot_be_option_injection(self):
        with self.assertRaises(ValueError):
            enrich_package("--query")

    @mock.patch("jarvis_tui.package_inventory._fixed_query")
    def test_documentation_uses_installed_rpm_metadata_only(self, query):
        query.side_effect = [
            "cargo|1.90.0|1.fc44|https://doc.rust-lang.org/cargo/\n",
            "/usr/share/doc/cargo/README.md\n",
        ]
        result = package_documentation("cargo")
        self.assertEqual(result["installed_version"], "1.90.0-1.fc44")
        self.assertEqual(result["rpm_url"], "https://doc.rust-lang.org/cargo/")
        self.assertFalse(result["network_used"])


if __name__ == "__main__":
    unittest.main()
