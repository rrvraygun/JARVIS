#!/usr/bin/env python3
import importlib.util
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "knowledge_store", ROOT / "scripts/knowledge_store.py"
)
store = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(store)


with tempfile.TemporaryDirectory() as directory:
    database = Path(directory) / "knowledge.db"
    store.init_database(database)
    assert database.stat().st_mode & 0o777 == 0o600
    with closing(store.connect(database)) as connection, connection:
        assert store.seed_sources(connection)["seeded"] >= 9
        assert store.seed_sources(connection)["seeded"] == 0
        assert store.seed_catalog(connection)["seeded"] >= 20

        try:
            store.add_fact(
                connection,
                {
                    "fact_key": "privacy.secret-test",
                    "value": "not-written",
                    "privacy_class": "secret",
                    "collector": "fixture",
                    "collector_version": "1",
                    "prerequisites": {},
                },
            )
            raise AssertionError("secret plaintext was accepted")
        except ValueError as exc:
            assert "requires_unlocked_encryption" in str(exc)

        failure = store.add_attempt(
            connection,
            {
                "attempt_id": "attempt-failure",
                "executable": "/usr/bin/fixture",
                "argv": ["--wrong"],
                "purpose": "fixture failed syntax",
                "expected": {"exit": 0},
                "actual": {"exit": 2, "message": "unexpected option"},
                "exit_code": 2,
                "timed_out": False,
                "outcome": "failure",
                "privacy_class": "internal",
                "output_excerpt": "token=sk-abcdefghijklmnopqrstuvwxyz012345",
            },
        )
        assert failure["error_id"]
        saved = connection.execute(
            "SELECT output_excerpt FROM command_attempts WHERE attempt_id='attempt-failure'"
        ).fetchone()[0]
        assert "sk-" not in saved and "REDACTED" in saved

        lesson = store.append_lesson_revision(
            connection,
            {
                "lesson_id": "lesson-fixture",
                "title": "Use the corrected fixture option",
                "guidance": "Use --correct only when fixture version 1 is installed.",
                "prerequisites": {"fixture_version": "1"},
                "exclusions": ["version 2"],
                "validation": ["exit code 0", "expected output"],
                "source_error_ids": [failure["error_id"]],
                "success_threshold": 3,
            },
        )
        assert lesson["status"] == "draft"

        for index in range(3):
            attempt_id = f"attempt-success-{index}"
            store.add_attempt(
                connection,
                {
                    "attempt_id": attempt_id,
                    "executable": "/usr/bin/fixture",
                    "argv": ["--correct"],
                    "purpose": "fixture corrected syntax",
                    "expected": {"exit": 0},
                    "actual": {"exit": 0},
                    "exit_code": 0,
                    "timed_out": False,
                    "outcome": "success",
                    "privacy_class": "internal",
                    "output_excerpt": "ok",
                },
            )
            store.add_lesson_evidence(
                connection,
                {
                    "lesson_id": "lesson-fixture",
                    "attempt_id": attempt_id,
                    "evidence_type": "matching-success",
                    "prerequisites_match": True,
                    "independently_verified": True,
                    "details": {"fixture_version": "1"},
                },
            )

        resolved_error = store.revise_error(
            connection,
            failure["error_id"],
            {
                "diagnosis_status": "resolved",
                "candidate_cause": "wrong fixture option",
                "working_solution_attempt_id": "attempt-success-0",
                "reason": "verified corrected option",
            },
        )
        assert resolved_error["revision"] == 2 and resolved_error["status"] == "resolved"

        candidate = store.revise_lesson(connection, "lesson-fixture", "candidate", "threshold met")
        assert candidate["status"] == "candidate"
        try:
            store.revise_lesson(
                connection,
                "lesson-fixture",
                "approved",
                "bad approval",
                {"approver": "agent", "decision": "approved"},
            )
            raise AssertionError("agent approved a lesson")
        except ValueError as exc:
            assert "explicit_user_approval_required" in str(exc)
        approved = store.revise_lesson(
            connection,
            "lesson-fixture",
            "approved",
            "user reviewed",
            {
                "decision_id": "user-decision-1",
                "approver": "user",
                "decision": "approved",
            },
        )
        assert approved["status"] == "approved"

        store.add_decision(
            connection,
            {
                "objective": "select fixture syntax",
                "facts": [],
                "sources": [],
                "alternatives": ["--wrong", "--correct"],
                "selected_action": {"argv": ["--correct"]},
                "risk": {"score": 0},
                "validation": {"exit": 0},
                "outcome": {"status": "verified"},
            },
        )
        assert store.query(connection, "lessons", "corrected fixture", 5)

        context = {
            "capability": "update",
            "procedure": "change.execute",
            "command_id": "command-fixture",
            "executable": "/usr/bin/fixture",
            "argv": ["--change"],
            "targets": ["fixture-target"],
            "mutation": True,
            "privilege": True,
            "risk_score": 2,
            "risk": "medium",
            "validation": ["fixture healthy"],
            "rollback": ["fixture rollback"],
            "state_digest": "b" * 64,
            "approval_scope": "command",
            "state_age_seconds": 0,
            "capability_enabled": True,
            "requested_level": 1,
        }
        approval = {
            "id": "approval-fixture",
            "scope": "command",
            "scope_reference": "command-fixture",
            "action_digest": store.digest(store.redact(context)),
            "state_digest": "b" * 64,
            "approver": "user",
            "issued_at": "2026-01-01T00:00:00Z",
            "expires_at": "2099-01-01T00:00:00Z",
            "targets": ["fixture-target"],
            "decision": "approved",
            "nonce": "knowledge_nonce_123456",
            "consumed": False,
        }
        store.add_approval(connection, approval)
        assert store.consume_approval(connection, "approval-fixture", context)["valid"]
        replay = store.consume_approval(connection, "approval-fixture", context)
        assert not replay["valid"] and "approval_already_consumed" in replay["reasons"]
        assert store.verify(connection)["valid"]

        try:
            connection.execute(
                "UPDATE lesson_revisions SET status='approved' WHERE lesson_id='lesson-fixture'"
            )
            raise AssertionError("immutable lesson was updated")
        except sqlite3.IntegrityError:
            pass

print("knowledge-store tests passed")
