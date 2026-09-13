#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


TUI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.app_server import ALLOWED_NOTIFICATION_METHODS, ALLOWED_REQUEST_METHODS  # noqa: E402
from jarvis_tui.event_reducer import SERVER_REQUEST_METHODS  # noqa: E402
from jarvis_tui.preflight import PREFLIGHT_OUTPUT_SCHEMA  # noqa: E402


class GeneratedProtocolSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.compatibility = json.loads(
            (TUI_ROOT / "protocol-compatibility.json").read_text(encoding="utf-8")
        )
        self.schema_root = (
            TUI_ROOT / "vendor/codex-app-server-schema" / self.compatibility["codex_cli_version"]
        )

    def test_allowlist_is_pinned_to_generated_stable_schema(self) -> None:
        client_requests = (self.schema_root / "ClientRequest.json").read_text(encoding="utf-8")
        for method in ALLOWED_REQUEST_METHODS:
            self.assertIn(f'"{method}"', client_requests)
        self.assertEqual(
            set(self.compatibility["allowed_client_request_methods"]),
            set(ALLOWED_REQUEST_METHODS),
        )
        self.assertEqual(
            set(self.compatibility["allowed_client_notification_methods"]),
            set(ALLOWED_NOTIFICATION_METHODS),
        )
        self.assertFalse(self.compatibility["experimental_schema"])

    def test_every_stable_server_request_is_recognized(self) -> None:
        schema = json.loads((self.schema_root / "ServerRequest.json").read_text())
        stable = {
            method
            for variant in schema["oneOf"]
            for method in variant["properties"]["method"]["enum"]
        }
        self.assertLessEqual(stable, SERVER_REQUEST_METHODS)
        self.assertEqual(
            set(self.compatibility["recognized_server_request_methods"]),
            set(SERVER_REQUEST_METHODS),
        )

    def test_wire_values_match_version_generated_parameter_schemas(self) -> None:
        thread = json.loads((self.schema_root / "v2/ThreadStartParams.json").read_text())
        turn = json.loads((self.schema_root / "v2/TurnStartParams.json").read_text())
        injection = json.loads((self.schema_root / "v2/ThreadInjectItemsParams.json").read_text())
        approval_values = set()
        for option in thread["definitions"]["AskForApproval"]["oneOf"]:
            approval_values.update(option.get("enum", []))
        self.assertIn(
            self.compatibility["wire_values"]["execution_approval_policy"], approval_values
        )
        self.assertIn(
            self.compatibility["wire_values"]["preflight_approval_policy"], approval_values
        )
        self.assertIn(
            self.compatibility["wire_values"]["thread_sandbox"],
            thread["definitions"]["SandboxMode"]["enum"],
        )
        policy_types = {
            variant["properties"]["type"]["enum"][0]
            for variant in turn["definitions"]["SandboxPolicy"]["oneOf"]
        }
        self.assertIn(
            self.compatibility["wire_values"]["execution_turn_sandbox_policy"]["type"],
            policy_types,
        )
        self.assertIn(
            self.compatibility["wire_values"]["preflight_turn_sandbox_policy"]["type"],
            policy_types,
        )
        self.assertIn("outputSchema", turn["properties"])
        self.assertIn("anyOf", PREFLIGHT_OUTPUT_SCHEMA["properties"]["assessment"])
        self.assertNotIn("oneOf", json.dumps(PREFLIGHT_OUTPUT_SCHEMA))
        self.assertEqual(set(injection["required"]), {"threadId", "items"})
        self.assertEqual(injection["properties"]["items"]["type"], "array")


if __name__ == "__main__":
    unittest.main()
