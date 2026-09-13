from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from phase5_executor import (
    ExecutorError,
    InMemoryApprovalLedger,
    OperationApproval,
    SupervisedExecutor,
)


class Phase5ExecutorTests(unittest.TestCase):
    target = {"kind": "fixture", "id": "one"}
    policy_digest = "b" * 64

    def approval(self, **changes):
        value = dict(
            approval_id="approval-1",
            request_id="request-1",
            operation_id="fixture.operation",
            operation_revision="1.0.0",
            target_digest=SupervisedExecutor.target_digest(self.target),
            parameters_digest=SupervisedExecutor.parameters_digest({"mode": "safe"}),
            policy_digest=self.policy_digest,
            expires_at=(dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5))
            .isoformat()
            .replace("+00:00", "Z"),
            idempotency_key="idempotency-1",
            approved=True,
            consumed=False,
        )
        value.update(changes)
        return OperationApproval(**value)

    def test_unregistered_operation_fails_closed(self) -> None:
        with self.assertRaisesRegex(ExecutorError, "not registered"):
            SupervisedExecutor().execute(
                self.approval(),
                parameters={"mode": "safe"},
                target=self.target,
                active_policy_digest=self.policy_digest,
            )

    def test_parameter_binding_is_exact(self) -> None:
        with self.assertRaisesRegex(ExecutorError, "parameter binding"):
            SupervisedExecutor().execute(
                self.approval(),
                parameters={"mode": "other"},
                target=self.target,
                active_policy_digest=self.policy_digest,
            )

    def test_unapproved_expired_or_consumed_approval_fails(self) -> None:
        for approval in (
            self.approval(approved=False),
            self.approval(consumed=True),
            self.approval(expires_at="2000-01-01T00:00:00Z"),
        ):
            with self.assertRaises(ExecutorError):
                SupervisedExecutor().execute(
                    approval,
                    parameters={"mode": "safe"},
                    target=self.target,
                    active_policy_digest=self.policy_digest,
                )

    def test_target_and_policy_bindings_are_exact(self) -> None:
        for kwargs, message in (
            ({"target": {"kind": "fixture", "id": "other"}}, "target binding"),
            ({"active_policy_digest": "c" * 64}, "policy binding"),
        ):
            call = {
                "parameters": {"mode": "safe"},
                "target": self.target,
                "active_policy_digest": self.policy_digest,
            }
            call.update(kwargs)
            with self.assertRaisesRegex(ExecutorError, message):
                SupervisedExecutor().execute(self.approval(), **call)

    def test_one_use_ledger_rejects_replay(self) -> None:
        class Adapter:
            operation_id = "fixture.operation"
            revision = "1.0.0"

            def execute(self, parameters):
                return parameters

        ledger = InMemoryApprovalLedger()
        executor = SupervisedExecutor(
            enabled=True,
            adapters=(Adapter(),),
            ledger=ledger,
        )
        call = {
            "parameters": {"mode": "safe"},
            "target": self.target,
            "active_policy_digest": self.policy_digest,
        }
        with self.assertRaisesRegex(ExecutorError, "not activated"):
            executor.execute(self.approval(), **call)
        with self.assertRaisesRegex(ExecutorError, "already been consumed"):
            executor.execute(self.approval(), **call)


if __name__ == "__main__":
    unittest.main()
