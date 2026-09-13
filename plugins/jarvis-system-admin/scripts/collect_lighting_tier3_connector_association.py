#!/usr/bin/env python3
"""Read bounded DRM eDP status and backlight-to-PCI association metadata."""

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
REGISTRY = PLUGIN_ROOT / "registry/collectors/lighting-tier3-connector-association.json"
LIVE_OUTPUT_ROOT = BUNDLE_ROOT / "runtime/state/snapshots"
MAX_DRM_ENTRIES = 256
MAX_CARDS = 16
MAX_CONNECTORS = 64
MAX_BACKLIGHTS = 32
MAX_FIELD_BYTES = 256
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.:+-]{1,128}$")
CARD = re.compile(r"^card[0-9]+$")
CONNECTOR = re.compile(r"^card[0-9]+-(?:eDP|DP|HDMI-A|DisplayPort)-[A-Za-z0-9_.:+-]+$")
EDP = re.compile(r"^card[0-9]+-eDP-[A-Za-z0-9_.:+-]+$")
PCI_BDF = re.compile(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$")
HEX_ID = re.compile(r"^0x[0-9a-fA-F]{4,8}$")
STATUS = {"connected", "disconnected", "unknown"}
BACKLIGHT_TYPES = {"raw", "platform", "firmware"}


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
        data = os.read(descriptor, MAX_FIELD_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(data) > MAX_FIELD_BYTES or b"\x00" in data:
        raise CollectorError("allowlisted-field-malformed")
    try:
        value = data.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        raise CollectorError("allowlisted-field-invalid-utf8") from None
    if not value or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CollectorError("allowlisted-field-malformed")
    return value


def list_names(path: Path, sys_root: Path, maximum: int, kind: str) -> list[str]:
    try:
        resolved_inside(path, sys_root, kind)
    except FileNotFoundError:
        return []
    with os.scandir(path) as iterator:
        names = sorted(entry.name for entry in iterator)
    if len(names) > maximum:
        raise CollectorError(f"{kind}-entry-limit-exceeded")
    for name in names:
        if not SAFE_NAME.fullmatch(name):
            raise CollectorError(f"unsafe-{kind}-name")
    return names


def driver_name(device: Path, sys_root: Path) -> str | None:
    try:
        resolved = resolved_inside(device / "driver", sys_root, "driver-link")
    except FileNotFoundError:
        return None
    if not SAFE_NAME.fullmatch(resolved.name):
        raise CollectorError("unsafe-driver-name")
    return resolved.name


def pci_device(device: Path, sys_root: Path) -> str | None:
    try:
        resolved = resolved_inside(device, sys_root, "device-link")
    except FileNotFoundError:
        return None
    return resolved.name if PCI_BDF.fullmatch(resolved.name) else None


def hex_id(path: Path, sys_root: Path) -> str | None:
    value = read_text(path, sys_root)
    if value is None:
        return None
    if not HEX_ID.fullmatch(value):
        raise CollectorError("pci-id-malformed")
    return value.lower()


def collect_cards(sys_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = sys_root / "class/drm"
    entries = list_names(base, sys_root, MAX_DRM_ENTRIES, "drm")
    cards = [name for name in entries if CARD.fullmatch(name)]
    if len(cards) > MAX_CARDS:
        raise CollectorError("drm-card-limit-exceeded")
    card_records = []
    connector_records = []
    for card in cards:
        device = base / card / "device"
        card_records.append(
            {
                "card": card,
                "pci_device": pci_device(device, sys_root),
                "vendor": hex_id(device / "vendor", sys_root),
                "device": hex_id(device / "device", sys_root),
                "class": hex_id(device / "class", sys_root),
                "driver": driver_name(device, sys_root),
            }
        )
        connectors = [name for name in entries if name.startswith(card + "-")]
        if len(connectors) > MAX_CONNECTORS:
            raise CollectorError("drm-connector-limit-exceeded")
        for connector in connectors:
            if not CONNECTOR.fullmatch(connector):
                raise CollectorError("unsafe-connector-name")
            if not EDP.fullmatch(connector):
                continue
            status = read_text(base / connector / "status", sys_root)
            if status not in STATUS:
                raise CollectorError("connector-status-malformed")
            connector_records.append({"card": card, "connector": connector, "status": status})
    return card_records, connector_records


def collect_backlights(sys_root: Path) -> list[dict[str, Any]]:
    base = sys_root / "class/backlight"
    result = []
    for name in list_names(base, sys_root, MAX_BACKLIGHTS, "backlight"):
        provider = base / name
        kind = read_text(provider / "type", sys_root)
        if kind not in BACKLIGHT_TYPES:
            raise CollectorError("backlight-type-malformed")
        result.append(
            {
                "name": name,
                "type": kind,
                "pci_device": pci_device(provider / "device", sys_root),
                "driver": driver_name(provider / "device", sys_root),
            }
        )
    return result


def collect(
    config: dict[str, Any],
    filesystem_root: Path = Path("/"),
    fixture_mode: bool = False,
) -> dict[str, Any]:
    if (
        config.get("id") != "lighting-tier3-connector-association-readonly"
        or config.get("version") != "1.0.0"
    ):
        raise CollectorError("unsupported-lighting-tier3-collector")
    if config.get("execution_enabled") is not True or config.get("attempt_limit") != 1:
        raise CollectorError("lighting-tier3-policy-invalid")
    if config.get("privilege") != "unprivileged" or config.get("network") is not False:
        raise CollectorError("lighting-tier3-boundary-invalid")
    if not fixture_mode and filesystem_root != Path("/"):
        raise CollectorError("live-filesystem-root-must-be-root")
    filesystem_root = filesystem_root.resolve(strict=True)
    sys_root = (filesystem_root / "sys").resolve(strict=True)
    collected_at = timestamp()
    attempt_id = "lighting-tier3-" + hashlib.sha256(collected_at.encode()).hexdigest()[:16]
    cards, connectors = collect_cards(sys_root)
    backlights = collect_backlights(sys_root)
    value = {
        "cards": cards,
        "internal_edp_connectors": connectors,
        "backlights": backlights,
    }
    fact = {
        "fact_id": "lighting.connector.association",
        "fact_key": "lighting.connector.association",
        "value": value,
        "value_type": "json",
        "collected_at": collected_at,
        "collector": config["id"],
        "collector_version": config["version"],
        "source_attempt_id": attempt_id,
        "privacy_class": "internal",
        "prerequisites": {
            "fixed_drm_paths_only": True,
            "internal_edp_status_reads": len(connectors),
            "connector_status_may_wake_hardware": True,
            "subprocess": False,
            "network": False,
            "privilege": False,
            "state_change": False,
        },
        "status": "current",
    }
    summary = {
        "cards": len(cards),
        "internal_edp_connectors": len(connectors),
        "backlights": len(backlights),
        "connector_status_reads": len(connectors),
        "connector_status_may_wake_hardware": True,
        "state_change": False,
    }
    attempt = {
        "attempt_id": attempt_id,
        "requested_at": collected_at,
        "executable": "collect_lighting_tier3_connector_association.py",
        "argv": [],
        "cwd_class": "collector-isolated",
        "environment_keys": [],
        "purpose": "read-only associate firmware backlights with PCI graphics devices and inspect internal eDP connector status",
        "expected": {
            "attempt_limit": 1,
            "connector_status_may_wake_hardware": True,
            "subprocess": False,
            "network": False,
            "privilege": False,
            "state_change": False,
        },
        "actual": summary,
        "exit_code": 0,
        "timed_out": False,
        "outcome": "success",
        "output_excerpt": "Fixed DRM card, internal eDP status, and backlight-to-PCI associations collected without writes, methods, subprocess, network, or privilege.",
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
            "raw_paths_persisted": False,
            "connector_status_may_wake_hardware": True,
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
                "mode": "read-only-edp-status-and-backlight-association",
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
