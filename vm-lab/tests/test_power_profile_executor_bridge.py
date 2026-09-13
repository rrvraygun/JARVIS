from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import power_profile_executor_bridge as BRIDGE
import power_profile_mutation as MUTATION


def future() -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat().replace("+00:00", "Z")


class FakeLedger:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.consumed: list[str] = []

    def consume(self, approval: BRIDGE.PowerProfileApproval) -> None:
        self.events.append("consume")
        self.consumed.append(approval.approval_id)


class FailingLedger:
    def consume(self, approval: BRIDGE.PowerProfileApproval) -> None:
        raise BRIDGE.PowerProfileExecutorError("durable ledger unavailable")


class FakeTransport:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.active = "balanced"
        self.set_calls: list[str] = []

    def get_all(self) -> dict[str, object]:
        return {
            "ActiveProfile": self.active,
            "Profiles": [
                {"Profile": "power-saver", "Driver": "tuned"},
                {"Profile": "balanced", "Driver": "tuned"},
                {"Profile": "performance", "Driver": "tuned"},
            ],
            "PerformanceDegraded": "",
        }

    def set_active_profile(self, profile: str) -> None:
        self.events.append("adapter")
        self.set_calls.append(profile)
        self.active = profile


class PowerProfileExecutorBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events: list[str] = []
        self.transport = FakeTransport(self.events)
        self.adapter = MUTATION.SupervisedPowerProfileAdapter(self.transport)
        self.target = dict(BRIDGE.TARGET)
        self.parameters = {
            "requested_profile": "performance",
            "pre_profile": "balanced",
            "tui_confirmed": True,
            "active_session": True,
            "on_battery": False,
            "thermal_degraded": False,
        }
        self.policy_digest = BRIDGE.current_policy_digest()

    def approval(self, **overrides: object) -> BRIDGE.PowerProfileApproval:
        values: dict[str, object] = {
            "approval_id": "approval-1",
            "operation_id": BRIDGE.OPERATION_ID,
            "operation_revision": BRIDGE.OPERATION_REVISION,
            "parameters_digest": BRIDGE.PreparedPowerProfileExecutor.parameters_digest(
                self.parameters
            ),
            "target_digest": BRIDGE.PreparedPowerProfileExecutor.target_digest(self.target),
            "policy_digest": self.policy_digest,
            "expires_at": future(),
            "idempotency_key": "idem-1",
        }
        values.update(overrides)
        return BRIDGE.PowerProfileApproval(**values)

    def test_disabled_bridge_has_no_ledger_or_adapter_effect(self) -> None:
        executor = BRIDGE.PreparedPowerProfileExecutor(
            adapter=self.adapter, ledger=FakeLedger(self.events)
        )
        with self.assertRaisesRegex(BRIDGE.PowerProfileExecutorError, "disabled"):
            executor.execute(
                self.approval(),
                **self.parameters,
                target=self.target,
                active_policy_digest=self.policy_digest,
            )
        self.assertEqual(self.events, [])

    def test_enabled_bridge_consumes_before_adapter(self) -> None:
        executor = BRIDGE.PreparedPowerProfileExecutor(
            enabled=True, adapter=self.adapter, ledger=FakeLedger(self.events)
        )
        result = executor.execute(
            self.approval(),
            **self.parameters,
            target=self.target,
            active_policy_digest=self.policy_digest,
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(self.events, ["consume", "adapter"])

    def test_parameter_target_and_policy_bindings_fail_closed(self) -> None:
        executor = BRIDGE.PreparedPowerProfileExecutor(
            enabled=True, adapter=self.adapter, ledger=FakeLedger(self.events)
        )
        cases = [
            ("parameter binding mismatch", {"requested_profile": "power-saver"}, {}),
            (
                "target is not the fixed PPD target",
                {},
                {"target": {"provider": "wrong"}},
            ),
            (
                "active policy is not the checked-in policy",
                {},
                {"active_policy_digest": "b" * 64},
            ),
        ]
        for message, parameter_overrides, call_overrides in cases:
            call = dict(self.parameters)
            call.update(parameter_overrides)
            call.update(call_overrides)
            call_target = call.pop("target", self.target)
            call_policy = call.pop("active_policy_digest", self.policy_digest)
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(BRIDGE.PowerProfileExecutorError, message),
            ):
                executor.execute(
                    self.approval(),
                    **call,
                    target=call_target,
                    active_policy_digest=call_policy,
                )
        self.assertEqual(self.events, [])

    def test_expired_approval_fails_before_consumption(self) -> None:
        executor = BRIDGE.PreparedPowerProfileExecutor(
            enabled=True, adapter=self.adapter, ledger=FakeLedger(self.events)
        )
        expired = (
            (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        )
        with self.assertRaisesRegex(BRIDGE.PowerProfileExecutorError, "expired"):
            executor.execute(
                self.approval(expires_at=expired),
                **self.parameters,
                target=self.target,
                active_policy_digest=self.policy_digest,
            )
        self.assertEqual(self.events, [])

    def test_approval_beyond_policy_window_fails_before_consumption(self) -> None:
        executor = BRIDGE.PreparedPowerProfileExecutor(
            enabled=True, adapter=self.adapter, ledger=FakeLedger(self.events)
        )
        too_long = (
            (datetime.now(timezone.utc) + timedelta(seconds=61)).isoformat().replace("+00:00", "Z")
        )
        with self.assertRaisesRegex(BRIDGE.PowerProfileExecutorError, "exceeds policy window"):
            executor.execute(
                self.approval(expires_at=too_long),
                **self.parameters,
                target=self.target,
                active_policy_digest=self.policy_digest,
            )
        self.assertEqual(self.events, [])

    def test_adapter_and_ledger_are_required_when_enabled(self) -> None:
        with self.assertRaisesRegex(BRIDGE.PowerProfileExecutorError, "requires adapter"):
            BRIDGE.PreparedPowerProfileExecutor(enabled=True)

    def test_untrusted_adapter_shape_is_rejected(self) -> None:
        class Lookalike:
            operation_id = BRIDGE.OPERATION_ID
            revision = BRIDGE.OPERATION_REVISION

        with self.assertRaisesRegex(BRIDGE.PowerProfileExecutorError, "reviewed implementation"):
            BRIDGE.PreparedPowerProfileExecutor(adapter=Lookalike())  # type: ignore[arg-type]

    def test_ledger_failure_prevents_adapter_call(self) -> None:
        executor = BRIDGE.PreparedPowerProfileExecutor(
            enabled=True, adapter=self.adapter, ledger=FailingLedger()
        )
        with self.assertRaisesRegex(BRIDGE.PowerProfileExecutorError, "ledger unavailable"):
            executor.execute(
                self.approval(),
                **self.parameters,
                target=self.target,
                active_policy_digest=self.policy_digest,
            )
        self.assertEqual(self.events, [])


if __name__ == "__main__":
    unittest.main()
