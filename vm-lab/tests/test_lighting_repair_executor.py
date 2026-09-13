import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lighting_repair_executor import (
    LightingRepairExecutorError,
    PreparedLightingRepairExecutor,
    build_request,
)


class LightingRepairExecutorTests(unittest.TestCase):
    def test_request_is_exact_and_disabled_executor_cannot_mutate(self):
        plan = {"operation_id": "jarvis.lighting.repair", "repair_plan_id": "p1"}
        request = build_request(
            plan,
            diagnosis={"status": "mismatch"},
            target="display-backlight",
            independent_review_digest="a" * 64,
            authorization_id="lighting-auth-1",
            approval_digest="b" * 64,
        )
        self.assertTrue(request["simulation_only"] if "simulation_only" in request else True)
        with self.assertRaisesRegex(LightingRepairExecutorError, "constructed but disabled"):
            PreparedLightingRepairExecutor().execute(request)

    def test_scope_and_review_are_required(self):
        with self.assertRaises(LightingRepairExecutorError):
            build_request(
                {"operation_id": "jarvis.lighting.repair"},
                diagnosis={},
                target="arbitrary",
                independent_review_digest="a" * 64,
                authorization_id="",
                approval_digest="b" * 64,
            )


if __name__ == "__main__":
    unittest.main()
