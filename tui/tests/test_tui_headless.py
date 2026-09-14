#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TUI_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = TUI_ROOT.parent
sys.path.insert(0, str(TUI_ROOT / "src"))

try:
    import textual  # noqa: F401
    from jarvis_tui.app import (
        JarvisTui,
        _package_execution_diagnostic,
        _package_preview_diagnostic,
        _package_rollback_diagnostic,
    )
    from textual.widgets import Button, DataTable, Input, Select, Static, TabbedContent

    TEXTUAL_AVAILABLE = True
except ModuleNotFoundError:
    TEXTUAL_AVAILABLE = False

from jarvis_tui.actions import ActionRegistry  # noqa: E402
from jarvis_tui.app_server import AppServerError  # noqa: E402
from jarvis_tui.broker import JarvisBroker  # noqa: E402
from jarvis_tui.event_reducer import AppServerEventReducer  # noqa: E402
from jarvis_tui.event_store import EventJournal  # noqa: E402
from jarvis_tui.local_filesystem import (  # noqa: E402
    BoundedLocalFilesystemExecutor,
    LocalFilesystemPlanner,
)
from jarvis_tui.models import (  # noqa: E402
    AssessmentDecision,
    ExecutionRoute,
    IntentAssessment,
    IntentClass,
    TaskState,
)
from jarvis_tui.normal_terminal import NormalTerminalWorkflow  # noqa: E402
from jarvis_tui.package_control_client import PackageControlClientError  # noqa: E402
from jarvis_tui.package_inventory import PackageRecord  # noqa: E402
from jarvis_tui.power_inventory import PowerInventory, PowerSetting  # noqa: E402
from jarvis_tui.preflight import PreflightClassifierError  # noqa: E402
from jarvis_tui.presentation import ConversationEntry  # noqa: E402
from jarvis_tui.session import (  # noqa: E402
    AppServerSessionController,
    ConnectionState,
    ConversationContextSyncError,
)
from jarvis_tui.testing import FakeAppServerClient  # noqa: E402


class FixtureLocalControl:
    def capabilities(self):
        return ({"id": "knowledge"}, {"id": "health"})

    def knowledge_status(self):
        return {"available": True, "read_only": True, "integrity": "ok"}

    def query_knowledge(self, kind, text, limit=20):
        return ({"kind": kind, "title": "Fixture source", "query_match": text},)


