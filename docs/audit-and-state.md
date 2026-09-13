# Audit and state design

## Layout

```text
runtime/
  state/current/          redacted latest views
  state/snapshots/        immutable-by-convention timestamped snapshots
  state/baselines/        comparable health and performance baselines
  audit/events.jsonl      append-only event stream
  audit/manifests/        hashes covering stored artifacts
  reports/                human-readable summaries
  knowledge/knowledge.db  versioned structured facts and lessons
  documentation/local.jsonl  bounded local documentation import
  exports/                remote append-only receipts when configured
```

Every record includes schema version, UTC timestamp, hostname pseudonym or
approved identifier, collector version, coverage, privilege used, redactions,
source command, exit status, and evidence path. Change events additionally link
the objective, risk, approval, before/after snapshots, exact targets, validation,
rollback, and residual risk.

Allowlist collected fields. Never persist secret values, full environment dumps,
private keys, authentication databases, browser data, or unrestricted command
output. Treat audit text as sensitive. Use restrictive permissions, retention,
rotation, backups, and integrity manifests. Local hashes reveal accidental or
unsophisticated alteration but are not protection against a privileged attacker;
high-assurance deployments need signed remote append-only storage.

The TUI journal at `runtime/tui/events.jsonl` is scanned and hash-verified once
when an `EventJournal` instance first loads it. Its cached head binds file
identity, size/change evidence, verified byte offset, sequence, last hash, and
idempotency keys. Each later append validates only a cooperating writer's new
suffix under the file lock; replacement, truncation, or in-place-change
evidence forces a full scan. `verify()` always performs an independent full
chain scan. Appends remain mode `0600`, locked, flushed, and fsynced; this does
not rotate, truncate, rewrite, or delete the existing journal.

Streaming App Server deltas are accumulated only as bounded in-memory counts,
character/byte totals, sanitization flags, and a rolling digest. One summary is
written at authoritative item completion or terminal cleanup. Raw delta text,
preflight output, private reasoning, filesystem results, path/query text, and
directory listings are not journal fields.

Active Conversation context synchronization journals only entry/character
counts, attempt count, status, an error category when applicable, and a digest
of already-sanitized entry bindings. The quoted context payload is not copied
into this journal. Sanitized user-visible local filesystem results are retained in bounded conversation JSON; raw filesystem output remains excluded from the audit journal. When a later agent request sends active
context through Codex App Server `thread/inject_items`, Codex retention applies
outside JARVIS's local retention boundary.

Local filesystem execution is reserved once by task and immutable plan digest
before traversal begins, so duplicate dispatch cannot repeat an operation.
Filesystem admissions require both plan and target bindings; fixed registry
observations use a distinct registered-local-read authority.

Mutation reservations are likewise one-shot. Filesystem-mutation records omit
paths, names, content, Trash destinations, and rendered output; they contain
only typed operation, categorized target, status, duration, error/rollback
flags, and binding digests. Package records omit preview text and package names
from the TUI journal and retain only operation, counts, status, attempt count,
and plan/review/preview digests. The root helper's owner-specific recovery
record is a separate protected operational artifact, never a reusable approval.

Restricted and secret records are rejected until encrypted storage is
implemented and explicitly unlocked by the user. Command attempts create error
observations for failures and unexpected results. Knowledge revisions never
replace security audit events.
