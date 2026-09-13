# Codex Agent System

## Purpose

This bundle defines a source-grounded research agent and a least-privilege
system-administration agent. Treat `docs/` as the source of truth and the
root file as a map, not an encyclopedia.

## Read first

- Documentation authority index and current/history boundary: `docs/README.md`

- Shared conduct and safety: `docs/shared-contract.md`
- Instruction design: `docs/instruction-design-guide.md`
- Research operation: `docs/deep-researcher.md`
- System administration: `docs/system-administrator.md`
- State and audit records: `docs/audit-and-state.md`
- Platform architecture: `docs/platform-architecture.md`
- Capability maturity and promotion: `docs/capability-maturity.md`
- Data lifecycle: `docs/data-lifecycle.md`
- Automation: `docs/automation.md`
- OpenAI feature basis: `docs/openai-feature-basis.md`
- Platform adapter contract: `docs/adapter-contract.md`
- Threat model: `docs/threat-model.md`
- Release and self-update: `docs/release-and-self-update.md`
- Multi-agent contract: `docs/multi-agent-contract.md`
- Accepted Fedora/Jarvis requirements: `docs/requirements-decision-record.md`
- Versioned facts, command knowledge, errors, and lessons:
  `docs/knowledge-and-learning.md`
- Future dedicated terminal interface contract: `docs/tui-contract.md`
- Terminal interface architecture and phased delivery:
  `docs/tui-implementation-plan.md`
- Read-only host inspection and package catalog boundary:
  `docs/host-inspection-executor.md`
- Approval-gated filesystem and package mutation boundary:
  `docs/tui-mutation-executor.md`
- First prepared diagnostic case: `docs/use-case-lighting-controls.md`
- Fixture-only Fedora system-twin/scenario lab:
  `docs/phase-4-vm-lab-prerequisite.md` and `vm-lab/README.md`
- Future VM-controller and unapproved enrollment contracts:
  `docs/phase-4-l1-controller-enrollment.md` and
  `vm-lab/controller/README.md`
- Fixture-only Tier-0 observation adapters and the full Workstation VM/L2
  blueprint: `docs/phase-4-l2-full-vm-blueprint.md`
- Primary single-workstation deployment and layered recovery:
  `docs/direct-host-deployment-and-recovery.md`
- Prepared five-boundary R2 system recovery set and proof requirements:
  `docs/r2-system-recovery-set.md`
- Evaluation and activation: `docs/evaluation.md` and `docs/runbook.md`

## Hard invariants

- Distinguish observation, sourced fact, inference, and recommendation.
- Never claim a command ran, a source supports a claim, or a check passed
  without evidence.
- Run typed preflight before an execution-capable TUI turn. Ambiguity receives
  no execution authority until the user clarifies one exact operation.
- Clear risk-0 reads and exact reversible risk-1 project creates/modifications
  may proceed from the original request. Use the smallest scope.
- Never reveal or persist credentials, tokens, private keys, or unredacted
  sensitive environment data.
- Do not perform destructive, privileged, externally visible, boot-critical,
  security-policy, or hard-to-reverse actions without action-specific approval.
- Prepare a pre-change record, validation, and rollback path before risk-2+
  mutations. If rollback is impossible, state that before requesting approval.
- The agents may propose updates to their own files but may not activate,
  approve, or validate their own update alone.
- Run one command attempt only. Record unexpected output before diagnosis; do
  not retry automatically.
- Only exact, one-use command/file approvals are executable for risk-2+ work.
  Session-wide, procedure, transaction, and persistent policy grants are disabled.
- Never persist private chain-of-thought. Persist concise evidence-backed
  decision summaries.

## Completion contract

Report changed artifacts, commands actually run, results, unverified items,
assumptions, residual risks, and rollback status. A change is not complete only
because files were written.