@unittest.skipUnless(TEXTUAL_AVAILABLE, "pinned Textual dependency is not installed")
class TextualHeadlessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # UI fixtures must never reach deployed privileged helpers on the host.
        for boundary in (
            "jarvis_tui.package_control_client._invoke",
            "jarvis_tui.power_control_client._invoke",
            "jarvis_tui.service_operations.apply",
            "jarvis_tui.configuration_operations.apply",
            "jarvis_tui.privileged_operations.apply",
            "jarvis_tui.app.apply_driver_selection",
        ):
            guard = mock.patch(
                boundary, side_effect=AssertionError("live helper forbidden in UI fixture")
            )
            guard.start()
            self.addCleanup(guard.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(self._cleanup)
        registry = ActionRegistry.load(
            BUNDLE_ROOT / "plugins/jarvis-system-admin/registry/actions.json"
        )
        self.home = Path(self.temporary.name) / "home"
        self.desktop = self.home / "Escritorio"
        self.desktop.mkdir(parents=True)
        (self.desktop / "visible.txt").write_text("fixture", encoding="utf-8")
        config = self.home / ".config/user-dirs.dirs"
        config.parent.mkdir()
        config.write_text('XDG_DESKTOP_DIR="$HOME/Escritorio"\n', encoding="utf-8")
        planner = LocalFilesystemPlanner(
            BUNDLE_ROOT,
            home=self.home,
            xdg_config=config,
            identifier=lambda prefix: f"{prefix}_fixture",
        )
        self.broker = JarvisBroker(
            registry,
            EventJournal(Path(self.temporary.name) / "events.jsonl"),
            local_control=FixtureLocalControl(),  # type: ignore[arg-type]
            filesystem_planner=planner,
            filesystem_executor=BoundedLocalFilesystemExecutor(home=self.home),
        )
        self.client = FakeAppServerClient()
        self.session = AppServerSessionController(
            self.client, self.broker, BUNDLE_ROOT, live_turns_enabled=False
        )

    async def _cleanup(self) -> None:
        self.temporary.cleanup()

    def app(self, plain_mode: bool = False, *, enable_live_turns: bool = False):
        return JarvisTui(
            BUNDLE_ROOT,
            plain_mode=plain_mode,
            broker=self.broker,
            session=self.session,
            enable_live_turns=enable_live_turns,
            conversation_storage=Path(self.temporary.name) / "conversations",
        )

    async def _agent_package_preflight(self, task, context=None):
        plan = task.package_plan
        roots = plan.packages if plan is not None else ("fixture-package",)
        operation = "package_remove"
        assessment = IntentAssessment(
            assessment_id="assessment_agent_package",
            decision=AssessmentDecision.EXECUTE,
            intent_class=IntentClass.HOST_CHANGE,
            operation=operation,
            targets=roots,
            risk=3,
            route=ExecutionRoute.REGISTERED_WORKFLOW,
            reason="agent confirmed exact package roots",
        )
        self.broker.record_assessment(task, assessment)
        return assessment

    async def test_live_activity_preserves_short_streams_and_tool_status(self):
        from jarvis_tui.event_reducer import NormalizedEvent

        app = self.app()
        async with app.run_test(size=(120, 40)) as pilot:

            def emit(kind, status="in_progress", text=None, metadata=None, item="reply"):
                app._on_codex_event(
                    NormalizedEvent(
                        fingerprint=f"{kind}-{text}-{status}",
                        method="fixture",
                        kind=kind,
                        status=status,
                        turn_id="live-fixture",
                        item_id=item,
                        text=text,
                        metadata=metadata or {},
                    )
                )

            emit("turn_started")
            for fragment in ("Hello ", "from ", "the agent"):
                emit("agent_delta", text=fragment)
            emit(
                "tool_execution",
                metadata={"tool_type": "mcpToolCall", "tool": "inspect_packages", "query": "node"},
                item="tool",
            )
            await pilot.pause(0.2)
            visible = str(app.query_one("#live-activity", Static).content)
            self.assertIn("3 fragments", visible)
            self.assertIn("inspect_packages", visible)
            self.assertIn("node", visible)
            self.assertTrue(
                any("Hello from the agent" in entry.text for entry in app.presentation.conversation)
            )
            emit(
                "tool_execution",
                status="failed",
                metadata={"tool": "inspect_packages"},
                item="tool",
            )
            emit("observation_unavailable", status="unverified")
            emit("turn_completed", status="completed")
            await pilot.pause(0.2)
            self.assertIn(
                "Inspection unavailable", str(app.query_one("#live-activity", Static).content)
            )
            self.assertFalse(
                any("No fresh registered" in entry.text for entry in app.presentation.conversation)
            )

    async def test_global_model_selector_is_visible_and_has_options(self):
        from textual.widgets import Select

        app = self.app()
        async with app.run_test(size=(120, 40)) as pilot:
            from textual.widgets import TabbedContent

            app.query_one("#workspace-tabs", TabbedContent).active = "agents-pane"
            await pilot.pause()
            selector = app.query_one("#global-model-select", Select)
            self.assertGreater(selector.size.width, 0)
            self.assertGreater(selector.size.height, 0)
            self.assertEqual(len(selector._options), 5)
            self.assertIn(
                selector.value,
                {"gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5"},
            )
            await pilot.click("#global-model-select")
            await pilot.pause()
            self.assertTrue(selector.expanded)

    async def test_global_reasoning_selector_is_visible_and_selectable(self):
        from textual.widgets import Select, TabbedContent

        app = self.app()
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#workspace-tabs", TabbedContent).active = "agents-pane"
            await pilot.pause()
            selector = app.query_one("#global-reasoning-select", Select)
            self.assertGreater(selector.size.width, 0)
            self.assertEqual(len(selector._options), 8)
            selector.value = "high"
            await pilot.pause()
            self.assertEqual(app._selected_reasoning, "high")
            self.assertEqual(app.session.reasoning_effort, "high")

    async def test_domain_clean_view_and_raw_toggle(self):
        from textual.containers import VerticalScroll
        from textual.widgets import RichLog

        app = self.app()
        async with app.run_test(size=(120, 40)):
            app._domain_evidence["health"] = {
                "available": True,
                "read_only": True,
                "installed_count": 7,
            }
            await app._render_domain_clean("health")
            clean = app.query_one("#system-clean", VerticalScroll)
            self.assertGreater(len(list(clean.query(".domain-field"))), 0)
            app._set_domain_view("health", "raw")
            self.assertFalse(clean.display)
            self.assertTrue(app.query_one("#system-log", RichLog).display)
            app._set_domain_view("health", "clean")
            self.assertTrue(clean.display)

    async def test_specialist_dropdown_overlays_fixed_action_rail(self):
        from textual.widgets import Button, Select, TabbedContent

        app = self.app()
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#workspace-tabs", TabbedContent).active = "conversation-pane"
            await pilot.pause()
            selector = app.query_one("#specialist-select", Select)
            history = app.query_one("#conv-history", Button)
            before = history.region
            await pilot.click(selector)
            await pilot.pause()
            self.assertTrue(selector.expanded)
            self.assertEqual(history.region, before)
            self.assertGreater(history.region.y, selector.region.bottom)

    async def test_full_checkpoint_does_not_restore_context_before_rollback(self):
        app = self.app()
        checkpoint = mock.Mock()
        with (
            mock.patch.object(app, "_checkpoint_work_active", return_value=False),
            mock.patch.object(app, "_checkpoint_recovery_binding", return_value="a" * 64),
            mock.patch.object(app, "_restore_checkpoint_context") as restore,
            mock.patch.object(
                app, "run_worker", side_effect=lambda coro, **kw: coro.close()
            ) as worker,
        ):
            app._restore_context_checkpoint_if_confirmed(checkpoint, "full", True)
        restore.assert_not_called()
        worker.assert_called_once()

    async def test_normal_terminal_button_reviews_new_mode_and_executes_once(self):
        import threading
        from contextlib import contextmanager

        app = self.app()
        app.normal_terminal_workflow = NormalTerminalWorkflow(Path(self.temporary.name))
        source = {
            "id": "a" * 32,
            "domain": "development",
            "operation": "command",
            "argv": ["/usr/bin/printf", "JARVIS smoke\\n"],
            "target": str(self.home),
            "digest": "b" * 64,
        }
        ui_thread = threading.get_ident()
        events = []

        @contextmanager
        def suspend():
            self.assertEqual(threading.get_ident(), ui_thread)
            events.append("suspended")
            yield
            events.append("resumed")

        def invoke(*args, **kwargs):
            self.assertNotEqual(threading.get_ident(), ui_thread)
            self.assertEqual(events, ["suspended"])
            self.assertNotIn("timeout", kwargs)
            self.assertNotIn("capture_output", kwargs)
            return type("Completed", (), {"returncode": 0})()

        with (
            mock.patch.object(app.operation_workflow, "load", return_value=source),
            mock.patch.object(app, "suspend", suspend),
            mock.patch("jarvis_tui.normal_terminal.available", return_value=True),
            mock.patch("jarvis_tui.normal_terminal.subprocess.run", side_effect=invoke) as command,
        ):
            async with app.run_test(size=(140, 45)) as pilot:
                app.query_one("#domain-operation-development", Input).value = source["id"]
                app._review_normal_terminal()
                await pilot.pause()
                review = app.screen.proposal
                self.assertNotEqual(review["digest"], source["digest"])
                self.assertEqual(review["execution_mode"], "normal-terminal")
                self.assertNotIn("source_tree", review)
                await pilot.click("#operation-approve")
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertEqual(events, ["suspended", "resumed"])
                self.assertFalse(app._operation_busy)
                command.assert_called_once()
                records = list((app.normal_terminal_workflow.root / "results").glob("*.json"))
                self.assertEqual(len(records), 1)

    async def test_failed_checkpoint_rollback_preserves_context(self):
        app = self.app()
        with (
            mock.patch(
                "jarvis_tui.app.undo_transaction",
                side_effect=PackageControlClientError("cancelled"),
            ),
            mock.patch.object(app, "_later_mutation_events", return_value=()),
            mock.patch.object(app, "_restore_checkpoint_context") as restore,
            mock.patch.object(app, "_system_message"),
            mock.patch.object(app, "_render_all"),
        ):
            await app._execute_package_undo("a" * 64, mock.Mock())
        restore.assert_not_called()

    async def test_package_preview_exposes_stable_safe_reason_not_raw_output(self) -> None:
        code, message = _package_preview_diagnostic(
            RuntimeError("DNF could not resolve the requested installation: private detail")
        )
        self.assertEqual(code, "package_preview.dnf_unresolved")
        self.assertNotIn("private detail", message)

    async def test_pending_recovery_record_is_not_presented_as_indeterminate(self) -> None:
        indeterminate, code, message = _package_execution_diagnostic(
            PackageControlClientError("a package transaction is already awaiting rollback")
        )
        self.assertFalse(indeterminate)
        self.assertEqual(code, "package_helper.recovery_record_pending")
        self.assertIn("Archive rollback record", message)

    async def test_known_helper_pre_execution_refusal_is_not_presented_as_indeterminate(
        self,
    ) -> None:
        indeterminate, code, message = _package_execution_diagnostic(
            PackageControlClientError(
                "authorized package operation failed (exit 2): package transaction can no longer be resolved"
            )
        )
        self.assertFalse(indeterminate)
        self.assertEqual(code, "package_helper.transaction_unresolved")
        self.assertIn("no package was changed", message)

    async def test_rollback_scope_change_is_not_presented_as_indeterminate(self) -> None:
        indeterminate, code, message = _package_rollback_diagnostic(
            PackageControlClientError(
                "rollback removal would affect packages outside the recorded set"
            )
        )
        self.assertFalse(indeterminate)
        self.assertEqual(code, "package_rollback.scope_changed")
        self.assertIn("No package rollback ran", message)

    async def test_delayed_preflight_projects_immediately_disables_send_and_preserves_busy_draft(
        self,
    ) -> None:
        gate = asyncio.Event()
        started = asyncio.Event()
        self.session.snapshot.connection = ConnectionState.READY

        async def delayed(task, context=None):
            started.set()
            await gate.wait()
            assessment = IntentAssessment(
                assessment_id="assessment_delayed",
                decision=AssessmentDecision.CLARIFY,
                intent_class=IntentClass.INSPECT,
                operation="clarify fixture",
                targets=(),
                risk=0,
                route=ExecutionRoute.NONE,
                reason="fixture ambiguity",
                clarification_question="Which fixture scope?",
                clarification_options=("Current workspace", "Desktop/Escritorio"),
            )
            self.broker.record_assessment(task, assessment)
            return assessment

        self.session.preflight_task = delayed  # type: ignore[method-assign]
        app = self.app(enable_live_turns=True)
        async with app.run_test(size=(100, 34)) as pilot:
            composer = app.query_one("#composer", Input)
            composer.value = "Diagnose a deliberately delayed fixture."
            await pilot.press("enter")
            await started.wait()
            await pilot.pause()
            self.assertEqual(app.active_view, "conversation")
            self.assertEqual(
                len([entry for entry in app.presentation.conversation if entry.role == "user"]), 1
            )
            projected = app.query_one("#conversation-log").text
            self.assertIn("Diagnose a deliberately delayed", projected)
            self.assertIn("fixture.", projected)
            self.assertTrue(app.query_one("#send-request", Button).disabled)
            composer.value = "draft typed while busy"
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(composer.value, "draft typed while busy")
            self.assertEqual(len(self.broker._tasks), 1)
            await pilot.press("ctrl+3")
            await pilot.pause()
            self.assertEqual(app.active_view, "agents")
            gate.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertFalse(app.query_one("#send-request", Button).disabled)
            self.assertEqual(
                len([entry for entry in app.presentation.conversation if entry.role == "user"]), 1
            )

    async def test_desktop_list_uses_local_route_without_app_server_or_approval(self) -> None:
        app = self.app()
        async with app.run_test(size=(100, 34)) as pilot:
            composer = app.query_one("#composer", Input)
            composer.value = "list the files inside Escritorio"
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertEqual(self.client.requests, [])
            self.assertEqual(self.client.responses, [])
            admission = next(iter(app.presentation.admissions.values()))
            self.assertEqual(admission.route.value, "local_read")
            self.assertEqual(admission.authority, "bounded-local-read")
            self.assertIn("visible.txt", app.query_one("#conversation-log").text)
            self.assertEqual(
                len([entry for entry in app.presentation.conversation if entry.role == "user"]), 1
            )
            self.assertFalse(app.query_one("#send-request", Button).disabled)
            timeline = "\n".join(app.presentation.render_timeline())
            self.assertIn("bounded local-read executor", timeline)
            self.assertNotIn("host authority none", timeline.casefold())
            audit = json.dumps(self.broker.journal.read())
            self.assertNotIn("visible.txt", audit)
            self.assertNotIn("Directory (", audit)

    async def test_desktop_directory_create_waits_for_one_modal_approval_without_app_server(
        self,
    ) -> None:
        app = self.app(enable_live_turns=True)
        async with app.run_test(size=(100, 34)) as pilot:
            composer = app.query_one("#composer", Input)
            composer.value = "create a new directory in Escritorio named Proyecto2"
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(app.screen.__class__.__name__, "PowerChangeReviewScreen")
            self.assertTrue(app.query_one("#send-request", Button).disabled)
            self.assertFalse((self.desktop / "Proyecto2").exists())
            self.assertEqual(self.client.requests, [])
            await pilot.click("#confirm-power-change")
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertTrue((self.desktop / "Proyecto2").is_dir())
            self.assertEqual(self.client.requests, [])
            self.assertEqual(self.client.responses, [])
            self.assertFalse(app.query_one("#send-request", Button).disabled)
            self.assertEqual(
                len([entry for entry in app.presentation.conversation if entry.role == "user"]),
                1,
            )
            self.assertIn("Created directory", app.query_one("#conversation-log").text)
            timeline = "\n".join(app.presentation.render_timeline())
            self.assertIn("fresh one-use approval", timeline)
            self.assertIn("bounded local mutation completed", timeline)

    async def test_declined_desktop_create_changes_nothing_and_restores_send(self) -> None:
        app = self.app(enable_live_turns=True)
        async with app.run_test(size=(100, 34)) as pilot:
            app.query_one(
                "#composer", Input
            ).value = "create a new directory in Escritorio named DeclinedTarget"
            await pilot.press("enter")
            await pilot.pause()
            await pilot.click("#cancel-power-change")
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertFalse((self.desktop / "DeclinedTarget").exists())
            self.assertFalse(app.query_one("#send-request", Button).disabled)
            self.assertIn("nothing was changed", app.query_one("#conversation-log").text)

    async def test_exact_package_remove_uses_one_modal_and_registered_helper_without_agent_turn(
        self,
    ) -> None:
        app = self.app(enable_live_turns=True)
        self.session.snapshot.connection = ConnectionState.READY
        self.session.preflight_task = self._agent_package_preflight  # type: ignore[method-assign]
        preview = {
            "operation": "remove",
            "packages": ["fixture-package"],
            "affected_installs": [],
            "affected_removals": ["fixture-package", "fixture-dependent"],
            "pre_state": {
                "fixture-package": "fixture-package|0|1|1.x86_64",
                "fixture-dependent": "fixture-dependent|0|1|1.noarch",
            },
            "preview": "Removing:\n fixture-package.x86_64\n fixture-dependent.noarch\nTransaction Summary:\n",
            "preview_digest": "a" * 64,
            "approval_digest": "b" * 64,
        }
        with (
            mock.patch("jarvis_tui.app.package_helper_available", return_value=True),
            mock.patch("jarvis_tui.app.package_helper_matches_bundle", return_value=True),
            mock.patch.object(self.broker, "preview_package_remove", return_value=preview),
            mock.patch(
                "jarvis_tui.app.remove_transaction", return_value={"status": "passed"}
            ) as executor,
            mock.patch.object(app, "_load_package_inventory", new=mock.AsyncMock()),
        ):
            async with app.run_test(size=(100, 34)) as pilot:
                app.query_one(
                    "#composer", Input
                ).value = 'uninstall "fixture-package" package, implying 2 more dependencies will be uninstalled'
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "PowerChangeReviewScreen")
                self.assertTrue(app.query_one("#send-request", Button).disabled)
                self.assertEqual(self.client.requests, [])
                await pilot.click("#confirm-power-change")
                await app.workers.wait_for_complete()
                await pilot.pause()
                executor.assert_called_once_with(("fixture-package",), "a" * 64, "b" * 64)
                self.assertEqual(self.client.requests, [])
                self.assertEqual(self.client.responses, [])
                self.assertFalse(app.query_one("#send-request", Button).disabled)
                self.assertIn(
                    "Package remove completed and verified",
                    app.query_one("#conversation-log").text,
                )
                self.assertIn(
                    "I identified an exact system package remove request",
                    app.query_one("#conversation-log").text,
                )

    async def test_missing_package_root_continuation_stays_off_the_model_route(self) -> None:
        app = self.app(enable_live_turns=True)
        self.session.snapshot.connection = ConnectionState.READY
        self.session.preflight_task = self._agent_package_preflight  # type: ignore[method-assign]
        preview = {
            "operation": "remove",
            "packages": ["fixture-package"],
            "affected_installs": [],
            "affected_removals": ["fixture-package", "fixture-dependent"],
            "pre_state": {
                "fixture-package": "fixture-package|0|1|1.x86_64",
                "fixture-dependent": "fixture-dependent|0|1|1.noarch",
            },
            "preview": "Removing:\n fixture-package.x86_64\nRemoving dependent packages:\n fixture-dependent.noarch\nTransaction Summary:\n",
            "preview_digest": "1" * 64,
            "approval_digest": "2" * 64,
        }
        with (
            mock.patch("jarvis_tui.app.package_helper_available", return_value=True),
            mock.patch("jarvis_tui.app.package_helper_matches_bundle", return_value=True),
            mock.patch.object(self.broker, "preview_package_remove", return_value=preview),
        ):
            async with app.run_test(size=(100, 34)) as pilot:
                app.query_one("#composer", Input).value = "uninstall package"
                await pilot.press("enter")
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertIsNotNone(app._pending_clarification)
                self.assertEqual(self.client.requests, [])
                app.query_one("#composer", Input).value = '"fixture-package"'
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "PowerChangeReviewScreen")
                self.assertEqual(self.client.requests, [])
                await pilot.click("#cancel-power-change")
                await app.workers.wait_for_complete()

    async def test_fresh_package_request_supersedes_an_unrelated_clarification(self) -> None:
        app = self.app(enable_live_turns=True)
        self.session.snapshot.connection = ConnectionState.READY
        self.session.preflight_task = self._agent_package_preflight  # type: ignore[method-assign]
        pending = self.broker.capture_text("heyy")
        self.broker.record_assessment(
            pending,
            IntentAssessment(
                assessment_id="assessment_greeting_clarification",
                decision=AssessmentDecision.CLARIFY,
                intent_class=IntentClass.EXPLAIN,
                operation="clarify greeting",
                targets=(),
                risk=0,
                route=ExecutionRoute.NONE,
                reason="fixture greeting ambiguity",
                clarification_question="What would you like help with?",
                clarification_options=("Explain", "Inspect", "Change"),
            ),
        )
        preview = {
            "operation": "remove",
            "packages": ["fixture-package"],
            "affected_installs": [],
            "affected_removals": ["fixture-package"],
            "pre_state": {"fixture-package": "fixture-package|0|1|1.x86_64"},
            "preview": "Removing:\n fixture-package.x86_64\nTransaction Summary:\n",
            "preview_digest": "3" * 64,
            "approval_digest": "4" * 64,
        }
        with (
            mock.patch("jarvis_tui.app.package_helper_available", return_value=True),
            mock.patch("jarvis_tui.app.package_helper_matches_bundle", return_value=True),
            mock.patch.object(self.broker, "preview_package_remove", return_value=preview),
        ):
            async with app.run_test(size=(100, 34)) as pilot:
                app._pending_clarification = pending
                app.query_one("#composer", Input).value = 'uninstall "fixture-package" package'
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(pending.state, TaskState.CANCELLED)
                self.assertEqual(app.screen.__class__.__name__, "PowerChangeReviewScreen")
                self.assertEqual(self.client.requests, [])
                await pilot.click("#cancel-power-change")
                await app.workers.wait_for_complete()

    async def test_packages_tab_consumes_one_broker_approval_before_helper(self) -> None:
        app = self.app(enable_live_turns=True)
        preview = {
            "operation": "remove",
            "packages": ["fixture-package"],
            "affected_installs": [],
            "affected_removals": ["fixture-package"],
            "pre_state": {"fixture-package": "fixture-package|0|1|1.x86_64"},
            "preview": "Removing:\n fixture-package.x86_64\nTransaction Summary:\n",
            "preview_digest": "c" * 64,
            "approval_digest": "d" * 64,
        }
        with (
            mock.patch("jarvis_tui.app.package_helper_available", return_value=True),
            mock.patch("jarvis_tui.app.package_helper_matches_bundle", return_value=True),
            mock.patch.object(self.broker, "preview_package_remove", return_value=preview),
            mock.patch(
                "jarvis_tui.app.remove_transaction", return_value={"status": "passed"}
            ) as executor,
            mock.patch.object(app, "_load_package_inventory", new=mock.AsyncMock()),
        ):
            async with app.run_test(size=(120, 42)) as pilot:
                app.query_one("#package-name", Input).value = "fixture-package"
                await app._preview_package_install("remove")
                task = app._package_preview_task
                self.assertIsNotNone(task)
                assert task is not None
                self.assertEqual(task.state, TaskState.AWAITING_APPROVAL)
                app._review_package_apply()
                await pilot.pause()
                self.assertEqual(app.screen.__class__.__name__, "PowerChangeReviewScreen")
                await pilot.click("#confirm-power-change")
                await app.workers.wait_for_complete()
                await pilot.pause()
                executor.assert_called_once_with(("fixture-package",), "c" * 64, "d" * 64)
                self.assertEqual(task.state, TaskState.COMPLETED)
                self.assertIsNone(app._package_preview)
                self.assertIsNone(app._package_preview_task)
                events = self.broker.journal.read()
                self.assertEqual(
                    sum(event["event_type"] == "package.transaction.approved" for event in events),
                    1,
                )
                self.assertEqual(
                    sum(
                        event["event_type"] == "package.transaction.execution.reserved"
                        for event in events
                    ),
                    1,
                )

    async def test_reserved_package_failure_is_reported_indeterminate(self) -> None:
        app = self.app(enable_live_turns=True)
        preview = {
            "operation": "install",
            "packages": ["fixture-package"],
            "affected_installs": ["fixture-package"],
            "affected_removals": [],
            "pre_state": {"fixture-package": None},
            "preview": "Installing:\n fixture-package.x86_64\nTransaction Summary:\n",
            "preview_digest": "e" * 64,
            "approval_digest": "f" * 64,
        }
        with (
            mock.patch(
                "jarvis_tui.app.authoritative_status", return_value={"record_status": "none"}
            ) as status_read,
            mock.patch("jarvis_tui.app.package_helper_available", return_value=True),
            mock.patch("jarvis_tui.app.package_helper_matches_bundle", return_value=True),
            mock.patch.object(self.broker, "preview_package_install", return_value=preview),
            mock.patch(
                "jarvis_tui.app.apply_transaction",
                side_effect=PackageControlClientError("fixture lost response"),
            ),
        ):
            async with app.run_test(size=(120, 42)) as pilot:
                app.query_one("#package-name", Input).value = "fixture-package"
                await app._preview_package_install("install")
                task = app._package_preview_task
                assert task is not None
                app._review_package_apply()
                await pilot.pause()
                await pilot.click("#confirm-power-change")
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertEqual(task.state, TaskState.FAILED)
                status_read.assert_called_once()
                self.assertNotIn("no package was changed", app.query_one("#conversation-log").text)
                self.assertIn("indeterminate", app.query_one("#conversation-log").text)
                self.assertNotIn("failed safely", app.query_one("#conversation-log").text)

    async def test_local_exchange_becomes_next_agent_context_but_stays_out_of_durable_results(
        self,
    ) -> None:
        sensitive = self.desktop / "contraseñadriversgrafica.txt"
        sensitive.write_text("never expose this filename or content", encoding="utf-8")
        observed_context = None

        async def capture_context(task, context=None):
            nonlocal observed_context
            observed_context = context
            assessment = IntentAssessment(
                assessment_id="assessment_context_fixture",
                decision=AssessmentDecision.CLARIFY,
                intent_class=IntentClass.EXPLAIN,
                operation="clarify greeting",
                targets=(),
                risk=0,
                route=ExecutionRoute.NONE,
                reason="fixture stops before execution",
                clarification_question="How can I help next?",
                clarification_options=("Explain the listing", "Continue with another task"),
            )
            self.broker.record_assessment(task, assessment)
            return assessment

        self.session.preflight_task = capture_context  # type: ignore[method-assign]
        self.session.snapshot.connection = ConnectionState.READY
        app = self.app(enable_live_turns=True)
        async with app.run_test(size=(100, 34)) as pilot:
            composer = app.query_one("#composer", Input)
            composer.value = "list the files inside Escritorio"
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertIn("visible.txt", app.query_one("#conversation-log").text)
            self.assertNotIn("contraseñadriversgrafica", app.query_one("#conversation-log").text)

            composer.value = "Please help me plan the next project change."
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()

            self.assertIsNotNone(observed_context)
            context_text = "\n".join(entry.text for entry in observed_context.entries)
            self.assertIn("list the files inside Escritorio", context_text)
            self.assertIn("visible.txt", context_text)
            self.assertNotIn("contraseñadriversgrafica", context_text)
            self.assertNotIn("Please help me plan the next project change.", context_text)

            stored = "\n".join(
                path.read_text(encoding="utf-8")
                for path in (Path(self.temporary.name) / "conversations").glob("*.json")
            )
            self.assertIn("visible.txt", stored)
            self.assertIn("Directory (desktop)", stored)

    async def test_terminal_agent_item_status_transition_repaints_same_length_text(self) -> None:
        app = self.app()
        async with app.run_test(size=(100, 34)) as pilot:
            started = self.session.reducer.normalize(
                {
                    "method": "item/started",
                    "params": {
                        "turnId": "turn_reply",
                        "item": {
                            "id": "item_reply",
                            "type": "agentMessage",
                            "text": "Hello from the agent.",
                        },
                    },
                }
            )
            completed = self.session.reducer.normalize(
                {
                    "method": "item/completed",
                    "params": {
                        "turnId": "turn_reply",
                        "item": {
                            "id": "item_reply",
                            "type": "agentMessage",
                            "text": "Hello from the agent.",
                        },
                    },
                }
            )
            assert started is not None and completed is not None
            app._on_codex_event(started)
            await pilot.pause()
            self.assertIn("Hello from the agent.", app.query_one("#conversation-log").text)
            app._on_codex_event(completed)
            await pilot.pause()
            self.assertIn("Hello from the agent.", app.query_one("#conversation-log").text)
            self.assertNotIn("AGENT:", app.query_one("#conversation-log").text)
            self.assertEqual(
                app.query_one("#conversation-log").text.count("Hello from the agent."), 1
            )

    async def test_zero_request_id_opens_exact_approval_and_declines_once(self) -> None:
        task = self.broker.capture_text("Inspect the exact fixture target.")
        self.broker.record_assessment(
            task,
            IntentAssessment(
                assessment_id="assessment_zero_request",
                decision=AssessmentDecision.EXECUTE,
                intent_class=IntentClass.INSPECT,
                operation="inspect fixture",
                targets=(str(BUNDLE_ROOT),),
                risk=0,
                route=ExecutionRoute.REVIEWED_BASH,
                reason="exact fixture target",
            ),
        )
        self.broker.admit(task)
        self.session.snapshot.active_turn_id = "turn_zero"
        self.session.snapshot.active_task_id = task.task_id
        self.session._turn_tasks["turn_zero"] = [task]
        app = self.app(enable_live_turns=True)
        async with app.run_test(size=(100, 34)) as pilot:
            await self.session.process_event(
                {
                    "method": "item/commandExecution/requestApproval",
                    "id": 0,
                    "params": {
                        "threadId": "thread_zero",
                        "turnId": "turn_zero",
                        "itemId": "item_zero",
                        "command": "printf fixture",
                        "cwd": str(BUNDLE_ROOT),
                    },
                }
            )
            await pilot.pause()
            self.assertIn(0, self.session.snapshot.pending_requests)
            self.assertEqual(app.screen.__class__.__name__, "CodexApprovalReviewScreen")
            await pilot.click("#codex-decline")
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertEqual(self.client.responses, [(0, {"decision": "decline"})])
            self.assertNotIn(0, self.session.snapshot.pending_requests)

    async def test_deterministic_ambiguity_asks_once_without_local_or_model_execution(self) -> None:
        async def forbidden_preflight(task, context=None):
            raise AssertionError("deterministic ambiguity must not invoke model preflight")

        self.session.preflight_task = forbidden_preflight  # type: ignore[method-assign]
        app = self.app(enable_live_turns=True)
        async with app.run_test(size=(100, 34)) as pilot:
            app.query_one("#composer", Input).value = "list files"
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            task = next(iter(self.broker._tasks.values()))
            self.assertEqual(task.state, TaskState.NEEDS_CLARIFICATION)
            self.assertEqual(app.presentation.admissions, {})
            self.assertEqual(self.client.requests, [])
            questions = [
                entry
                for entry in app.presentation.timeline
                if entry.kind == "task.needs_clarification"
            ]
            self.assertEqual(len(questions), 1)
            self.assertFalse(app.query_one("#send-request", Button).disabled)

    async def test_classifier_failure_and_cancellation_always_restore_send_without_replay(
        self,
    ) -> None:
        self.session.snapshot.connection = ConnectionState.READY

        async def malformed(task, context=None):
            self.broker.transition(task, TaskState.FAILED, reason="preflight.invalid_shape")
            raise PreflightClassifierError("preflight.invalid_shape", "fixture")

        self.session.preflight_task = malformed  # type: ignore[method-assign]
        app = self.app(enable_live_turns=True)
        async with app.run_test(size=(100, 34)) as pilot:
            app.query_one("#composer", Input).value = "Diagnose malformed classifier fixture."
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertFalse(app.query_one("#send-request", Button).disabled)
            self.assertIn("classifier_failed", "\n".join(app.presentation.render_timeline()))
            self.assertEqual(self.client.requests, [])

        gate = asyncio.Event()
        started = asyncio.Event()

        async def never_complete(task, context=None):
            started.set()
            await gate.wait()
            raise AssertionError("cancelled submission must not resume")

        self.session.preflight_task = never_complete  # type: ignore[method-assign]
        cancelled_app = self.app(enable_live_turns=True)
        async with cancelled_app.run_test(size=(100, 34)) as pilot:
            cancelled_app.query_one("#composer", Input).value = "Diagnose cancellable fixture."
            await pilot.press("enter")
            await started.wait()
            await pilot.click("#cancel-turn")
            await cancelled_app.workers.wait_for_complete()
            await pilot.pause()
            self.assertFalse(cancelled_app.query_one("#send-request", Button).disabled)
            task = list(self.broker._tasks.values())[-1]
            self.assertEqual(task.state, TaskState.CANCELLED)
            self.assertEqual(self.client.requests, [])

    async def test_context_sync_failure_restores_send_and_is_not_a_policy_denial(self) -> None:
        self.session.snapshot.connection = ConnectionState.READY

        async def fail_sync(task, context=None):
            raise ConversationContextSyncError()

        self.session.preflight_task = fail_sync  # type: ignore[method-assign]
        app = self.app(enable_live_turns=True)
        async with app.run_test(size=(100, 34)) as pilot:
            app.query_one("#composer", Input).value = "hello after local context"
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertFalse(app.query_one("#send-request", Button).disabled)
            conversation = app.query_one("#conversation-log").text
            timeline = "\n".join(app.presentation.render_timeline())
            self.assertIn("could not be synchronized safely", conversation)
            self.assertIn("conversation_context.sync_failed", timeline)
            self.assertNotIn("policy denial", conversation.casefold())
            self.assertEqual(self.client.requests, [])

    async def test_timeout_disconnect_and_unexpected_exception_restore_send(self) -> None:
        self.session.snapshot.connection = ConnectionState.READY
        failures = (
            TimeoutError("fixture timeout"),
            AppServerError("app_server_disconnected"),
            RuntimeError("fixture unexpected failure"),
        )
        for index, failure in enumerate(failures):

            async def fail_once(task, context=None, failure=failure):
                raise failure

            self.session.preflight_task = fail_once  # type: ignore[method-assign]
            app = self.app(enable_live_turns=True)
            async with app.run_test(size=(100, 34)) as pilot:
                app.query_one("#composer", Input).value = f"Diagnose failure fixture {index}."
                await pilot.press("enter")
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertFalse(app.query_one("#send-request", Button).disabled)
                task = list(self.broker._tasks.values())[-1]
                self.assertEqual(task.state, TaskState.FAILED)
        self.assertEqual(self.client.requests, [])

    async def test_natural_language_navigation_and_offline_no_replay(self) -> None:
        app = self.app(plain_mode=True)
        async with app.run_test(size=(100, 34)) as pilot:
            self.assertEqual(app.query_one("#workspace-tabs", TabbedContent).tab_count, 13)
            composer = app.query_one("#composer", Input)
            composer.value = "Diagnose the fixture without inspecting Fedora."
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(app.presentation.admissions, {})
            self.assertEqual(self.client.requests, [])
            await pilot.press("ctrl+3")
            await pilot.pause()
            self.assertEqual(app.active_view, "agents")
            self.assertEqual(app.query_one("#workspace-tabs", TabbedContent).active, "agents-pane")
            await pilot.press("ctrl+9")
            await pilot.pause()
            self.assertEqual(app.active_view, "operations")
            self.assertIn(
                "PHASE 6 OPERATIONAL CONSOLE",
                "\n".join(app.presentation.render_operational_console()),
            )

    async def test_conversation_carries_selected_specialist_context(self) -> None:
        app = self.app(plain_mode=True)
        app._active_specialist = app.agent_registry.get("jarvis-system-architect")
        async with app.run_test(size=(100, 34)) as pilot:
            await pilot.press("ctrl+2")
            await pilot.pause()
            self.assertEqual(len(app.query("#specialist-context")), 0)
            self.assertEqual(len(app.query("#composer")), 1)
            composer = app.query_one("#composer", Input)
            composer.value = "Explain the current CPU energy preference."
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(len(app.query("#composer")), 1)
            task = next(iter(self.broker._tasks.values()))
            self.assertEqual(task.agent_id, "jarvis-system-architect")
            self.assertEqual(task.agent_version, "1.0.0")
            self.assertTrue(
                any(
                    "Active JARVIS specialist: JARVIS Architect" in value
                    for value in task.intent.constraints
                )
            )
            self.assertIn("Explain the current CPU energy preference.", task.intent.text or "")

    async def test_conversation_formatter_keeps_long_incoming_messages_as_one_value(self) -> None:
        app = self.app(plain_mode=True)
        async with app.run_test(size=(100, 34)) as pilot:
            await pilot.press("ctrl+2")
            await pilot.pause()
            entry = ConversationEntry(
                "agent:long",
                "agent",
                "package-search-result-" * 32,
                "completed",
            )
            rendered = app._format_message_whatsapp_style(entry)
            self.assertIn("package-search-result-package-search-result", rendered)
            self.assertTrue(app.query_one("#conversation-log").soft_wrap)
            short = app._format_message_whatsapp_style(
                ConversationEntry("user:short", "user", "heyy", "completed")
            )
            self.assertEqual(len(short.splitlines()), 1)
            self.assertEqual(short, "heyy")

    async def test_completed_turn_renders_agent_response_without_activity_cards(self) -> None:
        app = self.app()
        reducer = AppServerEventReducer()
        async with app.run_test(size=(120, 42)) as pilot:
            events = (
                {
                    "method": "turn/started",
                    "params": {"turn": {"id": "turn", "status": "inProgress"}},
                },
                {
                    "method": "item/completed",
                    "params": {
                        "turnId": "turn",
                        "item": {
                            "id": "answer",
                            "type": "agentMessage",
                            "status": "completed",
                            "text": "The requested package result is ready.",
                        },
                    },
                },
                {
                    "method": "turn/completed",
                    "params": {"turn": {"id": "turn", "status": "completed"}},
                },
            )
            for value in events:
                event = reducer.normalize(value)
                assert event is not None
                app.presentation.apply_event(event)
            app._render_all()
            await pilot.pause()
            response = app.query_one(".response-message").query_one(
                ".conversation-message-content", Static
            )
            self.assertIn("The requested package result is ready.", str(response.content))

    async def test_installation_specialist_catalog_search_uses_agent_workflow(self) -> None:
        def inspect_packages(query: str, *, refresh: bool = True):
            self.assertTrue(refresh)
            self.assertIn("energy", query.casefold())
            return {
                "available": True,
                "stale": False,
                "installed_count": 10,
                "available_count": 20,
                "matches": [
                    {
                        "name": "power-profiles-daemon",
                        "state": "available",
                        "origin": "fedora",
                        "summary": "Power profile management daemon",
                    }
                ],
            }

        self.broker.local_control.inspect_packages = inspect_packages  # type: ignore[attr-defined]
        app = self.app(enable_live_turns=True)
        app._active_specialist = app.agent_registry.get("jarvis-installation-specialist")
        async with app.run_test(size=(100, 34)) as pilot:
            composer = app.query_one("#composer", Input)
            composer.value = "check the available packages related with energy management"
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            task = next(iter(self.broker._tasks.values()))
            self.assertEqual(task.agent_id, "jarvis-installation-specialist")
            self.assertEqual(
                app.presentation.admissions[task.task_id].route.value, "agent_conversation"
            )
            conversation = app.query_one("#conversation-log").text
            self.assertNotIn("Cached Fedora package catalog search", conversation)

    async def test_power_specialist_catalog_recommendation_uses_agent_workflow(self) -> None:
        def inspect_packages(query: str, *, refresh: bool = True):
            return {
                "available": True,
                "stale": False,
                "installed_count": 10,
                "available_count": 20,
                "matches": [
                    {
                        "name": "powertop",
                        "state": "available",
                        "origin": "fedora",
                        "summary": "Power consumption monitor",
                    }
                ],
            }

        self.broker.local_control.inspect_packages = inspect_packages  # type: ignore[attr-defined]
        app = self.app(enable_live_turns=True)
        app._active_specialist = app.agent_registry.get("jarvis-power-expert")
        async with app.run_test(size=(120, 42)) as pilot:
            composer = app.query_one("#composer", Input)
            composer.value = "which packages improve battery power management"
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertIsNone(app._pending_package_handoff)
            self.assertNotIn(
                "Cached Fedora package catalog search", app.query_one("#conversation-log").text
            )

    async def test_lighting_controls_have_a_confirmation_gated_apply_path(self) -> None:
        app = self.app(plain_mode=True)
        async with app.run_test(size=(120, 42)) as pilot:
            await pilot.press("ctrl+4")
            await pilot.pause()
            self.assertEqual(app.active_view, "lighting")
            self.assertIn(
                "Preview only",
                "\n".join(str(line) for line in app.query_one("#lighting-log").lines),
            )
            control = app.query_one("#lighting-brightness")
            before = control.value
            await pilot.click("#lighting-brightness-down")
            await pilot.pause()
            self.assertEqual(control.value, before - 1)
            await pilot.click("#lighting-preview")
            await pilot.pause()
            preview = "\n".join(str(line) for line in app.query_one("#lighting-log").lines)
            self.assertIn("exact selection", preview)

    @mock.patch("jarvis_tui.app.scan_power_inventory")
    async def test_power_tab_loads_driver_settings(self, scan_power_mock) -> None:
        scan_power_mock.return_value = PowerInventory(
            providers=("CPU frequency: intel_pstate", "TuneD / tuned-ppd"),
            settings=(
                PowerSetting("CPU", "Governor", "powersave", "performance, powersave", "/sys/test"),
            ),
            limitations=("read-only",),
        )
        app = self.app()
        async with app.run_test(size=(120, 42)) as pilot:
            await pilot.press("ctrl+g")
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertEqual(app.active_view, "power")
            table = app.query_one("#power-settings-table", DataTable)
            self.assertEqual(table.row_count, 1)
            table.focus()
            await pilot.press("enter")
            await pilot.pause()
            self.assertIn(
                "Governor",
                str(app.query_one("#power-details-content", Static).content),
            )

    async def test_user_submission_creates_a_conversation_checkpoint(self) -> None:
        app = self.app()
        async with app.run_test(size=(120, 42)) as pilot:
            composer = app.query_one("#composer", Input)
            composer.value = "hello checkpoint"
            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()
            self.assertEqual(len(app._conversation_checkpoints), 1)
            self.assertEqual(
                app._conversation_checkpoints[0].user_message_key,
                next(entry.key for entry in app.presentation.conversation if entry.role == "user"),
            )
            checkpoint_id = app._conversation_checkpoints[0].checkpoint_id
            checkpoint_button = app.query_one(f"#checkpoint-{checkpoint_id}", Button)
            self.assertEqual(checkpoint_button.region.width, 20)
            self.assertEqual(checkpoint_button.region.height, 3)
            message = checkpoint_button.parent.parent.parent
            self.assertIsNotNone(message)
            message_box = message.query_one("ConversationMessage")
            self.assertIsNotNone(message_box.query_one(".conversation-message-top", Static))
            self.assertIsNotNone(message_box.query_one(".conversation-message-bottom", Static))
            self.assertGreaterEqual(checkpoint_button.region.y, message_box.region.bottom)
            checkpoint_control = checkpoint_button.parent
            self.assertEqual(checkpoint_control.region.width, 20)
            self.assertGreater(checkpoint_control.region.x, message_box.region.x)
            self.assertLessEqual(checkpoint_control.region.right, message.region.right)
            self.assertLessEqual(message.region.right - checkpoint_button.region.right, 2)
            history = app.query_one("#conv-history", Button)
            self.assertEqual(history.region.width, 12)
            self.assertGreater(history.region.x, 0)
            self.assertLess(history.region.right, app.size.width)
            await pilot.click(checkpoint_button, offset=(1, 1))
            await pilot.pause()
            self.assertEqual(app.screen.__class__.__name__, "CheckpointChoiceScreen")
            self.assertIsNotNone(app.screen.query_one("#checkpoint-context", Button))
            self.assertIsNotNone(app.screen.query_one("#checkpoint-full", Button))
            cancel = app.screen.query_one("#checkpoint-cancel", Button)
            self.assertEqual(cancel.label.plain, "Cancel")
            self.assertEqual(cancel.region.width, 14)
            self.assertEqual(message.region.width, message_box.region.width)

    @mock.patch("jarvis_tui.app.scan_power_inventory")
    async def test_power_tab_drafts_persistent_goal_profile(self, scan_power_mock) -> None:
        scan_power_mock.return_value = PowerInventory(
            providers=("Power Profiles D-Bus",),
            settings=(
                PowerSetting(
                    "Profiles",
                    "Desktop profile",
                    "balanced",
                    "power-saver, balanced, performance",
                    "/profile",
                    True,
                    "power.profile",
                ),
                PowerSetting(
                    "CPU",
                    "EPP",
                    "balance_performance",
                    "power, balance_power, balance_performance, performance",
                    "/epp",
                    True,
                    "cpu.epp",
                ),
            ),
            limitations=("fixture",),
        )
        app = self.app()
        async with app.run_test(size=(140, 48)) as pilot:
            await pilot.press("ctrl+g")
            await app.workers.wait_for_complete()
            await pilot.pause()
            name = app.query_one("#power-profile-name", Input)
            name.value = "Battery Saver"
            await pilot.click("#power-profile-draft")
            await pilot.pause()
            self.assertIsNotNone(app._power_profile_plan)
            self.assertIn("Battery Saver", app.query_one("#power-profile-status", Static).content)

    @mock.patch("jarvis_tui.app.scan_power_inventory")
    async def test_power_profile_requests_use_agent_route(self, scan_power_mock) -> None:
        scan_power_mock.return_value = PowerInventory(
            providers=("Power Profiles D-Bus",),
            settings=(
                PowerSetting(
                    "Profiles",
                    "Desktop profile",
                    "balanced",
                    "power-saver, balanced, performance",
                    "/profile",
                    True,
                    "power.profile",
                ),
                PowerSetting(
                    "CPU",
                    "EPP",
                    "balance_performance",
                    "power, balance_power, balance_performance, performance",
                    "/epp",
                    True,
                    "cpu.epp",
                ),
            ),
            limitations=("fixture",),
        )
        app = self.app(enable_live_turns=True)
        app._active_specialist = app.agent_registry.get("jarvis-power-expert")
        async with app.run_test(size=(140, 48)) as pilot:
            composer = app.query_one("#composer", Input)
            composer.value = "create a power profile optimized for max performance and low-requiring sessions/tasks"
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            # This fixture is intentionally offline. The request must not be
            # answered by the former local keyword parser or create a Python
            # draft; it must fail closed while trying the agent route.
            self.assertIsNone(app._pending_clarification)
            self.assertIsNone(app._power_profile_plan)
            self.assertNotIn("Which power-profile setup", app.query_one("#conversation-log").text)

    async def test_agents_tab_definition_editor(self) -> None:
        app = self.app()
        async with app.run_test(size=(110, 40)) as pilot:
            app.action_show_agents()
            await pilot.pause()
            table = app.query_one("#agents-table", DataTable)
            self.assertGreaterEqual(table.row_count, 2)
            table.focus()
            await pilot.press("enter")
            await pilot.pause()
            self.assertIn("jarvis-", app.query_one("#agent-definition").text)
            self.assertIn("jarvis-", str(app.query_one("#agent-id", Static).content))
            self.assertTrue(app.query_one("#agent-tools", Input).value)
            self.assertTrue(app.query_one("#agent-knowledge-sources", Input).value)
            app.query_one("#agent-editor-mode", Select).value = "raw"
            await pilot.pause()
            self.assertTrue(app.query_one("#agent-raw").display)
            self.assertFalse(app.query_one("#agent-structured").display)
            app.query_one("#agent-editor-mode", Select).value = "structured"
            await pilot.pause()
            app.query_one("#agent-purpose", Input).value = ""
            app.query_one("#agent-purpose", Input).value = "Updated test purpose"
            await pilot.pause()
            await pilot.click("#agent-validate")
            await pilot.pause()
            app._validate_agent_draft()
            self.assertEqual(app._agent_editor_draft["purpose"], "Updated test purpose")
            self.assertTrue(app.agent_registry.validate(app._agent_editor_draft).valid)

    async def test_layout_mounts_at_compact_and_wide_sizes(self) -> None:
        for size in ((72, 20), (160, 50)):
            app = self.app()
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                self.assertIsNotNone(app.query_one("#composer", Input))
                self.assertIsNotNone(app.query_one("#cancel-turn", Button))
                self.assertIn(
                    "execution: typed preflight; read-only agent; registered one-use operations",
                    app.presentation.overview.safety,
                )

    @mock.patch("jarvis_tui.app.scan_rpm")
    async def test_packages_load_automatically_when_tab_opens(self, scan_rpm_mock) -> None:
        scan_rpm_mock.return_value = (
            PackageRecord(
                "demo",
                "1",
                "1",
                "x86_64",
                "Fedora",
                "Demo package",
                "other",
                "General system or user-space component",
                "rpmdb",
            ),
        )
        app = self.app()
        async with app.run_test(size=(120, 42)) as pilot:
            await pilot.press("ctrl+0")
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertTrue(app._package_loaded)
            self.assertEqual(len(app._package_records), 1)
            self.assertEqual(app._package_records[0].nevra, "demo-1-1.x86_64")
            table = app.query_one("#packages-table", DataTable)
            self.assertEqual(table.row_count, 1)
            self.assertGreaterEqual(table.size.height, 10)
            table.focus()
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(app.query_one("#package-name", Input).value, "demo")
            self.assertIn(
                "demo-1-1.x86_64",
                str(app.query_one("#package-details-content", Static).content),
            )
            package_query = app.query_one("#package-name", Input)
            package_query.value = "Demo package"
            package_query.focus()
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(table.row_count, 1)
            self.assertIn(
                "filter: Demo package",
                str(app.query_one("#package-summary", Static).content),
            )
            scan_rpm_mock.assert_called_once_with()

    async def test_composer_paste_preserves_all_clipboard_lines(self):
        app = self.app()
        async with app.run_test(size=(100, 34)):
            composer = app.query_one("#composer", Input)
            event = mock.Mock(text="first line\nsecond line\nthird line")
            composer._on_paste(event)
            self.assertEqual(composer.value, "first line\nsecond line\nthird line")
            event.stop.assert_called_once()

    async def test_login_button_reconnects_before_starting_managed_login(self):
        app = self.app()

        async def reconnect():
            app.session.snapshot.connection = ConnectionState.LOGIN_REQUIRED

        app.session.connect = mock.AsyncMock(side_effect=reconnect)
        app.session.begin_chatgpt_login = mock.AsyncMock(
            return_value={"type": "chatgpt", "authUrl": "https://chatgpt.com/login"}
        )
        with mock.patch("jarvis_tui.app.webbrowser.open", return_value=True):
            async with app.run_test(size=(120, 42)):
                await app._begin_chatgpt_login()

        app.session.connect.assert_awaited_once()
        app.session.begin_chatgpt_login.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
