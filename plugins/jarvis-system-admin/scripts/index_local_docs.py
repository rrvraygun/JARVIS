#!/usr/bin/env python3
"""Index allowlisted local Bash/man documentation without administering the host."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry/commands/bash-fedora.json"
SAFE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
SAFE_NAME = re.compile(r"^[a-zA-Z0-9_.+-]+$")
MAX_DOC_BYTES = 2 * 1024 * 1024


def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def run_document_command(argv: list[str]) -> tuple[int, str]:
    environment = {
        "PATH": SAFE_PATH,
        "LANG": "C.UTF-8",
        "LC_ALL": "C",
        "MANPAGER": "cat",
        "PAGER": "cat",
        "MANWIDTH": "120",
    }
    completed = subprocess.run(
        argv,
        cwd="/",
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=20,
        check=False,
    )
    output = completed.stdout[:MAX_DOC_BYTES].decode("utf-8", errors="replace")
    return completed.returncode, output


def local_doc(command: dict[str, Any]) -> dict[str, Any] | None:
    name = str(command["executable"])
    if not SAFE_NAME.fullmatch(name):
        raise ValueError(f"unsafe command name: {name}")
    methods = command.get("docs", [])
    attempts: list[tuple[str, list[str]]] = []
    man = shutil.which("man", path=SAFE_PATH)
    bash = shutil.which("bash", path=SAFE_PATH)
    executable = shutil.which(name, path=SAFE_PATH)
    if "bash-help" in methods and bash:
        attempts.append(("bash-help", [bash, "--noprofile", "--norc", "-c", f"help -- {name}"]))
    if "man" in methods and man:
        attempts.append(("man", [man, name]))
    if executable and command.get("safe_help"):
        attempts.append(("safe-help", [executable, *command["safe_help"][0:1]]))
    for method, argv in attempts:
        status, content = run_document_command(argv)
        if status == 0 and content.strip():
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            return {
                "source_id": f"local-{command['id']}-{content_hash[:16]}",
                "source_class": "installed-documentation",
                "authority_tier": 0,
                "title": f"{name} local {method}",
                "publisher": "installed Fedora system",
                "locator": f"local:{method}:{name}",
                "applicable_versions": {
                    "executable_path": executable,
                    "method": method,
                },
                "retrieved_at": timestamp(),
                "content_hash": content_hash,
                "content": content,
                "complete": True,
                "community_confirmation_required": False,
            }
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    if args.preview:
        print(
            json.dumps(
                {
                    "commands": [item["id"] for item in registry["commands"]],
                    "network": False,
                },
                indent=2,
            )
        )
        return 0
    if args.registry.resolve() != REGISTRY.resolve():
        raise ValueError("custom documentation registries are not an execution interface")
    if args.output.exists():
        raise ValueError("refusing_to_overwrite_existing_output")
    records = [
        record for command in registry["commands"] if (record := local_doc(command)) is not None
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=args.output.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.chmod(0o600)
    os.replace(temporary, args.output)
    print(json.dumps({"output": str(args.output), "documents": len(records), "mode": "read-only"}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError,
        ValueError,
        KeyError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
