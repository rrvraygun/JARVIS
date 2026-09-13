#!/usr/bin/env python3
"""Deterministic control-plane utilities; never executes host administration."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ZERO_HASH = "0" * 64
SENSITIVE = re.compile(
    r"(?i)(password|passwd|secret|token|private[_-]?key|api[_-]?key|credential|cookie|authorization)"
)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(k): "[REDACTED]" if SENSITIVE.search(str(k)) else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def capabilities() -> dict[str, dict[str, Any]]:
    data = load(ROOT / "registry/capabilities.json")
    return {item["id"]: item for item in data["capabilities"]}


def procedures() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted((ROOT / "registry/procedures").glob("*.json")):
        item = load(path)
        key = f"{item['id']}@{item['version']}"
        if key in result:
            raise ValueError(f"duplicate procedure: {key}")
        result[key] = item
    return result


def actions() -> dict[str, dict[str, Any]]:
    data = load(ROOT / "registry/actions.json")
    result = {item["id"]: item for item in data["actions"]}
    if len(result) != len(data["actions"]):
        raise ValueError("duplicate action id")
    return result


def action_digest(context: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(redact(context))).hexdigest()


def policy(context: dict[str, Any]) -> dict[str, Any]:
    registry = capabilities()
    rules = load(ROOT / "policy/policy.json")
    cap_id = context.get("capability")
    reasons: list[str] = []
    required: list[str] = []
    independent_review = False

    if cap_id not in registry:
        return {
            "decision": "denied",
            "reasons": ["capability_not_registered"],
            "action_digest": action_digest(context),
        }
    cap = registry[cap_id]
    enabled = bool(context.get("capability_enabled", cap["default_enabled"]))
    if not enabled:
        return {
            "decision": "denied",
            "reasons": ["capability_disabled"],
            "action_digest": action_digest(context),
        }
    requested_level = int(context.get("requested_level", 1))
    if requested_level > int(cap["max_level"]):
        return {
            "decision": "denied",
            "reasons": ["capability_level_exceeded"],
            "action_digest": action_digest(context),
        }

    prohibited = set(context.get("prohibited_traits", [])) & set(rules["always_deny"])
    if prohibited:
        return {
            "decision": "denied",
            "reasons": sorted(prohibited),
            "action_digest": action_digest(context),
        }

    approval_scope = str(context.get("approval_scope", "command"))
    scope_policy = rules.get("approval_scopes", {}).get(approval_scope)
    if not scope_policy or not scope_policy.get("defined"):
        return {
            "decision": "denied",
            "reasons": ["approval_scope_not_defined"],
            "action_digest": action_digest(context),
        }
    if (context.get("mutation") or context.get("privilege")) and not scope_policy.get(
        "execution_enabled"
    ):
        return {
            "decision": "denied",
            "reasons": ["approval_scope_defined_but_disabled"],
            "action_digest": action_digest(context),
        }

    if context.get("mutation"):
        required.append("host_mutation")
    for field, label in (
        ("privilege", "privilege"),
        ("external_effect", "external_side_effect"),
        ("downtime", "downtime"),
        ("destructive", "destructive"),
        ("self_update", "self_update"),
    ):
        if context.get(field):
            required.append(label)
    risk_score = int(
        context.get(
            "risk_score",
            {"low": 0, "medium": 2, "high": 3, "critical": 4}.get(context.get("risk"), 4),
        )
    )
    if risk_score >= 3 or context.get("irreversible"):
        independent_review = True
    if context.get("mutation") and rules.get("mutation_requires_independent_review", True):
        independent_review = True
    if context.get("self_update"):
        independent_review = True

    max_age = rules.get("state_max_age_seconds", {}).get(cap_id)
    age = context.get("state_age_seconds")
    if max_age is not None and (age is None or int(age) > int(max_age)):
        reasons.append("state_stale_or_missing")
    rollback_threshold = int(rules.get("mutation_rollback_required_at_or_above", 0))
    if (
        context.get("mutation")
        and risk_score >= rollback_threshold
        and not context.get("rollback")
        and not context.get("irreversible")
    ):
        reasons.append("rollback_missing")
    if (
        context.get("dry_run_supported")
        and rules.get("dry_run_required_when_supported")
        and not context.get("dry_run")
    ):
        reasons.append("dry_run_missing")
    if not context.get("validation"):
        reasons.append("validation_missing")

    if reasons:
        return {
            "decision": "denied",
            "reasons": reasons,
            "action_digest": action_digest(context),
        }
    if required:
        return {
            "decision": "approval_required",
            "reasons": sorted(set(required)),
            "independent_review_required": independent_review,
            "approval_scope": approval_scope,
            "attempt_limit": int(rules.get("attempt_limit", 1)),
            "action_digest": action_digest(context),
        }
    return {
        "decision": "allowed",
        "reasons": [],
        "independent_review_required": False,
        "approval_scope": approval_scope,
        "attempt_limit": int(rules.get("attempt_limit", 1)),
        "action_digest": action_digest(context),
    }


def init_store(path: Path) -> None:
    for rel in (
        "audit",
        "approvals",
        "state/current",
        "state/snapshots",
        "knowledge",
        "documentation",
        "reports",
        "locks",
        "exports",
    ):
        (path / rel).mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)


def last_hash(ledger: Path) -> str:
    if not ledger.exists() or not ledger.stat().st_size:
        return ZERO_HASH
    last = ledger.read_text(encoding="utf-8").splitlines()[-1]
    return json.loads(last)["event_hash"]


def append_event(event_path: Path, ledger: Path) -> dict[str, Any]:
    event = redact(load(event_path))
    for field in (
        "schema_version",
        "id",
        "timestamp",
        "event_type",
        "actor",
        "status",
        "details",
    ):
        if field not in event:
            raise ValueError(f"missing event field: {field}")
    ledger.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with ledger.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        lines = handle.read().splitlines()
        valid, _, previous = _verify_ledger_lines(lines)
        if not valid:
            fcntl.flock(handle, fcntl.LOCK_UN)
            raise ValueError("audit ledger integrity verification failed before append")
        event.pop("event_hash", None)
        event["previous_hash"] = previous
        event["event_hash"] = hashlib.sha256(previous.encode() + canonical(event)).hexdigest()
        handle.seek(0, os.SEEK_END)
        handle.write(canonical(event).decode() + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle, fcntl.LOCK_UN)
    os.chmod(ledger, 0o600)
    return event


def _verify_ledger_lines(lines: list[str]) -> tuple[bool, int, str]:
    previous = ZERO_HASH
    count = 0
    for line in lines:
        try:
            event = json.loads(line)
            supplied = event.pop("event_hash")
        except (AttributeError, KeyError, json.JSONDecodeError):
            return False, count, "invalid_record"
        if event.get("previous_hash") != previous:
            return False, count, "previous_hash_mismatch"
        expected = hashlib.sha256(previous.encode() + canonical(event)).hexdigest()
        if supplied != expected:
            return False, count, "event_hash_mismatch"
        previous = supplied
        count += 1
    return True, count, previous


def verify_ledger(ledger: Path) -> tuple[bool, int, str]:
    try:
        return _verify_ledger_lines(ledger.read_text(encoding="utf-8").splitlines())
    except OSError:
        return False, 0, "ledger_unreadable"


def validate_bundle() -> list[str]:
    errors: list[str] = []
    caps = capabilities()
    registered_procedures: dict[str, dict[str, Any]] = {}
    for path in sorted((ROOT / "registry/procedures").glob("*.json")):
        item = load(path)
        if item.get("capability") not in caps and item.get("capability") != "parameterized":
            errors.append(f"{path.name}: unknown capability")
        key = f"{item.get('id')}@{item.get('version')}"
        if key in registered_procedures:
            errors.append(f"{path.name}: duplicate procedure {key}")
        registered_procedures[key] = item
    try:
        registered_actions = actions()
    except (KeyError, ValueError) as exc:
        errors.append(f"actions.json: {exc}")
        registered_actions = {}
    for action_id, item in registered_actions.items():
        if item.get("capability") not in caps:
            errors.append(f"{action_id}: unknown capability")
        if item.get("procedure") not in registered_procedures:
            errors.append(f"{action_id}: unknown procedure")
        if item.get("mutates_host") and item.get("availability") == "enabled":
            errors.append(
                f"{action_id}: mutating action cannot be enabled before an executor exists"
            )
        if item.get("availability") == "unavailable" and not item.get("unavailable_reason"):
            errors.append(f"{action_id}: unavailable action requires a reason")
    for path in sorted((ROOT / "registry/collector-plans").glob("*.json")):
        item = load(path)
        if item.get("execution_enabled") is not False:
            errors.append(f"{path.name}: prepared collector plans must be non-executable")
    for path in (ROOT / "schemas").glob("*.json"):
        try:
            load(path)
        except Exception as exc:  # validation command should report all failures
            errors.append(f"{path.name}: {exc}")
    return errors


def verify_approval(
    context: dict[str, Any], approval: dict[str, Any], now: dt.datetime | None = None
) -> dict[str, Any]:
    reasons: list[str] = []
    rules = load(ROOT / "policy/policy.json")
    if approval.get("decision") != "approved":
        reasons.append("not_approved")
    if approval.get("approver") != "user":
        reasons.append("user_approval_required")
    if approval.get("action_digest") != action_digest(context):
        reasons.append("action_digest_mismatch")
    if approval.get("state_digest") != context.get("state_digest"):
        reasons.append("state_digest_mismatch")
    if sorted(approval.get("targets", [])) != sorted(context.get("targets", [])):
        reasons.append("targets_mismatch")
    scope = str(approval.get("scope", ""))
    expected_scope = str(context.get("approval_scope", "command"))
    if scope != expected_scope:
        reasons.append("approval_scope_mismatch")
    scope_policy = rules.get("approval_scopes", {}).get(scope)
    if not scope_policy or not scope_policy.get("execution_enabled"):
        reasons.append("approval_scope_not_enabled")
    reference_fields = {
        "command": "command_id",
        "procedure": "procedure",
        "transaction": "transaction_id",
    }
    reference_field = reference_fields.get(scope)
    if not reference_field or approval.get("scope_reference") != context.get(reference_field):
        reasons.append("scope_reference_mismatch")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", str(approval.get("nonce", ""))):
        reasons.append("invalid_nonce")
    if approval.get("consumed"):
        reasons.append("approval_already_consumed")
    try:
        issued = dt.datetime.fromisoformat(str(approval["issued_at"]).replace("Z", "+00:00"))
        expires = dt.datetime.fromisoformat(str(approval["expires_at"]).replace("Z", "+00:00"))
        current = now or dt.datetime.now(dt.timezone.utc)
        if issued > current + dt.timedelta(minutes=1):
            reasons.append("approval_issued_in_future")
        if expires <= issued:
            reasons.append("invalid_approval_interval")
        if expires <= current:
            reasons.append("approval_expired")
    except (KeyError, ValueError, TypeError):
        reasons.append("invalid_expiry")
    return {
        "valid": not reasons,
        "reasons": reasons,
        "action_digest": action_digest(context),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p_policy = sub.add_parser("policy")
    p_policy.add_argument("context", type=Path)
    p_digest = sub.add_parser("digest")
    p_digest.add_argument("context", type=Path)
    p_init = sub.add_parser("init-store")
    p_init.add_argument("path", type=Path)
    p_append = sub.add_parser("append-event")
    p_append.add_argument("event", type=Path)
    p_append.add_argument("ledger", type=Path)
    p_verify = sub.add_parser("verify-ledger")
    p_verify.add_argument("ledger", type=Path)
    p_approval = sub.add_parser("verify-approval")
    p_approval.add_argument("context", type=Path)
    p_approval.add_argument("approval", type=Path)
    sub.add_parser("validate")
    args = parser.parse_args()

    if args.command == "policy":
        print(json.dumps(policy(load(args.context)), indent=2, sort_keys=True))
    elif args.command == "digest":
        print(action_digest(load(args.context)))
    elif args.command == "init-store":
        init_store(args.path)
    elif args.command == "append-event":
        print(json.dumps(append_event(args.event, args.ledger), indent=2, sort_keys=True))
    elif args.command == "verify-ledger":
        valid, count, tail = verify_ledger(args.ledger)
        print(json.dumps({"valid": valid, "events": count, "tail_hash": tail}, indent=2))
        return 0 if valid else 1
    elif args.command == "verify-approval":
        result = verify_approval(load(args.context), load(args.approval))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["valid"] else 1
    elif args.command == "validate":
        errors = validate_bundle()
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
        return 0 if not errors else 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
