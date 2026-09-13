#!/usr/bin/env python3
"""Immutable Fedora knowledge store; this program never administers the host."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import re
import sqlite3
import sys
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "storage/schema.sql"
ZERO_HASH = "0" * 64
SENSITIVE_KEY = re.compile(
    r"(?i)(password|passwd|secret|token|private[_-]?key|api[_-]?key|credential|cookie|authorization|serial|machine[_-]?id)"
)
VALUE_PATTERNS = (
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
        "[REDACTED-PRIVATE-KEY]",
    ),
    (
        re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
        "[REDACTED-AUTHORIZATION]",
    ),
    (
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b"),
        "[REDACTED-TOKEN]",
    ),
    (
        re.compile(r"(?<![A-Za-z0-9])(?:10|127)\.(?:\d{1,3}\.){2}\d{1,3}(?![A-Za-z0-9])"),
        "[REDACTED-LOCAL-IP]",
    ),
    (
        re.compile(r"(?<![A-Za-z0-9])192\.168\.(?:\d{1,3}\.)\d{1,3}(?![A-Za-z0-9])"),
        "[REDACTED-LOCAL-IP]",
    ),
    (
        re.compile(
            r"(?<![A-Za-z0-9])172\.(?:1[6-9]|2\d|3[01])\.(?:\d{1,3}\.)\d{1,3}(?![A-Za-z0-9])"
        ),
        "[REDACTED-LOCAL-IP]",
    ),
    (re.compile(r"/home/[^/\s]+"), "/home/[REDACTED-USER]"),
)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def redact_text(value: str) -> str:
    result = value
    for pattern, replacement in VALUE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if SENSITIVE_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def init_database(path: Path) -> None:
    with closing(connect(path)) as connection, connection:
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        connection.execute("UPDATE metadata SET value='2' WHERE key='schema_version'")
        for row in connection.execute(
            """SELECT * FROM error_reports e WHERE NOT EXISTS
               (SELECT 1 FROM error_report_revisions r WHERE r.error_id=e.error_id)"""
        ).fetchall():
            append_error_revision(
                connection,
                row["error_id"],
                row["diagnosis_status"],
                row["candidate_cause"],
                row["working_solution_attempt_id"],
                "migrated immutable error observation",
            )
    path.chmod(0o600)


def encryption_ready(connection: sqlite3.Connection) -> bool:
    row = connection.execute("SELECT value FROM metadata WHERE key='encryption_state'").fetchone()
    return bool(row and row[0] == "unlocked")


def enforce_privacy(connection: sqlite3.Connection, privacy_class: str) -> None:
    if privacy_class in {"restricted", "secret"} and not encryption_ready(connection):
        raise ValueError("restricted_or_secret_storage_requires_unlocked_encryption")


def next_revision(
    connection: sqlite3.Connection, table: str, id_column: str, object_id: str
) -> tuple[int, str]:
    allowed = {
        "source_revisions": "source_id",
        "fact_revisions": "fact_id",
        "command_catalog_revisions": "command_id",
        "lesson_revisions": "lesson_id",
    }
    if allowed.get(table) != id_column:
        raise ValueError("unsupported revision table")
    row = connection.execute(
        f"SELECT revision, record_hash FROM {table} WHERE {id_column}=? ORDER BY revision DESC LIMIT 1",
        (object_id,),
    ).fetchone()
    return (int(row[0]) + 1, str(row[1])) if row else (1, ZERO_HASH)


def add_source(connection: sqlite3.Connection, item: dict[str, Any]) -> dict[str, Any]:
    item = redact(item)
    source_id = str(item["source_id"])
    revision, previous = next_revision(connection, "source_revisions", "source_id", source_id)
    record = {
        "source_id": source_id,
        "revision": revision,
        "source_class": item["source_class"],
        "authority_tier": int(item["authority_tier"]),
        "title": item["title"],
        "publisher": item["publisher"],
        "locator": item["locator"],
        "applicable_versions": item.get("applicable_versions", {}),
        "retrieved_at": item.get("retrieved_at", now()),
        "content_hash": item.get("content_hash") or digest(item.get("content", "")),
        "content": item.get("content"),
        "complete": bool(item.get("complete", False)),
        "community_confirmation_required": bool(
            item.get("community_confirmation_required", int(item["authority_tier"]) >= 6)
        ),
        "previous_hash": previous,
    }
    record_hash = digest(record)
    connection.execute(
        """INSERT INTO source_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            source_id,
            revision,
            record["source_class"],
            record["authority_tier"],
            record["title"],
            record["publisher"],
            record["locator"],
            canonical(record["applicable_versions"]),
            record["retrieved_at"],
            record["content_hash"],
            record["content"],
            int(record["complete"]),
            int(record["community_confirmation_required"]),
            previous,
            record_hash,
        ),
    )
    return {"source_id": source_id, "revision": revision, "record_hash": record_hash}


