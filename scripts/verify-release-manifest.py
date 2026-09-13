#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "release-manifest.json").read_text())
errors = []
if not manifest.get("files"):
    raise SystemExit("empty release manifest")
for item in manifest["files"]:
    path = root / item["path"]
    if not path.is_file():
        errors.append(f"missing: {item['path']}")
        continue
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != item["sha256"]:
        errors.append(f"hash mismatch: {item['path']}")
if errors:
    raise SystemExit("\n".join(errors))
print(f"verified {len(manifest['files'])} entries")
