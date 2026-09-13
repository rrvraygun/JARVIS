#!/usr/bin/env python3
"""Generate a deterministic source manifest without modifying live profiles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
excluded_parts = {
    "runtime",
    "control-store",
    "__pycache__",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
}
excluded_names = {"release-manifest.json"}
files = []
for path in sorted(root.rglob("*")):
    if (
        not path.is_file()
        or excluded_parts.intersection(path.relative_to(root).parts)
        or path.name in excluded_names
    ):
        continue
    relative = path.relative_to(root).as_posix()
    files.append(
        {
            "path": relative,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": path.stat().st_size,
        }
    )
manifest = {
    "schema_version": 1,
    "version": (root / "VERSION").read_text().strip(),
    "files": files,
}
(root / "release-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
print(f"wrote {len(files)} entries")
