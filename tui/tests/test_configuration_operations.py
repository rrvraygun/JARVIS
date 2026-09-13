from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "configuration_fixture", ROOT / "vm-lab/scripts/jarvis_configuration_control.py"
)
assert spec and spec.loader
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
UUID = "11111111-1111-4111-8111-111111111111"


class ConfigurationOperationTests(unittest.TestCase):
    def test_fixed_commands_and_invalid_targets(self):
        self.assertEqual(
            api.command("network.ipv4_dns", UUID, ["1.1.1.1"]),
            ["/usr/bin/nmcli", "connection", "modify", "uuid", UUID, "ipv4.dns", "1.1.1.1"],
        )
        self.assertEqual(
            api.command("security.firewall_service", "public/https", "present"),
            ["/usr/bin/firewall-cmd", "--zone=public", "--add-service=https"],
        )
        self.assertEqual(
            api.command("security.restore_labels", "/etc/example.conf", "default"),
            ["/usr/sbin/restorecon", "--", "/etc/example.conf"],
        )
        for adapter, target, value in [
            ("network.ipv4_dns", "ambiguous-name", ["1.1.1.1"]),
            ("network.ipv4_dns", UUID, ["example.test"]),
            ("security.firewall_service", "public/ssh;echo", "present"),
            ("security.restore_labels", "/etc/../tmp/file", "default"),
            ("security.restore_labels", "/etc/file", "permissive"),
        ]:
            with self.assertRaises(ValueError):
                api.command(adapter, target, value)

    def test_one_reserved_attempt_and_exact_receipt(self):
        state = {"value": [], "target": UUID}
        policy = {"allowed_values": [["1.1.1.1"]], "recovery_evidence_digest": "a" * 64}
        request = {
            "id": "b" * 32,
            "adapter": "network.ipv4_dns",
            "target": UUID,
            "desired": ["1.1.1.1"],
            "pre_state_digest": api.digest(state),
            "policy_digest": api.digest(policy),
        }
        events = []

        def reserve(record):
            events.append("reserved")

        def run(argv, **kwargs):
            self.assertEqual(events, ["reserved"])
            events.append("executed")
            return subprocess.CompletedProcess(argv, 0)

        result = api.apply(request, state, policy, reserve, run)
        self.assertEqual(result["status"], "applied_unverified")
        self.assertEqual(events, ["reserved", "executed"])
        request["pre_state_digest"] = "wrong"
        runner = Mock()
        with self.assertRaises(ValueError):
            api.apply(request, state, policy, Mock(), runner)
        runner.assert_not_called()

    def test_used_reservation_prevents_configuration_command(self):
        state = {"value": "absent"}
        policy = {"allowed_values": ["present"], "recovery_evidence_digest": "a" * 64}
        request = {
            "id": "b" * 32,
            "adapter": "security.firewall_service",
            "target": "public/https",
            "desired": "present",
            "pre_state_digest": api.digest(state),
            "policy_digest": api.digest(policy),
        }
        runner = Mock()
        with self.assertRaises(FileExistsError):
            api.apply(request, state, policy, Mock(side_effect=FileExistsError), runner)
        runner.assert_not_called()

    def test_selinux_hardlinks_are_rejected_before_reading_label(self):
        import stat
        from types import SimpleNamespace
        from unittest.mock import patch

        directory = SimpleNamespace(st_uid=0, st_mode=stat.S_IFDIR | 0o755)
        regular = SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o644, st_nlink=2)
        with (
            patch.object(api.os, "open", side_effect=[10, 11, 12]),
            patch.object(api.os, "fstat", side_effect=[directory, regular]),
            patch.object(api.os, "close"),
            patch.object(api.os, "getxattr") as label,
        ):
            with self.assertRaisesRegex(ValueError, "selinux_target_unsafe"):
                api.file_identity("/etc/example.conf")
            label.assert_not_called()

    def test_configuration_observation_caps_output_during_read(self):
        with self.assertRaisesRegex(ValueError, "observation_output_limit"):
            api.bounded_read_process(["/usr/bin/python3", "-c", 'print("x"*10000)'])
