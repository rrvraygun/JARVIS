#!/usr/bin/env python3
"""Collect bounded Tier-0 lighting state without subprocesses or device writes."""

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
REGISTRY = PLUGIN_ROOT / "registry/collectors/lighting-tier0.json"
LIVE_OUTPUT_ROOT = BUNDLE_ROOT / "runtime/state/snapshots"
MAX_FIELD_BYTES = 4096
MAX_PROC_BYTES = 262144
MAX_BACKLIGHTS = 32
MAX_LEDS = 256
MAX_DRM_ENTRIES = 256
MAX_CARDS = 16
MAX_CONNECTORS = 64
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.:+-]{1,128}$")
CARD_NAME = re.compile(r"^card[0-9]+$")
KEYBOARD_LED = re.compile(r"(?:^|::)(?:kbd_backlight|kbd_zoned_backlight(?:-[0-9]+)?)(?:$|:)")
HEX_ID = re.compile(r"^0x[0-9a-fA-F]{4,8}$")
SMALL_TOKEN = re.compile(r"^[A-Za-z0-9_.:+-]{1,128}$")
RUNTIME_STATUS = {
    "active",
    "suspended",
    "suspending",
    "resuming",
    "error",
    "unsupported",
}
POWER_CONTROL = {"auto", "on"}
BACKLIGHT_TYPE = {"raw", "platform", "firmware"}
BOOT_RELEVANT = re.compile(r"(?i)(?:backlight|video=|nvidia|nouveau|i915|amdgpu)")
MODULE_RELEVANT = re.compile(
    r"(?i)(?:nvidia|nouveau|i915|amdgpu|backlight|video|wmi|laptop|acpi|led|hid_asus)"
)


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


def read_bytes_bounded(
    path: Path, allowed_root: Path, limit: int = MAX_FIELD_BYTES
) -> bytes | None:
    try:
        resolved = resolved_inside(path, allowed_root, "read")
    except FileNotFoundError:
        return None
    value = resolved.stat()
    if not stat.S_ISREG(value.st_mode):
        raise CollectorError("allowlisted-field-not-regular")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(resolved, flags)
    try:
        data = os.read(descriptor, limit + 1)
    finally:
        os.close(descriptor)
    if len(data) > limit:
        raise CollectorError("allowlisted-field-oversized")
    if b"\x00" in data:
        raise CollectorError("allowlisted-field-nul-byte")
    return data


def read_text(path: Path, allowed_root: Path, limit: int = MAX_FIELD_BYTES) -> str | None:
    data = read_bytes_bounded(path, allowed_root, limit)
    if data is None:
        return None
    try:
        return data.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        raise CollectorError("allowlisted-field-invalid-utf8") from None


def read_integer(path: Path, allowed_root: Path) -> int | None:
    value = read_text(path, allowed_root)
    if value is None:
        return None
    if not re.fullmatch(r"-?[0-9]{1,20}", value):
        raise CollectorError("allowlisted-integer-malformed")
    return int(value)


def read_small_token(path: Path, allowed_root: Path, allowed: set[str] | None = None) -> str | None:
    value = read_text(path, allowed_root)
    if value is None:
        return None
    if not SMALL_TOKEN.fullmatch(value):
        raise CollectorError("allowlisted-token-malformed")
    if allowed is not None and value not in allowed:
        raise CollectorError("allowlisted-token-unexpected-value")
    return value


def read_hex_id(path: Path, allowed_root: Path) -> str | None:
    value = read_text(path, allowed_root)
    if value is None:
        return None
    if not HEX_ID.fullmatch(value):
        raise CollectorError("allowlisted-hex-id-malformed")
    return value.lower()


def list_names(path: Path, allowed_root: Path, maximum: int, kind: str) -> list[str]:
    try:
        resolved_inside(path, allowed_root, kind)
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


def driver_name(device_path: Path, sys_root: Path) -> str | None:
    link = device_path / "driver"
    try:
        resolved = resolved_inside(link, sys_root, "driver-link")
    except FileNotFoundError:
        return None
    return safe_name(resolved.name, "driver")


