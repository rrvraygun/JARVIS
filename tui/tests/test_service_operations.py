from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "service_helper_fixture", ROOT / "vm-lab/scripts/jarvis_service_control.py"
)
assert spec and spec.loader
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class ServiceOperationTests(unittest.TestCase):
    def test_digest_drift_and_protected_units_never_execute(self):
        runner = Mock()
        with self.assertRaises(ValueError):
            api.valid_unit("auditd.service")
        with self.assertRaises(ValueError):
            api.valid_unit("example.service; whoami")
        with self.assertRaises(ValueError):
            api.execute(
                {
                    "id": "a" * 32,
                    "operation": "restart",
                    "unit": "fixture.service",
                    "pre_state_digest": "wrong",
                    "policy_digest": "wrong",
                },
                {},
                {},
                Mock(),
                runner,
            )
        runner.assert_not_called()

    def test_reservation_precedes_exact_single_service_command(self):
        state = {"UnitFileState": "enabled", "ActiveState": "active"}
        policy = {"operations": ["restart"], "recovery_evidence_digest": "a" * 64}
        request = {
            "id": "b" * 32,
            "operation": "restart",
            "unit": "fixture.service",
            "pre_state_digest": api.binding(state),
            "policy_digest": api.binding(policy),
        }
        events = []

        def reserve(record):
            events.append("reserved")

        def run(argv, **kwargs):
            self.assertEqual(events, ["reserved"])
            self.assertEqual(argv, ["/usr/bin/systemctl", "restart", "fixture.service"])
            events.append("executed")
            return subprocess.CompletedProcess(argv, 0)

        result = api.execute(request, state, policy, reserve, run)
        self.assertEqual(events, ["reserved", "executed"])
        self.assertEqual(result["status"], "applied_unverified")

    def test_duplicate_reservation_prevents_command(self):
        state = {"UnitFileState": "disabled"}
        policy = {"operations": ["enable"], "recovery_evidence_digest": "a" * 64}
        request = {
            "id": "b" * 32,
            "operation": "enable",
            "unit": "fixture.service",
            "pre_state_digest": api.binding(state),
            "policy_digest": api.binding(policy),
        }
        runner = Mock()
        with self.assertRaises(FileExistsError):
            api.execute(request, state, policy, Mock(side_effect=FileExistsError), runner)
        runner.assert_not_called()

    def test_install_effects_are_exact_and_complex_syntax_rejected(self):
        self.assertEqual(
            api.install_links(b"[Install]\nWantedBy=multi-user.target\n", "fixture.service"),
            ["/etc/systemd/system/multi-user.target.wants/fixture.service"],
        )
        for text in (
            b"[Install]\nAlso=another.service\n",
            b"[Install]\nAlias=alias.service\n",
            b"[Install]\nWantedBy=%i.target\n",
        ):
            with self.assertRaises(ValueError):
                api.install_links(text, "fixture.service")

    def test_dependency_graph_is_refused_before_reading_fragment(self):
        output = (
            b"Id=fixture.service\nLoadState=loaded\nNeedDaemonReload=no\nRequires=another.service\n"
        )
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, output))
        with self.assertRaisesRegex(ValueError, "complex_effects"):
            api.observe("fixture.service", runner)
