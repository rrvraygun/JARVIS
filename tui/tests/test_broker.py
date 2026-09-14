#!/usr/bin/env python3
from __future__ import annotations

import asyncio
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
from jarvis_tui.event_store import EventJournal  # noqa: E402
from jarvis_tui.models import (  # noqa: E402
    AdmissionRoute,
    AssessmentDecision,
    ExecutionRoute,
    IntentAssessment,
    IntentClass,
    TaskState,
)
from jarvis_tui.preflight import preflight_prompt  # noqa: E402
from jarvis_tui.specialists import load_specialists  # noqa: E402


class Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self, prefix: str) -> str:
        self.value += 1
        return f"{prefix}_{self.value}"


class BrokerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        registry = ActionRegistry.load(
            BUNDLE_ROOT / "plugins/jarvis-system-admin/registry/actions.json"
        )
        self.journal = EventJournal(Path(self.temporary.name) / "events.jsonl")
        self.broker = JarvisBroker(
            registry,
            self.journal,
            session_id="session_fixture",
            clock=lambda: "2026-08-05T12:00:00Z",
            identifier=Ids(),
        )

    def assess(self, task, *, intent_class=IntentClass.INSPECT, risk=0, targets=("/tmp",)):
        self.broker.record_assessment(
            task,
            IntentAssessment(
                assessment_id=self.broker.identifier("assessment"),
                decision=AssessmentDecision.EXECUTE,
                intent_class=intent_class,
                operation="fixture operation",
                targets=targets,
                risk=risk,
                route=ExecutionRoute.CONVERSATION,
                reason="fixture is exact",
            ),
        )

    def test_both_ingress_paths_use_the_same_pipeline(self) -> None:
        natural = self.broker.capture_text(
            "Diagnose why display and keyboard lighting stop in low-power mode."
        )
        catalog = self.broker.capture_action(
            "health.lighting.diagnose",
            {
                "affected_controls": "both",
                "nvidia_power_correlation": "suspected",
                "external_display_affected": "not_tested",
            },
        )
        self.assertEqual(natural.state, TaskState.CAPTURED)
        self.assertEqual(catalog.state, TaskState.CAPTURED)
        self.assertEqual(natural.pipeline_version, catalog.pipeline_version)
        self.assertEqual(natural.session_id, catalog.session_id)
        events = self.journal.read()
        self.assertEqual(
            [item["event_type"] for item in events], ["intent.captured", "intent.captured"]
        )
        self.assertEqual(
            {item["details"]["pipeline_version"] for item in events},
            {"3.0.0"},
        )
        encoded = json.dumps(events)
        self.assertNotIn("Diagnose why display", encoded)
        self.assertNotIn("suspected", encoded)
        self.assertIn("content_digest", encoded)

    def test_short_greeting_skips_model_preflight_but_uses_conversation_route(self) -> None:
        task = self.broker.capture_text("heyy!")
        assessment = self.broker.assess_deterministic_task(task)
        self.assertIsNotNone(assessment)
        assert assessment is not None
        self.assertEqual(assessment.intent_class, IntentClass.EXPLAIN)
        self.assertEqual(assessment.route, ExecutionRoute.CONVERSATION)
        self.assertEqual(assessment.targets, ())

    def test_agent_package_assessment_binds_a_polite_package_request(self) -> None:
        task = self.broker.capture_text('can you uninstall the "rust" package')
        self.assertIsNone(self.broker.assess_deterministic_task(task))
        self.assertIsNotNone(task.package_plan)
        prompt = preflight_prompt(task, str(BUNDLE_ROOT))
        self.assertIn("package_remove", prompt)
        self.assertIn("never propose sudo, dnf, Bash", prompt)
        self.assertIn("rsut versus rust", prompt)
        assessment = IntentAssessment(
            assessment_id="assessment_package_remove",
            decision=AssessmentDecision.EXECUTE,
            intent_class=IntentClass.HOST_CHANGE,
            operation="package_remove",
            targets=("rust",),
            risk=3,
            route=ExecutionRoute.REGISTERED_WORKFLOW,
            reason="agent confirmed system package root",
        )
        self.broker.bind_agent_package_assessment(task, assessment)
        self.broker.record_assessment(task, assessment)
        self.assertEqual(self.broker.admit(task).route, AdmissionRoute.REGISTERED_MUTATION)

    def test_non_package_model_target_becomes_a_safe_exact_root_clarification(self) -> None:
        task = self.broker.capture_text("I want an official Go release")
        assessment = IntentAssessment(
            assessment_id="assessment_go",
            decision=AssessmentDecision.EXECUTE,
            intent_class=IntentClass.HOST_CHANGE,
            operation="package_install",
            targets=("official Go release",),
            risk=3,
            route=ExecutionRoute.REGISTERED_WORKFLOW,
            reason="fixture package source",
        )
        bound = self.broker.bind_agent_package_assessment(task, assessment)
        self.assertEqual(bound.decision, AssessmentDecision.CLARIFY)
        self.assertEqual(bound.route, ExecutionRoute.NONE)
        self.assertIn("Distribution Go toolchain (golang)", bound.clarification_options)
        self.assertIsNone(task.package_plan)

    def test_prepared_turn_is_read_only_and_not_transmitted(self) -> None:
        task = self.broker.capture_action(
            "health.lighting.diagnose",
            {
                "affected_controls": "both",
                "nvidia_power_correlation": "suspected",
            },
        )
        self.broker.assess_registered_task(task)
        request = self.broker.prepare_turn_request(
            task,
            thread_id="thr_fixture",
            workspace=BUNDLE_ROOT,
            request_id=17,
        )
        self.assertEqual(request["method"], "turn/start")
        self.assertEqual(request["id"], 17)
        self.assertEqual(request["params"]["sandboxPolicy"]["type"], "readOnly")
        self.assertEqual(
            request["params"]["sandboxPolicy"],
            {"type": "readOnly", "networkAccess": False},
        )
        self.assertFalse(request["params"]["approvalPolicy"]["granular"]["sandbox_approval"])
        self.assertEqual(
            request["params"]["approvalPolicy"],
            {"granular": {"mcp_elicitations": True, "rules": False, "sandbox_approval": False}},
        )
        prompt = request["params"]["input"][0]["text"]
        self.assertIn("health.lighting.diagnose@1.0.0", prompt)
        self.assertIn("Do not broaden scope", prompt)
        envelope = prompt.split("<jarvis_intent_envelope>\n", 1)[1].split(
            "\n</jarvis_intent_envelope>", 1
        )[0]
        self.assertEqual(json.loads(envelope)["source"], "catalog_action")

    def test_context_derived_answer_is_classified_and_compiled_without_tools(self) -> None:
        task = self.broker.capture_text(
            "Can you tell me how many .png files are there in the directory?"
        )
        classifier = preflight_prompt(task, str(BUNDLE_ROOT))
        self.assertIn("exactly one recent compatible result", classifier)
        self.assertIn("counting, summarizing, comparing, or explaining", classifier)
        self.assertIn("no new filesystem or tool operation", classifier)
        self.assertIn("current, fresh, refreshed, or changed state", classifier)

        self.broker.record_assessment(
            task,
            IntentAssessment(
                assessment_id=self.broker.identifier("assessment"),
                decision=AssessmentDecision.EXECUTE,
                intent_class=IntentClass.EXPLAIN,
                operation="count PNG entries in prior bounded listing",
                targets=(),
                risk=0,
                route=ExecutionRoute.CONVERSATION,
                reason="one recent listing contains sufficient evidence",
            ),
        )
        prompt = self.broker.compile_agent_prompt(task)
        self.assertIn("answer-only conversation turn", prompt)
        self.assertIn("Answer from the active Conversation evidence", prompt)
        self.assertIn("Do not call tools", prompt)
        self.assertIn("Do not refresh prior evidence", prompt)
        self.assertIn("State relevant snapshot limits", prompt)
        self.assertNotIn("reviewed Bash", prompt)
        self.assertNotIn("submit the exact command/file approval", prompt)

    def test_specialist_contract_is_supplied_once_then_referenced(self) -> None:
        specialist = next(
            item for item in load_specialists(BUNDLE_ROOT) if item.id == "jarvis-github-agent"
        )
        task = self.broker.capture_text(
            "Inspect this repository.",
            agent_id=specialist.id,
            agent_version=specialist.version,
        )
        self.broker.record_assessment(
            task,
            IntentAssessment(
                assessment_id=self.broker.identifier("assessment"),
                decision=AssessmentDecision.EXECUTE,
                intent_class=IntentClass.INSPECT,
                operation="inspect repository",
                targets=(str(BUNDLE_ROOT),),
                risk=0,
                route=ExecutionRoute.REGISTERED_WORKFLOW,
                reason="exact fixture target",
            ),
        )
        first = self.broker.compile_agent_prompt(task, specialist=specialist)
        later = self.broker.compile_agent_prompt(
            task, specialist=specialist, include_specialist_context=False
        )
        self.assertIn("Act as JARVIS GitHub Agent", first)
        self.assertIn("Specialist contract digest:", first)
        self.assertNotIn("Act as JARVIS GitHub Agent", later)
        self.assertIn("same specialist contract was already supplied", later)

    def test_journal_redacts_and_detects_tampering(self) -> None:
        self.journal.append(
            "test.event",
            "broker",
            "recorded",
            {"access_token": "do-not-store", "safe": "value"},
        )
        event = self.journal.read()[0]
        self.assertEqual(event["details"]["access_token"], "[REDACTED]")
        self.assertEqual(self.journal.verify()[0], True)
        event["details"]["safe"] = "tampered"
        self.journal.path.write_text(json.dumps(event) + "\n", encoding="utf-8")
        self.assertEqual(self.journal.verify()[0], False)

    def test_natural_language_and_catalog_share_scoped_execution(self) -> None:
        natural = self.broker.capture_text("Diagnose a lighting symptom.")
        catalog = self.broker.capture_action(
            "health.lighting.diagnose",
            {
                "affected_controls": "both",
                "nvidia_power_correlation": "suspected",
            },
        )
        self.assess(natural)
        self.broker.assess_registered_task(catalog)
        natural_admission = self.broker.admit(natural)
        catalog_admission = self.broker.admit(catalog)
        for admission in (natural_admission, catalog_admission):
            self.assertEqual(admission.route, AdmissionRoute.AGENT_CONVERSATION)
            self.assertEqual(admission.decision, "allow_scoped_execution")
            self.assertEqual(admission.host_authority, "agent-read-only")
            self.assertTrue(admission.execution_authorized)
            self.assertTrue(admission.agent_turn_authorized)
            self.assertFalse(admission.mutation_authorized)
            self.assertEqual(admission.authority, "current-user-agent")
        self.assertEqual(self.broker.admit(natural), natural_admission)
        admitted = [
            event for event in self.journal.read() if event["event_type"] == "task.admitted"
        ]
        self.assertEqual(len(admitted), 2)

    def test_non_agent_action_routes_to_local_read(self) -> None:
        task = self.broker.capture_action(
            "knowledge.search", {"kind": "sources", "query": "backlight"}
        )
        self.broker.assess_registered_task(task)
        admission = self.broker.admit(task)
        self.assertEqual(admission.route, AdmissionRoute.LOCAL_READ)
        self.assertEqual(admission.host_authority, "none")
        self.assertEqual(admission.authority, "registered-local-read")
        self.assertTrue(admission.execution_authorized)
        self.assertFalse(admission.agent_turn_authorized)
        self.assertFalse(admission.mutation_authorized)
        self.assertIsNone(admission.sandbox_policy)

    def test_deterministic_filesystem_result_is_not_persisted_in_journal(self) -> None:
        target = Path(self.temporary.name) / "bounded-target"
        target.mkdir()
        (target / "private-listing-marker.txt").write_text(
            "private-content-marker", encoding="utf-8"
        )
        task = self.broker.capture_text(f"list files in {target}")
        assessment = self.broker.assess_deterministic_task(task)
        self.assertIsNotNone(assessment)
        admission = self.broker.admit(task)
        self.assertEqual(admission.route, AdmissionRoute.LOCAL_READ)
        result = asyncio.run(self.broker.execute_local_filesystem_read(task))
        self.assertIn("private-listing-marker.txt", result.display_text)
        encoded = json.dumps(self.journal.read())
        self.assertNotIn("private-listing-marker.txt", encoded)
        self.assertNotIn("private-content-marker", encoded)
        with self.assertRaisesRegex(RuntimeError, "execution reservation"):
            asyncio.run(self.broker.execute_local_filesystem_read(task))
        reservations = [
            event
            for event in self.journal.read()
            if event["event_type"] == "local_read.execution.reserved"
        ]
        self.assertEqual(len(reservations), 1)
        self.assertIn("target_digest", encoded)


if __name__ == "__main__":
    unittest.main()
