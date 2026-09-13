from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis_tui.update_plan import prepare


class UpdatePlanTests(unittest.TestCase):
    def test_normal_updates_and_critical_recovery_gate(self):
        normal = prepare(["bash-5.2.26-3.fc44.x86_64"], recovery_verified=False)
        self.assertFalse(normal["recovery_required"])
        critical = prepare(["kernel-core-6.14.0-1.fc44.x86_64"], recovery_verified=False)
        self.assertTrue(critical["recovery_required"])
        self.assertIn("current_R2_recovery_not_verified", critical["blockers"])
        reported = prepare(["kernel-core-6.14.0-1.fc44.x86_64"], recovery_verified=True)
        self.assertFalse(reported["execution_authorized"])
        self.assertIn("signed_local_artifacts_and_exact_root_review_required", reported["blockers"])

    def test_akmods_are_critical_and_caller_flags_cannot_grant_authority(self):
        plan = prepare(["akmod-nvidia-1.0-1.fc44.x86_64"], recovery_verified=True)
        self.assertTrue(plan["critical_families"])
        self.assertTrue(plan["blockers"])
        self.assertFalse(plan["execution_authorized"])

    def test_requires_unique_exact_nevra(self):
        with self.assertRaises(ValueError):
            prepare(["kernel-core"], recovery_verified=True)
        with self.assertRaises(ValueError):
            prepare(["bash-1.0-1.x86_64", "bash-1.0-1.x86_64"], recovery_verified=True)