def add_fact(connection: sqlite3.Connection, item: dict[str, Any]) -> dict[str, Any]:
    privacy_class = str(item.get("privacy_class", "internal"))
    enforce_privacy(connection, privacy_class)
    item = redact(item)
    fact_id = str(item.get("fact_id") or item["fact_key"])
    revision, previous = next_revision(connection, "fact_revisions", "fact_id", fact_id)
    record = {
        "fact_id": fact_id,
        "revision": revision,
        "machine_scope": "enrolled-workstation",
        "fact_key": item["fact_key"],
        "value": item["value"],
        "value_type": item.get("value_type", type(item["value"]).__name__),
        "collected_at": item.get("collected_at", now()),
        "valid_until": item.get("valid_until"),
        "collector": item["collector"],
        "collector_version": item["collector_version"],
        "source_attempt_id": item.get("source_attempt_id"),
        "privacy_class": privacy_class,
        "prerequisites": item.get("prerequisites", {}),
        "status": item.get("status", "current"),
        "previous_hash": previous,
    }
    record_hash = digest(record)
    connection.execute(
        """INSERT INTO fact_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            fact_id,
            revision,
            record["machine_scope"],
            record["fact_key"],
            canonical(record["value"]),
            record["value_type"],
            record["collected_at"],
            record["valid_until"],
            record["collector"],
            record["collector_version"],
            record["source_attempt_id"],
            privacy_class,
            canonical(record["prerequisites"]),
            record["status"],
            previous,
            record_hash,
        ),
    )
    return {"fact_id": fact_id, "revision": revision, "record_hash": record_hash}


def add_attempt(connection: sqlite3.Connection, item: dict[str, Any]) -> dict[str, Any]:
    privacy_class = str(item.get("privacy_class", "internal"))
    enforce_privacy(connection, privacy_class)
    item = redact(item)
    attempt_id = str(item.get("attempt_id") or uuid.uuid4())
    output = str(item.get("output_excerpt", ""))
    record = {
        "attempt_id": attempt_id,
        "requested_at": item.get("requested_at", now()),
        "executable": item["executable"],
        "argv": item.get("argv", []),
        "cwd_class": item.get("cwd_class", "workspace"),
        "environment_keys": item.get("environment_keys", []),
        "purpose": item["purpose"],
        "expected": item.get("expected", {}),
        "actual": item.get("actual", {}),
        "exit_code": item.get("exit_code"),
        "timed_out": bool(item.get("timed_out", False)),
        "outcome": item["outcome"],
        "output_hash": item.get("output_hash") or hashlib.sha256(output.encode()).hexdigest(),
        "output_excerpt": output,
        "output_bytes": int(item.get("output_bytes", len(output.encode()))),
        "privacy_class": privacy_class,
        "evidence": item.get("evidence", []),
        "action_digest": item.get("action_digest")
        or digest({"executable": item["executable"], "argv": item.get("argv", [])}),
    }
    record_hash = digest(record)
    connection.execute(
        """INSERT INTO command_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            attempt_id,
            record["requested_at"],
            record["executable"],
            canonical(record["argv"]),
            record["cwd_class"],
            canonical(record["environment_keys"]),
            record["purpose"],
            canonical(record["expected"]),
            canonical(record["actual"]),
            record["exit_code"],
            int(record["timed_out"]),
            record["outcome"],
            record["output_hash"],
            output,
            record["output_bytes"],
            privacy_class,
            canonical(record["evidence"]),
            record["action_digest"],
            record_hash,
        ),
    )
    result = {"attempt_id": attempt_id, "record_hash": record_hash}
    if record["outcome"] in {"failure", "unexpected"}:
        error_id = str(uuid.uuid4())
        error_record = {
            "error_id": error_id,
            "attempt_id": attempt_id,
            "created_at": now(),
            "error_class": item.get("error_class", "unexpected-command-result"),
            "expected": record["expected"],
            "observed": record["actual"],
            "diagnosis_status": item.get("diagnosis_status", "unreviewed"),
            "candidate_cause": item.get("candidate_cause"),
            "working_solution_attempt_id": item.get("working_solution_attempt_id"),
        }
        report_hash = digest(error_record)
        connection.execute(
            "INSERT INTO error_reports VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                error_id,
                attempt_id,
                error_record["created_at"],
                error_record["error_class"],
                canonical(error_record["expected"]),
                canonical(error_record["observed"]),
                error_record["diagnosis_status"],
                error_record["candidate_cause"],
                error_record["working_solution_attempt_id"],
                report_hash,
            ),
        )
        append_error_revision(
            connection,
            error_id,
            error_record["diagnosis_status"],
            error_record["candidate_cause"],
            error_record["working_solution_attempt_id"],
            "initial error observation",
        )
        result["error_id"] = error_id
    return result


