"""Refuse to launch isolated build code without effective cgroup v2 limits."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def check_limits(cgroup: Path) -> bool:
    try:
        memory = int((cgroup / "memory.max").read_text().strip())
        processes = int((cgroup / "pids.max").read_text().strip())
        quota, period = map(int, (cgroup / "cpu.max").read_text().split())
        return 0 < memory <= 1073741824 and 0 < processes <= 32 and 0 < quota <= period
    except (OSError, ValueError):
        return False


def main() -> int:
    rows = Path("/proc/self/cgroup").read_text().splitlines()
    entry = next((row[3:] for row in rows if row.startswith("0::")), None)
    if entry is None or ".." in Path(entry).parts:
        print("Build refused: effective resource limits are unavailable.")
        return 78
    if len(sys.argv) < 5 or sys.argv[4] != "/usr/bin/bwrap":
        return 78
    receipt, identity, digest = sys.argv[1:4]
    if (
        len(identity) != 32
        or len(digest) != 64
        or not entry.endswith("/jarvis-build-" + identity + ".service")
    ):
        return 78
    group = Path("/sys/fs/cgroup") / entry.lstrip("/")
    info = group.stat()
    parent = os.open(str(Path(receipt).parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        descriptor = os.open(
            Path(receipt).name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent,
        )
        with os.fdopen(descriptor, "w") as stream:
            json.dump(
                {
                    "id": identity,
                    "digest": digest,
                    "cgroup": entry,
                    "identity": [info.st_dev, info.st_ino],
                    "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                },
                stream,
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent)
    finally:
        os.close(parent)
    if not check_limits(group):
        print("Build refused: effective resource limits are unavailable.")
        return 78
    os.execv(sys.argv[4], sys.argv[4:])
    return 78


if __name__ == "__main__":
    raise SystemExit(main())
