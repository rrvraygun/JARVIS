---
name: system-repair
description: Diagnose and repair Linux boot, package, service, filesystem, network, driver, configuration, or application failures through the smallest evidence-backed and recoverable change. Use after diagnosis identifies a likely cause; require backups, exact targets, approval, validation, and escalation for data-loss or lockout risk.
---

# System repair

1. Reproduce or establish the failure and preserve diagnostic evidence.
2. Read [repair-gates.md](references/repair-gates.md). Rank hypotheses and run the
   next discriminating read-only check; do not shotgun fixes.
   For display brightness or keyboard illumination, also read
   [lighting-repair.md](references/lighting-repair.md).
3. Identify recent changes and the smallest reversible repair.
4. Protect user data, capture configuration and pre-state, and prepare recovery.
5. Present exact commands, targets, risk, downtime, rollback, and validation.
6. Obtain approval, execute one causal intervention at a time, and stop if actual
   state diverges from the approved assumptions.
7. Re-run the original reproduction and health checks. Roll back on regression
   when safe, preserve evidence, and audit the outcome.