def append_error_revision(
    connection: sqlite3.Connection,
    error_id: str,
    status: str,
    candidate_cause: str | None,
    working_solution_attempt_id: str | None,
    reason: str,
) -> dict[str, Any]:
    error = connection.execute(
        "SELECT error_id FROM error_reports WHERE error_id=?", (error_id,)
    ).fetchone()
    if not error:
        raise ValueError("error_report_not_found")
    prior = connection.execute(
        "SELECT revision, record_hash FROM error_report_revisions WHERE error_id=? ORDER BY revision DESC LIMIT 1",
        (error_id,),
    ).fetchone()
    revision = int(prior["revision"]) + 1 if prior else 1
    previous = str(prior["record_hash"]) if prior else ZERO_HASH
    record = {
        "error_id": error_id,
        "revision": revision,
        "created_at": now(),
        "diagnosis_status": status,
        "candidate_cause": candidate_cause,
        "working_solution_attempt_id": working_solution_attempt_id,
        "reason": reason,
        "previous_hash": previous,
    }
    record_hash = digest(record)
    connection.execute(
        "INSERT INTO error_report_revisions VALUES (?,?,?,?,?,?,?,?,?)",
        (
            error_id,
            revision,
            record["created_at"],
            status,
            candidate_cause,
            working_solution_attempt_id,
            reason,
            previous,
            record_hash,
        ),
    )
    return {
        "error_id": error_id,
        "revision": revision,
        "status": status,
        "record_hash": record_hash,
    }


def add_error_report(connection: sqlite3.Connection, item: dict[str, Any]) -> dict[str, Any]:
    item = redact(item)
    attempt = connection.execute(
        "SELECT attempt_id, expected_json, actual_json FROM command_attempts WHERE attempt_id=?",
        (item["attempt_id"],),
    ).fetchone()
    if not attempt:
        raise ValueError("attempt_not_found")
    error_id = str(item.get("error_id") or uuid.uuid4())
    record = {
        "error_id": error_id,
        "attempt_id": item["attempt_id"],
        "created_at": item.get("created_at", now()),
        "error_class": item["error_class"],
        "expected": item.get("expected", json.loads(attempt["expected_json"])),
        "observed": item.get("observed", json.loads(attempt["actual_json"])),
        "diagnosis_status": item.get("diagnosis_status", "unreviewed"),
        "candidate_cause": item.get("candidate_cause"),
        "working_solution_attempt_id": item.get("working_solution_attempt_id"),
    }
    report_hash = digest(record)
    connection.execute(
        "INSERT INTO error_reports VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            error_id,
            record["attempt_id"],
            record["created_at"],
            record["error_class"],
            canonical(record["expected"]),
            canonical(record["observed"]),
            record["diagnosis_status"],
            record["candidate_cause"],
            record["working_solution_attempt_id"],
            report_hash,
        ),
    )
    revision = append_error_revision(
        connection,
        error_id,
        record["diagnosis_status"],
        record["candidate_cause"],
        record["working_solution_attempt_id"],
        "initial error observation",
    )
    return {
        "error_id": error_id,
        "attempt_id": record["attempt_id"],
        "report_hash": report_hash,
        "revision": revision["revision"],
    }


