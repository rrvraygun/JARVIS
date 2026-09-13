from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lighting_repair_plan import (
    LightingRepairPlanError,
    PreparedLightingRepairExecutor,
    build_plan,
)


class LightingRepairPlanTests(unittest.TestCase):
    def test_builds_exact_disabled_plan(self) -> None:
        plan = build_plan(
            {"id": "lighting.backlight.requested-vs-actual", "status": "mismatch"},
            target="display-backlight",
            pre_state={"brightness": "12", "actual_brightness": "4"},
        )
        self.assertFalse(plan["execution_enabled"])
        self.assertFalse(plan["network_used"])
        self.assertFalse(plan["credentials_used"])
        self.assertFalse(plan["arbitrary_command"])
        self.assertIn("new explicit approval", plan["rollback"][0])

    def test_rejects_unknown_or_unready_scope(self) -> None:
        with self.assertRaises(LightingRepairPlanError):
            build_plan({"status": "unknown"}, target="display-backlight", pre_state={"x": 1})
        with self.assertRaises(LightingRepairPlanError):
            build_plan({"status": "consistent"}, target="display-backlight", pre_state={"x": 1})
        with self.assertRaises(LightingRepairPlanError):
            build_plan({"status": "mismatch"}, target="filesystem", pre_state={"x": 1})

    def test_executor_is_fail_closed(self) -> None:
        executor = PreparedLightingRepairExecutor()
        with self.assertRaises(LightingRepairPlanError):
            executor.execute({"operation_id": "jarvis.lighting.repair"})


if __name__ == "__main__":
    unittest.main()
