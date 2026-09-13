#!/usr/bin/env python3
"""Report only relevant platform-driver names rejected by the Tier-1 grammar."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

MAX_PLATFORM_DRIVERS = 1024
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.:+@-]{1,192}$")
INTERFACE_RELEVANT = re.compile(
    r"(?i)(?:backlight|kbd|keyboard|hotkey|wmi|acpi|video|ideapad|thinkpad|"
    r"dell|hp[_-]|asus|acer|msi|clevo|tuxedo|alienware|razer|gigabyte|aorus|framework)"
)


class DiagnosticError(ValueError):
    """A bounded diagnostic contract violation."""


def resolve_inside(path: Path, root: Path) -> Path:
    root_resolved = root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise DiagnosticError("platform-driver-root-escaped-sysfs") from None
    return resolved


def diagnose(sys_root: Path) -> dict[str, object]:
    sys_root = sys_root.resolve(strict=True)
    base = sys_root / "bus/platform/drivers"
    resolve_inside(base, sys_root)
    with os.scandir(base) as iterator:
        names = sorted(entry.name for entry in iterator)
    if len(names) > MAX_PLATFORM_DRIVERS:
        raise DiagnosticError("platform-driver-entry-limit-exceeded")
    relevant = [name for name in names if INTERFACE_RELEVANT.search(name)]
    rejected = []
    for name in relevant:
        if SAFE_NAME.fullmatch(name):
            continue
        encoded = name.encode("utf-8", errors="strict")
        rejected.append(
            {
                "name": name,
                "utf8_sha256": hashlib.sha256(encoded).hexdigest(),
                "codepoints": [f"U+{ord(character):04X}" for character in name],
                "length": len(name),
            }
        )
    return {
        "schema_version": 1,
        "diagnostic": "lighting-tier1-platform-driver-name-contract",
        "scope": "/sys/bus/platform/drivers entry names only",
        "platform_driver_entries": len(names),
        "relevant_entries": len(relevant),
        "rejected_entries": rejected,
        "files_read_inside_entries": 0,
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