def revise_error(
    connection: sqlite3.Connection, error_id: str, item: dict[str, Any]
) -> dict[str, Any]:
    item = redact(item)
    status = str(item["diagnosis_status"])
    if status == "resolved" and not item.get("working_solution_attempt_id"):
        raise ValueError("resolved_error_requires_working_solution_attempt")
    if item.get("working_solution_attempt_id"):
        exists = connection.execute(
            "SELECT attempt_id FROM command_attempts WHERE attempt_id=?",
            (item["working_solution_attempt_id"],),
        ).fetchone()
        if not exists:
            raise ValueError("working_solution_attempt_not_found")
    return append_error_revision(
        connection,
        error_id,
        status,
        item.get("candidate_cause"),
        item.get("working_solution_attempt_id"),
        item["reason"],
    )


def seed_sources(connection: sqlite3.Connection) -> dict[str, Any]:
    registry = read_json(ROOT / "registry/sources.json")
    imported = []
    for source in registry["seed_sources"]:
        source_id = str(source["id"])
        existing = connection.execute(
            "SELECT source_id FROM source_revisions WHERE source_id=? LIMIT 1",
            (source_id,),
        ).fetchone()
        if existing:
            continue
        imported.append(
            add_source(
                connection,
                {
                    "source_id": source_id,
                    "source_class": "source-registry",
                    "authority_tier": source["tier"],
                    "title": source_id,
                    "publisher": source["publisher"],
                    "locator": source["locator"],
                    "applicable_versions": {"strategy": source["version_strategy"]},
                    "content": None,
                    "content_hash": digest(source),
                    "complete": False,
                    "community_confirmation_required": int(source["tier"]) >= 4,
                },
            )
        )
    return {"seeded": len(imported), "sources": imported}


def seed_catalog(connection: sqlite3.Connection) -> dict[str, Any]:
    registry = read_json(ROOT / "registry/commands/bash-fedora.json")
    imported = []
    for command in registry["commands"]:
        command_id = str(command["id"])
        existing = connection.execute(
            "SELECT * FROM command_catalog_revisions WHERE command_id=? ORDER BY revision DESC LIMIT 1",
            (command_id,),
        ).fetchone()
        methods = command.get("docs", [])
        safe_arguments = command.get("safe_help", [])
        prohibited = ["sudo", "shell-control-operator", "untrusted-argument"]
        if existing and (
            existing["executable"] == command["executable"]
            and existing["domain"] == command["domain"]
            and bool(existing["mutates_host"]) == bool(command["mutates_host"])
            and bool(existing["privilege_possible"]) == bool(command["privilege_possible"])
            and json.loads(existing["documentation_methods_json"]) == methods
            and json.loads(existing["safe_argument_patterns_json"]) == safe_arguments
            and json.loads(existing["prohibited_patterns_json"]) == prohibited
            and existing["status"] == "active"
        ):
            continue
        revision, previous = next_revision(
            connection, "command_catalog_revisions", "command_id", command_id
        )
        record = {
            "command_id": command_id,
            "revision": revision,
            "executable": command["executable"],
            "domain": command["domain"],
            "mutates_host": bool(command["mutates_host"]),
            "privilege_possible": bool(command["privilege_possible"]),
            "documentation_methods": methods,
            "safe_argument_patterns": safe_arguments,
            "prohibited_patterns": prohibited,
            "status": "active",
            "previous_hash": previous,
        }
        record_hash = digest(record)
        connection.execute(
            "INSERT INTO command_catalog_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                command_id,
                revision,
                record["executable"],
                record["domain"],
                int(record["mutates_host"]),
                int(record["privilege_possible"]),
                canonical(record["documentation_methods"]),
                canonical(record["safe_argument_patterns"]),
                canonical(record["prohibited_patterns"]),
                "active",
                previous,
                record_hash,
            ),
        )
        imported.append(
            {"command_id": command_id, "revision": revision, "record_hash": record_hash}
        )
    return {"seeded": len(imported), "commands": imported}


def latest_lesson(connection: sqlite3.Connection, lesson_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM lesson_revisions WHERE lesson_id=? ORDER BY revision DESC LIMIT 1",
        (lesson_id,),
    ).fetchone()
    if not row:
        raise ValueError("lesson_not_found")
    return row


