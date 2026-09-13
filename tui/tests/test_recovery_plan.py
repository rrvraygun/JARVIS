from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis_tui.recovery_plan import prepare


class RecoveryPlanTests(unittest.TestCase):
    def test_plan_binds_device_and_keeps_each_step_approval_scoped(self):
        plan = prepare(
            device_uuid="E824FE8B24FE5BCE",
            mountpoint="/run/media/tipexxx/LG_EXT_HDD",
            repository_prefix="e372e10c",
            destination="/var/lib/jarvis-recovery-scratch",
        )
        self.assertEqual(plan["boundaries"], ["root", "home", "machines", "boot", "efi"])
        self.assertEqual(plan["retention"], {"keep_last": 10, "deletion": "separate-exact-approval"})
        self.assertEqual([step["sequence"] for step in plan["operations"]], list(range(1, 13)))
        self.assertFalse(plan["claims"]["full_system_recovery"])
        self.assertIn("repository_integrity_not_currently_verified", plan["blockers"])

    def test_invalid_identity_and_retention_are_rejected(self):
        with self.assertRaises(ValueError):
            prepare(device_uuid="bad", mountpoint="/run/media/tipexxx/x", repository_prefix="e372e10c", destination="/tmp/x")
        with self.assertRaises(ValueError):
            prepare(device_uuid="E824FE8B24FE5BCE", mountpoint="/run/media/tipexxx/x", repository_prefix="e372e10c", destination="/tmp/x", retention=11)
