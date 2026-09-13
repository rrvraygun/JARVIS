# Operating model

## Control objects

- Capability: what the agent is allowed to attempt.
- Procedure: versioned steps, inputs, gates, validation, and rollback.
- Action context: exact proposed operation and risk attributes.
- Policy decision: allow, approval required, or deny with reasons.
- Approval: actor-bound, target-bound, digest-bound, and expiring authorization.
- State record: timestamped observation with coverage and freshness.
- Audit event: redacted append-only record linked by hashes.

## Lifecycle

`request -> classify -> collect evidence -> policy -> approval -> preflight ->
execute -> validate -> rollback if needed -> state update -> audit -> review`

Use subagents only for independent evidence collection or review. The primary
agent owns authorization, reconciliation, final validation, and audit closure.
Hooks enforce lifecycle checks but do not replace sandboxing, approvals, OS
permissions, or procedure validation. Scheduled automation may observe and
report; unattended mutation requires a separately reviewed machine policy.