def append_lesson_revision(connection: sqlite3.Connection, item: dict[str, Any]) -> dict[str, Any]:
    item = redact(item)
    lesson_id = str(item.get("lesson_id") or uuid.uuid4())
    revision, previous = next_revision(connection, "lesson_revisions", "lesson_id", lesson_id)
    record = {
        "lesson_id": lesson_id,
        "revision": revision,
        "created_at": item.get("created_at", now()),
        "status": item.get("status", "draft"),
        "title": item["title"],
        "guidance": item["guidance"],
        "scope": "enrolled-workstation",
        "prerequisites": item.get("prerequisites", {}),
        "exclusions": item.get("exclusions", []),
        "validation": item.get("validation", []),
        "source_error_ids": item.get("source_error_ids", []),
        "success_threshold": int(item.get("success_threshold", 3)),
        "user_decision_id": item.get("user_decision_id"),
        "reason": item.get("reason", "new lesson"),
        "previous_hash": previous,
    }
    record_hash = digest(record)
    connection.execute(
        "INSERT INTO lesson_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            lesson_id,
            revision,
            record["created_at"],
            record["status"],
            record["title"],
            record["guidance"],
            record["scope"],
            canonical(record["prerequisites"]),
            canonical(record["exclusions"]),
            canonical(record["validation"]),
            canonical(record["source_error_ids"]),
            record["success_threshold"],
            record["user_decision_id"],
            record["reason"],
            previous,
            record_hash,
        ),
    )
    return {
        "lesson_id": lesson_id,
        "revision": revision,
        "status": record["status"],
        "record_hash": record_hash,
    }


def add_lesson_evidence(connection: sqlite3.Connection, item: dict[str, Any]) -> dict[str, Any]:
    latest_lesson(connection, str(item["lesson_id"]))
    attempt = connection.execute(
        "SELECT attempt_id FROM command_attempts WHERE attempt_id=?",
        (item["attempt_id"],),
    ).fetchone()
    if not attempt:
        raise ValueError("attempt_not_found")
    item = redact(item)
    record = {
        "evidence_id": str(item.get("evidence_id") or uuid.uuid4()),
        "lesson_id": item["lesson_id"],
        "attempt_id": item["attempt_id"],
        "recorded_at": item.get("recorded_at", now()),
        "evidence_type": item["evidence_type"],
        "prerequisites_match": bool(item.get("prerequisites_match", False)),
        "independently_verified": bool(item.get("independently_verified", False)),
        "details": item.get("details", {}),
    }
    record_hash = digest(record)
    connection.execute(
        "INSERT INTO lesson_evidence VALUES (?,?,?,?,?,?,?,?,?)",
        (
            record["evidence_id"],
            record["lesson_id"],
            record["attempt_id"],
            record["recorded_at"],
            record["evidence_type"],
            int(record["prerequisites_match"]),
            int(record["independently_verified"]),
            canonical(record["details"]),
            record_hash,
        ),
    )
    return {"evidence_id": record["evidence_id"], "record_hash": record_hash}


