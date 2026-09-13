"""TUI-only mutation previews.

These builders produce explicit approval screens and never execute host
changes. Registration and live execution remain separate deployment gates.
"""

from __future__ import annotations

from typing import Any


def lighting_repair_preview(*, repair_plan_id: str, target: str, rollback: str) -> dict[str, Any]:
    if not repair_plan_id or target not in {"display-backlight", "keyboard-leds"} or not rollback:
        raise ValueError("lighting repair preview requires an exact plan, target, and rollback")
    return {
        "operation": "jarvis.lighting.repair",
        "target": target,
        "repair_plan_id": repair_plan_id,
        "mutation": True,
        "simulation_only": True,
        "independent_review_required": True,
        "active_session_confirmation_required": True,
        "rollback": rollback,
        "status": "preview_only_unavailable_for_execution",
    }


def power_profile_preview(*, profile: str, current_profile: str) -> dict[str, Any]:
    if profile not in {"power-saver", "balanced", "performance"} or not current_profile:
        raise ValueError("power preview requires an exact supported profile and current state")
    return {
        "operation": "jarvis.powerprofile.select",
        "requested_profile": profile,
        "pre_profile": current_profile,
        "mutation": True,
        "simulation_only": True,
        "independent_review_required": True,
        "active_session_confirmation_required": True,
        "one_transition_per_approval": True,
        "rollback_requires_new_approval": True,
        "status": "preview_only_unavailable_for_execution",
    }
