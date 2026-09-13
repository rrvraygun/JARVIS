#!/usr/bin/env python3
import datetime as dt
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("jarvisctl", ROOT / "scripts/jarvisctl.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)
fixtures = ROOT / "tests/fixtures"

read_only = json.loads((fixtures / "read-only.json").read_text())
update = json.loads((fixtures / "update.json").read_text())
forbidden = json.loads((fixtures / "forbidden.json").read_text())
assert module.policy(read_only)["decision"] == "allowed"
assert module.policy(update)["decision"] == "approval_required"
assert module.policy(forbidden)["decision"] == "denied"

procedure_scope = dict(update)
procedure_scope["approval_scope"] = "procedure"
assert module.policy(procedure_scope)["decision"] == "denied"

missing_recovery = dict(update)
missing_recovery.pop("rollback")
assert "rollback_missing" in module.policy(missing_recovery)["reasons"]

approval_context = {
    **update,
    "command_id": "dnf-update-1",
    "executable": "/usr/bin/dnf",
    "argv": ["upgrade"],
    "state_digest": "a" * 64,
    "approval_scope": "command",
}
fixed_now = dt.datetime(2026, 8, 5, 12, 0, tzinfo=dt.timezone.utc)
approval = {
    "id": "approval-1",
    "scope": "command",
    "scope_reference": "dnf-update-1",
    "action_digest": module.action_digest(approval_context),
    "state_digest": "a" * 64,
    "approver": "user",
    "issued_at": "2026-08-05T11:59:00Z",
    "expires_at": "2026-08-05T12:05:00Z",
    "targets": ["fixture-package"],
    "decision": "approved",
    "nonce": "fixture_nonce_123456",
    "consumed": False,
}
assert module.verify_approval(approval_context, approval, fixed_now)["valid"]
replayed = dict(approval)
replayed["consumed"] = True
assert (
    "approval_already_consumed"
    in module.verify_approval(approval_context, replayed, fixed_now)["reasons"]
)

with tempfile.TemporaryDirectory() as directory:
    store = Path(directory)
    module.init_store(store)
    ledger = store / "audit/events.jsonl"
    first = module.append_event(fixtures / "event.json", ledger)
    assert first["details"]["password"] == "[REDACTED]"
    second = module.append_event(fixtures / "event.json", ledger)
    assert second["previous_hash"] == first["event_hash"]
    valid, count, _ = module.verify_ledger(ledger)
    assert valid and count == 2
    lines = ledger.read_text().splitlines()
    tampered = json.loads(lines[0])
    tampered["status"] = "tampered"
    lines[0] = json.dumps(tampered, separators=(",", ":"), sort_keys=True)
    ledger.write_text("\n".join(lines) + "\n")
    assert module.verify_ledger(ledger)[0] is False
    try:
        module.append_event(fixtures / "event.json", ledger)
    except ValueError as exc:
        assert "integrity" in str(exc)
    else:
        raise AssertionError("tampered ledger accepted a new event")

print("control-plane tests passed")
