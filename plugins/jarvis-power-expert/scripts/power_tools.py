"""Typed, bounded Power Expert tools exposed through the Jarvis MCP server.

These tools are deliberately proposal-oriented. Observation and validation may
run without approval; mutation remains in the TUI/broker's exact approval and
registered-helper boundary.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

BUNDLE_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BUNDLE_ROOT / "tui" / "src"))

from jarvis_tui.power_control_client import POWER_CONTROL_OPTIONS  # noqa: E402
from jarvis_tui.power_inventory import scan_power_inventory, scan_power_telemetry  # noqa: E402
from jarvis_tui.power_profile_results import PowerProfileApplicationStore  # noqa: E402
from jarvis_tui.power_profiles import PowerProfile  # noqa: E402

MAX_CONTROLS = 16


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _inventory_dict() -> dict[str, Any]:
    inventory = scan_power_inventory()
    return {
        "providers": list(inventory.providers),
        "hardware": list(inventory.hardware),
        "software": list(inventory.software),
        "conflicts": list(inventory.conflicts),
        "limitations": list(inventory.limitations),
        "settings": [asdict(item) for item in inventory.settings],
        "telemetry": asdict(inventory.telemetry),
    }


def _validate_variants(variants: Any) -> dict[str, dict[str, str]]:
    if not isinstance(variants, dict) or set(variants) != {"ac", "battery"}:
        raise ValueError("variants must contain exactly ac and battery")
    normalized: dict[str, dict[str, str]] = {}
    inventory = scan_power_inventory()
    observed = {item.control_id: item for item in inventory.settings if item.control_id}
    for variant in ("ac", "battery"):
        values = variants[variant]
        if not isinstance(values, dict) or len(values) > MAX_CONTROLS:
            raise ValueError("profile variant controls are invalid")
        normalized[variant] = {}
        for control, value in values.items():
            if not isinstance(control, str) or not isinstance(value, str):
                raise ValueError("profile controls must be strings")
            if value not in POWER_CONTROL_OPTIONS.get(control, ()):
                raise ValueError(f"control is not reviewed or value is not allowlisted: {control}")
            item = observed.get(control)
            if item is None or not item.available or not item.writable_by_jarvis:
                raise ValueError(f"control is recommendation-only on this host: {control}")
            choices = {choice.strip() for choice in item.choices.split(",")}
            if choices and value not in choices and item.current != value:
                raise ValueError(f"value is not exposed by the current provider: {control}")
            normalized[variant][control] = value
    return normalized


def power_tool_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name in {"power_inventory", "inspect_power_inventory"}:
        return {"status": "observed", "evidence": _inventory_dict()}
    if name in {"power_telemetry", "inspect_power_telemetry"}:
        return {"status": "observed", "telemetry": asdict(scan_power_telemetry())}
    if name == "power_retrieve_evidence":
        record = PowerProfileApplicationStore().load_latest_applied()
        return {
            "status": "observed",
            "latest_verified_application": record.to_dict() if record is not None else None,
            "note": "Only bounded Power evidence is returned; private reasoning and credentials are excluded.",
        }
    if name == "power_capabilities":
        inventory = scan_power_inventory()
        return {
            "status": "observed",
            "controls": {
                control: {
                    "allowed_values": list(values),
                    "reviewed_adapter": True,
                    "observed": next(
                        (asdict(item) for item in inventory.settings if item.control_id == control),
                        None,
                    ),
                }
                for control, values in POWER_CONTROL_OPTIONS.items()
            },
            "recommendation_only": [
                asdict(item)
                for item in inventory.settings
                if item.writable_by_jarvis and item.control_id not in POWER_CONTROL_OPTIONS
            ],
        }
    if name == "power_profile_plan":
        profile_id = str(args.get("profile_id") or "profile_" + _digest(args)[:16])
        profile_name = args.get("name")
        goal = args.get("goal")
        if not isinstance(profile_name, str) or not 1 <= len(profile_name.strip()) <= 120:
            raise ValueError("profile name is invalid")
        if not isinstance(goal, str):
            raise ValueError("profile goal is required")
        profile = PowerProfile(
            profile_id,
            profile_name.strip(),
            goal,
            _validate_variants(args.get("variants")),
        )
        return {
            "status": "draft_ready",
            "profile": profile.to_dict(),
            "profile_digest": profile.profile_digest,
            "execution": "not applied; exact Jarvis approval is required",
        }
    if name == "power_profile_apply":
        requested = args.get("requested")
        pre_state = args.get("pre_state")
        profile_digest = args.get("profile_digest")
        variant = args.get("selected_variant")
        if (
            not isinstance(requested, dict)
            or not isinstance(pre_state, dict)
            or not isinstance(profile_digest, str)
            or variant not in {"ac", "battery"}
        ):
            raise ValueError("exact profile application proposal is incomplete")
        if set(requested) != set(pre_state) or len(requested) > MAX_CONTROLS:
            raise ValueError("application proposal control set is invalid")
        for control, value in requested.items():
            if value not in POWER_CONTROL_OPTIONS.get(control, ()):
                raise ValueError("application contains an unreviewed control or value")
        current = {
            item.control_id: item.current
            for item in scan_power_inventory().settings
            if item.control_id in requested and item.available and item.writable_by_jarvis
        }
        if current != pre_state:
            raise ValueError("application pre-state is stale or not currently observed")
        return {
            "status": "approval_required",
            "profile_digest": profile_digest,
            "selected_variant": variant,
            "requested": requested,
            "pre_state": pre_state,
            "approval": "Jarvis must show and consume one exact user approval before apply",
            "os_authorization": "registered helper may request desktop authorization after Jarvis approval",
        }
    if name == "power_validate":
        requested = args.get("requested")
        pre_state = args.get("pre_state")
        if not isinstance(requested, dict) or not isinstance(pre_state, dict):
            raise ValueError("validation requires requested and pre_state objects")
        current = {
            item.control_id: item.current
            for item in scan_power_inventory().settings
            if item.control_id in requested and item.available and item.writable_by_jarvis
        }
        return {
            "status": "validated" if current == pre_state else "stale",
            "current": current,
            "requested": requested,
            "pre_state": pre_state,
            "mutation": "not executed",
        }
    if name == "power_verify":
        requested = args.get("requested")
        if not isinstance(requested, dict):
            raise ValueError("verification requires requested object")
        current = {
            item.control_id: item.current
            for item in scan_power_inventory().settings
            if item.control_id in requested
        }
        return {
            "status": "verified" if current == requested else "mismatch",
            "resulting": current,
            "requested": requested,
        }
    if name == "power_profile_rollback":
        return {
            "status": "recovery_proposal",
            "record_digest": args.get("record_digest"),
            "approval": "fresh exact user approval is required; no rollback was executed",
        }
    if name == "power_recovery_plan":
        return {
            "status": "recovery_proposal",
            "record_digest": args.get("record_digest"),
            "approval": "fresh exact user approval is required; no recovery was executed",
        }
    if name == "stage_registered_power_action":
        return {
            "status": "approval_required",
            "action": args.get("action", "power-profile.select"),
            "execution": "registered adapter only; no mutation was executed",
        }
    raise ValueError("unknown_power_tool")
