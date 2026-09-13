from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


TUI_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = TUI_ROOT.parent
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.actions import ActionRegistry  # noqa: E402
from jarvis_tui.broker import JarvisBroker  # noqa: E402
from jarvis_tui.event_store import EventJournal  # noqa: E402
from jarvis_tui.local_filesystem import LocalFilesystemPlanner  # noqa: E402
from jarvis_tui.local_mutation import (  # noqa: E402
    BoundedLocalFilesystemMutationExecutor,
    LocalFilesystemMutationPlanner,
    LocalMutationReviewer,
)
from jarvis_tui.models import AdmissionRoute, OneUseApproval  # noqa: E402


class Ids:
    def __init__(self) -> None:
        self.index = 0

    def __call__(self, prefix: str) -> str:
        self.index += 1
        return f"{prefix}_{self.index}"


class LocalMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.home = root / "home"
        self.desktop = self.home / "Escritorio"
        self.workspace = root / "workspace"
        self.desktop.mkdir(parents=True)
        self.workspace.mkdir()
        config = self.home / ".config/user-dirs.dirs"
        config.parent.mkdir()
        config.write_text('XDG_DESKTOP_DIR="$HOME/Escritorio"\n', encoding="utf-8")
        (self.home / ".local/share/Trash/files").mkdir(parents=True)
        (self.home / ".local/share/Trash/info").mkdir(parents=True)
        self.ids = Ids()
        read_planner = LocalFilesystemPlanner(
            self.workspace,
            home=self.home,
            xdg_config=config,
            identifier=self.ids,
        )
        self.planner = LocalFilesystemMutationPlanner(read_planner, identifier=self.ids)
        self.executor = BoundedLocalFilesystemMutationExecutor(home=self.home)
        registry = ActionRegistry.load(
            BUNDLE_ROOT / "plugins/jarvis-system-admin/registry/actions.json"
        )
        self.journal = EventJournal(root / "events.jsonl")
        self.broker = JarvisBroker(
            registry,
            self.journal,
            identifier=self.ids,
            filesystem_planner=read_planner,
            mutation_planner=self.planner,
            mutation_reviewer=LocalMutationReviewer(),
            mutation_executor=self.executor,
            workspace=self.workspace,
        )

    def test_exact_desktop_directory_create_is_local_reviewed_and_once_only(self) -> None:
        task = self.broker.capture_text("create a new directory in Escritorio named Proyecto2")
        assessment = self.broker.assess_deterministic_task(task)
        self.assertIsNotNone(assessment)
        admission = self.broker.admit(task)
        self.assertEqual(admission.route, AdmissionRoute.LOCAL_MUTATION)
        self.assertTrue(admission.approval_required)
        self.assertFalse(admission.execution_authorized)
        self.assertFalse((self.desktop / "Proyecto2").exists())
        approval = self.broker.create_local_mutation_approval(task)
        result = asyncio.run(self.broker.execute_local_filesystem_mutation(task, approval))
        self.assertEqual(result.status, "completed")
        self.assertTrue((self.desktop / "Proyecto2").is_dir())
        with self.assertRaisesRegex(RuntimeError, "approved reviewed plan"):
            asyncio.run(self.broker.execute_local_filesystem_mutation(task, approval))
        journal = json.dumps(self.journal.read())
        self.assertNotIn("Proyecto2", journal)
        self.assertIn("local_mutation.execution.reserved", journal)

    def test_spanish_and_absolute_create_forms(self) -> None:
        spanish = self.planner.plan("crear una carpeta en Escritorio llamada ProyectoDos")
        self.assertIsNotNone(spanish.plan)
        absolute = self.planner.plan(f"create directory {self.workspace / 'absolute-target'}")
        self.assertIsNotNone(absolute.plan)
        self.assertEqual(absolute.plan.target_path, str(self.workspace / "absolute-target"))

    def test_sensitive_existing_and_symlink_targets_fail_closed(self) -> None:
        sensitive = self.planner.plan("create a directory in Escritorio named credentials")
        self.assertEqual(sensitive.denial_code, "local_mutation.invalid_name")
        existing = self.desktop / "existing"
        existing.mkdir()
        collision = self.planner.plan("create a directory in Escritorio named existing")
        self.assertEqual(collision.denial_code, "local_mutation.target_exists")
        link = self.desktop / "linked"
        link.symlink_to(existing, target_is_directory=True)
        denied = self.planner.plan(f"delete directory {link}")
        self.assertEqual(denied.denial_code, "local_mutation.symlink_target_denied")

    def test_move_to_trash_is_reversible_and_replay_is_rejected(self) -> None:
        target = self.desktop / "old.txt"
        target.write_text("fixture", encoding="utf-8")
        planned = self.planner.plan(f"delete file {target}")
        self.assertIsNotNone(planned.plan)
        plan = planned.plan
        assert plan is not None
        review = LocalMutationReviewer().review(plan)
        approval = OneUseApproval(
            "approval_fixture", plan.plan_digest, review.review_digest, "2026-08-26T00:00:00Z"
        )
        result = asyncio.run(self.executor.execute(plan, review, approval))
        self.assertEqual(result.status, "completed")
        self.assertFalse(target.exists())
        self.assertEqual(len(tuple((self.home / ".local/share/Trash/files").iterdir())), 1)
        replay = asyncio.run(self.executor.execute(plan, review, approval))
        self.assertEqual(replay.error_code, "local_mutation.approval_replayed")

    def test_trash_rechecks_source_inode_immediately_before_rename(self) -> None:
        target = self.desktop / "replaceable.txt"
        target.write_text("approved inode", encoding="utf-8")
        planned = self.planner.plan(f"delete file {target}")
        plan = planned.plan
        assert plan is not None
        review = LocalMutationReviewer().review(plan)
        approval = OneUseApproval(
            "approval_race",
            plan.plan_digest,
            review.review_digest,
            "2026-08-27T00:00:00Z",
        )
        original_trash = self.executor._trash

        def replace_then_trash(parent_fd, name, source, bound_plan):
            target.unlink()
            target.write_text("replacement inode", encoding="utf-8")
            return original_trash(parent_fd, name, source, bound_plan)

        with mock.patch.object(self.executor, "_trash", side_effect=replace_then_trash):
            result = asyncio.run(self.executor.execute(plan, review, approval))

        self.assertEqual(result.error_code, "local_mutation.trash_changed")
        self.assertEqual(target.read_text(encoding="utf-8"), "replacement inode")
        self.assertEqual(tuple((self.home / ".local/share/Trash/files").iterdir()), ())

    def test_special_and_hidden_mutation_targets_are_denied(self) -> None:
        fifo = self.desktop / "fixture-pipe"
        import os

        os.mkfifo(fifo)
        special = self.planner.plan(f"delete file {fifo}")
        self.assertEqual(special.denial_code, "local_mutation.special_file_denied")
        hidden = self.planner.plan("create a directory in Escritorio named .private")
        self.assertEqual(hidden.denial_code, "local_mutation.invalid_name")

    def test_post_write_durability_failure_is_reported_as_indeterminate(self) -> None:
        planned = self.planner.plan("create a new directory in Escritorio named MaybeCreated")
        plan = planned.plan
        assert plan is not None
        review = LocalMutationReviewer().review(plan)
        approval = OneUseApproval(
            "approval_indeterminate",
            plan.plan_digest,
            review.review_digest,
            "2026-08-27T00:00:00Z",
        )
        with mock.patch("jarvis_tui.local_mutation.os.fsync", side_effect=OSError("fixture")):
            result = asyncio.run(self.executor.execute(plan, review, approval))
        self.assertEqual(result.error_code, "local_mutation.outcome_indeterminate")
        self.assertTrue(result.rollback_available)
        self.assertTrue((self.desktop / "MaybeCreated").is_dir())


if __name__ == "__main__":
    unittest.main()
