# Approval-gated TUI mutation executors

**Current contract:** 2026-08-27

This document defines the current mutation boundary that complements the
approval-free bounded reader in `host-inspection-executor.md`. It does not turn
the TUI into a shell and does not grant standing host authority.

## Product behavior

Natural-language tasks use one broker pipeline in this order:

1. capture and render the pending user entry;
2. attempt deterministic bounded read planning;
3. attempt deterministic exact filesystem-mutation planning;
4. retain deterministic exact package roots as a candidate, then use one typed
   agent-planning preflight for package clarification/confirmation;
5. use one typed model preflight when no deterministic grammar matches;
6. route selected Power Expert requests directly to the read-only agent workflow, where
   typed Power MCP tools own observation, drafting, validation, and approval
   staging.

Exact reads remain approval-free and Python-only. Every mutation waits for a
fresh, visible, one-use decision. Decline and cancel grant no authority, perform
no write, and restore Send. No approval is queued, merged, persisted as a
standing grant, or replayed.

The model path remains useful for requests outside the deliberately small
deterministic grammar. Typed admission may grant a current-user agent turn, but
not mutation itself. Agent turns are read-only. Registered operations cross the graphical exact-review boundary; generic command/file approval cannot grant execution. See `governed-operations.md` for the staged contract.
Root work is unavailable through arbitrary Bash; it must use a registered
Polkit helper.

## Current-user filesystem mutations

`local_mutation.py` recognizes conservative English and Spanish forms for:

- creating one new directory;
- creating one new empty UTF-8 text file; and
- moving one existing current-user-owned regular file or directory to the
  current user's freedesktop Trash.

It accepts XDG Desktop/Escritorio, Documents/Documentos, and
Downloads/Descargas aliases, the workspace/project alias, and exact absolute
paths. XDG configuration is parsed as data and never sourced. The target must
be writable by the current user and must not be ambiguous, hidden, sensitive,
special, protected, or reached through a directory symlink. Create operations
never overwrite. Deletion means a same-filesystem move to Trash, never unlink
or recursive removal.

An immutable plan binds operation, target and parent identity, content digest
and size when applicable, rollback wording, risk, and a stable plan digest. A
separate deterministic review binds its own digest. The modal mints an
in-memory approval only after an affirmative click. Execution reserves the
plan once, consumes the approval once, rechecks policy and descriptor identity,
uses Python filesystem APIs in a worker thread, fsyncs material writes, and
verifies the immediate postcondition. A Trash operation repeats the approved
device/inode/type comparison at the last pathname lookup immediately before
the atomic rename. It never uses Bash or user-built argv.

The event journal receives operation type, target category, counts/status,
duration, error code, and digests. It never receives path text, filenames,
created content, Trash names, or rendered output.

## Exact package installation and removal

`package_mutation.py` recognizes exact Fedora package names for install and
remove in English and Spanish, including quoted names and common forms such as
`uninstall "rust" package`. A request for packages “related to” named roots
uses those roots only; DNF, not a name-matching sweep, determines dependent
removals. Generic goals such as “latest” or “everything” clarify instead of
guessing. Kernel, boot, authentication, package-manager, desktop, and other
explicitly protected package removals are denied.

Before approval, JARVIS performs one cache-only DNF simulation. Removal uses
the DNF5 form `remove --no-autoremove`; the dialog shows the bounded resolved install/removal set
(at most 200 packages) and the preview. A recognized request does not create a
model preflight turn or an intermediate dependency-choice dialogue: the single
approval applies to the exact DNF-resolved effect. The approval digest binds operation,
exact names, current RPM state,
and preview digest. The root-owned helper re-runs the same cache-only preview,
rejects drift or protected removals, writes durable pre-state, runs one fixed
DNF install/remove command, and verifies post-state. Names are validated data;
repository URLs, shell fragments, arbitrary options, upgrades, and repository
changes are not accepted.

The preview digest is computed from normalized DNF transaction package rows
(package identity/architecture and version-release), with known
non-semantic cache/log housekeeping omitted and row ordering normalized. This
keeps the approval bound to the exact resolved package effect while allowing
the helper's required second simulation to match the UI preview.

Package mutations are agent-orchestrated, not agent-shell-executed. The typed
agent planner may ask one clarification about installation source or exact
roots. Once clear, it hands only `package_install`/`package_remove` and exact
roots to the registered preview/approval path; it must not propose `sudo`,
`dnf`, Bash, or an App Server command approval.

Before a package preview, execution, or recovery review, the TUI compares the
deployed root helper hash with the reviewed helper source in the active bundle.
A mismatch is reported before any approval; reinstalling the helper is then a
separate privileged deployment action that runs no package transaction.

DNF5 transaction-summary count lines are not package-list sections. Both
preview layers stop parsing at those counts, so trailing DNF status text cannot
be mistaken for a removal target. When a removal heading is localized or
extended, they use only RPM-shaped rows from DNF's transaction table; mixed
install/upgrade transactions remain rejected.

One authoritative rollback record may exist per user. Undo is a separate
operation with a fresh one-use reservation, confirmation, and Polkit
authentication. Undo of removal requests the exact epoch/version/release/arch
recorded before the transaction and deletes the recovery record only after the
same bound RPM state is verified. The helper first performs another cache-only
rollback simulation and rejects any effect outside the recorded set. Ambiguous
multilib pre-state is rejected before the original removal. Package history is useful evidence but is
not represented as complete system recovery.

If an earlier helper attempt left a `prepared` record, a fresh recovery review
may reconcile it only when every recorded pre-state is still exactly present.
That clears an incomplete record without running DNF. Any state difference
remains indeterminate and is not cleared automatically.

An applied record whose rollback has become unsafe may instead be archived with
one separate confirmation. The helper fsyncs a root-owned sealed copy and then
retires the active record; it runs no DNF command and permanently removes that
record's rollback capability, allowing later package transactions.

## Authority and admission

TUI package version 0.7.0-dev and task pipeline version 3.0.0 introduce
task-admission schema version 3, which distinguishes:

- `local_read`: execution authorized for one bounded read, no mutation;
- `local_mutation`: reviewed current-user filesystem plan, approval pending;
- `registered_mutation`: reviewed registered package plan, approval pending;
- `agent_conversation`: current-user agent surface with approval at the App
  Server tool boundary; and
- `blocked`: no authority.

An approval-pending admission has `execution_authorized=false` and
`mutation_authorized=false`. Authority exists only after the exact review is
affirmed and is consumed by the single execution reservation.

## Failure and recovery

There is one attempt. Target drift, preview drift, helper absence, Polkit
decline, permission failure, cancellation before reservation, unexpected
output, or verification failure stops without retry. Once a mutation is
reserved and executing, the TUI does not pretend it can safely cancel or replay
the worker. An indeterminate outcome is reported as such and requires direct
inspection before any new plan.

The filesystem path provides operation-level rollback through Trash, not a
filesystem snapshot. The package path provides a narrow helper record, not
boot, configuration, or user-data recovery. Higher-risk changes remain subject
to the recovery levels in `direct-host-deployment-and-recovery.md`.
