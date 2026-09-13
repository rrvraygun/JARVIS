"""Digest-bound rolling checkpoints for one persisted conversation."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_CHECKPOINTS = 5
MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
SCHEMA_VERSION = 2


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


@dataclass(frozen=True)
class ConversationCheckpoint:
    checkpoint_id: str
    conversation_id: str
    user_message_key: str
    created_at: str
    entries: tuple[dict[str, Any], ...]
    journal_sequence: int
    action_task_ids: tuple[str, ...]
    schema_version: int = SCHEMA_VERSION
    checkpoint_digest: str = ""

    def binding_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "checkpoint_id": self.checkpoint_id,
            "conversation_id": self.conversation_id,
            "user_message_key": self.user_message_key,
            "created_at": self.created_at,
            "entries": self.entries,
            "journal_sequence": self.journal_sequence,
            "action_task_ids": self.action_task_ids,
        }

    def __post_init__(self) -> None:
        if (
            self.schema_version not in {1, SCHEMA_VERSION}
            or not self.checkpoint_id.startswith("checkpoint_")
            or not self.conversation_id
            or not self.user_message_key
            or self.journal_sequence < 0
            or len(self.entries) > 500
        ):
            raise ValueError("invalid conversation checkpoint")
        expected = _digest(self.binding_payload())
        if not self.checkpoint_digest:
            object.__setattr__(self, "checkpoint_digest", expected)
        elif self.checkpoint_digest != expected:
            raise ValueError("conversation checkpoint digest mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {**self.binding_payload(), "checkpoint_digest": self.checkpoint_digest}

    @classmethod
    def create(
        cls,
        *,
        conversation_id: str,
        user_message_key: str,
        entries: list[dict[str, Any]],
        journal_sequence: int,
        action_task_ids: tuple[str, ...] = (),
    ) -> "ConversationCheckpoint":
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        seed = _digest(
            {
                "conversation_id": conversation_id,
                "user_message_key": user_message_key,
                "created_at": timestamp,
                "entries": entries,
            }
        )[:24]
        return cls(
            checkpoint_id=f"checkpoint_{seed}",
            conversation_id=conversation_id,
            user_message_key=user_message_key,
            created_at=timestamp,
            entries=tuple(entries),
            journal_sequence=journal_sequence,
            action_task_ids=tuple(action_task_ids),
        )


class ConversationCheckpointStore:
    """Owner-only atomic storage, retaining five user-message checkpoints."""

    def __init__(self, root: Path) -> None:
        self.root = root / "checkpoints"

    def _path(self, conversation_id: str) -> Path:
        if not conversation_id.startswith("conv_") or "/" in conversation_id:
            raise ValueError("invalid checkpoint conversation id")
        return self.root / f"{conversation_id}.json"

    def load(self, conversation_id: str) -> tuple[ConversationCheckpoint, ...]:
        path = self._path(conversation_id)
        try:
            info = path.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or not stat.S_ISREG(info.st_mode)
                or info.st_size > MAX_DOCUMENT_BYTES
            ):
                return ()
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("schema_version") not in {
                1,
                SCHEMA_VERSION,
            }:
                return ()
            rows = value.get("checkpoints")
            if not isinstance(rows, list) or len(rows) > MAX_CHECKPOINTS:
                return ()
            checkpoints = tuple(
                ConversationCheckpoint(
                    checkpoint_id=str(item["checkpoint_id"]),
                    conversation_id=str(item["conversation_id"]),
                    user_message_key=str(item["user_message_key"]),
                    created_at=str(item["created_at"]),
                    entries=tuple(dict(entry) for entry in item["entries"]),
                    journal_sequence=int(item["journal_sequence"]),
                    action_task_ids=tuple(
                        str(task_id) for task_id in item.get("action_task_ids", ())
                    ),
                    schema_version=int(item.get("schema_version", 0)),
                    checkpoint_digest=str(item.get("checkpoint_digest", "")),
                )
                for item in rows
                if isinstance(item, dict)
            )
            if len(checkpoints) != len(rows) or any(
                item.conversation_id != conversation_id for item in checkpoints
            ):
                return ()
            return checkpoints
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            return ()

    def save(self, checkpoint: ConversationCheckpoint) -> tuple[ConversationCheckpoint, ...]:
        existing = [
            item
            for item in self.load(checkpoint.conversation_id)
            if item.user_message_key != checkpoint.user_message_key
        ]
        values = tuple([*existing, checkpoint][-MAX_CHECKPOINTS:])
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        path = self._path(checkpoint.conversation_id)
        payload = json.dumps(
            {"schema_version": SCHEMA_VERSION, "checkpoints": [item.to_dict() for item in values]},
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ).encode()
        fd, name = tempfile.mkstemp(prefix=".checkpoint.", suffix=".tmp", dir=self.root)
        temporary = Path(name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                fd = -1
                stream.write(payload)
                stream.write(b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            os.chmod(path, 0o600)
        finally:
            if fd >= 0:
                os.close(fd)
            temporary.unlink(missing_ok=True)
        return values
