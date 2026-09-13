#!/usr/bin/env python3
"""Collect passive platform and lighting topology without subprocesses or writes."""

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
REGISTRY = PLUGIN_ROOT / "registry/collectors/lighting-tier1-platform.json"
LIVE_OUTPUT_ROOT = BUNDLE_ROOT / "runtime/state/snapshots"
MAX_FIELD_BYTES = 4096
MAX_OUTPUT_BYTES = 262144
MAX_MODULES = 1024
MAX_PLATFORM_DRIVERS = 1024
MAX_PLATFORM_DEVICES = 2048
MAX_BACKLIGHTS = 32
MAX_LEDS = 512
MAX_INPUT_ENTRIES = 512
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.:+@-]{1,192}$")
SAFE_INTERFACE_NAME = re.compile(
    r"^[A-Za-z0-9_.:+@-](?:[A-Za-z0-9_.:+@ -]{0,190}[A-Za-z0-9_.:+@-])?$"
)
INPUT_NAME = re.compile(r"^input[0-9]+$")
HEX_FIELD = re.compile(r"^[0-9a-fA-F]{1,8}$")
INTERFACE_RELEVANT = re.compile(
    r"(?i)(?:backlight|kbd|keyboard|hotkey|wmi|acpi|video|ideapad|thinkpad|"
    r"dell|hp[_-]|asus|acer|msi|clevo|tuxedo|alienware|razer|gigabyte|aorus|framework)"
)
INPUT_RELEVANT = re.compile(
    r"(?i)(?:keyboard|hotkey|wmi|acpi|video bus|ideapad|thinkpad|dell|hp|asus|"
    r"acer|msi|clevo|tuxedo|alienware|razer|gigabyte|aorus|framework|at translated set 2)"
)
UEVENT_KEYS = {"DRIVER", "MODALIAS", "PCI_CLASS", "PCI_ID", "PCI_SUBSYS_ID"}
DMI_FIELDS = (
    "sys_vendor",
    "product_name",
    "product_version",
    "board_vendor",
    "board_name",
)
FORBIDDEN_DMI_FIELDS = {
    "product_serial",
    "board_serial",
    "chassis_serial",
    "product_uuid",
    "chassis_asset_tag",
}


class CollectorError(ValueError):
    """A fail-closed collector contract violation."""


def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def safe_name(value: str, kind: str) -> str:
    if not SAFE_NAME.fullmatch(value):
        raise CollectorError(f"unsafe-{kind}-name")
    return value


def safe_interface_name(value: str, kind: str) -> str:
    if not SAFE_INTERFACE_NAME.fullmatch(value):
        raise CollectorError(f"unsafe-{kind}-name")
    return value


def resolved_inside(path: Path, root: Path, kind: str) -> Path:
    root_resolved = root.resolve(strict=True)
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        raise
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise CollectorError(f"{kind}-escaped-allowlisted-root") from None
    return resolved


def read_bytes(path: Path, root: Path, limit: int = MAX_FIELD_BYTES) -> bytes | None:
    try:
        resolved = resolved_inside(path, root, "read")
    except FileNotFoundError:
        return None
    metadata = resolved.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise CollectorError("allowlisted-field-not-regular")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(resolved, flags)
    try:
        value = os.read(descriptor, limit + 1)
    finally:
        os.close(descriptor)
    if len(value) > limit:
        raise CollectorError("allowlisted-field-oversized")
    if b"\x00" in value:
        raise CollectorError("allowlisted-field-nul-byte")
    return value


def read_text(path: Path, root: Path, limit: int = MAX_FIELD_BYTES) -> str | None:
    value = read_bytes(path, root, limit)
    if value is None:
        return None
    try:
        text = value.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        raise CollectorError("allowlisted-field-invalid-utf8") from None
    if any(
        (ord(character) < 32 and character not in "\n\t") or ord(character) == 127
        for character in text
    ):
        raise CollectorError("allowlisted-field-control-character")
    return text


def read_identity_text(path: Path, root: Path) -> str | None:
    value = read_text(path, root, 256)
    if value is None or value == "":
        return None
    if len(value) > 192:
        raise CollectorError("identity-field-too-long")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CollectorError("identity-field-control-character")
    return value


def list_names(path: Path, root: Path, maximum: int, kind: str) -> list[str]:
    try:
        resolved_inside(path, root, kind)
    except FileNotFoundError:
        return []
    try:
        with os.scandir(path) as iterator:
            names = sorted(entry.name for entry in iterator)
    except FileNotFoundError:
        return []
    if len(names) > maximum:
        raise CollectorError(f"{kind}-entry-limit-exceeded")
    return [safe_name(name, kind) for name in names]


