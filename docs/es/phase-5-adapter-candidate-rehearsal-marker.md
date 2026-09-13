# Phase 5 adapter candidate — disposable rehearsal marker

## Purpose

This is the first candidate for exercising the Phase 5 approval and rollback
plumbing without touching the workstation. The implementation is in
`vm-lab/scripts/phase5_rehearsal_marker.py` and its focused tests are in
`vm-lab/tests/test_phase5_rehearsal_marker.py`. It is a
disposable-scratch-only operation, not a host adapter and not a TUI action.

## Exact operation

- operation ID: `jarvis.rehearsal.marker`
- revision: `1.0.0`
- target class: one scratch directory opened beneath a separately trusted,
  owner-controlled disposable rehearsal root; its digest is included in the
  approval
- parameters: exactly `{ "state": "present" }` or `{ "state": "absent" }`
- effect: create or clear only the adapter-owned marker below that scratch
  directory; `absent` is represented by a verified empty marker so no
  pathname-based deletion can remove an unexpected inode
- rollback: execute the opposite state with a new approval; no in-place reuse
  of an approval is allowed
- output: bounded status object containing only operation, target digest, and
  resulting marker state

The implementation must reject symlink targets, path traversal, non-owned
directories, unexpected files, extra parameters, and any target outside the
disposable rehearsal root. It must not invoke a shell, subprocess, network,
privileged helper, device, or system service.

## Promotion gates

This candidate remains unregistered and disabled until all of the following are
complete:

1. implement the adapter against a temporary rehearsal root only;
2. test present/absent, stale marker, symlink, traversal, wrong owner, wrong
   digest, interruption, replay, expiry, and rollback cases;
3. bind it to the durable authority ledger and OS authorization boundary;
4. obtain a fresh independent review of the adapter and evidence;
5. obtain explicit user approval for one disposable rehearsal attempt.

## Rehearsal result

The user-authorized disposable rehearsal passed on 2026-08-07 at
`2026-08-07T17:24:01Z`: `present` then `absent`, identical target digest,
empty final marker, and temporary-root cleanup. Evidence is recorded in
`runtime/reports/2026-08-07-phase5-rehearsal-marker.json`. This does not enable
the executor or authorize a host adapter.

The candidate does not authorize host execution, fact persistence, policy
mutation, or any TUI bypass. A separate host adapter would require a new
operation ID, revision, scope, review, and approval.