def collect_backlights(sys_root: Path) -> list[dict[str, Any]]:
    base = sys_root / "class/backlight"
    result = []
    for name in list_names(base, sys_root, MAX_BACKLIGHTS, "backlight"):
        provider = base / name
        kind = read_small_token(provider / "type", sys_root, BACKLIGHT_TYPE)
        result.append(
            {
                "name": name,
                "brightness": read_integer(provider / "brightness", sys_root),
                "actual_brightness": read_integer(provider / "actual_brightness", sys_root),
                "max_brightness": read_integer(provider / "max_brightness", sys_root),
                "type": kind,
                "bl_power": read_integer(provider / "bl_power", sys_root),
                "driver": driver_name(provider / "device", sys_root),
            }
        )
    return result


def active_trigger(path: Path, sys_root: Path) -> str | None:
    value = read_text(path, sys_root)
    if value is None:
        return None
    matches = re.findall(r"\[([^\]]+)\]", value)
    if len(matches) > 1:
        raise CollectorError("multiple-active-led-triggers")
    if not matches:
        return None
    return safe_name(matches[0], "led-trigger")


def collect_keyboard_leds(sys_root: Path) -> list[dict[str, Any]]:
    base = sys_root / "class/leds"
    result = []
    for name in list_names(base, sys_root, MAX_LEDS, "led"):
        if not KEYBOARD_LED.search(name):
            continue
        provider = base / name
        result.append(
            {
                "name": name,
                "brightness": read_integer(provider / "brightness", sys_root),
                "max_brightness": read_integer(provider / "max_brightness", sys_root),
                "active_trigger": active_trigger(provider / "trigger", sys_root),
            }
        )
    return result


