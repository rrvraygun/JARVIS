# 2026-08-28 stabilization session

**Objective:** begin the JARVIS 0.7.0-dev codebase audit and sanitation release.

## Changes in this session

- Added bounded App Server environment and protocol-ingress controls.
- Removed automatic network-command approval and the obsolete sudo/DNF helper.
- Hardened conversation persistence, clipboard privacy, cancellation settlement,
  power target writes, generic ledger append verification, and safe diagnostics.
- Added the first living documentation index, architecture map, generated
  inventory, audit report, backlog, locked development tooling, and local
  quality-gate skeleton.

## Evidence

- Pre-change archive and baseline are recorded in `audits/2026-08-28-codebase-audit.md`.
- Focused App Server/session/event/conversation tests passed.
- Focused mutation/power/headless tests passed.
- The full TUI suite passed outside the sandbox: 223 tests in 121.667 seconds
  on the final package/cancellation source state.
  Inside the restricted sandbox, the same suite passed 220 tests and only the
  expected Unix-socket bind test was denied by the environment.
- Three independent read-only Luna reviews found and guided fixes for protocol
  privacy, persistence snapshots, package lifecycle ordering, cancellation
  settlement, power target identity, documentation, and validation coverage.
- A full quality-gate attempt exposed transient Ruff/Mypy cache files in the
  release manifest. The generator now excludes tool caches; the regenerated
  source manifest verifies 728 first-party entries.
- The first full-gate attempt also exceeded the execution time boundary because
  it ran the complete TUI suite twice. The outer profile now owns that suite and
  tells the nested legacy validator to skip only the duplicate invocation.
- The final validator trace exposed a stale VM-controller schema. It now admits
  only the contract-only baseline or the documented H1 Tier-0 read-only state.
- Related observation and action schemas were reconciled with the same current
  H1 status; their mutation, privilege, and network denials remain unchanged.
- The final fast quality profile passed. The legacy fixture/contract validator
  also passed with the already-completed TUI portion explicitly skipped to
  avoid duplicate execution.

## Unverified and residual risk

- Full release validation, documentation archival, broader workflow extraction,
  MCP store-root hardening, coverage-threshold enforcement, and medium/low
  static-analysis findings remain open.
- No live host package, power, service, Polkit, or helper activation occurred.

## Rollback

Restore project files from the source-only archive recorded in the dated audit.
Do not restore, rotate, truncate, or delete runtime journals or user data.
