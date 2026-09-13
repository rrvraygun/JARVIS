#!/usr/bin/python3 -I
"""Root entry point; requires the separately installed root-owned executor."""

import importlib.util
import json
import os
import stat
from pathlib import Path


def main() -> int:
    path = Path("/usr/libexec/jarvis_privileged_control.py")
    try:
        info = path.lstat()
        parent = path.parent.lstat()
        if (
            os.geteuid() != 0
            or not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & 0o022
            or info.st_nlink != 1
            or not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != 0
            or parent.st_mode & 0o022
        ):
            raise ValueError("executor_not_root_controlled")
        spec = importlib.util.spec_from_file_location("jarvis_privileged_control", path)
        if spec is None or spec.loader is None:
            raise ValueError("executor_unavailable")
        executor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(executor)
        return int(executor.main("boot"))
    except (OSError, ValueError):
        print(json.dumps({"status": "blocked", "error": "reviewed_root_executor_not_installed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
