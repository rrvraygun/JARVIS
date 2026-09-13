# Version-aware knowledge and learning system

## Purpose

The knowledge system improves command selection without turning prior output
into authority. It answers four different questions with separate evidence:

1. What is true about this workstation now?
2. What syntax and behavior apply to the installed versions?
3. What happened when a command was attempted?
4. Which reusable operational lessons has the user approved?

Never collapse those questions into a single mutable memory field.

## Storage model

`storage/schema.sql` defines an SQLite database with immutable revisions for:

- documentation sources and locally cached content;
- Fedora facts and their freshness/prerequisites;
- an allowlisted Bash/Fedora command catalog;
- single-attempt command outcomes and automatically linked error reports;
- lesson revisions and independent success/conflict evidence;
- auditable decision summaries;
- command, procedure, and transaction approvals plus replay records;
- remote append-only export receipts.

Database triggers block updates and deletes to critical historical rows. A new
fact or lesson status is a new revision. The external JSONL ledger remains the
security event sequence; SQLite is not a replacement for it.

## Source registry

`registry/sources.json` ranks evidence by applicability and authority. Rankings
are routing rules, not automatic truth scores. Version-matched local and official
documentation wins over a newer but incompatible page. Source records include
publisher, locator, retrieval time, applicable versions, content hash,
completeness, and community-confirmation requirements.

`scripts/index_local_docs.py` collects only allowlisted local Bash help, man
pages, or explicitly safe version/help output. It invokes processes directly,
uses no arbitrary shell input, caps output, makes one attempt per method, and
writes a private JSONL import file. The resulting SQLite content provides the
offline core. Network retrieval and freshness updates remain a later, separately
controlled feature.

## Fedora facts

`scripts/collect_fedora_inventory.py` reads the collector registry and executes
exact unprivileged argument arrays with a fixed environment, timeout, output cap,
and one-attempt limit. It excludes hostname, username, addresses, serials,
machine ID, browser data, documents, credential stores, and environment dumps.
It cannot invoke privilege helpers or arbitrary executables supplied by a user.

Collected facts are not permanent truth. Each carries collection time,
collector version, source attempt, prerequisites, privacy class, and status.
Policy freshness gates decide whether the fact may support a later action.

Codex CLI commands run inside a sandbox that can change mount options, deny
runtime writes, hide protected device data, and appear as a container to
virtualization detection. Every fact therefore records observation scope.
Observer-only results cannot establish host configuration. A successful exit
code is insufficient when output contains warnings, denied side effects, extra
constraints, or fails a command-specific expectation.

## Command construction

Store commands as `executable` plus `argv[]`. Render Bash text only for the user
interface. Before execution, record shell expansions, redirections, pipelines,
working-directory class, environment keys, exact targets, expected exit codes,
output expectations, timeout, risk, rollback, and validation.

The command catalog describes whether an executable can mutate and which local
documentation lookup methods are safe. It is not an execution allowlist. Actual
execution still requires capability policy, sandbox/OS permission, and approval.

## Error and lesson state machine

```text
attempt
  ├─ expected success ──> verified success evidence
  ├─ failure ───────────> error observation ──> diagnosis
  └─ unexpected result ─> error observation ──> diagnosis

diagnosed + working verified solution
  └─> draft lesson
       └─> three independent matching successes
            └─> promotion candidate
                 └─> explicit user approval
                      └─> active lesson
                           └─ conflict/version change/unexpected effect
                                └─> suspended revision
```

Automation cannot activate a lesson. Success count alone is insufficient unless
prerequisites match and validation is independent. A conflict prevents candidate
promotion. Version changes suspend applicability until revalidated.

In the natural-language interface, `activate_lesson` is the only activation
tool and its MCP policy is `prompt`, forcing a direct user approval interaction.
Do not treat approval of another command, a chat statement from earlier scope, or
an agent-generated decision object as lesson activation.

Error diagnosis is also revisioned. The original observation remains immutable;
a later diagnosis or resolution appends a revision linked to the verified working
attempt. Failed and successful attempts are never edited to make history appear
cleaner.

## Decision records

A decision record contains objective, facts, source references, alternatives,
selected action, risk, validation, and outcome. It deliberately excludes private
model reasoning. This produces a stable audit artifact without treating verbose
reasoning as factual evidence.

## Approval model

All scopes are data-modelled:

| Scope | Binding | Initial execution |
|---|---|---|
| Command | exact executable, argv, targets, state/action digests, nonce, expiry | enabled |
| Procedure | exact versioned procedure and bounded sequence | disabled |
| Transaction | reviewed atomic group, ordering, recovery | disabled |

Even future procedure or transaction approval can retain per-command gates.
Approvals are user-issued, expiring, state-bound, target-bound, non-transferable,
and single-use. The initial pre-authorized safe-list feature is defined but off.

## Privacy and encryption boundary

The database currently accepts only `public` and redacted `internal` records.
`restricted` or `secret` writes fail until encryption state is configured and
unlocked. This is intentional: an encryption TODO must never become permission
to store sensitive plaintext. Definitive release requires authenticated
encryption, user-mediated key unlocking, backup key recovery, and tests.

## Remote integrity boundary

The remote sink schema supports restricted SSH append, object lock,
transparency-log, or offline-media receipts. No destination is configured and no
network export occurs. Enabling a sink requires separate user approval, encrypted
transport/storage, least-privilege credentials, and append-only verification.

## Current limitations

- Local hashes and immutable SQLite triggers do not resist a privileged attacker.
- Documentation fetching and refresh are not yet network-connected.
- Encryption and remote append-only backup are release blockers.
- No state-changing Fedora executor exists in this phase.
- Protected host facts that the Codex sandbox cannot expose remain unknown until
  the user approves a separately designed read path; the agent must not bypass
  the sandbox to make the inventory appear complete.
- The TUI and unattended monitoring are future interfaces.
