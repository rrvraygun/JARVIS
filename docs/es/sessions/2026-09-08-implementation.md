# 2026-09-07–08 implementation continuation

## Scope and preservation

The user authorized implementation of the audited plan and subsequently asked to
continue. All edits are in an isolated candidate. The baseline copy preserved
765 source entries and verified every original manifest hash. No Git repository
was available. No active source, authentication state, host policy, service,
package, security setting or network configuration has been replaced.

The detailed implemented scope and explicit unimplemented executors are in
[governed operations](../governed-operations.md). This is not a completion claim
for the entire JARVIS backlog or a request for blanket host approval.

## Changes

- Bounded collector I/O, safe project reads, redaction and fresh timestamps.
- Read-only agent turns, process-scoped MCP dispatch, evidence binding, one-use
  approval reservation before transport and fixed runtime-profile validation.
- Typed operation proposals, isolated Cargo, new-copy Cargo-file edits, text-project
  backup/restore, exact TCP checks, and inactive service helper/Polkit artifacts.
- Separate outcome verifier, source snapshots, cgroup guard and bounded transcripts.
- Five on-demand domain views and exact operation review without activity cards.
- Documentation reconciliation and tests for unsafe paths, overflow, secrets,
  scope/argument mismatch, cancelled submission, duplicate approvals, drift,
  recovery copies, resource limits, service receipts and unsupported effects.
- Pre-existing typing defects corrected without suppressing the checker, including
  the package catalog assessment's wrong return type and Power conflict tuple.
- Recovery tests now use explicit fixtures instead of relying on personal runtime
  reports absent from a clean source copy.

## Evidence recorded during development

- The baseline's full TUI run had 262 tests, 261 passing and one Unix-socket bind
  PermissionError in this sandbox.
- A clean baseline type check reproduced 28 pre-existing errors in five modules;
  the earlier cached check was not a reliable baseline for a source-only checkout.
- The expanded fifteen-module type check subsequently passed after corrections.
- Focused suites passed during development, including 31 new governance/service/
  scope tests in the latest focused run. Final gate results are recorded below
  after execution, rather than inferred from these focused checks.
- An intermediate 279-test TUI run exposed the known socket restriction, one
  personal-runtime-dependent fixture and two assertions describing the old UI.
  The fixture and the directly affected assertions were corrected.

## Independent review

An independent read-only reviewer identified gaps in the original authority
boundary, structured redaction, snapshot identity, service effects, scope lifecycle
and app overrides. Corrections and regression tests were made in the candidate.
One review attempt hit the service usage limit; subsequent reviews resumed after
the user continued. No review authorizes deployment or proves live behavior.

## Outstanding work

Real isolated Cargo, dependency-copy and text-project backup/restore tests passed on 2026-09-09 (details below). No privileged helper mutation, external TCP check or new full system restore has been performed. The real active JARVIS App Server/MCP session
has not been replaced or restarted. Update/boot executors, general binary/user-data backup, automated full-system recovery orchestration and direct dependency application to an existing project are not complete. Narrow DNS/SELinux/firewall helpers have since been prepared but not deployed. Existing manual R2 evidence and the newly connected external disk are documented in `2026-09-08-external-backup-target.md`. Keep these distinctions when continuing.

Rollback of this development means retaining the original checkout and baseline;
no host rollback has been required. Partial candidate workspaces are retained
until a separately reviewed cleanup.

## Final validation

The 2026-09-09 complete gate passed 307 TUI tests plus bundle validation and 792 manifest entries. Subsequent review fixes passed 58 focused tests; final refreshed validation is recorded in the closure plan. This is not an activated release.

## Isolated integration observations

An authentication-free temporary App Server successfully initialized and passed
candidate effective-profile validation after accounting for its explicit `local`
transport field. No model turn, user credentials or active JARVIS session was used.
A synthetic native permission probe could not run its allowed-read control and
returned AppServerError; native denial enforcement remains unverified here.

### Continuation 2026-09-09

Observed final focused scope checks: 55 tests passed; strict typing passed for 8 modules. User supplied four unique Restic snapshot rows, latest 0b203a54 on 2026-08-07, 20.035 GiB. Full repository check result remains pending. No activation performed.

Recovery descriptions now distinguish separate project copies from host/external effects; operation cancellation waits for bounded settlement. First focused run after adding subprocess error handling exposed a missing subprocess import (28 tests, two errors); recorded before correction. Checkpoint mutation coverage and full-restore ordering were identified as blockers, then corrected in the continuation below.

Checkpoint continuation: seven focused tests passed. Static checking then detected two overbroad edit sites (archive callback and package diagnostic), plus import ordering; corrected before broader validation. New checkpoints use schema 2; legacy chat remains readable, while full recovery requires tracked mutation history and a matching package receipt.

## Verified continuation — 2026-09-09

- Full host-context quality gate passed: 307 TUI tests, static checks, dependency checks, independent package/schema/policy/VM/host fixtures, shell checks, Bandit and manifest validation. The earlier socket restriction did not reproduce in host context.
- A freshly started real candidate MCP server listed 41 tools, returned a new read-only health observation and rejected forbidden activation. This does not establish authenticated model/tool integration.
- Independent read-only review found late observation attribution across turn replacement and inconsistent persisted `verified` state. Generation-bound evidence now rejects cross-turn observations; one receipt validator derives verification for UI, MCP and transcripts. Reviewer found no new blocker in the follow-up scope. Fifty-eight focused tests passed, including regressions for both findings.
- First real Cargo fixture run failed once: Fedora `/usr/bin/ld` points through `/etc/alternatives/ld`, absent in the sandbox. Failure was recorded before diagnosis. The sandbox now creates only that synthetic linker link to `/usr/bin/ld.bfd`; it mounts no host `/etc`. A new reviewed fixture run completed with exit 0 and a passing separate verifier, including unchanged source and snapshot trees.
- Actual dependency editing to a new fixture workspace passed the separate verifier. The initial backup proposal rejected shared `/tmp` as a destination parent before execution; no backup or restore attempt followed that refusal. New plans used an owner-only fixture container; backup and restoration to new destinations both passed independent verification.
- No user projects, external backup disk contents, packages, persistent services, firewall, DNS, SELinux or boot state were changed by these smoke tests. The transient bounded user service used for Cargo finished. Fixture copies and operation receipts are retained; cleanup is separate.
- The active source and authentication remain untouched. Full Restic check output, exact boot scope, general binary-data recovery, automated system-recovery and update/boot executors remain pending; they are not represented as completed by the successful narrow tests.
