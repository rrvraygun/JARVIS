import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis_tui.event_reducer import AppServerEventReducer
from jarvis_tui.usage_metrics import UsageLedger, payload_metrics


class UsageTests(unittest.TestCase):
    def test_logical_request_includes_classifier_and_multiple_tool_responses(self):
        ledger = UsageLedger()
        ledger.start_thread("thread")
        for phase, total, cached in [
            ("preflight", 100, 0),
            ("execution", 250, 70),
            ("execution", 450, 170),
            ("execution", 450, 170),
        ]:
            report = ledger.observe(
                "thread",
                "task",
                phase,
                {
                    "total_tokens": total,
                    "total_cached_input_tokens": cached,
                    "last_total_tokens": 200,
                    "usage_valid": True,
                },
            )
        self.assertEqual(report["logical_turn"]["total_tokens"], 450)
        self.assertEqual(report["phase_totals"]["preflight"]["total_tokens"], 100)
        self.assertEqual(report["phase_totals"]["execution"]["total_tokens"], 350)
        self.assertEqual(report["logical_turn"]["total_cached_input_tokens"], 170)
        self.assertTrue(report["complete"])
        next_report = ledger.observe("thread", "next", "preflight", {"total_tokens": 500})
        self.assertEqual(next_report["logical_turn"]["total_tokens"], 50)

    def test_resume_and_counter_decrease_are_incomplete(self):
        ledger = UsageLedger()
        report = ledger.observe("resumed", "task", "execution", {"total_tokens": 900})
        self.assertFalse(report["complete"])
        self.assertEqual(report["logical_turn"], {})
        report = ledger.observe("resumed", "task", "execution", {"total_tokens": 950})
        self.assertEqual(report["logical_turn"]["total_tokens"], 50)
        report = ledger.observe("resumed", "task", "execution", {"total_tokens": 20})
        self.assertFalse(report["complete"])
        self.assertEqual(report["logical_turn"]["total_tokens"], 50)

    def test_checkpoint_thread_does_not_inherit_counters(self):
        ledger = UsageLedger()
        ledger.start_thread("old")
        ledger.observe("old", "old_task", "execution", {"total_tokens": 500})
        ledger.start_thread("new")
        report = ledger.observe("new", "new_task", "preflight", {"total_tokens": 40})
        self.assertEqual(report["logical_turn"]["total_tokens"], 40)
        self.assertTrue(report["complete"])

    def test_zero_cache_and_cumulative_above_window_are_valid(self):
        event = AppServerEventReducer().normalize(
            {
                "method": "thread/tokenUsage/updated",
                "params": {
                    "tokenUsage": {
                        "modelContextWindow": 100,
                        "total": {"totalTokens": 1000, "cachedInputTokens": 0},
                        "last": {"totalTokens": 0, "outputTokens": 0},
                    }
                },
            }
        )
        self.assertTrue(event.metadata["usage_valid"])
        self.assertEqual(event.metadata["last_total_tokens"], 0)
        self.assertEqual(event.metadata["total_cached_input_tokens"], 0)

    def test_payload_metrics_never_include_contents(self):
        metrics = payload_metrics(
            {
                "input": [{"text": "sensitive-example"}],
                "config": {"secret": "sensitive-example"},
                "arguments": {"secret": "sensitive-example"},
            }
        )
        self.assertNotIn("sensitive-example", str(metrics))
        self.assertEqual(metrics["units"], "utf8_bytes_not_tokens")
        self.assertFalse(metrics["server_added_context_measured"])
