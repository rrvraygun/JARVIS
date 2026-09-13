#!/usr/bin/env python3
from __future__ import annotations

import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

TUI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.conversation_manager import (  # noqa: E402
    ConversationManager,
    ConversationStorageError,
)


class ConversationManagerPrivacyTests(unittest.TestCase):
    def test_all_visible_roles_and_state_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manager = ConversationManager(Path(temporary) / "conversations")
            conversation = manager.new_conversation()
            manager.add_message(
                "user",
                "install go",
                {
                    "key": "task:1",
                    "status": "completed",
                    "specialist_id": "jarvis-installation-specialist",
                    "specialist_version": "1.0.0",
                },
            )
            manager.add_message(
                "jarvis",
                "Which package?\nOptions: golang / go-task",
                {"key": "local:1", "status": "needs_clarification", "task_id": "task-1"},
            )
            manager.add_message("action", "package.install", {"key": "action:1"})
            manager.add_message("system", "approval requested", {"key": "system:1"})
            loaded = manager.load_conversation(conversation.id)
            assert loaded is not None
            self.assertEqual(
                [item["role"] for item in loaded.messages], ["user", "jarvis", "action", "system"]
            )
            self.assertEqual(loaded.messages[1]["status"], "needs_clarification")
            self.assertEqual(loaded.messages[1]["task_id"], "task-1")
            self.assertEqual(loaded.messages[0]["specialist_id"], "jarvis-installation-specialist")

    def test_storage_is_private_and_persisted_text_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            storage = Path(temporary) / "conversations"
            manager = ConversationManager(storage)
            manager.new_conversation()
            manager.add_message(
                "user",
                "token=never-persist-this\nAKIAABCDEFGHIJKLMNOP\nvisible\x1b]0;forged-title\x07",
            )
            files = tuple(storage.glob("conv_*.json"))
            self.assertEqual(len(files), 1)
            self.assertEqual(stat.S_IMODE(storage.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(files[0].stat().st_mode), 0o600)
            encoded = files[0].read_text(encoding="utf-8")
            self.assertNotIn("never-persist-this", encoded)
            self.assertNotIn("AKIAABCDEFGHIJKLMNOP", encoded)
            self.assertNotIn("\x1b", encoded)
            self.assertIn("token=[redacted]", encoded)
            self.assertEqual(json.loads(encoded)["messages"][0]["role"], "user")

    def test_rejects_path_traversal_and_symlinked_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            storage = Path(temporary) / "conversations"
            manager = ConversationManager(storage)
            with self.assertRaises(ConversationStorageError):
                manager.load_conversation("../../outside")
            target = Path(temporary) / "outside.json"
            target.write_text("{}", encoding="utf-8")
            link = storage / "conv_20260828_120000_000000.json"
            link.symlink_to(target)
            with self.assertRaises(ConversationStorageError):
                manager.load_conversation("conv_20260828_120000_000000")
            with self.assertRaises(ConversationStorageError):
                manager.delete_conversation("conv_20260828_120000_000000")

    def test_atomic_save_leaves_no_temporary_document(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            storage = Path(temporary) / "conversations"
            manager = ConversationManager(storage)
            conversation = manager.new_conversation()
            manager.add_message("user", "saved once")
            manager.save_conversation(conversation)
            self.assertEqual(len(tuple(storage.glob("*.tmp"))), 0)
            loaded = manager.load_conversation(conversation.id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.messages[0]["content"], "saved once")  # type: ignore[union-attr]

    def test_snapshot_isolated_from_later_in_memory_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manager = ConversationManager(
                Path(temporary) / "conversations", auto_save_enabled=False
            )
            conversation = manager.new_conversation()
            conversation.add_message("user", "first")
            snapshot = json.loads(json.dumps(conversation.to_dict()))
            conversation.add_message("agent", "later")
            manager.save_snapshot(snapshot)
            loaded = manager.load_conversation(conversation.id)
            assert loaded is not None
            self.assertEqual([item["content"] for item in loaded.messages], ["first"])


if __name__ == "__main__":
    unittest.main()
