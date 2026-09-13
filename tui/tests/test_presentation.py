#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TUI_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = TUI_ROOT.parent
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.actions import ActionRegistry  # noqa: E402
from jarvis_tui.broker import JarvisBroker  # noqa: E402
from jarvis_tui.event_reducer import AppServerEventReducer  # noqa: E402
from jarvis_tui.event_store import EventJournal  # noqa: E402
from jarvis_tui.local_mutation import LocalFilesystemMutationResult  # noqa: E402
from jarvis_tui.models import (  # noqa: E402
    AssessmentDecision,
    ExecutionRoute,
    IntentAssessment,
    IntentClass,
    LocalMutationOperation,
    TaskState,
)
from jarvis_tui.operational_export import ExportDeliveryError  # noqa: E402
from jarvis_tui.presentation import (  # noqa: E402
    ACTIVE_CONTEXT_CHARACTER_LIMIT,
    CONTEXT_OMISSION_TEXT,
    ConversationEntry,
    JarvisPresentation,
)
from jarvis_tui.session import SessionSnapshot  # noqa: E402


class PresentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        registry = ActionRegistry.load(
            BUNDLE_ROOT / "plugins/jarvis-system-admin/registry/actions.json"
        )
        self.broker = JarvisBroker(
            registry, EventJournal(Path(self.temporary.name) / "events.jsonl")
        )
        self.presentation = JarvisPresentation()

    def _event(self, message: dict):
        event = AppServerEventReducer().normalize(message)
        assert event
        return event

    def test_streamed_message_is_replaced_by_authoritative_completion(self) -> None:
        task = self.broker.capture_text("Explain a fixture.")
        self.broker.record_assessment(
            task,
            IntentAssessment(
                assessment_id="assessment_fixture",
                decision=AssessmentDecision.EXECUTE,
                intent_class=IntentClass.EXPLAIN,
                operation="explain fixture",
                targets=(),
                risk=0,
                route=ExecutionRoute.CONVERSATION,
                reason="fixture is exact",
            ),
        )
        self.presentation.capture_task(task, self.broker.admit(task))
        reducer = AppServerEventReducer()
        for text in ("partial ", "answer"):
            event = reducer.normalize(
                {
                    "method": "item/agentMessage/delta",
                    "params": {"turnId": "turn", "itemId": "item", "delta": text},
                }
            )
            assert event
            self.presentation.apply_event(event)
        final = reducer.normalize(
            {
                "method": "item/completed",
                "params": {
                    "turnId": "turn",
                    "item": {
                        "id": "item",
                        "type": "agentMessage",
                        "status": "completed",
                        "text": "authoritative answer",
                    },
                },
            }
        )
        assert final
        self.presentation.apply_event(final)
        rendered = "\n".join(self.presentation.render_conversation())
        self.assertIn("authoritative answer", rendered)
        self.assertNotIn("partial answer", rendered)

    def test_tool_activity_is_correlated_and_excluded_from_agent_context(self) -> None:
        reducer = AppServerEventReducer()
        started = reducer.normalize(
            {
                "method": "item/started",
                "params": {"turnId": "turn", "item": {"id": "tool", "type": "commandExecution"}},
            }
        )
        output = reducer.normalize(
            {
                "method": "item/commandExecution/outputDelta",
                "params": {"turnId": "turn", "itemId": "tool", "delta": "safe output"},
            }
        )
        completed = reducer.normalize(
            {
                "method": "item/completed",
                "params": {
                    "turnId": "turn",
                    "item": {"id": "tool", "type": "commandExecution", "status": "completed"},
                },
            }
        )
        assert started is not None and output is not None and completed is not None
        for event in (started, output, completed):
            self.presentation.apply_event(event)
        activities = [entry for entry in self.presentation.conversation if entry.role == "activity"]
        self.assertEqual(activities, [])
        self.assertNotIn(
            "safe output",
            "\n".join(item.text for item in self.presentation.context_snapshot().entries),
        )

    def test_pending_capture_precedes_truthful_admission_without_legacy_literal(self) -> None:
        task = self.broker.capture_text("Explain a fixture.")
        self.presentation.capture_pending_task(task)
        self.assertEqual(len(self.presentation.conversation), 1)
        self.assertEqual(self.presentation.conversation[0].status, "resolving_intent")
        pending = "\n".join(self.presentation.render_timeline())
        self.assertIn("admission not yet decided", pending)
        self.assertIn("no execution authority granted", pending)
        self.broker.record_assessment(
            task,
            IntentAssessment(
                assessment_id="assessment_fixture",
                decision=AssessmentDecision.EXECUTE,
                intent_class=IntentClass.EXPLAIN,
                operation="explain fixture",
                targets=(),
                risk=0,
                route=ExecutionRoute.CONVERSATION,
                reason="fixture is exact",
            ),
        )
        admission = self.broker.admit(task)
        self.presentation.apply_admission(task, admission)
        self.assertEqual(len(self.presentation.conversation), 1)
        timeline = "\n".join(self.presentation.render_timeline())
        self.assertIn("current-user agent surface", timeline)
        self.assertNotIn("host authority none", timeline.casefold())

    def test_classifier_failure_is_not_presented_as_policy_denial(self) -> None:
        task = self.broker.capture_text("Fixture classifier failure.")
        self.presentation.capture_pending_task(task)
        self.presentation.mark_classifier_failure(task, "preflight.invalid_shape", "assessment")
        rendered = "\n".join(
            (*self.presentation.render_conversation(), *self.presentation.render_timeline())
        )
        self.assertIn("classifier_failed", rendered)
        self.assertIn("category=assessment", rendered)
        self.assertIn("not a policy-risk determination", rendered)
        self.assertNotIn("host authority none", rendered.casefold())

    def test_local_mutation_result_uses_mutation_fields_not_read_fields(self) -> None:
        task = self.broker.capture_text("create directory fixture")
        self.presentation.capture_pending_task(task)
        task.state = TaskState.COMPLETED
        self.presentation.set_local_mutation_result(
            task,
            LocalFilesystemMutationResult(
                operation=LocalMutationOperation.CREATE_DIRECTORY,
                status="completed",
                display_text="Created directory: fixture",
                plan_digest="a" * 64,
                target_digest="b" * 64,
                target_category="workspace",
                duration_ms=3,
                sanitized_or_redacted=False,
                rollback_available=True,
            ),
        )
        timeline = "\n".join(self.presentation.render_timeline())
        self.assertIn("bounded local mutation completed", timeline)
        self.assertNotIn("files_examined", timeline)

    def test_package_preview_failure_renders_only_its_safe_code(self) -> None:
        task = self.broker.capture_text("remove package fixture")
        self.presentation.capture_pending_task(task)
        self.presentation.mark_package_preview_failure(task, "package_preview.runtimeerror")
        timeline = "\n".join(self.presentation.render_timeline())
        self.assertIn("package_preview.runtimeerror", timeline)
        self.assertIn("no execution authority granted", timeline)

    def test_active_context_prunes_oldest_complete_exchanges_with_visible_marker(self) -> None:
        entries: list[ConversationEntry] = []
        for index in range(4):
            entries.extend(
                (
                    ConversationEntry(
                        key=f"user:{index}",
                        role="user",
                        text=f"user-{index}:" + ("u" * 9_990),
                        status="completed",
                        task_id=f"task:{index}",
                    ),
                    ConversationEntry(
                        key=f"local:{index}",
                        role="jarvis",
                        text=f"result-{index}:" + ("r" * 9_988),
                        status="completed",
                        task_id=f"task:{index}",
                    ),
                )
            )

        self.presentation.reset_conversation(tuple(entries))
        snapshot = self.presentation.context_snapshot()
        rendered = "\n".join(self.presentation.render_conversation())

        self.assertLessEqual(snapshot.character_count, ACTIVE_CONTEXT_CHARACTER_LIMIT)
        self.assertEqual(self.presentation.conversation[0].text, CONTEXT_OMISSION_TEXT)
        self.assertIn("user-3:", rendered)
        self.assertIn("result-3:", rendered)
        self.assertNotIn("user-0:", rendered)
        self.assertNotIn("result-0:", rendered)
        self.assertEqual(
            {entry.text for entry in snapshot.entries},
            {entry.text for entry in self.presentation.conversation},
        )

    def test_context_snapshot_excludes_only_the_current_pending_task(self) -> None:
        first = self.broker.capture_text("Earlier local request")
        current = self.broker.capture_text("Current model request")
        self.presentation.capture_pending_task(first)
        self.presentation.add_local_conversation(
            "Earlier bounded local result", task_id=first.task_id
        )
        self.presentation.capture_pending_task(current)

        snapshot = self.presentation.context_snapshot(exclude_task_id=current.task_id)
        text = "\n".join(entry.text for entry in snapshot.entries)
        self.assertIn("Earlier local request", text)
        self.assertIn("Earlier bounded local result", text)
        self.assertNotIn("Current model request", text)

    def test_context_snapshot_keeps_all_visible_conversation_roles(self) -> None:
        self.presentation.reset_conversation(
            (
                ConversationEntry("user:1", "user", "user request", "completed"),
                ConversationEntry("jarvis:1", "jarvis", "Which package?", "completed"),
                ConversationEntry(
                    "action:1", "action", "Options: package-a / package-b", "completed"
                ),
                ConversationEntry("system:1", "system", "No package was changed.", "completed"),
                ConversationEntry("agent:1", "agent", "I can help.", "completed"),
            )
        )
        roles = {entry.role for entry in self.presentation.context_snapshot().entries}
        self.assertEqual(roles, {"user", "jarvis", "action", "system", "agent"})

    def test_loaded_timeline_omits_legacy_stream_and_protocol_noise(self) -> None:
        events = tuple(
            {
                "sequence": index + 1,
                "event_type": "codex.event.normalized",
                "status": "received",
                "details": {
                    "method": "item/agentMessage/delta",
                    "kind": "agent_delta",
                },
            }
            for index in range(600)
        ) + (
            {
                "sequence": 601,
                "event_type": "codex.event.normalized",
                "status": "ready",
                "details": {
                    "method": "mcpServer/startupStatus/updated",
                    "kind": "protocol_event",
                },
            },
            {
                "sequence": 602,
                "event_type": "task.state.changed",
                "status": "completed",
                "task_id": "task_fixture",
                "details": {},
            },
            {
                "sequence": 603,
                "event_type": "codex.event.normalized",
                "status": "failed",
                "task_id": "task_fixture",
                "details": {"method": "error", "kind": "error"},
            },
        )

        self.presentation.load_journal(events)
        rendered = self.presentation.render_timeline()
        joined = "\n".join(rendered)
        self.assertLessEqual(len(rendered), 4)
        self.assertIn("legacy/non-material protocol records omitted: 601", joined)
        self.assertIn("task.state.changed", joined)
        self.assertIn("codex error", joined)
        self.assertNotIn("agent_delta", joined)
        self.assertNotIn("mcpServer/startupStatus/updated", joined)

    def test_loaded_timeline_caps_material_history_without_changing_audit_input(self) -> None:
        events = tuple(
            {
                "sequence": index + 1,
                "event_type": "task.state.changed",
                "status": "completed",
                "task_id": f"task_{index}",
                "details": {},
            }
            for index in range(300)
        )

        self.presentation.load_journal(events)
        rendered = self.presentation.render_timeline()
        joined = "\n".join(rendered)
        self.assertEqual(len(events), 300)
        self.assertEqual(len(rendered), 101)
        self.assertIn("older material journal records omitted: 200", joined)
        self.assertNotIn("journal sequence 200\n", joined)
        self.assertIn("journal sequence 201", joined)
        self.assertIn("journal sequence 300", joined)

    def test_read_only_jarvisd_status_is_visible_in_overview(self) -> None:
        self.presentation.refresh_overview(
            SessionSnapshot(),
            capabilities=1,
            enabled_actions=1,
            unavailable_actions=0,
            knowledge_status={"available": False, "reason": "offline"},
            recovered_tasks=0,
            jarvisd_status={"host_authority": "H1 Tier-0 read-only enabled"},
            h1_scope="4 adapters / 14 facts · scope abc123",
            recovery_status={
                "r1": {"status": "completed"},
                "r2": {"status": "passed", "mismatch_total": 0},
            },
        )
        rendered = self.presentation.render_overview()
        self.assertIn("jarvisd: H1 Tier-0 read-only enabled", rendered)
        self.assertIn("H1 scope: 4 adapters / 14 facts", rendered)
        self.assertIn("recovery evidence: R1=completed; R2=passed; mismatches=0", rendered)

    def test_plan_pending_request_and_private_data_projection(self) -> None:
        plan = self._event(
            {
                "method": "turn/plan/updated",
                "params": {
                    "turnId": "turn",
                    "plan": [
                        {"step": "Inspect fixture evidence", "status": "inProgress"},
                        {"step": "Report findings", "status": "pending"},
                    ],
                },
            }
        )
        self.presentation.apply_event(plan)
        reasoning = self._event(
            {
                "method": "item/reasoning/textDelta",
                "params": {"turnId": "turn", "delta": "private chain data"},
            }
        )
        self.presentation.apply_event(reasoning)
        request = self._event(
            {
                "method": "item/commandExecution/requestApproval",
                "id": 9,
                "params": {"turnId": "turn", "command": "private command"},
            }
        )
        self.presentation.apply_event(request)
        self.assertIn("Inspect fixture evidence", "\n".join(self.presentation.render_plan()))
        encoded = "\n".join(
            (*self.presentation.render_conversation(), *self.presentation.render_timeline())
        )
        self.assertNotIn("private chain data", encoded)
        self.assertNotIn("private command", encoded)
        self.assertIn("approve once", "\n".join(self.presentation.render_approvals()))

    def test_codex_approval_hides_command_content(self) -> None:
        codex_request = self._event(
            {
                "method": "item/commandExecution/requestApproval",
                "id": 19,
                "params": {
                    "threadId": "thread",
                    "turnId": "turn",
                    "itemId": "item",
                    "command": "private command",
                },
            }
        )
        self.presentation.apply_event(codex_request)
        rendered = "\n".join(self.presentation.render_approvals())
        self.assertIn("CODEX APP SERVER REQUESTS", rendered)
        self.assertIn("approve once", rendered)
        self.assertNotIn("private command", rendered)

    def test_overview_knowledge_and_timeline_have_semantic_labels(self) -> None:
        snapshot = SessionSnapshot()
        self.presentation.refresh_overview(
            snapshot,
            capabilities=15,
            enabled_actions=5,
            unavailable_actions=1,
            knowledge_status={"available": True, "integrity": "ok"},
            recovered_tasks=2,
        )
        self.presentation.set_knowledge_results(
            "sources", "fixture", ({"title": "Fixture source", "authority_tier": 1},)
        )
        overview = self.presentation.render_overview()
        self.assertIn("read-only agent; registered one-use operations", overview)
        self.assertIn("15", overview)
        self.assertIn("Fixture source", "\n".join(self.presentation.render_knowledge()))
        self.assertIn("completed", "\n".join(self.presentation.render_timeline()))

    def test_phase6_operational_console_is_read_only_and_redacted(self) -> None:
        self.presentation.add_notice("failed attempt: private payload", status="failed")
        self.presentation.refresh_operational_console(
            jarvisd_status={
                "host_authority": "H1 Tier-0 read-only enabled",
                "notifications": ("thermal degradation reported",),
            },
            recovery_status={
                "r1": {"status": "completed"},
                "r2": {"status": "passed"},
                "proof_gaps": (),
            },
            knowledge_status={"available": True, "integrity": "ok"},
        )
        rendered = "\n".join(self.presentation.render_operational_console())
        self.assertIn("PHASE 6 OPERATIONAL CONSOLE — READ ONLY", rendered)
        self.assertIn("H1 Tier-0 read-only enabled", rendered)
        self.assertIn("automatic policy or profile promotion: disabled", rendered)
        self.assertIn(
            "prepared operations: lighting observation/repair and power-profile transition; unregistered",
            rendered,
        )
        self.assertIn("thermal degradation reported", rendered)
        self.assertNotIn("abc123", rendered)
        self.assertIn("ui: status=failed; sequence=1; diagnosis=unavailable", rendered)
        self.assertNotIn("private payload", rendered)
        self.assertNotIn(
            "thermal degradation reported",
            json.loads(self.presentation.redacted_operational_export())["notifications"],
        )
        self.assertNotIn("execute command", rendered.casefold())

    def test_phase6_export_is_deterministic_bounded_and_has_no_authority(self) -> None:
        self.presentation.refresh_operational_console(
            jarvisd_status={
                "host_authority": "read-only\x1b[31m",
                "notifications": (
                    "token=secret\x1b",
                    "Authorization: Bearer abc123",
                    'token="private value"',
                ),
            },
            recovery_status={"r1": {"status": "completed"}},
        )
        first = self.presentation.redacted_operational_export()
        second = self.presentation.redacted_operational_export()
        self.assertEqual(first, second)
        value = json.loads(first)
        self.assertEqual(value["kind"], "jarvis.phase6.operational-report")
        self.assertFalse(any(value["capabilities"].values()))
        self.assertLessEqual(len(first), 32_000)
        self.assertNotIn("\\u001b", first)
        self.assertNotIn("\x1b", first)
        self.assertNotIn("secret", first)
        self.assertNotIn("abc123", first)
        self.assertNotIn("private value", first)
        self.presentation.operational.notifications = tuple("x" * 2_000 for _ in range(100))
        bounded = self.presentation.redacted_operational_export()
        self.assertEqual(json.loads(bounded)["kind"], "jarvis.phase6.operational-report")

    def test_phase6_empty_evidence_is_unknown_not_absence(self) -> None:
        self.presentation.refresh_operational_console()
        rendered = "\n".join(self.presentation.render_operational_console())
        self.assertIn("unknown: no verified failure evidence loaded", rendered)
        self.assertIn("integrity: unverified bounded projection", rendered)

    def test_phase6_locked_store_and_audit_failure_fail_closed(self) -> None:
        self.presentation.refresh_operational_console(
            jarvisd_status={"connection": "unavailable", "audit_integrity": "corrupt"},
            knowledge_status={"available": False, "reason": "knowledge_database_locked"},
        )
        rendered = "\n".join(self.presentation.render_operational_console())
        self.assertIn("restricted store: locked", rendered)
        self.assertIn("integrity: failed", rendered)
        self.assertIn("no replay or authority granted", rendered)

    def test_phase6_export_delivery_is_explicit_bounded_and_no_overwrite(self) -> None:
        destination = Path(self.temporary.name) / "operational-report.json"
        result = self.presentation.deliver_redacted_operational_export(destination)
        self.assertEqual(result.mode, 0o600)
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        self.assertEqual(
            json.loads(destination.read_text())["kind"], "jarvis.phase6.operational-report"
        )
        with self.assertRaises(ExportDeliveryError):
            self.presentation.deliver_redacted_operational_export(destination)

    def test_phase6_export_delivery_rejects_relative_or_authoritative_payload(self) -> None:
        with self.assertRaises(ExportDeliveryError):
            self.presentation.deliver_redacted_operational_export(Path("relative.json"))
        with self.assertRaises(ExportDeliveryError):
            from jarvis_tui.operational_export import deliver_redacted_export

            deliver_redacted_export(
                json.dumps(
                    {
                        "kind": "jarvis.phase6.operational-report",
                        "capabilities": {"execute_commands": True},
                    }
                ),
                Path(self.temporary.name) / "bad.json",
            )

    def test_phase6_export_delivery_rejects_symlink_and_world_writable_parent(self) -> None:
        symlink = Path(self.temporary.name) / "link.json"
        symlink.symlink_to(Path(self.temporary.name) / "outside.json")
        with self.assertRaises(ExportDeliveryError):
            self.presentation.deliver_redacted_operational_export(symlink)
        unsafe = Path(self.temporary.name) / "unsafe"
        unsafe.mkdir()
        unsafe.chmod(0o777)
        self.addCleanup(lambda: unsafe.chmod(0o700))
        with self.assertRaises(ExportDeliveryError):
            self.presentation.deliver_redacted_operational_export(unsafe / "report.json")

    def test_safe_tool_lifecycle_is_visible_without_tool_payload(self) -> None:
        event = self._event(
            {
                "method": "item/completed",
                "params": {
                    "turnId": "turn",
                    "item": {
                        "id": "search",
                        "type": "webSearch",
                        "status": "completed",
                        "query": "private search payload",
                        "result": "private tool output",
                    },
                },
            }
        )
        self.presentation.apply_event(event)
        rendered = "\n".join(
            (*self.presentation.render_conversation(), *self.presentation.render_timeline())
        )
        self.assertIn("webSearch: completed", rendered)
        self.assertNotIn("private search payload", rendered)
        self.assertNotIn("private tool output", rendered)


if __name__ == "__main__":
    unittest.main()
