#!/usr/bin/env python3
"""Prepare a candidate profile only; never overwrite an active config or copy auth."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tui/src"))
from jarvis_tui.private_records import directory  # noqa: E402
from jarvis_tui.runtime_profile import render  # noqa: E402

if __name__ == "__main__":
    parent = directory(ROOT / "runtime/codex-home")
    try:
        fd = os.open(
            "config.candidate.toml",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent,
        )
        with os.fdopen(fd, "w") as stream:
            stream.write(render(ROOT))
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent)
    finally:
        os.close(parent)
    print("Prepared config.candidate.toml. Activation and authentication remain separate.")