def revise_lesson(
    connection: sqlite3.Connection,
    lesson_id: str,
    status: str,
    reason: str,
    decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous = latest_lesson(connection, lesson_id)
    if status == "candidate":
        if previous["status"] not in {"draft", "suspended"}:
            raise ValueError("lesson_not_candidate_eligible")
        successes = connection.execute(
            """SELECT COUNT(DISTINCT attempt_id) FROM lesson_evidence
               WHERE lesson_id=? AND evidence_type='matching-success'
               AND prerequisites_match=1 AND independently_verified=1""",
            (lesson_id,),
        ).fetchone()[0]
        conflicts = connection.execute(
            "SELECT COUNT(*) FROM lesson_evidence WHERE lesson_id=? AND evidence_type IN ('conflict','version-change','unexpected-effect')",
            (lesson_id,),
        ).fetchone()[0]
        if successes < previous["success_threshold"] or conflicts:
            raise ValueError("candidate_threshold_or_conflict_check_failed")
    user_decision_id = None
    if status == "approved":
        if previous["status"] != "candidate":
            raise ValueError("only_candidate_can_be_approved")
        if (
            not decision
            or decision.get("decision") != "approved"
            or decision.get("approver") != "user"
        ):
            raise ValueError("explicit_user_approval_required")
        user_decision_id = str(decision.get("decision_id") or uuid.uuid4())
    return append_lesson_revision(
        connection,
        {
            "lesson_id": lesson_id,
            "status": status,
            "title": previous["title"],
            "guidance": previous["guidance"],
            "prerequisites": json.loads(previous["prerequisites_json"]),
            "exclusions": json.loads(previous["exclusions_json"]),
            "validation": json.loads(previous["validation_json"]),
            "source_error_ids": json.loads(previous["source_error_ids_json"]),
            "success_threshold": previous["success_threshold"],
            "user_decision_id": user_decision_id,
            "reason": reason,
        },
    )


def add_decision(connection: sqlite3.Connection, item: dict[str, Any]) -> dict[str, Any]:
    item = redact(item)
    record = {
        "decision_id": str(item.get("decision_id") or uuid.uuid4()),
        "created_at": item.get("created_at", now()),
        "objective": item["objective"],
        "facts": item.get("facts", []),
        "sources": item.get("sources", []),
        "alternatives": item.get("alternatives", []),
        "selected_action": item.get("selected_action", {}),
        "risk": item.get("risk", {}),
        "validation": item.get("validation", {}),
        "outcome": item.get("outcome", {}),
    }
    record_hash = digest(record)
    connection.execute(
        "INSERT INTO decision_records VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            record["decision_id"],
            record["created_at"],
            record["objective"],
            canonical(record["facts"]),
            canonical(record["sources"]),
            canonical(record["alternatives"]),
            canonical(record["selected_action"]),
            canonical(record["risk"]),
            canonical(record["validation"]),
            canonical(record["outcome"]),
            record_hash,
        ),
    )
    return {"decision_id": record["decision_id"], "record_hash": record_hash}


def add_approval(connection: sqlite3.Connection, item: dict[str, Any]) -> dict[str, Any]:
    item = redact(item)
    required = (
        "id",
        "scope",
        "scope_reference",
        "action_digest",
        "state_digest",
        "approver",
        "issued_at",
        "expires_at",
        "targets",
        "decision",
        "nonce",
    )
    missing = [field for field in required if field not in item]
    if missing:
        raise ValueError(f"approval_missing_fields:{','.join(missing)}")
    if item["scope"] not in {"command", "procedure", "transaction"}:
        raise ValueError("invalid_approval_scope")
    if item["approver"] != "user":
        raise ValueError("user_approval_required")
    if item["decision"] not in {"approved", "denied", "revoked"}:
        raise ValueError("invalid_approval_decision")
    record = {
        "approval_id": item["id"],
        "scope": item["scope"],
        "issued_at": item["issued_at"],
        "expires_at": item["expires_at"],
        "approver": item["approver"],
        "decision": item["decision"],
        "action_digest": item["action_digest"],
        "state_digest": item["state_digest"],
        "targets": item["targets"],
        "nonce": item["nonce"],
        "scope_reference": item["scope_reference"],
        "approval": item,
    }
    record_hash = digest(record)
    connection.execute(
        "INSERT INTO approval_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            record["approval_id"],
            record["scope"],
            record["issued_at"],
            record["expires_at"],
            record["approver"],
            record["decision"],
            record["action_digest"],
            record["state_digest"],
            canonical(record["targets"]),
            record["nonce"],
            record["scope_reference"],
            canonical(record["approval"]),
            record_hash,
        ),
    )
    return {
        "approval_id": record["approval_id"],
        "scope": record["scope"],
        "record_hash": record_hash,
    }


