# Multi-agent contract

## Roles

- Primary Jarvis agent: decomposes, routes, reconciles, authorizes through the
  control plane, and owns final outcome and audit closure.
- System explorer: bounded read-only evidence.
- Change planner: registered approval-ready plan.
- Outcome verifier: independent result and invariant check.
- Policy auditor: independent control and ledger review.
- Recovery reviewer: independent rollback, backup, and rescue assessment.

## Delegation rules

Delegate only independent, bounded work. State exact inputs, allowed tools,
permission mode, file/target ownership, expected output, deadline, and stop
conditions. Subagents cannot grant authority, widen scope, accept risk, approve a
change, or mark their own output independently verified.

Use separate evidence and review agents for high-impact work. Do not leak an
intended conclusion into an independent evaluation prompt. The primary must wait
for required results, reconcile contradictions, re-run deterministic policy, and
retain responsibility for the final decision.

## Handoff shape

Return conclusion; observed evidence and provenance; inferences; unknowns;
targets touched; commands or tools used; validation; policy concerns; and next
action. Never return a bare “looks good.”
