#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

TUI_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = TUI_ROOT.parent
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.models import (  # noqa: E402  # noqa: E402
    AssessmentDecision,
    ExecutionRoute,
    IntentAssessment,
    IntentAssessmentValidationError,
    IntentClass,
    IntentEnvelope,
    IntentSource,
    TaskMode,
    TaskRecord,
    TaskState,
)
from jarvis_tui.preflight import (  # noqa: E402
    PREFLIGHT_OUTPUT_SCHEMA,
    PreflightClassifierError,
    parse_preflight_output,
    preflight_prompt,
)

VALID = (
    {
        "decision": "execute",
        "intent_class": "explain",
        "operation": "explain",
        "targets": [],
        "risk": 0,
        "route": "conversation",
        "reason": "pure explanation",
        "clarification_question": None,
        "clarification_options": [],
    },
    {
        "decision": "execute",
        "intent_class": "inspect",
        "operation": "inspect",
        "targets": ["/srv/example"],
        "risk": 0,
        "route": "reviewed_bash",
        "reason": "exact target",
        "clarification_question": None,
        "clarification_options": [],
    },
    {
        "decision": "clarify",
        "intent_class": "host_change",
        "operation": "service state",
        "targets": [],
        "risk": 3,
        "route": "none",
        "reason": "ambiguous state",
        "clarification_question": "Which service state should I apply?",
        "clarification_options": ["Start it", "Enable at boot", "Both"],
    },
    {
        "decision": "deny",
        "intent_class": "host_change",
        "operation": "unsafe request",
        "targets": [],
        "risk": 4,
        "route": "none",
        "reason": "permanent denial",
        "clarification_question": None,
        "clarification_options": [],
    },
)


class TypedPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        validator_path = BUNDLE_ROOT / "plugins/jarvis-system-admin/scripts/schema_validate.py"
        spec = importlib.util.spec_from_file_location("jarvis_schema_validate", validator_path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.validate_schema = staticmethod(module.validate)

    def test_every_valid_decision_branch_satisfies_schema_and_domain_model(self) -> None:
        for index, payload in enumerate(VALID):
            with self.subTest(decision=payload["decision"], intent_class=payload["intent_class"]):
                wire = {"assessment": payload}
                self.assertEqual(self.validate_schema(PREFLIGHT_OUTPUT_SCHEMA, wire), [])
                assessment = parse_preflight_output(json.dumps(wire), f"assessment_{index}")
                self.assertEqual(assessment.decision.value, payload["decision"])

    def test_invalid_cross_field_matrix_is_rejected_with_stable_model_code(self) -> None:
        invalid = (
            (
                {**VALID[2], "clarification_options": ["Only one"]},
                "preflight.invalid_clarification",
            ),
            ({**VALID[1], "route": "none"}, "preflight.invalid_route"),
            ({**VALID[1], "targets": []}, "preflight.missing_target"),
            ({**VALID[3], "route": "conversation"}, "preflight.invalid_route"),
            (
                {**VALID[1], "clarification_question": "Unexpected?"},
                "preflight.invalid_decision_variant",
            ),
            ({**VALID[3], "targets": ["forbidden"]}, "preflight.invalid_decision_variant"),
        )
        for payload, code in invalid:
            with self.subTest(code=code):
                wire = {"assessment": payload}
                with self.assertRaises(PreflightClassifierError) as caught:
                    parse_preflight_output(json.dumps(wire), "assessment_fixture")
                self.assertEqual(caught.exception.code, code)

    def test_schema_and_python_model_enforce_decision_matrix_fail_closed(self) -> None:
        decisions = ("execute", "clarify", "deny")
        classes = ("explain", "inspect", "project_change", "host_change", "external_effect")
        routes = ("conversation", "registered_workflow", "reviewed_bash", "local_read", "none")
        targets_values = ([], ["/exact/target"])
        clarification_values = (
            (None, []),
            ("Which exact option?", ["First", "Second"]),
            ("Which exact option?", ["Only one"]),
            (None, ["First", "Second"]),
        )
        for decision in decisions:
            for intent_class in classes:
                for route in routes:
                    for targets in targets_values:
                        for question, options in clarification_values:
                            payload = {
                                "decision": decision,
                                "intent_class": intent_class,
                                "operation": "matrix operation",
                                "targets": targets,
                                "risk": 0,
                                "route": route,
                                "reason": "matrix reason",
                                "clarification_question": question,
                                "clarification_options": options,
                            }
                            schema_accepts = not self.validate_schema(
                                PREFLIGHT_OUTPUT_SCHEMA, {"assessment": payload}
                            )
                            try:
                                IntentAssessment.from_dict(payload, "assessment_matrix")
                            except IntentAssessmentValidationError:
                                model_accepts = False
                            else:
                                model_accepts = True
                            if model_accepts:
                                self.assertTrue(
                                    schema_accepts,
                                    (decision, intent_class, route, targets, question, options),
                                )
                            if not schema_accepts:
                                self.assertFalse(
                                    model_accepts,
                                    (decision, intent_class, route, targets, question, options),
                                )

    def test_invalid_json_and_root_shape_have_stable_codes(self) -> None:
        cases = (
            ("not-json", "preflight.invalid_json"),
            ("[]", "preflight.invalid_shape"),
            ("{}", "preflight.invalid_shape"),
        )
        for raw, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(PreflightClassifierError) as caught:
                    parse_preflight_output(raw, "assessment_fixture")
                self.assertEqual(caught.exception.code, code)

    def test_exact_inspection_is_executable_without_confirmation(self) -> None:
        assessment = IntentAssessment.from_dict(VALID[1], "assessment_fixture")
        self.assertEqual(assessment.decision, AssessmentDecision.EXECUTE)
        self.assertEqual(assessment.route, ExecutionRoute.REVIEWED_BASH)
        self.assertFalse(assessment.requires_confirmation)

    def test_clarification_without_options_is_rejected_with_stable_code(self) -> None:
        with self.assertRaises(IntentAssessmentValidationError) as caught:
            IntentAssessment(
                assessment_id="assessment_fixture",
                decision=AssessmentDecision.CLARIFY,
                intent_class=IntentClass.INSPECT,
                operation="inspect",
                targets=(),
                risk=0,
                route=ExecutionRoute.NONE,
                reason="target missing",
                clarification_question="Which target?",
            )
        self.assertEqual(caught.exception.code, "preflight.invalid_clarification")

    def test_schema_uses_nested_supported_any_of_variants(self) -> None:
        self.assertFalse(PREFLIGHT_OUTPUT_SCHEMA["additionalProperties"])
        self.assertEqual(PREFLIGHT_OUTPUT_SCHEMA["required"], ["assessment"])
        assessment = PREFLIGHT_OUTPUT_SCHEMA["properties"]["assessment"]
        branches = assessment["anyOf"]
        self.assertEqual(len(branches), 4)
        self.assertTrue(all(branch["type"] == "object" for branch in branches))
        self.assertTrue(all(branch["additionalProperties"] is False for branch in branches))
        self.assertTrue(
            all(set(branch["required"]) == set(branch["properties"]) for branch in branches)
        )

    def test_wire_schema_uses_only_portable_fine_tuned_keywords(self) -> None:
        unsupported = {
            "allOf",
            "not",
            "dependentRequired",
            "dependentSchemas",
            "if",
            "then",
            "else",
            "minLength",
            "maxLength",
            "pattern",
            "format",
            "minimum",
            "maximum",
            "multipleOf",
            "patternProperties",
            "minItems",
            "maxItems",
        }

        def walk(value):
            if isinstance(value, dict):
                self.assertFalse(unsupported.intersection(value), value)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(PREFLIGHT_OUTPUT_SCHEMA)

    def test_classifier_does_not_treat_outside_project_as_a_policy_denial(self) -> None:
        intent = IntentEnvelope(
            intent_id="intent_fixture",
            session_id="session_fixture",
            source=IntentSource.NATURAL_LANGUAGE,
            requested_mode=TaskMode.DIAGNOSE,
            text="edit /home/user/Documents/example.txt",
            action_id=None,
            action_version=None,
            parameters={},
            constraints=(),
            created_at="2026-08-27T00:00:00Z",
        )
        task = TaskRecord(
            task_id="task_fixture",
            session_id="session_fixture",
            intent=intent,
            state=TaskState.CAPTURED,
            created_at="2026-08-27T00:00:00Z",
            updated_at="2026-08-27T00:00:00Z",
        )
        prompt = preflight_prompt(task, "/workspace")
        self.assertIn("outside the project", prompt)
        self.assertIn("exact one-use approval", prompt)
        self.assertIn("current branch", prompt)
        self.assertIn("fresh registered repository inspection", prompt)


if __name__ == "__main__":
    unittest.main()
