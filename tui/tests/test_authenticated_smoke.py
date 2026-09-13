"""No live account or external service is used by these tests."""

import importlib.util
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/smoke-authenticated.py"
SPEC = importlib.util.spec_from_file_location("smoke_authenticated", SCRIPT)
assert SPEC and SPEC.loader
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


class FakeClient:
    def __init__(self, result=None, fail=False):
        self.result = result
        self.fail = fail
        self.calls = []

    async def start(self):
        self.calls.append("start")
        if self.fail:
            raise RuntimeError("sensitive-provider-error")

    async def request(self, method, params):
        self.calls.append((method, params))
        return self.result

    async def stop(self):
        self.calls.append("stop")


class AuthenticatedSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_account_read_without_refresh_and_no_identity_output(self):
        client = FakeClient({"account": {"type": "chatgpt", "email": "private@example.test"}})
        result = await SMOKE.probe(client)
        self.assertTrue(result["account_available"])
        self.assertFalse(result["authenticated_turn_verified"])
        self.assertNotIn("private", json.dumps(result))
        self.assertEqual(client.calls, ["start", ("account/read", {"refreshToken": False}), "stop"])

    async def test_no_account_is_not_a_pass(self):
        result = await SMOKE.probe(FakeClient({"account": None}))
        self.assertEqual(result["status"], "login_required")

    async def test_error_is_sanitized_and_child_stopped(self):
        client = FakeClient(fail=True)
        result = await SMOKE.probe(client)
        self.assertEqual(result["status"], "account_probe_failed")
        self.assertNotIn("sensitive", json.dumps(result))
        self.assertEqual(client.calls, ["start", "stop"])
