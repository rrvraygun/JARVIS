#!/usr/bin/env python3
"""Verify documentation links and the minimum living-documentation set."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
REQUIRED = (
    ROOT / "docs/README.md",
    ROOT / "docs/codebase-map.md",
    ROOT / "docs/generated/codebase-inventory.md",
    ROOT / "docs/audits/2026-08-28-codebase-audit.md",
    ROOT / "docs/sessions/2026-08-28-stabilization.md",
    ROOT / "docs/stabilization-backlog.md",
)


def main() -> int:
    errors: list[str] = []
    for path in REQUIRED:
        if not path.is_file():
            errors.append(f"missing living document: {path.relative_to(ROOT)}")
    for path in [ROOT / "AGENTS.md", ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]:
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            value = target.split("#", 1)[0]
            if not value or "://" in value or value.startswith("mailto:"):
                continue
            if not (path.parent / value).resolve().exists():
                errors.append(f"broken link: {path.relative_to(ROOT)} -> {target}")
    root_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    with (ROOT / "tui/pyproject.toml").open("rb") as stream:
        tui_version = tomllib.load(stream)["project"]["version"]
    expected_tui = root_version.replace("-dev", ".dev0")
    if tui_version != expected_tui:
        errors.append(f"version mismatch: VERSION={root_version}, tui={tui_version}")
    if errors:
        print("\n".join(errors))
        return 1
    print("documentation contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
