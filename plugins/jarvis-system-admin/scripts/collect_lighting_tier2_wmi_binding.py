#!/usr/bin/env python3
"""Collect passive NVIDIA WMI backlight binding metadata without method calls."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = PLUGIN_ROOT.parents[1]
REGISTRY = PLUGIN_ROOT / "registry/collectors/lighting-tier2-wmi-binding.json"
LIVE_OUTPUT_ROOT = BUNDLE_ROOT / "runtime/state/snapshots"
GUID = "603E9613-EF25-4338-A3D0-C46177516DB7"
GUID_INSTANCE = re.compile(r"^603E9613-EF25-4338-A3D0-C46177516DB7-[0-9A-Fa-f]{2}$", re.IGNORECASE)
SAFE_BACKLIGHT = re.compile(r"^[A-Za-z0-9_.:+-]{1,128}$")
BACKLIGHT_TYPES = {"raw", "platform", "firmware"}
MAX_WMI_DEVICES = 512
MAX_DRIVER_ENTRIES = 64
MAX_BACKLIGHTS = 32
MAX_FIELD_BYTES = 128


class CollectorError(ValueError):
    """A fail-closed collector contract violation."""


def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def resolved_inside(path: Path, root: Path, kind: str) -> Path:
    root_resolved = root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise CollectorError(f"{kind}-escaped-sysfs") from None
    return resolved


def bounded_names(path: Path, sys_root: Path, maximum: int, kind: str) -> list[str]:
    try:
        resolved_inside(path, sys_root, kind)
    except FileNotFoundError:
        return []
    with os.scandir(path) as iterator:
        names = sorted(entry.name for entry in iterator)
    if len(names) > maximum:
        raise CollectorError(f"{kind}-entry-limit-exceeded")
    return names


def read_text(path: Path, sys_root: Path) -> str | None:
    try:
        resolved = resolved_inside(path, sys_root, "field")
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise CollectorError("allowlisted-field-not-regular")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(resolved, flags)
    try:
        value = os.read(descriptor, MAX_FIELD_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(value) > MAX_FIELD_BYTES or b"\x00" in value:
        raise CollectorError("allowlisted-field-malformed")
    try:
        text = value.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        raise CollectorError("allowlisted-field-invalid-utf8") from None
    if not text or any(ord(character) < 32 or ord(character) == 127 for character in text):
        raise CollectorError("allowlisted-field-malformed")
    return text


def boolean_parameter(path: Path, sys_root: Path) -> bool | None:
    value = read_text(path, sys_root)
    if value is None:
        return None
    if value in {"Y", "1"}:
        return True
    if value in {"N", "0"}:
        return False
    raise CollectorError("boolean-module-parameter-malformed")


def collect_backlights(sys_root: Path) -> list[dict[str, str]]:
    base = sys_root / "class/backlight"
    result = []
    for name in bounded_names(base, sys_root, MAX_BACKLIGHTS, "backlight"):
        if not SAFE_BACKLIGHT.fullmatch(name):
            raise CollectorError("unsafe-backlight-name")
        kind = read_text(base / name / "type", sys_root)
        if kind not in BACKLIGHT_TYPES:
            raise CollectorError("backlight-type-malformed")
        result.append({"name": name, "type": kind})
    return result


def collect(
    config: dict[str, Any],
    filesystem_root: Path = Path("/"),
    fixture_mode: bool = False,
) -> dict[str, Any]:
    if (
        config.get("id") != "lighting-tier2-wmi-binding-readonly"
        or config.get("version") != "1.0.0"
    ):
        raise CollectorError("unsupported-lighting-tier2-collector")
    if config.get("execution_enabled") is not True or config.get("attempt_limit") != 1:
        raise CollectorError("lighting-tier2-policy-invalid")
    if config.get("privilege") != "unprivileged" or config.get("network") is not False:
        raise CollectorError("lighting-tier2-boundary-invalid")
    if not fixture_mode and filesystem_root != Path("/"):
        raise CollectorError("live-filesystem-root-must-be-root")
    filesystem_root = filesystem_root.resolve(strict=True)
    sys_root = (filesystem_root / "sys").resolve(strict=True)
    wmi_devices = [
        name.upper()
        for name in bounded_names(
            sys_root / "bus/wmi/devices", sys_root, MAX_WMI_DEVICES, "wmi-device"
        )
        if GUID_INSTANCE.fullmatch(name)
    ]
    driver_path = sys_root / "bus/wmi/drivers/nvidia-wmi-ec-backlight"
    bound_devices = [
        name.upper()
        for name in bounded_names(driver_path, sys_root, MAX_DRIVER_ENTRIES, "wmi-driver")
        if GUID_INSTANCE.fullmatch(name)
    ]
    force = boolean_parameter(
        sys_root / "module/nvidia_wmi_ec_backlight/parameters/force", sys_root
    )
    backlights = collect_backlights(sys_root)
    collected_at = timestamp()
    attempt_id = "lighting-tier2-" + hashlib.sha256(collected_at.encode()).hexdigest()[:16]
    value = {
        "brightness_guid": GUID,
        "firmware_guid_instances": wmi_devices,
        "driver_directory_present": driver_path.exists(),
        "bound_guid_instances": bound_devices,
        "module_force": force,
        "registered_backlights": backlights,
    }
    fact = {
        "fact_id": "lighting.wmi.backlight-binding",
        "fact_key": "lighting.wmi.backlight-binding",
        "value": value,
        "value_type": "json",
        "collected_at": collected_at,
        "collector": config["id"],
        "collector_version": config["version"],
        "source_attempt_id": attempt_id,
        "privacy_class": "internal",
        "prerequisites": {
            "entry_names_and_fixed_parameter_only": True,
            "wmi_method_evaluated": False,
            "subprocess": False,
            "network": False,
            "privilege": False,
            "device_wake_operation": False,
            "state_change": False,
        },
        "status": "current",
    }
    summary = {
        "firmware_guid_instances": len(wmi_devices),
        "bound_guid_instances": len(bound_devices),
        "registered_backlights": len(backlights),
        "wmi_method_evaluated": False,
        "device_wake_operation_attempted": False,
        "state_change": False,
    }
    attempt = {
        "attempt_id": attempt_id,
        "requested_at": collected_at,
        "executable": "collect_lighting_tier2_wmi_binding.py",
        "argv": [],
        "cwd_class": "collector-isolated",
        "environment_keys": [],
        "purpose": "passive NVIDIA brightness WMI GUID, binding, force-parameter, and provider-type observation",
        "expected": {
            "attempt_limit": 1,
            "wmi_method_evaluation": False,
            "subprocess": False,
            "network": False,
            "privilege": False,
            "device_wake_operation": False,
            "state_change": False,
        },
        "actual": summary,
        "exit_code": 0,
        "timed_out": False,
        "outcome": "success",
        "output_excerpt": "Passive WMI namespace and backlight registration metadata collected without method evaluation, subprocess, network, privilege, or writes.",
        "output_bytes": len(canonical({"summary": summary})),
        "privacy_class": "internal",
        "evidence": [{"collector": config["id"], "version": config["version"]}],
    }
    result = {
        "schema_version": 1,
        "collector": config["id"],
        "collector_version": config["version"],
        "collected_at": collected_at,
        "privacy": {
            "sensitive_collection": False,
            "redacted": True,
            "wmi_method_evaluated": False,
            "raw_paths_persisted": False,
        },
        "attempts": [attempt],
        "facts": [fact],
    }
    if len(canonical(result)) > int(config["default_output_limit_bytes"]):
        raise CollectorError("collector-output-limit-exceeded")
    return result


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise CollectorError("refusing-to-overwrite-existing-output")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.chmod(0o600)
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--fixture-mode", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--fixture-root", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    config = json.loads(args.registry.read_text(encoding="utf-8"))
    if args.preview:
        print(
            json.dumps(
                {
                    "collector": config["id"],
                    "version": config["version"],
                    "probe_groups": config["probe_groups"],
                    "forbidden_operations": config["forbidden_operations"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.registry.resolve() != REGISTRY.resolve() and not args.fixture_mode:
        raise CollectorError("custom-registry-requires-fixture-mode")
    filesystem_root = args.fixture_root if args.fixture_mode else Path("/")
    if filesystem_root is None:
        raise CollectorError("fixture-root-required")
    output = args.output.resolve(strict=False)
    if not args.fixture_mode:
        live_root = LIVE_OUTPUT_ROOT.resolve(strict=False)
        try:
            output.relative_to(live_root)
        except ValueError:
            raise CollectorError("live-output-outside-runtime-snapshots") from None
    result = collect(config, filesystem_root=filesystem_root, fixture_mode=args.fixture_mode)
    atomic_write(output, result)
    print(
        json.dumps(
            {
                "output": str(output),
                "collector": config["id"],
                "attempt_limit": 1,
                "mode": "read-only-passive-wmi-binding-no-method-evaluation",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CollectorError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "code": str(exc)}, sort_keys=True))
        raise SystemExit(3)
