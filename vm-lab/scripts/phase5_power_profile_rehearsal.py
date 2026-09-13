#!/usr/bin/env python3
"""Disposable in-memory rehearsal for the power-profile transition contract.

This is not a host adapter.  It cannot reach D-Bus, TuneD, the filesystem, or
the executor; all state exists in the simulator object for one process.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

PROFILE_NAMES = ("power-saver", "balanced", "performance")
OPERATION_ID = "jarvis.powerprofile.select"
REVISION = "1.0.0"
SIMULATOR_TARGET = "tuned-ppd-simulator-v1"


class RehearsalError(ValueError):
    """Raised when a simulated transition cannot satisfy its contract."""


@dataclass
class SimulatedProvider:
    """An isolated typed provider with no external side effects."""

    active_profile: str = "balanced"

    def __post_init__(self) -> None:
        if self.active_profile not in PROFILE_NAMES:
            raise RehearsalError("simulator initial profile is unsupported")

    def read_active_profile(self) -> str:
        return self.active_profile

    def set_active_profile(self, profile: str) -> None:
        if profile not in PROFILE_NAMES:
            raise RehearsalError("simulator profile is unsupported")
        self.active_profile = profile


def rehearse_transition(
    requested_profile: str = "performance",
    *,
    expected_pre_profile: str = "balanced",
    initial_profile: str = "balanced",
) -> dict[str, Any]:
    """Exercise one transition and exact rollback in disposable memory."""

    provider = SimulatedProvider(initial_profile)
    if requested_profile not in PROFILE_NAMES:
        raise RehearsalError("requested profile is unsupported")
    if expected_pre_profile not in PROFILE_NAMES:
        raise RehearsalError("expected pre-profile is unsupported")
    pre_profile = provider.read_active_profile()
    if pre_profile != expected_pre_profile:
        raise RehearsalError("pre-profile does not match the approved rehearsal state")

    provider.set_active_profile(requested_profile)
    post_profile = provider.read_active_profile()
    if post_profile != requested_profile:
        raise RehearsalError("simulated postcondition failed")

    provider.set_active_profile(pre_profile)
    rollback_profile = provider.read_active_profile()
    if rollback_profile != pre_profile:
        raise RehearsalError("simulated rollback postcondition failed")
    return {
        "status": "passed",
        "operation_id": OPERATION_ID,
        "revision": REVISION,
        "target": SIMULATOR_TARGET,
        "requested_profile": requested_profile,
        "pre_profile": pre_profile,
        "post_profile": post_profile,
        "rollback_profile": rollback_profile,
        "host_effect_occurred": False,
        "dbus_calls": 0,
        "filesystem_writes": 0,
        "executor_invoked": False,
        "rollback_verified": True,
        "temporary_state_discarded": True,
    }


def main() -> int:
    try:
        result = rehearse_transition()
    except RehearsalError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
