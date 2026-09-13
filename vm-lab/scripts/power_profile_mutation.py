#!/usr/bin/env python3
"""Prepared, unregistered supervised TuneD/PPD profile adapter.

The adapter has one fixed D-Bus mutation: setting ActiveProfile. It is not
registered with the executor or TUI in this revision. Callers must provide the
approved TUI/session gates; the durable one-use ledger remains an executor
responsibility before this adapter may be wired.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol

import power_profile_authorization as authorization
from power_profile_status import (
    BUS_NAME,
    INTERFACE,
    OBJECT_PATH,
    PowerProfileStatus,
    PowerProfileStatusError,
    parse_properties,
)


class PowerProfileMutationError(ValueError):
    """Raised when a supervised transition cannot complete safely."""


class ProfileTransport(Protocol):
    def get_all(self) -> Mapping[str, Any]:
        """Read the fixed provider properties."""

    def set_active_profile(self, profile: str) -> None:
        """Set only the fixed ActiveProfile property."""


class FixedDbusProfileTransport:
    """System-bus transport with exactly one read and one write operation."""

    def __init__(self, bus_factory: Callable[[], Any] | None = None) -> None:
        self._bus_factory = bus_factory or self._system_bus

    @staticmethod
    def _system_bus() -> Any:
        try:
            import dbus  # type: ignore[import-not-found]
        except ImportError as exc:
            raise PowerProfileMutationError("Python D-Bus bindings are unavailable") from exc
        return dbus.SystemBus()

    def _properties(self) -> Any:
        try:
            import dbus  # type: ignore[import-not-found]

            bus = self._bus_factory()
            proxy = bus.get_object(BUS_NAME, OBJECT_PATH)
            return dbus.Interface(proxy, dbus.PROPERTIES_IFACE)
        except PowerProfileMutationError:
            raise
        except Exception as exc:
            raise PowerProfileMutationError("power-profile provider is unavailable") from exc

    def get_all(self) -> Mapping[str, Any]:
        try:
            return self._properties().GetAll(INTERFACE)
        except PowerProfileMutationError:
            raise
        except Exception as exc:
            raise PowerProfileMutationError("power-profile status read failed") from exc

    def set_active_profile(self, profile: str) -> None:
        if profile not in authorization.PROFILES:
            raise PowerProfileMutationError("requested profile is unsupported")
        try:
            import dbus  # type: ignore[import-not-found]

            self._properties().Set(INTERFACE, "ActiveProfile", dbus.String(profile))
        except PowerProfileMutationError:
            raise
        except Exception as exc:
            raise PowerProfileMutationError("power-profile mutation failed") from exc


class SupervisedPowerProfileAdapter:
    """One-transition adapter; intentionally not registered in this revision."""

    operation_id = "jarvis.powerprofile.select"
    revision = "1.0.0"

    def __init__(self, transport: ProfileTransport) -> None:
        self._transport = transport

    @staticmethod
    def _status(raw: Mapping[str, Any]) -> PowerProfileStatus:
        try:
            return parse_properties(raw)
        except PowerProfileStatusError as exc:
            raise PowerProfileMutationError("provider status is invalid") from exc

    def execute(
        self,
        requested_profile: str,
        *,
        pre_profile: str,
        tui_confirmed: bool,
        active_session: bool,
        on_battery: bool = False,
        thermal_degraded: bool = False,
        notification_sink: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Perform one exact transition after external ledger admission.

        This method deliberately does not consume the durable ledger. The
        executor must consume it before a future registration can call here.
        """

        before = self._status(self._transport.get_all())
        try:
            plan = authorization.build_plan(
                requested_profile,
                pre_profile=pre_profile,
                tui_confirmed=tui_confirmed,
                active_session=active_session,
                on_battery=on_battery,
                thermal_degraded=thermal_degraded,
                provider_degraded=before.performance_degraded,
            )
        except authorization.PowerProfileAuthorizationError as exc:
            raise PowerProfileMutationError(str(exc)) from exc
        if before.active_profile != plan.pre_profile:
            raise PowerProfileMutationError("provider pre-state is stale")
        available_profiles = {profile["Profile"] for profile in before.profiles}
        if requested_profile not in available_profiles:
            raise PowerProfileMutationError("requested profile is unavailable from provider")
        if before.active_profile == requested_profile:
            raise PowerProfileMutationError("requested profile is already active")
        if notification_sink is not None:
            for notification in plan.notifications:
                try:
                    notification_sink(notification)
                except Exception:
                    # Notification delivery is advisory and must not widen or
                    # block the single approved state-changing operation.
                    pass
        try:
            self._transport.set_active_profile(requested_profile)
        except Exception as exc:
            raise PowerProfileMutationError(
                "mutation outcome is indeterminate; stopped without automatic rollback; "
                "new approval required"
            ) from exc
        try:
            after = self._status(self._transport.get_all())
        except Exception as exc:
            raise PowerProfileMutationError(
                "postcondition could not be verified; stopped without automatic rollback; "
                "new approval required"
            ) from exc
        if after.active_profile != requested_profile:
            raise PowerProfileMutationError(
                "postcondition failed; stopped without automatic rollback; new approval required"
            )
        return {
            "status": "passed",
            "operation_id": self.operation_id,
            "revision": self.revision,
            "provider": "tuned-ppd",
            "pre_profile": before.active_profile,
            "post_profile": after.active_profile,
            "notifications": list(plan.notifications),
            "rollback_requires_new_approval": True,
            "automatic_rollback": False,
            "authorization_consumed_by_adapter": False,
        }