def link_basename(path: Path, root: Path, kind: str) -> str | None:
    try:
        resolved = resolved_inside(path, root, kind)
    except FileNotFoundError:
        return None
    return safe_name(resolved.name, kind)


def interface_link_basename(path: Path, root: Path, kind: str) -> str | None:
    try:
        resolved = resolved_inside(path, root, kind)
    except FileNotFoundError:
        return None
    return safe_interface_name(resolved.name, kind)


def collect_identity(sys_root: Path) -> dict[str, str | None]:
    base = sys_root / "class/dmi/id"
    result: dict[str, str | None] = {}
    for field in DMI_FIELDS:
        if field in FORBIDDEN_DMI_FIELDS:
            raise CollectorError("forbidden-dmi-field-in-allowlist")
        result[field] = read_identity_text(base / field, sys_root)
    return result


def filtered_names(base: Path, sys_root: Path, maximum: int, kind: str) -> list[str]:
    try:
        resolved_inside(base, sys_root, kind)
    except FileNotFoundError:
        return []
    with os.scandir(base) as iterator:
        names = sorted(entry.name for entry in iterator)
    if len(names) > maximum:
        raise CollectorError(f"{kind}-entry-limit-exceeded")
    return [safe_interface_name(name, kind) for name in names if INTERFACE_RELEVANT.search(name)]


def collect_interfaces(sys_root: Path) -> dict[str, list[str]]:
    return {
        "module_names": filtered_names(sys_root / "module", sys_root, MAX_MODULES, "module"),
        "platform_driver_names": filtered_names(
            sys_root / "bus/platform/drivers",
            sys_root,
            MAX_PLATFORM_DRIVERS,
            "platform-driver",
        ),
        "platform_device_names": filtered_names(
            sys_root / "bus/platform/devices",
            sys_root,
            MAX_PLATFORM_DEVICES,
            "platform-device",
        ),
    }


def parse_uevent(path: Path, sys_root: Path) -> dict[str, str]:
    text = read_text(path, sys_root)
    if text is None:
        return {}
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            raise CollectorError("uevent-line-malformed")
        key, value = line.split("=", 1)
        if key not in UEVENT_KEYS:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.:+,/-]{1,512}", value):
            raise CollectorError("uevent-value-malformed")
        result[key.lower()] = value
    return result


def collect_backlight_topology(sys_root: Path) -> list[dict[str, Any]]:
    base = sys_root / "class/backlight"
    result = []
    for provider_name in list_names(base, sys_root, MAX_BACKLIGHTS, "backlight"):
        device = base / provider_name / "device"
        result.append(
            {
                "provider": provider_name,
                "driver": link_basename(device / "driver", sys_root, "driver"),
                "device_bus": link_basename(device / "subsystem", sys_root, "device-bus"),
                "firmware_node_class": link_basename(
                    device / "firmware_node/subsystem", sys_root, "firmware-node-class"
                ),
                "uevent_identity": parse_uevent(device / "uevent", sys_root),
            }
        )
    return result


def collect_led_candidates(sys_root: Path) -> list[str]:
    names = list_names(sys_root / "class/leds", sys_root, MAX_LEDS, "led")
    return [name for name in names if INTERFACE_RELEVANT.search(name)]


def read_hex_field(path: Path, sys_root: Path) -> str | None:
    value = read_text(path, sys_root, 32)
    if value is None:
        return None
    if not HEX_FIELD.fullmatch(value):
        raise CollectorError("input-id-field-malformed")
    return value.lower()


def collect_input_candidates(sys_root: Path) -> list[dict[str, Any]]:
    base = sys_root / "class/input"
    result: list[dict[str, Any]] = []
    for input_name in list_names(base, sys_root, MAX_INPUT_ENTRIES, "input"):
        if not INPUT_NAME.fullmatch(input_name):
            continue
        provider = base / input_name
        name = read_identity_text(provider / "name", sys_root)
        if name is None or not INPUT_RELEVANT.search(name):
            continue
        result.append(
            {
                "input": input_name,
                "name": name,
                "driver": interface_link_basename(
                    provider / "device/driver", sys_root, "input-driver"
                ),
                "id": {
                    "bustype": read_hex_field(provider / "id/bustype", sys_root),
                    "vendor": read_hex_field(provider / "id/vendor", sys_root),
                    "product": read_hex_field(provider / "id/product", sys_root),
                    "version": read_hex_field(provider / "id/version", sys_root),
                },
            }
        )
    return result


