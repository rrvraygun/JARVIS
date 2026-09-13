#!/usr/bin/env python3
"""Admission-only contract for a future supervised power-profile change.

This module validates a proposed transition and returns a notification-aware
plan. It never calls D-Bus, Polkit, the authority ledger, TuneD, or the TUI.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

POLICY_PATH = (
    Path(__file__).resolve().parents[1] / "controller" / "power-profile-authorization-policy.json"
)
PROFILES = ("power-saver", "balanced", "performance")
POLKIT_ACTION = "org.freedesktop.UPower.PowerProfiles.switch-profile"
EXPECTED_PROVIDER = {
    "bus_name": "org.freedesktop.UPower.PowerProfiles",
    "object_path": "/org/freedesktop/UPower/PowerProfiles",
    "interface": "org.freedesktop.UPower.PowerProfiles",
    "mutation": "org.freedesktop.DBus.Properties.Set:ActiveProfile",
    "polkit_action": POLKIT_ACTION,
    "target": "current-active-user-session",
}
EXPECTED_AUTHORIZATION = {
    "tui_confirmation_required": True,
    "active_session_permission_required": True,
    "password_prompt_required": False,
    "expiry_seconds": 60,
    "one_use": True,
    "ledger": "existing-durable-authority-ledger",
    "one_transition_per_approval": True,
    "rollback_requires_new_approval": True,
}
EXPECTED_WARNINGS = {
    "battery": "notify-only",
    "thermal_degradation": "notify-only",
    "provider_degraded": "notify-only",
}
EXPECTED_PROHIBITED = (
    "sudo",
    "shell",
    "tuned-adm",
    "direct-sysfs",
    "direct-nvidia-control",
    "profile-holds",
    "automatic-profile-switching",
    "automatic-rollback",
    "arbitrary-parameters",
)


class PowerProfileAuthorizationError(ValueError):
    """Raised when a proposed transition is outside the approved boundary."""


@dataclass(frozen=True)
class TransitionPlan:
    requested_profile: str
    pre_profile: str
    provider: str
    notifications: tuple[str, ...]
    expires_in_seconds: int = 60
    one_use: bool = True
    rollback_requires_new_approval: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation_id": "jarvis.powerprofile.select",
            "operation_revision": "1.0.0",
            "provider": self.provider,
            "pre_profile": self.pre_profile,
            "requested_profile": self.requested_profile,
            "notifications": list(self.notifications),
            "expires_in_seconds": self.expires_in_seconds,
            "one_use": self.one_use,
            "rollback_requires_new_approval": self.rollback_requires_new_approval,
            "host_effect_occurred": False,
            "authorization_consumed": False,
        }


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PowerProfileAuthorizationError("authorization policy is unavailable") from exc
    if not isinstance(value, dict):
        raise PowerProfileAuthorizationError("authorization policy is not an object")
    return value


def build_plan(
    requested_profile: str,
    *,
    pre_profile: str,
    provider: str = "tuned-ppd",
    tui_confirmed: bool,
    active_session: bool,
    on_battery: bool = False,
    thermal_degraded: bool = False,
    provider_degraded: str = "",
    policy: Mapping[str, Any] | None = None,
) -> TransitionPlan:
    """Validate one exact request; no authorization is consumed here."""

    policy = policy or load_policy()
    if policy.get("schema_version") != 1:
        raise PowerProfileAuthorizationError("authorization policy schema drift")
    if (
        policy.get("operation_id") != "jarvis.powerprofile.select"
        or policy.get("operation_revision") != "1.0.0"
    ):
        raise PowerProfileAuthorizationError("operation binding drift")
    allowed = tuple(policy.get("allowed_profiles", ()))
    if allowed != PROFILES:
        raise PowerProfileAuthorizationError("profile allowlist drift")
    if requested_profile not in allowed or pre_profile not in allowed:
        raise PowerProfileAuthorizationError("requested or pre-profile is unsupported")
    if not tui_confirmed:
        raise PowerProfileAuthorizationError("explicit TUI confirmation is required")
    if not active_session:
        raise PowerProfileAuthorizationError("active user session permission is required")
    provider_policy = policy.get("provider")
    if (
        not isinstance(provider_policy, Mapping)
        or dict(provider_policy) != EXPECTED_PROVIDER
        or provider != "tuned-ppd"
    ):
        raise PowerProfileAuthorizationError("provider binding is invalid")
    auth = policy.get("authorization")
    if not isinstance(auth, Mapping) or dict(auth) != EXPECTED_AUTHORIZATION:
        raise PowerProfileAuthorizationError("authorization timing or one-use policy drift")
    if policy.get("warnings") != EXPECTED_WARNINGS:
        raise PowerProfileAuthorizationError("warning policy drift")
    if tuple(policy.get("prohibited", ())) != EXPECTED_PROHIBITED:
        raise PowerProfileAuthorizationError("prohibited capability policy drift")
    if any(
        policy.get(field) is not False
        for field in (
            "status_adapter_registered",
            "mutation_adapter_registered",
            "tui_reachable",
        )
    ):
        raise PowerProfileAuthorizationError("registration policy drift")
    notifications: list[str] = []
    if on_battery:
        notifications.append("on-battery")
    if thermal_degraded:
        notifications.append("thermal-degradation")
    if provider_degraded:
        notifications.append(f"provider-degraded:{provider_degraded[:64]}")
    return TransitionPlan(requested_profile, pre_profile, provider, tuple(notifications))


if __name__ == "__main__":
    print(json.dumps(load_policy(), sort_keys=True))