def consume_approval(
    connection: sqlite3.Connection, approval_id: str, context: dict[str, Any]
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT approval_json FROM approval_records WHERE approval_id=?", (approval_id,)
    ).fetchone()
    if not row:
        raise ValueError("approval_not_found")
    approval = json.loads(row[0])
    prior = connection.execute(
        "SELECT COUNT(*) FROM approval_uses WHERE approval_id=? AND result='consumed'",
        (approval_id,),
    ).fetchone()[0]
    if prior:
        valid = False
        reasons = ["approval_already_consumed"]
    else:
        control_spec = importlib.util.spec_from_file_location(
            "jarvisctl_for_approval", ROOT / "scripts/jarvisctl.py"
        )
        control = importlib.util.module_from_spec(control_spec)
        assert control_spec.loader
        control_spec.loader.exec_module(control)
        verification = control.verify_approval(redact(context), approval)
        valid = bool(verification["valid"])
        reasons = verification["reasons"]
    record = {
        "use_id": str(uuid.uuid4()),
        "approval_id": approval_id,
        "used_at": now(),
        "action_digest": digest(redact(context)),
        "result": "consumed" if valid else "rejected",
        "reason": "verified" if valid else ",".join(reasons),
    }
    record_hash = digest(record)
    connection.execute(
        "INSERT INTO approval_uses VALUES (?,?,?,?,?,?,?)",
        (
            record["use_id"],
            approval_id,
            record["used_at"],
            record["action_digest"],
            record["result"],
            record["reason"],
            record_hash,
        ),
    )
    return {
        "valid": valid,
        "reasons": reasons,
        "use_id": record["use_id"],
        "record_hash": record_hash,
    }


def import_inventory(connection: sqlite3.Connection, item: dict[str, Any]) -> dict[str, Any]:
    supported_collectors = {
        "fedora-readonly-inventory",
        "lighting-tier0-readonly",
        "lighting-tier1-platform-readonly",
        "lighting-tier2-wmi-binding-readonly",
        "lighting-tier3-connector-association-readonly",
    }
    if item.get("schema_version") != 1 or item.get("collector") not in supported_collectors:
        raise ValueError("unsupported_inventory")
    attempts = []
    for attempt in item.get("attempts", []):
        attempts.append(add_attempt(connection, attempt))
    facts = []
    for fact in item.get("facts", []):
        facts.append(add_fact(connection, fact))
    return {"attempts": attempts, "facts": facts}


def import_docs(connection: sqlite3.Connection, path: Path) -> dict[str, Any]:
    imported = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            imported.append(add_source(connection, json.loads(line)))
    return {"imported": len(imported), "sources": imported}


def query(connection: sqlite3.Connection, kind: str, text: str, limit: int) -> list[dict[str, Any]]:
    tables = {
        "facts": ("current_facts", "fact_key || ' ' || value_json"),
        "sources": (
            "source_revisions",
            "title || ' ' || publisher || ' ' || locator || ' ' || COALESCE(content_text,'')",
        ),
        "attempts": (
            "command_attempts",
            "executable || ' ' || purpose || ' ' || COALESCE(output_excerpt,'')",
        ),
        "errors": (
            "current_error_reports",
            "error_class || ' ' || COALESCE(candidate_cause,'') || ' ' || reason",
        ),
        "lessons": ("current_lessons", "title || ' ' || guidance || ' ' || reason"),
        "decisions": ("decision_records", "objective || ' ' || selected_action_json"),
    }
    if kind not in tables:
        raise ValueError("unsupported_query_kind")
    table, columns = tables[kind]
    rows = connection.execute(
        f"SELECT * FROM {table} WHERE lower({columns}) LIKE lower(?) LIMIT ?",
        (f"%{text}%", limit),
    ).fetchall()
    return [dict(row) for row in rows]


def verify(connection: sqlite3.Connection) -> dict[str, Any]:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = [dict(row) for row in connection.execute("PRAGMA foreign_key_check").fetchall()]
    chain_errors: list[str] = []
    checked = 0
    for table, id_column in (
        ("source_revisions", "source_id"),
        ("fact_revisions", "fact_id"),
        ("command_catalog_revisions", "command_id"),
        ("lesson_revisions", "lesson_id"),
        ("error_report_revisions", "error_id"),
    ):
        previous_by_id: dict[str, str] = {}
        for row in connection.execute(
            f"SELECT {id_column},revision,previous_hash,record_hash FROM {table} ORDER BY {id_column},revision"
        ):
            checked += 1
            object_id = str(row[id_column])
            expected_previous = previous_by_id.get(object_id, ZERO_HASH)
            if row["previous_hash"] != expected_previous:
                chain_errors.append(f"{table}:{object_id}:{row['revision']}:previous_hash")
            if not re.fullmatch(r"[0-9a-f]{64}", row["record_hash"]):
                chain_errors.append(f"{table}:{object_id}:{row['revision']}:record_hash_format")
            previous_by_id[object_id] = str(row["record_hash"])
    counts = {}
    for table in (
        "source_revisions",
        "fact_revisions",
        "current_facts",
        "command_catalog_revisions",
        "command_attempts",
        "error_reports",
        "error_report_revisions",
        "lesson_revisions",
        "lesson_evidence",
        "decision_records",
        "approval_records",
        "approval_uses",
    ):
        counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    return {
        "valid": integrity == "ok" and not foreign_keys and not chain_errors,
        "integrity": integrity,
        "foreign_key_errors": foreign_keys,
        "revision_chain_errors": chain_errors,
        "revision_links_checked": checked,
        "counts": counts,
    }


