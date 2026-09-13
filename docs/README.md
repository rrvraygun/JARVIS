# JARVIS documentation index

## Authority order

1. `AGENTS.md` defines repository-wide invariants and this documentation map.
2. `current-product-state.md` defines currently implemented product behavior.
3. Current contracts define subsystem boundaries and must agree with product state.
4. `generated/` is machine-derived inventory, never execution authority.
5. `audits/` and `sessions/` are evidence records.
6. `history/` indexes superseded design records and never overrides current contracts.

## Current contracts

- Product state and source map: `current-product-state.md`
- Shared safety and evidence: `shared-contract.md`
- Platform and threat boundaries: `platform-architecture.md`, `threat-model.md`
- TUI and host operations: `tui-contract.md`, `tui-mutation-executor.md`, `host-inspection-executor.md`
- Audit, data, recovery, and deployment: `audit-and-state.md`, `data-lifecycle.md`,
  `direct-host-deployment-and-recovery.md`, `r2-system-recovery-set.md`

## Living records

- Architecture and main files: `codebase-map.md`
- Modular specialist ownership and lifecycle: `modular-agent-architecture.md`
- Power Expert expansion and profile contract: `power-expert-expansion.md`
- Generated file/module inventory: `generated/codebase-inventory.md`
- Current stabilization backlog: `stabilization-backlog.md`
- Dated audit reports: `audits/`
- Dated session completion records: `sessions/`

The latest current records are `sessions/2026-09-12-global-model.md`,
`sessions/2026-09-12-inspection-live-activity.md` and
`sessions/2026-09-12-specialist-dispatch.md`; `CHANGELOG.md` indexes publishable
changes. Earlier phase files remain design history and do not override current
product state.

Every code-changing session updates its session record. Update current contracts
when behavior changes, regenerate the inventory when source membership changes,
and run the documentation/manifest checks before completion.

## Language versions

The English documentation in this tree is the primary version. A parallel Spanish
mirror is available under [`docs/es/`](es/LEEME.md). It preserves the same document
coverage with Spanish content and Spanish file names.
