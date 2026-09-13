---
name: jarvis-control-plane
description: Govern system-administration requests through registered capabilities, procedures, deterministic policy decisions, explicit approvals, state freshness, validation, rollback, redaction, and hash-chained audit events. Use whenever Codex plans, delegates, executes, monitors, records, or reviews inventory, health, benchmark, maintenance, update, repair, security, backup, recovery, or agent self-update work.
---

# Jarvis control plane

1. Read [operating-model.md](references/operating-model.md).
2. Classify the request to one capability and procedure. If none matches, stop;
   do not invent authority.
   Use `list_actions` and `get_action` for catalog discovery. These tools expose
   metadata only and never authorize or execute the selected action.
3. Create an action context containing targets, mutation, privilege, network,
   external effects, downtime, destructiveness, reversibility, evidence,
   validation, rollback, and requested capability level.
4. Run `scripts/jarvisctl.py policy <context.json>`. Treat `denied` as final.
5. For `approval_required`, generate an approval request and wait for an approval
   matching the action digest, targets, scope, expiry, and actor.
6. Re-evaluate immediately before execution. Reject stale state, changed targets,
   expired approval, missing recovery, or widened scope.
7. Execute only through the registered procedure and least-capable tool.
8. Validate outcome and invariants. Roll back when the procedure requires it.
9. Redact first, then append a ledger event. Never rewrite previous events.
10. Query version-matched system knowledge before selecting command syntax. Run
    a command at most once; record failure or unexpected output before diagnosis.
11. Treat repeated success as lesson evidence only. Automation may create a
    promotion candidate, but only the user may activate a lesson.

Natural-language permission never overrides deterministic denial, missing
capability registration, or an approval whose digest does not match.

The command approval scope is the only executable scope initially. Procedure
and transaction scopes are represented for future policy changes but fail
closed. Never persist private chain-of-thought; record a concise decision
summary instead.
