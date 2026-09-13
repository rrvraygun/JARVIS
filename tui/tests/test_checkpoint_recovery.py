from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis_tui.checkpoint_recovery import recovery_binding


class CheckpointRecoveryTests(unittest.TestCase):
    def events(self):
        return (
            {"event_type": "package.transaction.execution.reserved", "task_id": "task_a"},
            {
                "event_type": "package.transaction.completed",
                "task_id": "task_a",
                "status": "completed",
                "details": {"record_digest": "a" * 64},
            },
        )

    def test_exact_completed_package_receipt(self):
        self.assertEqual(recovery_binding(self.events()), "a" * 64)
        self.assertIsNone(recovery_binding(()))

    def test_unknown_and_unsettled_mutations_block_full_restore(self):
        for events in (
            self.events()[:1],
            self.events()[1:],
            self.events() * 2,
            ({"event_type": "registered_mutation.execution.reserved"},),
            ({"event_type": "local_mutation.completed"},),
        ):
            with self.subTest(events=events), self.assertRaises(ValueError):
                recovery_binding(events)

    def test_mismatched_or_unverified_receipt_rejected(self):
        for change in ({"status": "indeterminate"}, {"task_id": "task_b"}, {"details": {}}):
            reserved, completed = self.events()
            completed.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                recovery_binding((reserved, completed))
