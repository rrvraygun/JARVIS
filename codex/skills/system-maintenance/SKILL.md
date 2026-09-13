---
name: system-maintenance
description: Plan and perform bounded, reversible Linux maintenance such as cache management, log retention, stale temporary artifacts, service housekeeping, and capacity recovery. Use for cleanup or routine maintenance only after exact targets, ownership, retention, backup, approval, and validation are established.
---

# System maintenance

1. Diagnose the pressure or maintenance objective; do not clean by habit.
2. Read [cleanup-policy.md](references/cleanup-policy.md).
3. Resolve exact targets, owners, size, age, active use, retention, and recovery.
4. Prefer application-native rotation, pruning, package-manager cleanup, and trash
   over recursive deletion. Never use broad roots, unresolved variables, or globs.
5. Present a dry run, expected reclaimed capacity, exclusions, and rollback.
6. Obtain action-specific approval, execute the bounded operation, validate the
   service and capacity result, then audit what was removed and recoverability.