def collect_graphics(
    sys_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    base = sys_root / "class/drm"
    entries = list_names(base, sys_root, MAX_DRM_ENTRIES, "drm")
    cards = [name for name in entries if CARD_NAME.fullmatch(name)]
    if len(cards) > MAX_CARDS:
        raise CollectorError("drm-card-limit-exceeded")
    adapters: list[dict[str, Any]] = []
    routing: dict[str, list[str]] = {}
    for card in cards:
        connectors = [name for name in entries if name.startswith(card + "-")]
        if len(connectors) > MAX_CONNECTORS:
            raise CollectorError("drm-connector-limit-exceeded")
        routing[card] = connectors
        device = base / card / "device"
        runtime_status = read_small_token(device / "power/runtime_status", sys_root, RUNTIME_STATUS)
        power_control = read_small_token(device / "power/control", sys_root, POWER_CONTROL)
        adapters.append(
            {
                "card": card,
                "vendor": read_hex_id(device / "vendor", sys_root),
                "device": read_hex_id(device / "device", sys_root),
                "class": read_hex_id(device / "class", sys_root),
                "driver": driver_name(device, sys_root),
                "boot_vga": read_integer(device / "boot_vga", sys_root),
                "runtime_status": runtime_status,
                "runtime_usage": read_integer(device / "power/runtime_usage", sys_root),
                "power_control": power_control,
            }
        )
    return adapters, routing


def collect_kernel_context(proc_root: Path) -> dict[str, list[str]]:
    cmdline = read_text(proc_root / "cmdline", proc_root) or ""
    boot_parameters = []
    for value in cmdline.split():
        if BOOT_RELEVANT.search(value):
            if len(value) > 256 or not re.fullmatch(r"[A-Za-z0-9_.,:+/=-]+", value):
                raise CollectorError("relevant-boot-parameter-malformed")
            boot_parameters.append(value)
    modules_text = read_text(proc_root / "modules", proc_root, MAX_PROC_BYTES) or ""
    modules = []
    for line in modules_text.splitlines():
        fields = line.split()
        if not fields:
            continue
        name = safe_name(fields[0], "module")
        if MODULE_RELEVANT.search(name):
            modules.append(name)
    return {
        "relevant_boot_parameters": sorted(set(boot_parameters)),
        "relevant_loaded_modules": sorted(set(modules)),
    }


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
        "collector": "lighting-tier0-readonly",
        "collector_version": version,
        "source_attempt_id": attempt_id,
        "privacy_class": "internal",
        "prerequisites": {
            "sources": sources,
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
    if config.get("id") != "lighting-tier0-readonly" or config.get("version") != "1.0.0":
        raise CollectorError("unsupported-lighting-collector")
    if config.get("execution_enabled") is not True or config.get("attempt_limit") != 1:
        raise CollectorError("lighting-collector-policy-invalid")
    if config.get("privilege") != "unprivileged" or config.get("network") is not False:
        raise CollectorError("lighting-collector-boundary-invalid")
    if not fixture_mode and filesystem_root != Path("/"):
        raise CollectorError("live-filesystem-root-must-be-root")
    filesystem_root = filesystem_root.resolve(strict=True)
    sys_root = (filesystem_root / "sys").resolve(strict=True)
    proc_root = (filesystem_root / "proc").resolve(strict=True)
    collected_at = timestamp()
    attempt_id = "lighting-tier0-" + hashlib.sha256(collected_at.encode()).hexdigest()[:16]
    backlights = collect_backlights(sys_root)
    keyboard_leds = collect_keyboard_leds(sys_root)
    adapters, routing = collect_graphics(sys_root)
    kernel_context = collect_kernel_context(proc_root)
    facts = [
        make_fact(
            "lighting.display.providers",
            backlights,
            collected_at,
            attempt_id,
            config["version"],
            ["/sys/class/backlight"],
        ),
        make_fact(
            "lighting.keyboard.providers",
            keyboard_leds,
            collected_at,
            attempt_id,
            config["version"],
            ["/sys/class/leds"],
        ),
        make_fact(
            "graphics.adapters",
            adapters,
            collected_at,
            attempt_id,
            config["version"],
            ["/sys/class/drm/*/device"],
        ),
        make_fact(
            "graphics.routing",
            routing,
            collected_at,
            attempt_id,
            config["version"],
            ["/sys/class/drm names only"],
        ),
        make_fact(
            "kernel.graphics.context",
            kernel_context,
            collected_at,
            attempt_id,
            config["version"],
            ["/proc/cmdline filtered", "/proc/modules filtered"],
        ),
    ]
    summary = {
        "display_backlight_providers": len(backlights),
        "keyboard_light_providers": len(keyboard_leds),
        "drm_adapters": len(adapters),
        "drm_connector_names": sum(len(value) for value in routing.values()),
        "relevant_boot_parameters": len(kernel_context["relevant_boot_parameters"]),
        "relevant_loaded_modules": len(kernel_context["relevant_loaded_modules"]),
        "device_wake_operation_attempted": False,
        "state_change": False,
    }
    attempt = {
        "attempt_id": attempt_id,
        "requested_at": collected_at,
        "executable": "collect_lighting_tier0.py",
        "argv": [],
        "cwd_class": "collector-isolated",
        "environment_keys": [],
        "purpose": "bounded read-only lighting and graphics runtime metadata observation",
        "expected": {
            "attempt_limit": 1,
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
        "output_excerpt": "Tier-0 lighting metadata collected without subprocess, network, privilege, connector-status reads, or state changes.",
        "output_bytes": len(canonical({"summary": summary})),
        "privacy_class": "internal",
        "evidence": [{"collector": config["id"], "version": config["version"]}],
    }
    return {
        "schema_version": 1,
        "collector": config["id"],
        "collector_version": config["version"],
        "collected_at": collected_at,
        "privacy": {
            "sensitive_collection": False,
            "redacted": True,
            "raw_paths_persisted": False,
            "raw_kernel_command_line_persisted": False,
        },
        "attempts": [attempt],
        "facts": facts,
    }


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
                "mode": "read-only-no-device-wake-operation",
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
