import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis_tui.event_reducer import NormalizedEvent  # noqa: E402
from jarvis_tui.live_activity import LiveActivity  # noqa: E402


class LiveActivityTests(unittest.TestCase):
    def test_context_marker_is_present_before_usage_arrives(self):
        self.assertIn(
            "Context · unavailable / 781k · — left", LiveActivity(context_window=800_000).text()
        )

    def test_checkpoint_reset_returns_usage_to_zero(self):
        state = LiveActivity(context_window=65536, context_used=11000)
        state.reset_context()
        self.assertIn("Context · 0k / 64k · 100% left", state.text())

    def test_context_usage_is_compact_and_calculated(self):
        state = LiveActivity(context_window=800_000)
        state.update(
            NormalizedEvent(
                "a",
                "turn/tokenUsage/updated",
                "token_usage_updated",
                "received",
                metadata={"total_tokens": 58_000},
            )
        )
        self.assertIn("Context · 57k / 781k · 93% left", state.text())

    def test_nested_app_server_token_usage_is_read(self):
        from jarvis_tui.event_reducer import AppServerEventReducer

        event = AppServerEventReducer().normalize(
            {
                "method": "thread/tokenUsage/updated",
                "params": {
                    "threadId": "t",
                    "turnId": "u",
                    "tokenUsage": {
                        "modelContextWindow": 800000,
                        "total": {
                            "totalTokens": 58000,
                            "inputTokens": 50000,
                            "outputTokens": 8000,
                            "reasoningOutputTokens": 1000,
                        },
                        "last": {
                            "totalTokens": 1200,
                            "inputTokens": 900,
                            "outputTokens": 300,
                            "reasoningOutputTokens": 10,
                        },
                    },
                },
            }
        )
        self.assertEqual(event.kind, "token_usage_updated")
        self.assertEqual(event.metadata["total_tokens"], 58000)
        self.assertEqual(event.metadata["context_window"], 800000)

    def test_disconnect_stops_unfinished_tool_without_claiming_success(self):
        state = LiveActivity()
        with patch("jarvis_tui.live_activity.time.monotonic", return_value=10):
            state.update(
                NormalizedEvent("a", "fixture", "turn_started", "in_progress", turn_id="turn")
            )
            state.update(
                NormalizedEvent(
                    "b", "fixture", "tool_execution", "in_progress", turn_id="turn", item_id="tool"
                )
            )
        with patch("jarvis_tui.live_activity.time.monotonic", return_value=12):
            state.update(NormalizedEvent("c", "fixture", "disconnected", "offline"))
            before = state.text()
        with patch("jarvis_tui.live_activity.time.monotonic", return_value=30):
            self.assertEqual(before, state.text())
        self.assertIn("outcome unknown", before)
        self.assertNotIn("✓", before)
