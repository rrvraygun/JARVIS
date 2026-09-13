#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

TUI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.app_server import (  # noqa: E402
    ALLOWED_REQUEST_METHODS,
    APP_SERVER_ENVIRONMENT_KEYS,
    AppServerMethodDenied,
    StdioAppServerClient,
    _within_protocol_limits,
    subscription_account_status,
    subscription_environment,
    turn_start_request,
)


class InitializationTests(unittest.IsolatedAsyncioTestCase):
    async def test_declares_granular_approval_protocol_capability(self):
        client = StdioAppServerClient()
        process = type("Process", (), {"returncode": 0})()
        with (
            patch(
                "jarvis_tui.app_server.asyncio.create_subprocess_exec",
                AsyncMock(return_value=process),
            ),
            patch.object(client, "_read_loop", AsyncMock()),
            patch.object(client, "_stderr_loop", AsyncMock()),
            patch.object(client, "request", AsyncMock(return_value={})),
            patch.object(client, "notify", AsyncMock()),
        ):
            try:
                await client.start()
                method, params = client.request.call_args.args
                self.assertEqual(method, "initialize")
                self.assertEqual(params["capabilities"], {"experimentalApi": True})
                client.notify.assert_awaited_once_with("initialized", {})
            finally:
                await client.stop()


class AppServerContractTests(unittest.TestCase):
    def test_app_server_environment_preserves_configured_auth_without_logging(self) -> None:
        environment = subscription_environment(
            {
                "PATH": "/usr/bin",
                "OPENAI_API_KEY": "paid-api-key",
                "CODEX_API_KEY": "paid-codex-key",
                "CODEX_HOME": "/tmp/codex-fixture",
            }
        )
        self.assertEqual(environment["OPENAI_API_KEY"], "paid-api-key")
        self.assertEqual(environment["CODEX_API_KEY"], "paid-codex-key")
        self.assertEqual(environment["CODEX_HOME"], "/tmp/codex-fixture")
        self.assertNotIn(
            "AWS_SECRET_ACCESS_KEY",
            subscription_environment(
                {"PATH": "/usr/bin", "AWS_SECRET_ACCESS_KEY": "must-not-cross"}
            ),
        )
        self.assertIn("OPENAI_API_KEY", APP_SERVER_ENVIRONMENT_KEYS)

    def test_protocol_limits_reject_deep_or_oversized_values(self) -> None:
        nested: object = "value"
        for _ in range(33):
            nested = {"next": nested}
        self.assertFalse(_within_protocol_limits(nested))
        self.assertFalse(_within_protocol_limits({"text": "x" * (128 * 1024 + 1)}))
        self.assertTrue(_within_protocol_limits({"method": "turn/completed", "params": {}}))

    def test_turn_builder_uses_explicit_execution_policy(self) -> None:
        request = turn_start_request(
            "thr_fixture",
            "Prepare a diagnosis.",
            Path("/tmp/jarvis-fixture"),
            sandbox_policy={"type": "dangerFullAccess"},
            approval_policy="untrusted",
        )
        encoded = str(request)
        self.assertEqual(request["params"]["sandboxPolicy"], {"type": "dangerFullAccess"})
        self.assertEqual(request["params"]["approvalPolicy"], "untrusted")
        self.assertIn("dangerFullAccess", encoded)
        self.assertNotIn("thread/shellCommand", encoded)
        self.assertNotIn("process/spawn", encoded)

    def test_chatgpt_and_api_key_auth_are_ready(self) -> None:
        ready = subscription_account_status({"account": {"type": "chatgpt", "planType": "plus"}})
        api_key = subscription_account_status({"account": {"type": "apikey"}})
        missing = subscription_account_status({"account": None})
        self.assertEqual(ready["state"], "ready")
        self.assertEqual(api_key["state"], "ready")
        self.assertEqual(api_key["auth_mode"], "apiKey")
        self.assertEqual(missing["state"], "login_required")

    def test_transport_denies_non_phase_one_methods_before_writing(self) -> None:
        async def exercise() -> None:
            client = StdioAppServerClient()
            for method in ("thread/shellCommand", "command/exec", "process/spawn", "fs/watch"):
                with self.assertRaises(AppServerMethodDenied):
                    await client.request(method, {})

        import asyncio

        asyncio.run(exercise())

    def test_transport_exposes_exact_server_request_response_method(self) -> None:
        client = StdioAppServerClient()
        self.assertTrue(hasattr(client, "respond"))

    def test_transport_allows_only_the_context_injection_thread_extension(self) -> None:
        self.assertIn("thread/inject_items", ALLOWED_REQUEST_METHODS)
        self.assertNotIn("thread/injectItems", ALLOWED_REQUEST_METHODS)
        self.assertNotIn("conversation/create", ALLOWED_REQUEST_METHODS)


if __name__ == "__main__":
    unittest.main()
