"""Versioned, fail-closed specialist registry and user selection state."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .specialists import REGISTERED_TOOL_REFS, Specialist, load_specialists

MAX_DEFINITION_BYTES = 128_000
MAX_SELECTION_BYTES = 1_024


@dataclass(frozen=True)
class AgentValidation:
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class AgentRegistry:
    """Load reviewed plugin definitions and safe user-level active overrides."""

    def __init__(self, bundle_root: Path) -> None:
        self.bundle_root = bundle_root.resolve()
        self.override_dir = self.bundle_root / "runtime/agent-definitions"
        self.history_dir = self.override_dir / "history"
        self.selection_path = self.bundle_root / "runtime/agent-selection.json"
        self._base: dict[str, Specialist] = {
            item.id: item for item in load_specialists(self.bundle_root)
        }
        self._definitions: dict[str, Specialist] = dict(self._base)
        self._load_overrides()

    def all(self) -> tuple[Specialist, ...]:
        return tuple(
            sorted(self._definitions.values(), key=lambda item: item.display_name.casefold())
        )

    def selectable(self) -> tuple[Specialist, ...]:
        return tuple(item for item in self.all() if item.selectable and item.status == "enabled")

    def get(self, specialist_id: str) -> Specialist | None:
        return self._definitions.get(specialist_id)

    def default(self) -> Specialist | None:
        return (
            self.get("jarvis-system-architect") or (self.selectable() or self.all() or (None,))[0]
        )

    def selected(self) -> Specialist | None:
        value = self._read_selection()
        selected = self.get(value) if value else None
        if selected is not None and selected.selectable and selected.status == "enabled":
            return selected
        return self.default()

    def select(self, specialist_id: str) -> Specialist:
        selected = self.get(specialist_id)
        if selected is None or not selected.selectable or selected.status != "enabled":
            raise ValueError("specialist selection rejected: agent is unavailable")
        self._atomic_write_json(
            self.selection_path, {"schema_version": 1, "id": selected.id}, 0o600
        )
        return selected

    def draft(self, specialist_id: str) -> dict[str, Any]:
        specialist = self.get(specialist_id)
        if specialist is None:
            raise ValueError("unknown specialist")
        return specialist.to_dict()

    @staticmethod
    def validate(value: Any, *, expected_id: str | None = None) -> AgentValidation:
        errors: list[str] = []
        if not isinstance(value, dict):
            return AgentValidation(False, ("definition must be a JSON object",))
        known_fields = {
            "schema_version",
            "id",
            "display_name",
            "version",
            "purpose",
            "prompt",
            "knowledge_kinds",
            "knowledge_sources",
            "capabilities",
            "allowed_tools",
            "context_limit",
            "retention",
            "mutations",
            "network",
            "selectable",
            "status",
        }
        unknown_fields = sorted(set(value) - known_fields)
        if unknown_fields:
            errors.append("unknown fields: " + ", ".join(unknown_fields))
        if expected_id is not None and value.get("id") != expected_id:
            errors.append("agent id cannot be changed in the editor")
        try:
            Specialist.from_mapping(value)
        except (TypeError, ValueError) as exc:
            errors.append(str(exc))
        tools = value.get("allowed_tools")
        if isinstance(tools, list):
            unknown = sorted(set(tools) - REGISTERED_TOOL_REFS)
            if unknown:
                errors.append("unregistered tools: " + ", ".join(unknown))
        warnings: tuple[str, ...]
        if value.get("network") == "official-allowlist" and not value.get("knowledge_sources"):
            warnings = (
                "official-allowlist network is declared without explicit knowledge sources",
            )
        else:
            warnings = ()
        try:
            encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
            if len(encoded) > MAX_DEFINITION_BYTES:
                errors.append("definition exceeds the bounded size")
        except (TypeError, ValueError):
            errors.append("definition is not JSON serializable")
        return AgentValidation(not errors, tuple(errors), warnings)

    def activate(self, value: dict[str, Any]) -> Specialist:
        specialist_id = value.get("id")
        if not isinstance(specialist_id, str) or specialist_id not in self._base:
            raise ValueError("only reviewed installed agents may be activated")
        result = self.validate(value, expected_id=specialist_id)
        if not result.valid:
            raise ValueError("agent definition is invalid: " + "; ".join(result.errors))
        normalized = dict(value)
        normalized["schema_version"] = 2
        normalized["status"] = "enabled"
        specialist = Specialist.from_mapping(
            normalized, source=str(self.override_dir / f"{specialist_id}.json")
        )
        current_path = self.override_dir / f"{specialist_id}.json"
        try:
            if current_path.exists() or current_path.is_symlink():
                current_info = current_path.lstat()
                if stat.S_ISLNK(current_info.st_mode) or not stat.S_ISREG(current_info.st_mode):
                    raise ValueError("existing agent definition is unsafe")
                current = json.loads(current_path.read_text(encoding="utf-8"))
            else:
                current = self._base[specialist_id].to_dict()
            if (
                isinstance(current, dict)
                and self.validate(current, expected_id=specialist_id).valid
            ):
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                self._atomic_write_json(
                    self.history_dir / f"{specialist_id}-{stamp}.json", current, 0o600
                )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            raise ValueError("existing agent definition could not be archived safely")
        self._atomic_write_json(self.override_dir / f"{specialist_id}.json", normalized, 0o600)
        self._definitions[specialist_id] = specialist
        return specialist

    def rollback(self, specialist_id: str) -> Specialist:
        """Restore the newest archived active definition for one installed agent."""
        if specialist_id not in self._base:
            raise ValueError("unknown specialist")
        candidates = sorted(self.history_dir.glob(f"{specialist_id}-*.json"), reverse=True)
        if not candidates:
            raise ValueError("no archived agent definition is available")
        target = candidates[0]
        info = target.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise ValueError("archived agent definition is unsafe")
        value = json.loads(target.read_text(encoding="utf-8"))
        result = self.validate(value, expected_id=specialist_id)
        if not result.valid:
            raise ValueError("archived agent definition is invalid")
        restored = Specialist.from_mapping(
            value, source=str(self.override_dir / f"{specialist_id}.json")
        )
        self._atomic_write_json(self.override_dir / f"{specialist_id}.json", value, 0o600)
        self._definitions[specialist_id] = restored
        return restored

    def has_rollback(self, specialist_id: str) -> bool:
        return bool(tuple(self.history_dir.glob(f"{specialist_id}-*.json")))

    def reset(self, specialist_id: str) -> Specialist:
        if specialist_id not in self._base:
            raise ValueError("unknown specialist")
        target = self.override_dir / f"{specialist_id}.json"
        try:
            info = target.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise ValueError("agent override is not a regular file")
            target.unlink()
        except FileNotFoundError:
            pass
        self._definitions[specialist_id] = self._base[specialist_id]
        return self._definitions[specialist_id]

    def _load_overrides(self) -> None:
        try:
            info = self.override_dir.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                return
        except FileNotFoundError:
            return
        except OSError:
            return
        for path in sorted(self.override_dir.glob("jarvis-*.json")):
            try:
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                    continue
                if info.st_size > MAX_DEFINITION_BYTES:
                    continue
                value = json.loads(path.read_text(encoding="utf-8"))
                specialist_id = value.get("id") if isinstance(value, dict) else None
                if specialist_id not in self._base:
                    continue
                if not self.validate(value, expected_id=specialist_id).valid:
                    continue
                self._definitions[specialist_id] = Specialist.from_mapping(value, source=str(path))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue

    def _read_selection(self) -> str | None:
        try:
            info = self.selection_path.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or not stat.S_ISREG(info.st_mode)
                or info.st_size > MAX_SELECTION_BYTES
            ):
                return None
            value = json.loads(self.selection_path.read_text(encoding="utf-8"))
            selected = value.get("id") if isinstance(value, dict) else None
            return selected if isinstance(selected, str) else None
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def _atomic_write_json(path: Path, value: dict[str, Any], mode: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        parent_info = path.parent.lstat()
        if stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode):
            raise ValueError("agent state directory is unsafe")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, mode)
            encoded = (
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            if len(encoded) > MAX_DEFINITION_BYTES:
                raise ValueError("agent state exceeds the bounded size")
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            os.chmod(path, mode)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)
