from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis_tui.conversation_checkpoints import (  # noqa: E402
    ConversationCheckpoint,
    ConversationCheckpointStore,
)


class ConversationCheckpointTests(unittest.TestCase):
    def checkpoint(self, conversation_id: str, key: str, sequence: int) -> ConversationCheckpoint:
        return ConversationCheckpoint.create(
            conversation_id=conversation_id,
            user_message_key=key,
            entries=[{"key": key, "role": "user", "text": key, "status": "completed"}],
            journal_sequence=sequence,
        )

    def test_store_retains_five_newest_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConversationCheckpointStore(Path(directory))
            for index in range(6):
                store.save(self.checkpoint("conv_test", f"task:{index}", index))
            values = store.load("conv_test")
            self.assertEqual(len(values), 5)
            self.assertEqual(
                [item.user_message_key for item in values], [f"task:{i}" for i in range(1, 6)]
            )

    def test_checkpoint_digest_mismatch_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConversationCheckpointStore(Path(directory))
            path = store.root / "conv_test.json"
            store.save(self.checkpoint("conv_test", "task:1", 1))
            value = json.loads(path.read_text())
            value["checkpoints"][0]["checkpoint_digest"] = "0" * 64
            path.write_text(json.dumps(value))
            self.assertEqual(store.load("conv_test"), ())


if __name__ == "__main__":
    unittest.main()
