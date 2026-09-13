"""TUI preview builders for the bounded energy-control framework."""

from __future__ import annotations

from typing import Any


def energy_control_preview(
    *, operations: list[dict[str, Any]], thermal_degraded: bool, on_battery: bool
) -> dict[str, Any]:
    if not operations or len(operations) > 6:
        raise ValueError("energy preview requires 1-6 operations")
    controls = {item.get("control") for item in operations}
    if None in controls or len(controls) != len(operations):
        raise ValueError("energy controls must be unique and explicit")
    if thermal_degraded and controls & {"cpu.turbo", "power.profile"}:
        raise ValueError("thermal degradation blocks turbo/profile preview")
    return {
        "operation": "jarvis.energy-control.plan",
        "operations": operations,
        "thermal_degraded": thermal_degraded,
        "on_battery": on_battery,
        "simulation_only": True,
        "active_session_confirmation_required": True,
        "one_use": True,
        "rollback_requires_new_approval": True,
        "status": "preview_only_unavailable_for_execution",
    }
