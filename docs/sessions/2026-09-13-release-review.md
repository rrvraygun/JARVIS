# Release review — 2026-09-13

## Scope

Reviewed the synchronized root source tree, current contracts, generated
inventory, staged validation records and publication metadata. The root tree
now includes the latest candidate source while runtime data, credentials,
virtual environments and Python caches remain excluded from publication.

## Current implementation

- TUI and App Server session flow, including protocol compatibility fixes.
- Global model, reasoning-effort and context-window settings persisted for new
  turns.
- Per-conversation context isolation, token-usage marker and checkpoint reset.
- Clean/Raw domain evidence views with bounded field explanations.
- Normal terminal, Cargo isolation, package inspection and reviewed privileged
  helper contracts.
- Live activity and streaming projection with sanitized tool metadata.

## Documentation policy

`current-product-state.md` and `tui-contract.md` are current authorities.
`CHANGELOG.md` is the public change index. Dated phase, audit and session files
remain as historical provenance; contradictory snapshots are explicitly labeled
historical rather than silently deleted.

## Validation

- Fast quality gate: passed, 26 tests.
- Full root gate: 372 tests reached; 371 passed and one socket test was blocked
  by the managed sandbox's local-socket restriction. This is environmental and
  was previously verified separately outside the sandbox.
- Ruff, generated inventory, documentation checks and release manifest passed.
- Final root inventory: 832 files; runtime/staged candidate inventory remains
  separately tracked and is not part of the GitHub publication tree.

## Publication prerequisites

The workspace contains an empty `.git` directory, so no reliable commit diff or
remote can be generated here. Before pushing to GitHub, initialize a fresh Git
repository, review `CHANGELOG.md`, inspect the complete diff, and ensure runtime
and credential paths remain ignored. Privileged installation and real package or
boot mutations remain separately gated; this review does not certify them.