def output(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("seed-sources")
    sub.add_parser("seed-catalog")
    for name in (
        "add-source",
        "add-fact",
        "add-attempt",
        "add-error-report",
        "add-lesson",
        "add-lesson-evidence",
        "add-decision",
        "add-approval",
        "import-inventory",
    ):
        command = sub.add_parser(name)
        command.add_argument("input", type=Path)
    docs = sub.add_parser("import-docs")
    docs.add_argument("input", type=Path)
    candidate = sub.add_parser("promote-candidate")
    candidate.add_argument("lesson_id")
    approve = sub.add_parser("approve-lesson")
    approve.add_argument("lesson_id")
    approve.add_argument("decision", type=Path)
    suspend = sub.add_parser("suspend-lesson")
    suspend.add_argument("lesson_id")
    suspend.add_argument("--reason", required=True)
    revise = sub.add_parser("revise-error")
    revise.add_argument("error_id")
    revise.add_argument("input", type=Path)
    consume = sub.add_parser("consume-approval")
    consume.add_argument("approval_id")
    consume.add_argument("context", type=Path)
    search = sub.add_parser("query")
    search.add_argument(
        "kind",
        choices=("facts", "sources", "attempts", "errors", "lessons", "decisions"),
    )
    search.add_argument("text")
    search.add_argument("--limit", type=int, default=20)
    sub.add_parser("verify")
    args = parser.parse_args()

    init_database(args.db)
    with closing(connect(args.db)) as connection, connection:
        if args.command == "init":
            result = {
                "initialized": True,
                "database": str(args.db),
                "schema_version": 1,
            }
        elif args.command == "seed-sources":
            result = seed_sources(connection)
        elif args.command == "seed-catalog":
            result = seed_catalog(connection)
        elif args.command == "add-source":
            result = add_source(connection, read_json(args.input))
        elif args.command == "add-fact":
            result = add_fact(connection, read_json(args.input))
        elif args.command == "add-attempt":
            result = add_attempt(connection, read_json(args.input))
        elif args.command == "add-error-report":
            result = add_error_report(connection, read_json(args.input))
        elif args.command == "add-lesson":
            result = append_lesson_revision(connection, read_json(args.input))
        elif args.command == "add-lesson-evidence":
            result = add_lesson_evidence(connection, read_json(args.input))
        elif args.command == "add-decision":
            result = add_decision(connection, read_json(args.input))
        elif args.command == "add-approval":
            result = add_approval(connection, read_json(args.input))
        elif args.command == "import-inventory":
            result = import_inventory(connection, read_json(args.input))
        elif args.command == "import-docs":
            result = import_docs(connection, args.input)
        elif args.command == "promote-candidate":
            result = revise_lesson(
                connection,
                args.lesson_id,
                "candidate",
                "automated evidence threshold met",
            )
        elif args.command == "approve-lesson":
            result = revise_lesson(
                connection,
                args.lesson_id,
                "approved",
                "explicit user approval",
                read_json(args.decision),
            )
        elif args.command == "suspend-lesson":
            result = revise_lesson(connection, args.lesson_id, "suspended", args.reason)
        elif args.command == "revise-error":
            result = revise_error(connection, args.error_id, read_json(args.input))
        elif args.command == "consume-approval":
            result = consume_approval(connection, args.approval_id, read_json(args.context))
        elif args.command == "query":
            result = {"results": query(connection, args.kind, args.text, args.limit)}
        elif args.command == "verify":
            result = verify(connection)
        else:
            raise ValueError("unsupported command")
        output(result)
        return 0 if not isinstance(result, dict) or result.get("valid", True) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
