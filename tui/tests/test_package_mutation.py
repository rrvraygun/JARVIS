from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


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
    PackageMutationOperation,
)
from jarvis_tui.package_mutation import PackageMutationPlanner  # noqa: E402


class Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self, prefix: str) -> str:
        self.value += 1
        return f"{prefix}_{self.value}"


class PackageMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ids = Ids()
        self.planner = PackageMutationPlanner(identifier=self.ids)

    def test_exact_english_and_spanish_package_requests(self) -> None:
        install = self.planner.plan("install packages rust cargo")
        self.assertEqual(install.plan.operation, PackageMutationOperation.INSTALL)
        self.assertEqual(install.plan.packages, ("rust", "cargo"))
        remove = self.planner.plan("desinstalar paquete demo")
        self.assertEqual(remove.plan.operation, PackageMutationOperation.REMOVE)
        self.assertEqual(remove.plan.packages, ("demo",))

    def test_quoted_and_broad_root_removals_stay_deterministic(self) -> None:
        quoted = self.planner.plan(
            'uninstall "rust" package, implying 2 more dependencies will be uninstalled'
        )
        self.assertEqual(quoted.plan.operation, PackageMutationOperation.REMOVE)
        self.assertEqual(quoted.plan.packages, ("rust",))
        broad = self.planner.plan("uninstall all packages related to rust and cargo on the system")
        self.assertEqual(broad.plan.packages, ("rust", "cargo"))
        spanish = self.planner.plan('desinstalar el paquete "rust"')
        self.assertEqual(spanish.plan.packages, ("rust",))
        polite = self.planner.plan('can you uninstall the "rust" package')
        self.assertEqual(polite.plan.packages, ("rust",))
        question = self.planner.plan("can you uninstall rust packages?")
        self.assertEqual(question.plan.packages, ("rust",))
        typo = self.planner.plan("can you uninstall rust package=")
        self.assertEqual(typo.plan.packages, ("rust",))

    def test_missing_package_continuation_rebuilds_a_mechanical_request(self) -> None:
        self.assertTrue(self.planner.recognizes('uninstall "rust" package'))
        self.assertEqual(
            self.planner.continuation_text("uninstall package", '"rust"'),
            'uninstall package "rust"',
        )
        self.assertIsNone(self.planner.continuation_text("uninstall package", "option 1"))

    def test_non_exact_and_protected_removal_fail_closed(self) -> None:
        ambiguous = self.planner.plan("install latest rust")
        self.assertIsNotNone(ambiguous.clarification)
        protected = self.planner.plan("remove package systemd")
        self.assertEqual(protected.denial_code, "package_mutation.protected_package")

    def test_broker_admits_package_request_only_for_preview_and_fresh_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            journal = EventJournal(Path(directory) / "events.jsonl")
            broker = JarvisBroker(
                ActionRegistry.load(
                    BUNDLE_ROOT / "plugins/jarvis-system-admin/registry/actions.json"
                ),
                journal,
                identifier=self.ids,
                workspace=BUNDLE_ROOT,
            )
            task = broker.capture_text("install package fixture-package")
            assessment = broker.assess_deterministic_task(task)
            self.assertIsNone(assessment)
            self.assertIsNotNone(task.package_plan)
            agent_assessment = IntentAssessment(
                assessment_id="assessment_agent_package",
                decision=AssessmentDecision.EXECUTE,
                intent_class=IntentClass.HOST_CHANGE,
                operation="package_install",
                targets=("fixture-package",),
                risk=3,
                route=ExecutionRoute.REGISTERED_WORKFLOW,
                reason="agent confirmed exact package roots",
            )
            broker.bind_agent_package_assessment(task, agent_assessment)
            broker.record_assessment(task, agent_assessment)
            admission = broker.admit(task)
            self.assertEqual(admission.route, AdmissionRoute.REGISTERED_MUTATION)
            self.assertTrue(admission.approval_required)
            self.assertFalse(admission.execution_authorized)
            preview = {
                "operation": "install",
                "packages": ["fixture-package"],
                "preview_digest": "a" * 64,
                "approval_digest": "b" * 64,
                "affected_removals": [],
            }
            broker.approve_package_transaction(task, preview)
            with self.assertRaises(RuntimeError):
                broker.approve_package_transaction(task, preview)
            encoded = json.dumps(journal.read())
            self.assertNotIn("fixture-package", encoded)
            self.assertIn("package.transaction.approved", encoded)

    def test_package_rollback_confirmation_is_reserved_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            journal = EventJournal(Path(directory) / "events.jsonl")
            broker = JarvisBroker(
                ActionRegistry.load(
                    BUNDLE_ROOT / "plugins/jarvis-system-admin/registry/actions.json"
                ),
                journal,
                identifier=self.ids,
                workspace=BUNDLE_ROOT,
            )
            first_attempt = broker.new_package_undo_attempt()
            broker.reserve_package_undo("a" * 64, 2, first_attempt)
            with self.assertRaisesRegex(RuntimeError, "already approved"):
                broker.reserve_package_undo("a" * 64, 2, first_attempt)
            broker.reserve_package_undo("a" * 64, 2, broker.new_package_undo_attempt())
            events = journal.read()
            self.assertEqual(
                sum(
                    event["event_type"] == "package.rollback.execution.reserved" for event in events
                ),
                2,
            )

    def test_package_archive_confirmation_is_reserved_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            journal = EventJournal(Path(directory) / "events.jsonl")
            broker = JarvisBroker(
                ActionRegistry.load(
                    BUNDLE_ROOT / "plugins/jarvis-system-admin/registry/actions.json"
                ),
                journal,
                identifier=self.ids,
                workspace=BUNDLE_ROOT,
            )
            attempt = broker.new_package_archive_attempt()
            broker.reserve_package_archive("a" * 64, 1, attempt)
            with self.assertRaisesRegex(RuntimeError, "already approved"):
                broker.reserve_package_archive("a" * 64, 1, attempt)

    def test_preview_failure_journals_only_a_safe_category_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            journal = EventJournal(Path(directory) / "events.jsonl")
            broker = JarvisBroker(
                ActionRegistry.load(
                    BUNDLE_ROOT / "plugins/jarvis-system-admin/registry/actions.json"
                ),
                journal,
                identifier=self.ids,
                workspace=BUNDLE_ROOT,
            )
            task = broker.capture_text("remove package fixture-package")
            broker.assess_deterministic_task(task)
            broker.record_package_preview_failure(
                task,
                "package_preview.runtimeerror",
                "RuntimeError",
                RuntimeError("private DNF diagnostic"),
            )
            encoded = json.dumps(journal.read())
            self.assertIn("package.transaction.preview_failed", encoded)
            self.assertIn("package_preview.runtimeerror", encoded)
            self.assertNotIn("fixture-package", encoded)
            self.assertNotIn("private DNF diagnostic", encoded)


if __name__ == "__main__":
    unittest.main()
