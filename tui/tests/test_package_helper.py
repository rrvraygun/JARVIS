from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

BUNDLE_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = BUNDLE_ROOT / "vm-lab/scripts/jarvis_package_control.py"
SPEC = importlib.util.spec_from_file_location("jarvis_package_control_fixture", HELPER_PATH)
assert SPEC is not None and SPEC.loader is not None
helper = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = helper
SPEC.loader.exec_module(helper)


class PackageHelperTests(unittest.TestCase):
    def test_status_without_record_returns_bounded_empty_state(self) -> None:
        with (
            mock.patch.object(helper, "_uid", return_value=1000),
            mock.patch.object(helper, "_lock", return_value=mock.Mock()),
            mock.patch.object(
                helper,
                "_load",
                side_effect=helper.PackageControlError(
                    "no package transaction recovery record exists"
                ),
            ),
        ):
            result = helper.status()
        self.assertEqual(result["record_status"], "none")
        self.assertEqual(result["packages"], [])
        self.assertEqual(result["record_digest"], "0" * 64)

    def test_dnf5_summary_counts_never_become_resolved_package_names(self) -> None:
        output = (
            "Removing:\n demo.x86_64 1 repo 1 MiB\n"
            "Removing dependent packages:\n dependent.noarch 1 repo 1 MiB\n"
            "Transaction Summary:\n Removing: 2 packages\n"
            "Operation aborted by the user.\nCannot open log file\n"
        )
        self.assertEqual(helper._removed_packages(output), ("demo", "dependent"))

    def test_preview_digest_ignores_dnf_log_housekeeping(self) -> None:
        stable = "Installing:\n golang.x86_64 1 repo 1 MiB\nTransaction Summary:\n"
        noisy = stable + "Last metadata expiration check: 1 second ago\nCannot open log file\n"
        self.assertEqual(helper._canonicalize_preview(stable), helper._canonicalize_preview(noisy))

    def test_dnf5_table_overrides_unstructured_removal_status(self) -> None:
        output = (
            "Removing:\n transient-status\n"
            "Package Arch Version Repository Size\n"
            " demo x86_64 1 repo 1 MiB\n"
            " dependent noarch 1 repo 1 MiB\n"
            "Transaction Summary:\n Removing: 2 packages\n"
        )
        self.assertEqual(helper._removed_packages(output), ("demo", "dependent"))

    def test_dnf5_table_resolves_install_roots_when_heading_is_localized(self) -> None:
        output = (
            "Resolved transaction (localized output)\n"
            "Package Arch Version Repository Size\n"
            " golang x86_64 1 fedora 50 MiB\n"
            " golang-bin x86_64 1 fedora 10 MiB\n"
            "Transaction Summary:\n Installing: 2 packages\n"
        )
        self.assertEqual(helper._installed_packages(output), ("golang", "golang-bin"))

    def test_install_heading_and_table_views_are_unioned(self) -> None:
        output = (
            "Installing:\n golang.x86_64 1 repo 50 MiB\n"
            "Package Arch Version Repository Size\n"
            " golang x86_64 1 repo 50 MiB\n"
            " golang-bin x86_64 1 repo 10 MiB\n"
            "Transaction Summary:\n Installing: 2 packages\n"
        )
        self.assertEqual(helper._installed_packages(output), ("golang", "golang-bin"))

    def test_inline_install_heading_keeps_root(self) -> None:
        output = "Installing: golang.x86_64 1 repo 50 MiB\nTransaction Summary:\n"
        self.assertEqual(helper._installed_packages(output), ("golang",))

    def test_nevra_row_extracts_root_name(self) -> None:
        self.assertEqual(helper._row_package_name("golang-1.25.0-1.fc42.x86_64"), "golang")

    def test_indexed_dnf_table_extracts_package_before_architecture(self) -> None:
        output = (
            "Package Architecture Version Repository Size\n"
            " 1 golang x86_64 1.25 fedora 50 MiB\n"
            " 2 golang-bin x86_64 1.25 fedora 100 MiB\n"
        )
        self.assertEqual(helper._installed_packages(output), ("golang", "golang-bin"))

    def test_heading_rows_with_separate_architecture_are_packages(self) -> None:
        output = (
            "Installing dependencies:\n golang x86_64\n golang-bin x86_64\n golang-src noarch\n"
        )
        self.assertEqual(helper._installed_packages(output), ("golang", "golang-bin", "golang-src"))

    def test_installing_packages_heading_is_supported(self) -> None:
        output = "Installing packages:\n golang x86_64\n golang-bin x86_64\n"
        self.assertEqual(helper._installed_packages(output), ("golang", "golang-bin"))

    def test_prepared_record_is_reconciled_only_when_exact_pre_state_remains(self) -> None:
        record = {
            "operation": "remove",
            "names": ["demo"],
            "affected_removals": ["demo"],
            "pre_state": {"demo": "demo|0|1|1.x86_64"},
            "preview_digest": "a" * 64,
            "status": "prepared",
        }
        digest = helper._record_digest(record)
        with (
            mock.patch.object(helper, "_uid", return_value=1000),
            mock.patch.object(helper, "_lock", return_value=mock.Mock()),
            mock.patch.object(helper, "_load", return_value=record),
            mock.patch.object(helper, "_installed", return_value=record["pre_state"]),
            mock.patch.object(helper, "_delete_record") as delete_record,
            mock.patch.object(helper, "_run") as run,
        ):
            result = helper.undo(digest)
        self.assertEqual(result["operation"], "reconcile")
        delete_record.assert_called_once_with(1000)
        run.assert_not_called()

    def test_prepared_record_with_state_drift_is_not_cleared(self) -> None:
        record = {
            "operation": "remove",
            "names": ["demo"],
            "affected_removals": ["demo"],
            "pre_state": {"demo": "demo|0|1|1.x86_64"},
            "preview_digest": "a" * 64,
            "status": "prepared",
        }
        digest = helper._record_digest(record)
        with (
            mock.patch.object(helper, "_uid", return_value=1000),
            mock.patch.object(helper, "_lock", return_value=mock.Mock()),
            mock.patch.object(helper, "_load", return_value=record),
            mock.patch.object(helper, "_installed", return_value={"demo": None}),
            mock.patch.object(helper, "_delete_record") as delete_record,
        ):
            with self.assertRaisesRegex(helper.PackageControlError, "partial mutation"):
                helper.undo(digest)
        delete_record.assert_not_called()

    def test_applied_record_archives_before_retiring_active_record(self) -> None:
        record = {
            "operation": "install",
            "names": ["demo"],
            "affected_installs": ["demo"],
            "pre_state": {"demo": None},
            "post_state": {"demo": "demo|0|1|1.x86_64"},
            "preview_digest": "a" * 64,
            "status": "applied",
        }
        digest = helper._record_digest(record)
        with (
            mock.patch.object(helper, "_uid", return_value=1000),
            mock.patch.object(helper, "_lock", return_value=mock.Mock()),
            mock.patch.object(helper, "_load", return_value=record),
            mock.patch.object(helper, "_archive_record") as archive_record,
            mock.patch.object(helper, "_delete_record") as delete_record,
        ):
            result = helper.archive(digest)
        self.assertEqual(result["operation"], "archive")
        archive_record.assert_called_once_with(1000, record, digest)
        delete_record.assert_called_once_with(1000)

    def test_install_binds_and_verifies_every_resolved_addition(self) -> None:
        preview = (
            "Installing:\n"
            " demo.x86_64 1 repo 1 MiB\n"
            "Installing dependencies:\n"
            " dependent.noarch 1 repo 1 MiB\n"
            "Transaction Summary:\n"
        )
        preview_digest = helper.hashlib.sha256(preview.encode()).hexdigest()
        pre_state = {"demo": None, "dependent": None}
        approval_digest = helper._digest("install", ("demo",), pre_state, preview_digest)
        writes: list[dict] = []
        lock = mock.Mock()
        with (
            mock.patch.object(helper, "_uid", return_value=1000),
            mock.patch.object(helper, "_lock", return_value=lock),
            mock.patch.object(helper, "_preview", return_value=preview),
            mock.patch.object(
                helper,
                "_installed",
                side_effect=[pre_state, {"demo": "installed", "dependent": "installed"}],
            ),
            mock.patch.object(
                helper, "_record_path", return_value=mock.Mock(**{"exists.return_value": False})
            ),
            mock.patch.object(
                helper, "_write", side_effect=lambda _uid, value: writes.append(value)
            ),
            mock.patch.object(helper, "_run", return_value="") as transaction,
        ):
            result = helper.apply(["demo"], preview_digest, approval_digest)

        self.assertEqual(result["status"], "passed")
        transaction.assert_called_once_with(["dnf", "-y", "install", "demo"])
        self.assertEqual(writes[0]["affected_installs"], ["demo", "dependent"])
        self.assertEqual(set(writes[1]["post_state"]), {"demo", "dependent"})

    def test_install_rejects_non_additive_version_effects_before_writing(self) -> None:
        preview = (
            "Installing:\n demo.x86_64 1 repo 1 MiB\n"
            "Upgrading:\n existing.x86_64 2 repo 1 MiB\n"
            "Transaction Summary:\n"
        )
        preview_digest = helper.hashlib.sha256(preview.encode()).hexdigest()
        lock = mock.Mock()
        with (
            mock.patch.object(helper, "_uid", return_value=1000),
            mock.patch.object(helper, "_lock", return_value=lock),
            mock.patch.object(helper, "_preview", return_value=preview),
            mock.patch.object(helper, "_write") as write,
            mock.patch.object(helper, "_run") as transaction,
        ):
            with self.assertRaisesRegex(helper.PackageControlError, "strictly additive"):
                helper.apply(["demo"], preview_digest, "b" * 64)
        write.assert_not_called()
        transaction.assert_not_called()

    def test_remove_binds_verifies_and_records_every_resolved_removal(self) -> None:
        preview = (
            "Removing:\n"
            " demo.x86_64 1 repo 1 MiB\n"
            " dependent.noarch 1 repo 1 MiB\n"
            "Transaction Summary:\n"
        )
        preview_digest = helper.hashlib.sha256(preview.encode()).hexdigest()
        pre_state = {"demo": "demo|0|1|1.x86_64", "dependent": "dependent|0|1|1.noarch"}
        approval_digest = helper._digest("remove", ("demo",), pre_state, preview_digest)
        transaction_runs: list[list[str]] = []
        writes: list[dict] = []
        lock = mock.Mock()

        with (
            mock.patch.object(helper, "_uid", return_value=1000),
            mock.patch.object(helper, "_lock", return_value=lock),
            mock.patch.object(helper, "_preview", return_value=preview),
            mock.patch.object(
                helper, "_installed", side_effect=[pre_state, {"demo": None, "dependent": None}]
            ),
            mock.patch.object(
                helper, "_record_path", return_value=mock.Mock(**{"exists.return_value": False})
            ),
            mock.patch.object(
                helper, "_write", side_effect=lambda _uid, value: writes.append(value)
            ),
            mock.patch.object(
                helper, "_run", side_effect=lambda argv: transaction_runs.append(argv) or ""
            ),
        ):
            result = helper.remove(["demo"], preview_digest, approval_digest)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(
            transaction_runs,
            [["dnf", "-y", "remove", "--no-autoremove", "demo"]],
        )
        self.assertEqual(writes[0]["affected_removals"], ["demo", "dependent"])
        self.assertEqual(set(writes[0]["pre_state"]), {"demo", "dependent"})
        self.assertEqual(set(writes[1]["post_state"]), {"demo", "dependent"})
        lock.close.assert_called_once()

    def test_undo_of_removal_restores_entire_recorded_pre_state(self) -> None:
        record = {
            "operation": "remove",
            "names": ["demo"],
            "affected_removals": ["demo", "dependent"],
            "pre_state": {
                "demo": "demo|0|1|1.x86_64",
                "dependent": "dependent|2|3|4.noarch",
            },
            "post_state": {"demo": None, "dependent": None},
            "preview_digest": "a" * 64,
            "status": "applied",
        }
        digest = helper._record_digest(record)
        transaction_runs: list[list[str]] = []
        lock = mock.Mock()
        with (
            mock.patch.object(helper, "_uid", return_value=1000),
            mock.patch.object(helper, "_lock", return_value=lock),
            mock.patch.object(helper, "_load", return_value=record),
            mock.patch.object(helper, "_delete_record") as delete_record,
            mock.patch.object(
                helper,
                "_preview",
                return_value=(
                    "Installing:\n demo.x86_64 1 repo 1 MiB\n"
                    " dependent.noarch 3 repo 1 MiB\nTransaction Summary:\n"
                ),
            ),
            mock.patch.object(
                helper, "_run", side_effect=lambda argv: transaction_runs.append(argv) or ""
            ),
            mock.patch.object(
                helper,
                "_installed",
                return_value={
                    "demo": "demo|0|1|1.x86_64",
                    "dependent": "dependent|2|3|4.noarch",
                },
            ),
        ):
            result = helper.undo(digest)

        self.assertEqual(
            transaction_runs,
            [
                [
                    "dnf",
                    "-y",
                    "install",
                    "demo-1-1.x86_64",
                    "dependent-2:3-4.noarch",
                ]
            ],
        )
        self.assertEqual(set(result["packages"]), {"demo", "dependent"})
        delete_record.assert_called_once_with(1000)
        lock.close.assert_called_once()

    def test_undo_of_install_removes_only_packages_absent_from_pre_state(self) -> None:
        record = {
            "operation": "install",
            "names": ["demo"],
            "affected_installs": ["demo", "dependent", "already-present"],
            "pre_state": {"demo": None, "dependent": None, "already-present": "old-nevra"},
            "post_state": {"demo": "new", "dependent": "new", "already-present": "old-nevra"},
            "preview_digest": "b" * 64,
            "status": "applied",
        }
        digest = helper._record_digest(record)
        with (
            mock.patch.object(helper, "_uid", return_value=1000),
            mock.patch.object(helper, "_lock", return_value=mock.Mock()),
            mock.patch.object(helper, "_load", return_value=record),
            mock.patch.object(helper, "_delete_record") as delete_record,
            mock.patch.object(
                helper,
                "_preview",
                return_value=(
                    "Removing:\n demo.x86_64 1 repo 1 MiB\n"
                    " dependent.noarch 1 repo 1 MiB\nTransaction Summary:\n"
                ),
            ),
            mock.patch.object(helper, "_run", return_value="") as transaction,
            mock.patch.object(helper, "_installed", return_value={"demo": None, "dependent": None}),
        ):
            helper.undo(digest)

        transaction.assert_called_once_with(
            ["dnf", "-y", "remove", "--no-autoremove", "demo", "dependent"]
        )
        delete_record.assert_called_once_with(1000)

    def test_rollback_refuses_new_transaction_effects_outside_record(self) -> None:
        record = {
            "operation": "remove",
            "names": ["demo"],
            "affected_removals": ["demo"],
            "pre_state": {"demo": "demo|0|1|1.x86_64"},
            "post_state": {"demo": None},
            "preview_digest": "c" * 64,
            "status": "applied",
        }
        digest = helper._record_digest(record)
        with (
            mock.patch.object(helper, "_uid", return_value=1000),
            mock.patch.object(helper, "_lock", return_value=mock.Mock()),
            mock.patch.object(helper, "_load", return_value=record),
            mock.patch.object(
                helper,
                "_preview",
                return_value=(
                    "Installing:\n demo.x86_64 1 repo 1 MiB\n"
                    " extra.noarch 1 repo 1 MiB\nTransaction Summary:\n"
                ),
            ),
            mock.patch.object(helper, "_run") as transaction,
        ):
            with self.assertRaisesRegex(helper.PackageControlError, "outside the recorded set"):
                helper.undo(digest)
        transaction.assert_not_called()


if __name__ == "__main__":
    unittest.main()
