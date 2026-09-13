import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis_tui.package_inventory import (
    PackagePreviewError,
    REPOSITORY_FIELDS,
    _preview_dnf_install,
    _preview_dnf_remove,
    _preview_installed_packages,
    _preview_removed_packages,
    build_relationships,
    package_view,
    page_records,
    parse_repository_output,
    parse_rpm_output,
    preview_install_transaction,
    preview_remove_transaction,
    recommend_cached_packages,
    recommendation_record,
)


class PackageAvailabilityTests(unittest.TestCase):
    def test_available_combined_and_update_views(self):
        installed = parse_rpm_output("demo|1|1|x86_64|Fedora|Demo package\n")
        available = parse_repository_output(
            "demo|0|2|1|x86_64|updates|Fedora|MIT|Demo package\nnewpkg|0|1|1|noarch|fedora|Fedora|MIT|New package\n"
        )
        self.assertEqual(len(package_view(installed, available, "available")), 2)
        self.assertEqual(len(package_view(installed, available, "combined")), 3)
        updates = package_view(installed, available[:1], "updates")
        self.assertEqual(updates[0]["state"], "update-candidate")
        self.assertEqual(updates[0]["installed_nevra"], "demo-1-1.x86_64")

    def test_available_rows_label_same_category_installed_alternatives(self):
        installed = parse_rpm_output("nvidia-driver|1|1|x86_64|NVIDIA|NVIDIA graphics driver\n")
        available = parse_repository_output(
            "cuda-toolkit|0|1|1|x86_64|fedora|Fedora|MIT|NVIDIA compute toolkit\n"
        )
        row = package_view(installed, available, "available")[0]
        self.assertEqual(row["origin"], "fedora")
        self.assertIn("NVIDIA graphics", row["purpose"])
        self.assertEqual(row["installed_alternatives"], ("nvidia-driver",))

    def test_dnf_repository_format_uses_a_real_record_newline(self):
        self.assertTrue(REPOSITORY_FIELDS.endswith("\n"))
        self.assertNotIn("\\\\n", REPOSITORY_FIELDS)

    def test_relationships_distinguish_conflicts_and_similarity(self):
        values = build_relationships(
            conflicts=(("a", "b"),),
            providers=(("a", "video-driver"), ("c", "video-driver")),
            similarities=(("a", "d"),),
        )
        mapping = {(item.relation, item.authoritative) for item in values}
        self.assertIn(("conflicts", True), mapping)
        self.assertIn(("alternative-provider", True), mapping)
        self.assertIn(("similar-purpose", False), mapping)

    def test_pagination_is_bounded(self):
        self.assertEqual(
            page_records(tuple(range(250)), page=1, page_size=100), tuple(range(100, 200))
        )
        with self.assertRaises(ValueError):
            page_records((), page=-1)

    def test_recommendation_is_labeled_inferred(self):
        value = recommendation_record(
            goal="NVIDIA GPU compute",
            candidates=(
                {
                    "name": "cuda",
                    "category": "nvidia/gpu",
                    "purpose": "GPU compute",
                    "evidence": "sourced:fedora",
                },
                {"name": "editor", "category": "development", "purpose": "text editor"},
            ),
        )
        self.assertEqual(value["recommendation"], "cuda")
        self.assertEqual(value["recommendation_label"], "inferred")
        self.assertFalse(value["installation_performed"])

    def test_cached_recommendation_resolves_rust_with_repository_evidence(self):
        available = parse_repository_output(
            "rust|0|1.90.0|1.fc44|x86_64|updates|Fedora|MIT|Rust programming language\ncargo|0|1.90.0|1.fc44|x86_64|updates|Fedora|MIT|Rust package manager\n"
        )
        value = recommend_cached_packages("install latest rust", (), available)
        self.assertEqual(value["recommendation"], "rust")
        self.assertEqual(value["candidates"][0]["origin"], "updates")
        self.assertFalse(value["network_used"])

    @mock.patch("jarvis_tui.package_inventory._preview_dnf_install")
    @mock.patch("jarvis_tui.package_inventory.subprocess.run")
    def test_install_preview_is_cache_only_and_non_mutating(self, run, preview):
        preview.return_value = "Installing:\n rust.x86_64 1 repo 1 MiB\nInstalling dependencies:\n llvm.x86_64 1 repo 1 MiB\nTransaction Summary:\n"
        run.return_value = mock.Mock(returncode=1, stdout="")
        value = preview_install_transaction(("rust",))
        self.assertFalse(value["mutated"])
        self.assertTrue(value["requires_fresh_approval"])
        self.assertTrue(value["transaction_resolved"])
        self.assertEqual(value["affected_installs"], ["llvm", "rust"])
        self.assertEqual(set(value["pre_state"]), {"llvm", "rust"})
        self.assertEqual(preview.call_args.args[0], ("rust",))

    @mock.patch("jarvis_tui.package_inventory._preview_dnf_install")
    @mock.patch("jarvis_tui.package_inventory.subprocess.run")
    def test_install_preview_rejects_removing_an_installed_package(self, run, preview):
        run.return_value = mock.Mock(returncode=1, stdout="")
        preview.return_value = "Transaction Summary:\n Removing: 1 package\n"
        with self.assertRaisesRegex(RuntimeError, "removing or replacing"):
            preview_install_transaction(("rust",))

    @mock.patch("jarvis_tui.package_inventory.subprocess.run")
    def test_dnf5_preview_uses_valid_install_syntax(self, run):
        run.return_value = mock.Mock(
            returncode=1,
            stdout="Transaction Summary:\n Installing: 1 package\n",
            stderr="Operation aborted by the user.\n",
        )
        _preview_dnf_install(("rust", "cargo"), timeout_seconds=20)
        self.assertEqual(
            run.call_args.args[0],
            ["dnf", "--cacheonly", "--assumeno", "install", "rust", "cargo"],
        )

    @mock.patch("jarvis_tui.package_inventory.subprocess.run")
    def test_dnf5_preview_accepts_localized_summary(self, run):
        run.return_value = mock.Mock(
            returncode=1,
            stdout="Resumen de la transacción: Instalando: 5 paquetes\n",
            stderr="Operación cancelada por el usuario.\n",
        )
        self.assertIn("Resumen", _preview_dnf_install(("rust",), timeout_seconds=20))

    @mock.patch("jarvis_tui.package_inventory.subprocess.run")
    def test_remove_preview_disables_autoremove_and_matches_helper_scope(self, run):
        run.return_value = mock.Mock(
            returncode=1,
            stdout="Transaction Summary:\n Removing: 1 package\n",
            stderr="Operation aborted by the user.\n",
        )
        _preview_dnf_remove(("demo",), timeout_seconds=20)
        self.assertEqual(
            run.call_args.args[0],
            ["dnf", "--cacheonly", "--assumeno", "remove", "--no-autoremove", "demo"],
        )

    def test_remove_parser_reports_dependencies_and_protected_transactions(self):
        output = """Removing:\n demo.x86_64 1 repo 1 MiB\nRemoving dependent packages:\n helper.noarch 1 repo 1 MiB\nTransaction Summary:\n Removing: 2 packages\nOperation aborted by the user.\nCannot open log file\n"""
        self.assertEqual(_preview_removed_packages(output), ("demo", "helper"))

    def test_remove_table_overrides_unstructured_status_words(self):
        output = """Removing:\n transient-status\nPackage          Arch   Version  Repository  Size\n rust             x86_64 1        updates     1 MiB\n cargo            x86_64 1        updates     1 MiB\nTransaction Summary:\n Removing: 2 packages\n"""
        self.assertEqual(_preview_removed_packages(output), ("cargo", "rust"))

    def test_install_parser_reports_dependencies(self):
        output = "Installing:\n demo.x86_64 1 repo 1 MiB\nInstalling dependencies:\n helper.noarch 1 repo 1 MiB\nTransaction Summary:\n Installing: 2 packages\nOperation aborted by the user.\n"
        self.assertEqual(_preview_installed_packages(output), ("demo", "helper"))

    @mock.patch("jarvis_tui.package_inventory._preview_dnf_install")
    @mock.patch("jarvis_tui.package_inventory.subprocess.run")
    def test_install_preview_rejects_upgrade_reinstall_or_replace_sections(self, run, preview):
        run.return_value = mock.Mock(returncode=0, stdout="demo|0|1|1.x86_64")
        for heading in ("Upgrading", "Downgrading", "Reinstalling", "Replacing"):
            preview.return_value = (
                "Installing:\n demo.x86_64 1 repo 1 MiB\n"
                f"{heading}:\n existing.x86_64 2 repo 1 MiB\n"
                "Transaction Summary:\n"
            )
            with (
                self.subTest(heading=heading),
                self.assertRaisesRegex(RuntimeError, "additive transactions"),
            ):
                preview_install_transaction(("demo",))

    @mock.patch("jarvis_tui.package_inventory._preview_dnf_remove")
    @mock.patch("jarvis_tui.package_inventory.subprocess.run")
    def test_remove_preview_binds_dependency_set(self, run, preview):
        run.return_value = mock.Mock(returncode=0, stdout="demo|0|1|1.x86_64")
        preview.return_value = "Removing:\n demo.x86_64 1 repo 1 MiB\n helper.noarch 1 repo 1 MiB\nTransaction Summary:\n"
        value = preview_remove_transaction(("demo",))
        self.assertEqual(value["operation"], "remove")
        self.assertEqual(value["affected_removals"], ["demo", "helper"])
        self.assertEqual(set(value["pre_state"]), {"demo", "helper"})
        self.assertTrue(value["requires_fresh_approval"])

    @mock.patch("jarvis_tui.package_inventory._preview_dnf_remove")
    def test_remove_preview_reports_requested_root_missing_without_names(self, preview):
        preview.return_value = (
            "Removing:\n cargo.x86_64 1 repo 1 MiB\nTransaction Summary:\n Removing: 1 package\n"
        )
        with self.assertRaises(PackagePreviewError) as caught:
            preview_remove_transaction(("rust",))
        self.assertEqual(caught.exception.code, "package_preview.requested_root_missing")
        self.assertEqual(caught.exception.audit_details["requested_count"], 1)
        self.assertEqual(caught.exception.audit_details["resolved_count"], 1)
        self.assertNotIn("rust", str(caught.exception.audit_details))

    def test_remove_preview_rejects_protected_request_before_dnf(self):
        with self.assertRaises(PermissionError):
            preview_remove_transaction(("systemd",))


if __name__ == "__main__":
    unittest.main()
