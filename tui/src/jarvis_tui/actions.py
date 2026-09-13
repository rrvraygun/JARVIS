"""Versioned action-catalog loading and parameter validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ActionDefinition


def _matches_type(value: Any, expected: str) -> bool:
    return {
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "null": value is None,
    }.get(expected, False)


def validate_parameters(schema: dict[str, Any], parameters: dict[str, Any]) -> None:
    if schema.get("type") != "object":
        raise ValueError("action input_schema must describe an object")
    missing = sorted(set(schema.get("required", [])) - parameters.keys())
    if missing:
        raise ValueError(f"missing action parameters: {', '.join(missing)}")
    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        unknown = sorted(parameters.keys() - properties.keys())
        if unknown:
            raise ValueError(f"unknown action parameters: {', '.join(unknown)}")
    for key, value in parameters.items():
        rule = properties.get(key, {})
        if "enum" in rule and value not in rule["enum"]:
            raise ValueError(f"parameter {key} is not an allowed value")
        expected = rule.get("type")
        choices = expected if isinstance(expected, list) else [expected] if expected else []
        if choices and not any(_matches_type(value, item) for item in choices):
            raise ValueError(f"parameter {key} has the wrong type")
        if isinstance(value, str) and len(value) < int(rule.get("minLength", 0)):
            raise ValueError(f"parameter {key} is too short")


class ActionRegistry:
    def __init__(self, actions: list[ActionDefinition]) -> None:
        self._actions = {action.id: action for action in actions}
        if len(self._actions) != len(actions):
            raise ValueError("duplicate action id")

    @classmethod
    def load(cls, path: Path) -> ActionRegistry:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version") != 1:
            raise ValueError("unsupported action registry schema")
        return cls([ActionDefinition.from_dict(item) for item in data.get("actions", [])])

    def all(self) -> tuple[ActionDefinition, ...]:
        return tuple(sorted(self._actions.values(), key=lambda item: (item.category, item.title)))

    def get(self, action_id: str) -> ActionDefinition:
        try:
            return self._actions[action_id]
        except KeyError as exc:
            raise ValueError(f"unknown action: {action_id}") from exc

    def search(self, text: str) -> tuple[ActionDefinition, ...]:
        words = {part.casefold() for part in text.split() if part}
        if not words:
            return self.all()
        matches = []
        for action in self._actions.values():
            haystack = " ".join((action.id, action.title, action.summary, *action.tags)).casefold()
            if all(word in haystack for word in words):
                matches.append(action)
        return tuple(sorted(matches, key=lambda item: (item.category, item.title)))

    def validate_selection(self, action_id: str, parameters: dict[str, Any]) -> ActionDefinition:
        action = self.get(action_id)
        if action.availability != "enabled":
            reason = action.unavailable_reason or f"action is {action.availability}"
            raise ValueError(reason)
        validate_parameters(action.input_schema, parameters)
        return action
