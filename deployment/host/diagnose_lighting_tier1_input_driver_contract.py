#!/usr/bin/env python3
"""Report only candidate hotkey input driver names rejected by Tier-1."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path

MAX_INPUT_ENTRIES = 512
MAX_NAME_BYTES = 256
INPUT_NAME = re.compile(r"^input[0-9]+$")
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.:+@-]{1,192}$")
INPUT_RELEVANT = re.compile(
    r"(?i)(?:keyboard|hotkey|wmi|acpi|video bus|ideapad|thinkpad|dell|hp|asus|"
    r"acer|msi|clevo|tuxedo|alienware|razer|gigabyte|aorus|framework|at translated set 2)"
)


class DiagnosticError(ValueError):
    """A bounded diagnostic contract violation."""


def resolve_inside(path: Path, root: Path) -> Path:
    root_resolved = root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise DiagnosticError("input-metadata-path-escaped-sysfs") from None
    return resolved


def read_name(path: Path, sys_root: Path) -> str:
    resolved = resolve_inside(path, sys_root)
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise DiagnosticError("input-name-not-regular")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(resolved, flags)
    try:
        value = os.read(descriptor, MAX_NAME_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(value) > MAX_NAME_BYTES or b"\x00" in value:
        raise DiagnosticError("input-name-malformed")
    try:
        text = value.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        raise DiagnosticError("input-name-invalid-utf8") from None
    if (
        not text
        or len(text) > 192
        or any(ord(character) < 32 or ord(character) == 127 for character in text)
    ):
        raise DiagnosticError("input-name-malformed")
    return text


def diagnose(sys_root: Path) -> dict[str, object]:
    sys_root = sys_root.resolve(strict=True)
    base = sys_root / "class/input"
    resolve_inside(base, sys_root)
    with os.scandir(base) as iterator:
        names = sorted(entry.name for entry in iterator)
    if len(names) > MAX_INPUT_ENTRIES:
        raise DiagnosticError("input-entry-limit-exceeded")
    candidates = 0
    rejected = []
    for input_entry in names:
        if not INPUT_NAME.fullmatch(input_entry):
            continue
        input_path = base / input_entry
        try:
            name = read_name(input_path / "name", sys_root)
        except FileNotFoundError:
            continue
        if not INPUT_RELEVANT.search(name):
            continue
        candidates += 1
        try:
            driver_target = resolve_inside(input_path / "device/driver", sys_root)
        except FileNotFoundError:
            continue
        driver = driver_target.name
        if SAFE_NAME.fullmatch(driver):
            continue
        encoded = driver.encode("utf-8", errors="strict")
        rejected.append(
            {
                "input": input_entry,
                "input_name": name,
                "driver_name": driver,
                "driver_utf8_sha256": hashlib.sha256(encoded).hexdigest(),
                "driver_codepoints": [f"U+{ord(character):04X}" for character in driver],
                "driver_length": len(driver),
            }
        )
    return {
        "schema_version": 1,
        "diagnostic": "lighting-tier1-input-driver-name-contract",
        "scope": "/sys/class/input candidate names and driver symlink basenames only",
        "input_class_entries": len(names),
        "candidate_inputs": candidates,
        "rejected_entries": rejected,
        "raw_input_events_read": False,
        "state_change": False,
    }


def main() -> int:
    print(json.dumps(diagnose(Path("/sys")), sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DiagnosticError, OSError, UnicodeError) as exc:
        print(json.dumps({"status": "blocked", "code": str(exc)}, sort_keys=True))
        raise SystemExit(3)
