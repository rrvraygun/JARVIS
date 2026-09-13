#!/usr/bin/env python3
"""Validate the dependency-free JSON Schema subset used by Jarvis records."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any


def type_matches(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, True)


def validate(schema: dict[str, Any], value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if "anyOf" in schema:
        alternatives = [validate(option, value, path) for option in schema["anyOf"]]
        if not any(not item for item in alternatives):
            return [f"{path}: does not satisfy anyOf"]
    if "oneOf" in schema:
        alternatives = [validate(option, value, path) for option in schema["oneOf"]]
        if sum(not item for item in alternatives) != 1:
            return [f"{path}: does not satisfy exactly one oneOf branch"]
    expected = schema.get("type")
    if expected is not None:
        choices = expected if isinstance(expected, list) else [expected]
        if not any(type_matches(value, choice) for choice in choices):
            return [f"{path}: expected type {choices}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: does not equal const")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: not in enum")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < int(schema["minLength"]):
            errors.append(f"{path}: shorter than minLength")
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            errors.append(f"{path}: longer than maxLength")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            errors.append(f"{path}: does not match pattern")
        if schema.get("format") == "date-time":
            try:
                dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"{path}: invalid date-time")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: not above exclusiveMinimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            errors.append(f"{path}: fewer than minItems")
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            errors.append(f"{path}: more than maxItems")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: duplicate items")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                errors.extend(validate(schema["items"], item, f"{path}[{index}]"))
    if isinstance(value, dict):
        for required in schema.get("required", []):
            if required not in value:
                errors.append(f"{path}: missing required property {required}")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                errors.extend(validate(properties[key], item, f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: additional property {key}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schema", type=Path)
    parser.add_argument("instance", type=Path)
    args = parser.parse_args()
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    instance = json.loads(args.instance.read_text(encoding="utf-8"))
    errors = validate(schema, instance)
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
