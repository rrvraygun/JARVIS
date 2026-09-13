from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import power_profile_authorization as AUTH


class PowerProfileAuthorizationTests(unittest.TestCase):
    def _plan(self, **kwargs: object) -> AUTH.TransitionPlan:
        values: dict[str, object] = {
            "tui_confirmed": True,
            "active_session": True,
        }
        values.update(kwargs)
        return AUTH.build_plan("performance", pre_profile="balanced", **values)  # type: ignore[arg-type]

    def test_plan_binds_provider_and_one_use_boundary(self) -> None:
        result = self._plan().as_dict()
        self.assertEqual(result["provider"], "tuned-ppd")
        self.assertEqual(result["expires_in_seconds"], 60)
        self.assertTrue(result["one_use"])
        self.assertTrue(result["rollback_requires_new_approval"])
        self.assertFalse(result["host_effect_occurred"])
        self.assertFalse(result["authorization_consumed"])

    def test_warnings_are_notifications_only(self) -> None:
        result = self._plan(
            on_battery=True, thermal_degraded=True, provider_degraded="lap-detected"
        )
        self.assertEqual(
            result.notifications,
            ("on-battery", "thermal-degradation", "provider-degraded:lap-detected"),
        )

    def test_rejects_without_confirmation_or_active_session(self) -> None:
        with self.assertRaisesRegex(AUTH.PowerProfileAuthorizationError, "TUI"):
            self._plan(tui_confirmed=False)
        with self.assertRaisesRegex(AUTH.PowerProfileAuthorizationError, "active user"):
            self._plan(active_session=False)

    def test_rejects_profile_or_provider_drift(self) -> None:
        with self.assertRaisesRegex(AUTH.PowerProfileAuthorizationError, "unsupported"):
            AUTH.build_plan(
                "jarvis-balanced",
                pre_profile="balanced",
                tui_confirmed=True,
                active_session=True,
            )
        with self.assertRaisesRegex(AUTH.PowerProfileAuthorizationError, "provider"):
            self._plan(provider="power-profiles-daemon")

    def test_rejects_policy_binding_drift(self) -> None:
        policy = AUTH.load_policy()
        policy["authorization"] = dict(policy["authorization"])
        policy["authorization"]["expiry_seconds"] = 61
        with self.assertRaisesRegex(AUTH.PowerProfileAuthorizationError, "timing"):
            self._plan(policy=policy)

    def test_rejects_provider_session_ledger_and_registration_drift(self) -> None:
        for field, value, message in (
            ("bus_name", "evil.bus", "provider"),
            ("target", "all-users", "provider"),
        ):
            policy = AUTH.load_policy()
            policy["provider"] = dict(policy["provider"])
            policy["provider"][field] = value
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(AUTH.PowerProfileAuthorizationError, message),
            ):
                self._plan(policy=policy)
        policy = AUTH.load_policy()
        policy["authorization"] = dict(policy["authorization"])
        policy["authorization"]["ledger"] = "memory"
        with self.assertRaisesRegex(AUTH.PowerProfileAuthorizationError, "timing"):
            self._plan(policy=policy)
        policy = AUTH.load_policy()
        policy["tui_reachable"] = True
        with self.assertRaisesRegex(AUTH.PowerProfileAuthorizationError, "registration"):
            self._plan(policy=policy)


if __name__ == "__main__":
    unittest.main()
