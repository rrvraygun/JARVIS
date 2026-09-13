#!/usr/bin/env python3
"""Collect one bounded, unprivileged Fedora inventory; never retries or mutates."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
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
REGISTRY = ROOT / "registry/collectors/fedora-workstation.json"
SAFE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
DEFAULT_SIGNATURES = {
    ("uname", "-rmo"),
    ("bash", "--version"),
    ("rpm", "--eval", "%fedora"),
    ("rpm", "-q", "fedora-release-workstation"),
    ("rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}\\n", "dnf5"),
    ("flatpak", "--version"),
    ("rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}\\n", "rpm-ostree"),
    ("lscpu", "--json"),
    ("free", "--bytes"),
    ("lspci", "-nn"),
    ("lsusb",),
    ("lsblk", "--json", "--output", "NAME,TYPE,SIZE,FSTYPE,FSVER,MOUNTPOINTS"),
    ("findmnt", "--json", "--output", "TARGET,SOURCE,FSTYPE,OPTIONS", "/"),
    ("systemctl", "--version"),
    ("systemd-detect-virt",),
    ("getenforce",),
    ("mokutil", "--sb-state"),
    ("rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}\\n", "podman"),
    ("docker", "--version"),
    ("virsh", "--version"),
    ("qemu-system-x86_64", "--version"),
    ("btrfs", "version"),
    ("rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}\\n", "lvm2"),
    ("rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}\\n", "snapper"),
}

spec = importlib.util.spec_from_file_location(
    "knowledge_store", ROOT / "scripts/knowledge_store.py"
)
ks = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(ks)


def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def parse_output(kind: str, output: str) -> Any:
    clean = output.strip()
    if kind == "json":
        return json.loads(clean)
    if kind == "first-line":
        return clean.splitlines()[0] if clean else ""
    if kind == "lines":
        return clean.splitlines()
    return clean


def resolve(executable: str) -> str | None:
    if "/" in executable or executable in {"sudo", "su", "doas", "pkexec"}:
        raise ValueError("collector executable is not allowed")
    return shutil.which(executable, path=SAFE_PATH)


def collect(config: dict[str, Any], fixture_mode: bool = False) -> dict[str, Any]:
    if config.get("attempt_limit") != 1:
        raise ValueError("collector must enforce exactly one attempt")
    collected_at = timestamp()
    facts: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    environment = {"PATH": SAFE_PATH, "LANG": "C.UTF-8", "LC_ALL": "C"}
    for command in config["commands"]:
        argv = [str(value) for value in command["argv"]]
        if not fixture_mode and tuple(argv) not in DEFAULT_SIGNATURES:
            raise ValueError(
                f"collector signature is not compiled into the read-only allowlist: {argv}"
            )
        executable = resolve(argv[0])
        attempt_id = f"inventory-{command['id']}-{hashlib.sha256((collected_at + command['id']).encode()).hexdigest()[:16]}"
        base = {
            "attempt_id": attempt_id,
            "requested_at": collected_at,
            "executable": executable or argv[0],
            "argv": argv[1:],
            "cwd_class": "collector-isolated",
            "environment_keys": sorted(environment),
            "purpose": f"read-only inventory: {command['fact_key']}",
            "expected": {
                "success_codes": command.get("success_codes", [0]),
                "parser": command["parser"],
            },
            "privacy_class": "internal",
            "evidence": [{"collector": config["id"], "version": config["version"]}],
        }
        if not executable:
            attempts.append(
                {
                    **base,
                    "actual": {"reason": "executable unavailable"},
                    "exit_code": None,
                    "timed_out": False,
                    "outcome": "unavailable",
                    "output_excerpt": "",
                    "output_bytes": 0,
                }
            )
            continue
        try:
            completed = subprocess.run(
                [executable, *argv[1:]],
                cwd="/",
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=int(config["timeout_seconds"]),
                check=False,
            )
            raw = completed.stdout
            oversized = len(raw) > int(config["max_output_bytes"])
            raw = raw[: int(config["max_output_bytes"])]
            output = ks.redact_text(raw.decode("utf-8", errors="replace"))
            success = completed.returncode in command.get("success_codes", [0]) and not oversized
            parsed: Any = None
            parse_error: str | None = None
            forbidden_pattern = command.get("forbidden_output_regex")
            if success and forbidden_pattern and re.search(forbidden_pattern, output):
                success = False
                parse_error = "forbidden_output_pattern"
            if success:
                try:
                    parsed = parse_output(command["parser"], output)
                except (ValueError, json.JSONDecodeError) as exc:
                    success = False
                    parse_error = type(exc).__name__
            if success:
                outcome = "success"
            elif command.get("optional") and completed.returncode != 0 and not output.strip():
                outcome = "unavailable"
            else:
                outcome = "unexpected" if completed.returncode == 0 else "failure"
            actual = {
                "exit_code": completed.returncode,
                "oversized": oversized,
                "parse_error": parse_error,
            }
            attempts.append(
                {
                    **base,
                    "actual": actual,
                    "exit_code": completed.returncode,
                    "timed_out": False,
                    "outcome": outcome,
                    "output_excerpt": output[:65536],
                    "output_bytes": len(raw),
                }
            )
            if outcome == "success":
                facts.append(
                    {
                        "fact_id": command["fact_key"],
                        "fact_key": command["fact_key"],
                        "value": parsed,
                        "value_type": command["parser"],
                        "collected_at": collected_at,
                        "collector": config["id"],
                        "collector_version": config["version"],
                        "source_attempt_id": attempt_id,
                        "privacy_class": "internal",
                        "prerequisites": {
                            "executable": executable,
                            "argv": argv[1:],
                            "observation_scope": command.get(
                                "observation_scope",
                                "enrolled workstation visible through Codex sandbox",
                            ),
                        },
                        "status": "current",
                    }
                )
        except subprocess.TimeoutExpired as exc:
            output = ks.redact_text((exc.stdout or b"").decode("utf-8", errors="replace"))
            attempts.append(
                {
                    **base,
                    "actual": {"reason": "timeout"},
                    "exit_code": None,
                    "timed_out": True,
                    "outcome": "failure",
                    "output_excerpt": output[:65536],
                    "output_bytes": len(output.encode()),
                }
            )
    return {
        "schema_version": 1,
        "collector": config["id"],
        "collector_version": config["version"],
        "collected_at": collected_at,
        "privacy": {"sensitive_collection": False, "redacted": True},
        "attempts": attempts,
        "facts": facts,
    }


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    if path.exists():
        raise ValueError("refusing_to_overwrite_existing_output")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.chmod(0o600)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--fixture-mode", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    config = json.loads(args.registry.read_text(encoding="utf-8"))
    if args.preview:
        if args.registry.resolve() == REGISTRY.resolve():
            uncompiled = [
                command["argv"]
                for command in config["commands"]
                if tuple(command["argv"]) not in DEFAULT_SIGNATURES
            ]
            if uncompiled:
                raise ValueError(f"collector registry contains uncompiled signatures: {uncompiled}")
        print(json.dumps({"collector": config["id"], "commands": config["commands"]}, indent=2))
        return 0
    if args.registry.resolve() != REGISTRY.resolve() and not args.fixture_mode:
        raise ValueError(
            "custom collector registry requires test fixture mode and is not a deployment interface"
        )
    atomic_write(args.output, collect(config, fixture_mode=args.fixture_mode))
    print(json.dumps({"output": str(args.output), "mode": "read-only", "attempt_limit": 1}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
