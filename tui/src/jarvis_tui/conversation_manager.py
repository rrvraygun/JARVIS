"""Private, crash-safe persistence for the durable conversation projection."""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .terminal_safety import sanitize_and_redact_terminal_text

MAX_CONVERSATION_BYTES = 2 * 1024 * 1024
MAX_CONVERSATION_MESSAGES = 500
MAX_MESSAGE_CHARS = 64_000
CONVERSATION_ROLES = {"user", "agent", "jarvis", "action", "system", "activity"}
_CONVERSATION_ID = re.compile(r"conv_[0-9]{8}_[0-9]{6}_[0-9]{6}")


class ConversationStorageError(RuntimeError):
    """A safe, stable storage failure suitable for UI classification."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Conversation:
    """One terminal-sanitized, schema-compatible saved conversation."""

    def __init__(
        self,
        conversation_id: str | None = None,
        title: str = "New Conversation",
        messages: list[dict[str, Any]] | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
    ) -> None:
        self.id = conversation_id or self._generate_id()
        if not _CONVERSATION_ID.fullmatch(self.id):
            raise ConversationStorageError("conversation.invalid_id")
        self.title, _ = sanitize_and_redact_terminal_text(str(title)[:200])
        self.messages = self._normalized_messages(messages or [])
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()

    @staticmethod
    def _normalized_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(messages) > MAX_CONVERSATION_MESSAGES:
            raise ConversationStorageError("conversation.too_many_messages")
        normalized: list[dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, dict):
                raise ConversationStorageError("conversation.invalid_message")
            role = message.get("role")
            content = message.get("content")
            if role not in CONVERSATION_ROLES or not isinstance(content, str):
                raise ConversationStorageError("conversation.invalid_message")
            safe, _ = sanitize_and_redact_terminal_text(content[:MAX_MESSAGE_CHARS])
            normalized.append(_message_record(role, safe, message, len(normalized)))
        return normalized

    def add_message(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        if role not in CONVERSATION_ROLES:
            raise ConversationStorageError("conversation.invalid_role")
        if len(self.messages) >= MAX_CONVERSATION_MESSAGES:
            raise ConversationStorageError("conversation.too_many_messages")
        safe, _ = sanitize_and_redact_terminal_text(str(content)[:MAX_MESSAGE_CHARS])
        self.messages.append(_message_record(role, safe, metadata or {}, len(self.messages)))
        self.updated_at = datetime.now().isoformat()
        if len(self.messages) == 1 and role == "user":
            self.title = self._generate_title(safe)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "messages": self.messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Conversation:
        if not isinstance(data, dict):
            raise ConversationStorageError("conversation.invalid_document")
        messages = data.get("messages", [])
        if not isinstance(messages, list):
            raise ConversationStorageError("conversation.invalid_document")
        return cls(
            conversation_id=str(data.get("id", "")),
            title=str(data.get("title", "Untitled")),
            messages=messages,
            created_at=str(data.get("created_at", "")) or None,
            updated_at=str(data.get("updated_at", "")) or None,
        )

    @staticmethod
    def _generate_id() -> str:
        return f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

    @staticmethod
    def _generate_title(first_message: str) -> str:
        return first_message[:50].strip() + ("..." if len(first_message) > 50 else "")


class ConversationManager:
    """Own conversations; callers decide whether persistence is synchronous."""

    def __init__(self, storage_dir: Path | None = None, *, auto_save_enabled: bool = True) -> None:
        self.storage_dir = storage_dir or Path.home() / ".jarvis" / "conversations"
        self.storage_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = self.storage_dir.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise ConversationStorageError("conversation.storage_unsafe")
        os.chmod(self.storage_dir, 0o700)
        self.current_conversation: Conversation | None = None
        self.auto_save_enabled = auto_save_enabled

    @staticmethod
    def _validate_id(conversation_id: str) -> None:
        if not _CONVERSATION_ID.fullmatch(conversation_id):
            raise ConversationStorageError("conversation.invalid_id")

    def _path(self, conversation_id: str) -> Path:
        self._validate_id(conversation_id)
        return self.storage_dir / f"{conversation_id}.json"

    def new_conversation(self) -> Conversation:
        if (
            self.current_conversation
            and self.current_conversation.messages
            and self.auto_save_enabled
        ):
            self.save_conversation(self.current_conversation)
        self.current_conversation = Conversation()
        return self.current_conversation

    def add_message(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        if self.current_conversation is None:
            self.current_conversation = Conversation()
        self.current_conversation.add_message(role, content, metadata)
        if self.auto_save_enabled:
            self.save_conversation(self.current_conversation)

    def save_conversation(self, conversation: Conversation) -> None:
        path = self._path(conversation.id)
        encoded = json.dumps(conversation.to_dict(), indent=2, ensure_ascii=False).encode("utf-8")
        if len(encoded) > MAX_CONVERSATION_BYTES:
            raise ConversationStorageError("conversation.document_too_large")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{conversation.id}.", suffix=".tmp", dir=self.storage_dir
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            os.chmod(path, 0o600)
            directory = os.open(self.storage_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError as exc:
            raise ConversationStorageError("conversation.write_failed") from exc
        finally:
            temporary.unlink(missing_ok=True)

    def save_snapshot(self, value: dict[str, Any]) -> None:
        """Persist an immutable caller snapshot, never a live UI object."""
        self.save_conversation(Conversation.from_dict(value))

    def _load_path(self, path: Path) -> Conversation:
        descriptor = -1
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0))
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CONVERSATION_BYTES:
                raise ConversationStorageError("conversation.document_unsafe")
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = -1
                data = json.loads(stream.read().decode("utf-8"))
        except FileNotFoundError:
            raise
        except ConversationStorageError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConversationStorageError("conversation.read_failed") from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        return Conversation.from_dict(data)

    def load_conversation(self, conversation_id: str) -> Conversation | None:
        try:
            return self._load_path(self._path(conversation_id))
        except FileNotFoundError:
            return None

    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit < 1 or limit > MAX_CONVERSATION_MESSAGES:
            raise ConversationStorageError("conversation.invalid_limit")
        candidates: list[tuple[float, Path]] = []
        for path in self.storage_dir.glob("conv_*.json"):
            try:
                info = path.lstat()
                if stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode):
                    candidates.append((info.st_mtime, path))
            except OSError:
                continue
        rows: list[dict[str, Any]] = []
        for _, path in sorted(candidates, reverse=True)[:limit]:
            try:
                conversation = self._load_path(path)
            except (ConversationStorageError, FileNotFoundError):
                continue
            rows.append(
                {
                    "id": conversation.id,
                    "title": conversation.title,
                    "message_count": len(conversation.messages),
                    "created_at": conversation.created_at,
                    "updated_at": conversation.updated_at,
                }
            )
        return rows

    def delete_conversation(self, conversation_id: str) -> bool:
        path = self._path(conversation_id)
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise ConversationStorageError("conversation.document_unsafe")
            path.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise ConversationStorageError("conversation.delete_failed") from exc

    def resume_conversation(self, conversation_id: str) -> Conversation | None:
        conversation = self.load_conversation(conversation_id)
        if conversation is not None:
            self.current_conversation = conversation
        return conversation

    def get_current_conversation(self) -> Conversation | None:
        return self.current_conversation

    def replace_current_conversation(self, snapshot: dict[str, Any]) -> Conversation:
        """Replace active conversation from a validated checkpoint snapshot."""
        conversation = Conversation.from_dict(snapshot)
        self.current_conversation = conversation
        if self.auto_save_enabled:
            self.save_conversation(conversation)
        return conversation

    def format_conversation_for_display(self, conversation: Conversation | None = None) -> str:
        value = conversation or self.current_conversation
        if value is None:
            return ""
        lines: list[str] = []
        for message in value.messages:
            content, _ = sanitize_and_redact_terminal_text(str(message["content"]))
            timestamp = str(message.get("timestamp", ""))
            try:
                timestamp = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
            except ValueError:
                timestamp = ""
            heading = (
                f"[{timestamp}] {message['role'].upper()}:"
                if timestamp
                else f"{message['role'].upper()}:"
            )
            lines.extend((heading, content, ""))
        return "\n".join(lines)


def _message_record(
    role: str, content: str, metadata: dict[str, Any], index: int
) -> dict[str, Any]:
    """Build one bounded durable record, retaining visible entry identity/state."""
    key = str(metadata.get("key", f"history:{index}"))[:200]
    if not key:
        key = f"history:{index}"
    status = str(metadata.get("status", "completed"))[:64] or "completed"
    task_id = metadata.get("task_id")
    turn_id = metadata.get("turn_id")
    specialist_id = metadata.get("specialist_id")
    specialist_version = metadata.get("specialist_version")
    return {
        "key": key,
        "role": role,
        "content": content,
        "timestamp": str(metadata.get("timestamp", datetime.now().isoformat()))[:100],
        "status": status,
        "task_id": str(task_id)[:200] if task_id else None,
        "turn_id": str(turn_id)[:200] if turn_id else None,
        "specialist_id": str(specialist_id)[:200] if specialist_id else None,
        "specialist_version": str(specialist_version)[:100] if specialist_version else None,
        "metadata": {},
    }