def make_fact(
    key: str,
    value: Any,
    collected_at: str,
    attempt_id: str,
    version: str,
    sources: list[str],
) -> dict[str, Any]:
    return {
        "fact_id": key,
        "fact_key": key,
        "value": value,
        "value_type": "json",
        "collected_at": collected_at,
        "collector": "lighting-tier1-platform-readonly",
        "collector_version": version,
        "source_attempt_id": attempt_id,
        "privacy_class": "internal",
        "prerequisites": {
            "sources": sources,
            "no_serial_or_uuid": True,
            "no_raw_input_events": True,
            "no_subprocess": True,
            "no_network": True,
            "no_privilege": True,
            "no_device_wake_operation": True,
        },
        "status": "current",
    }


def collect(
    config: dict[str, Any],
    filesystem_root: Path = Path("/"),
    fixture_mode: bool = False,
) -> dict[str, Any]:
    if config.get("id") != "lighting-tier1-platform-readonly" or config.get("version") != "1.0.0":
        raise CollectorError("unsupported-lighting-tier1-collector")
    if config.get("execution_enabled") is not True or config.get("attempt_limit") != 1:
        raise CollectorError("lighting-tier1-policy-invalid")
    if config.get("privilege") != "unprivileged" or config.get("network") is not False:
        raise CollectorError("lighting-tier1-boundary-invalid")
    if set(config["probe_groups"][0].get("forbidden_fields", [])) != FORBIDDEN_DMI_FIELDS:
        raise CollectorError("lighting-tier1-sensitive-field-policy-invalid")
    if not fixture_mode and filesystem_root != Path("/"):
        raise CollectorError("live-filesystem-root-must-be-root")
    filesystem_root = filesystem_root.resolve(strict=True)
    sys_root = (filesystem_root / "sys").resolve(strict=True)
    collected_at = timestamp()
    attempt_id = "lighting-tier1-" + hashlib.sha256(collected_at.encode()).hexdigest()[:16]
    identity = collect_identity(sys_root)
    interfaces = collect_interfaces(sys_root)
    backlight_topology = collect_backlight_topology(sys_root)
    interfaces["candidate_led_names"] = collect_led_candidates(sys_root)
    input_candidates = collect_input_candidates(sys_root)
    facts = [
        make_fact(
            "hardware.platform.identity",
            identity,
            collected_at,
            attempt_id,
            config["version"],
            ["/sys/class/dmi/id allowlist"],
        ),
        make_fact(
            "lighting.platform.interfaces",
            interfaces,
            collected_at,
            attempt_id,
            config["version"],
            [
                "/sys/module names",
                "/sys/bus/platform names",
                "/sys/class/leds candidate names",
            ],
        ),
        make_fact(
            "lighting.backlight.topology",
            backlight_topology,
            collected_at,
            attempt_id,
            config["version"],
            ["/sys/class/backlight topology"],
        ),
        make_fact(
            "input.hotkey.candidates",
            input_candidates,
            collected_at,
            attempt_id,
            config["version"],
            ["/sys/class/input metadata allowlist"],
        ),
    ]
    summary = {
        "identity_fields_present": sum(value is not None for value in identity.values()),
        "relevant_modules": len(interfaces["module_names"]),
        "relevant_platform_drivers": len(interfaces["platform_driver_names"]),
        "relevant_platform_devices": len(interfaces["platform_device_names"]),
        "candidate_led_names": len(interfaces["candidate_led_names"]),
        "backlight_topologies": len(backlight_topology),
        "candidate_hotkey_inputs": len(input_candidates),
        "serial_or_uuid_read": False,
        "raw_input_event_read": False,
        "device_wake_operation_attempted": False,
        "state_change": False,
    }
    attempt = {
        "attempt_id": attempt_id,
        "requested_at": collected_at,
        "executable": "collect_lighting_tier1_platform.py",
        "argv": [],
        "cwd_class": "collector-isolated",
        "environment_keys": [],
        "purpose": "bounded passive platform, lighting-interface, topology, and hotkey-device metadata observation",
        "expected": {
            "attempt_limit": 1,
            "subprocess": False,
            "network": False,
            "privilege": False,
            "serial_or_uuid": False,
            "raw_input_events": False,
            "device_wake_operation": False,
            "state_change": False,
        },
        "actual": summary,
        "exit_code": 0,
        "timed_out": False,
        "outcome": "success",
        "output_excerpt": "Tier-1 platform metadata collected without serials, UUIDs, input events, subprocesses, D-Bus, network, privilege, device-wake operations, or state changes.",
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
            "serial_or_uuid_persisted": False,
            "raw_input_events_persisted": False,
            "raw_paths_persisted": False,
        },
        "attempts": [attempt],
        "facts": facts,
    }
    if len(canonical(result)) > int(config.get("default_output_limit_bytes", MAX_OUTPUT_BYTES)):
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
                "mode": "read-only-passive-platform-no-device-wake-operation",
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
