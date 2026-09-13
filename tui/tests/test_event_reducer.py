#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TUI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.event_reducer import (
    SERVER_REQUEST_METHODS,  # noqa: E402
    AppServerEventReducer,  # noqa: E402
)


class EventReducerTests(unittest.TestCase):
    def test_mcp_activity_exposes_only_safe_tool_summary(self):
        event = AppServerEventReducer().normalize(
            {
                "method": "item/completed",
                "params": {
                    "item": {
                        "id": "tool-1",
                        "type": "mcpToolCall",
                        "status": "failed",
                        "server": "jarvis_control",
                        "tool": "inspect_packages",
                        "arguments": {"query": "node", "secret": "do-not-display"},
                        "error": {"message": "do-not-display"},
                    }
                },
            }
        )
        self.assertEqual(event.kind, "tool_execution")
        self.assertEqual(event.metadata["tool"], "inspect_packages")
        self.assertEqual(event.metadata["query"], "node")
        self.assertEqual(event.metadata["error_code"], "tool_call_failed")
        self.assertNotIn("do-not-display", str(event.metadata))

    def test_all_recognized_server_requests_fail_closed_without_payload(self) -> None:
        reducer = AppServerEventReducer()
        for index, method in enumerate(sorted(SERVER_REQUEST_METHODS)):
            with self.subTest(method=method):
                event = reducer.normalize(
                    {
                        "method": method,
                        "id": index,
                        "params": {
                            "threadId": "thread",
                            "turnId": "turn",
                            "itemId": f"item-{index}",
                            "command": "private payload",
                        },
                    }
                )
                self.assertIsNotNone(event)
                self.assertEqual(event.kind, "server_request")  # type: ignore[union-attr]
                self.assertEqual(event.status, "pending")  # type: ignore[union-attr]
                self.assertNotIn("private payload", json.dumps(event.journal_details()))  # type: ignore[union-attr]

    def test_mcp_elicitation_request_keeps_safe_review_metadata(self) -> None:
        event = AppServerEventReducer().normalize(
            {
                "id": 7,
                "method": "mcpServer/elicitation/request",
                "params": {
                    "serverName": "jarvis_control",
                    "message": "Allow one Power inventory read?",
                    "mode": "form",
                    "requestedSchema": {"type": "object"},
                },
            }
        )
        assert event is not None
        self.assertEqual(event.kind, "server_request")
        self.assertEqual(event.metadata["server_name"], "jarvis_control")
        self.assertEqual(event.metadata["message"], "Allow one Power inventory read?")
        self.assertNotIn("requestedSchema", event.metadata)

    def test_lifecycle_events_are_idempotent_but_identical_deltas_are_not_lost(self) -> None:
        reducer = AppServerEventReducer()
        completed = {
            "method": "turn/completed",
            "params": {"threadId": "thr", "turn": {"id": "turn", "status": "completed"}},
        }
        self.assertIsNotNone(reducer.normalize(completed))
        self.assertIsNone(reducer.normalize(completed))
        delta = {
            "method": "item/agentMessage/delta",
            "params": {"threadId": "thr", "turnId": "turn", "itemId": "item", "delta": "the"},
        }
        self.assertEqual(reducer.normalize(delta).text, "the")  # type: ignore[union-attr]
        self.assertEqual(reducer.normalize(delta).text, "the")  # type: ignore[union-attr]

    def test_statusless_agent_items_derive_status_from_lifecycle_method(self) -> None:
        reducer = AppServerEventReducer()
        started = reducer.normalize(
            {
                "method": "item/started",
                "params": {
                    "turnId": "turn",
                    "item": {
                        "id": "agent-item",
                        "type": "agentMessage",
                        "text": "Hello from the agent.",
                    },
                },
            }
        )
        completed = reducer.normalize(
            {
                "method": "item/completed",
                "params": {
                    "turnId": "turn",
                    "item": {
                        "id": "agent-item",
                        "type": "agentMessage",
                        "text": "Hello from the agent.",
                    },
                },
            }
        )
        assert started is not None and completed is not None
        self.assertEqual(started.kind, "agent_message")
        self.assertEqual(started.status, "in_progress")
        self.assertEqual(completed.kind, "agent_message")
        self.assertEqual(completed.status, "completed")

    def test_item_lifecycle_normalizes_camel_case_without_masking_failure(self) -> None:
        reducer = AppServerEventReducer()
        in_progress = reducer.normalize(
            {
                "method": "item/started",
                "params": {
                    "item": {
                        "id": "one",
                        "type": "agentMessage",
                        "status": "inProgress",
                        "text": "working",
                    }
                },
            }
        )
        failed = reducer.normalize(
            {
                "method": "item/completed",
                "params": {
                    "item": {
                        "id": "two",
                        "type": "agentMessage",
                        "status": "failed",
                        "text": "failed safely",
                    }
                },
            }
        )
        assert in_progress is not None and failed is not None
        self.assertEqual(in_progress.status, "in_progress")
        self.assertEqual(failed.status, "failed")

    def test_reasoning_and_diffs_are_withheld_while_output_is_display_only(self) -> None:
        reducer = AppServerEventReducer()
        values = [
            {
                "method": "item/reasoning/textDelta",
                "params": {"turnId": "turn", "delta": "private reasoning"},
            },
            {
                "method": "item/commandExecution/outputDelta",
                "params": {"turnId": "turn", "delta": "secret command output"},
            },
            {
                "method": "turn/diff/updated",
                "params": {"turnId": "turn", "diff": "private file data"},
            },
        ]
        normalized = [reducer.normalize(item) for item in values]
        self.assertIsNone(normalized[0].text)  # type: ignore[union-attr]
        self.assertEqual(normalized[1].text, "secret command output")  # type: ignore[union-attr]
        self.assertIsNone(normalized[2].text)  # type: ignore[union-attr]
        encoded = json.dumps([item.journal_details() for item in normalized if item])
        self.assertNotIn("private reasoning", encoded)
        self.assertNotIn("secret command output", encoded)
        self.assertNotIn("private file data", encoded)

    def test_terminal_controls_are_sanitized(self) -> None:
        event = AppServerEventReducer().normalize(
            {
                "method": "item/agentMessage/delta",
                "params": {"delta": "safe\u001b]8;;https://bad.invalid\u0007click\u001b]8;;\u0007"},
            }
        )
        assert event
        self.assertNotIn("\x1b", event.text or "")
        self.assertTrue(event.text_sanitized_or_capped)

    def test_oversized_ingress_is_rejected_without_hashing_raw_content(self) -> None:
        event = AppServerEventReducer().normalize(
            {"method": "item/agentMessage/delta", "params": {"delta": "x" * (128 * 1024 + 1)}}
        )
        assert event
        self.assertEqual(event.kind, "protocol_error")
        self.assertEqual(event.metadata["reason"], "message_limits_exceeded")
        self.assertNotIn("x" * 100, json.dumps(event.journal_details()))

    def test_server_request_metadata_is_terminal_sanitized_and_bounded(self) -> None:
        event = AppServerEventReducer().normalize(
            {
                "method": "item/commandExecution/requestApproval",
                "id": 7,
                "params": {"command": "echo safe\x1b]0;forged\x07"},
            }
        )
        assert event
        self.assertNotIn("\x1b", str(event.metadata["command"]))


if __name__ == "__main__":
    unittest.main()
