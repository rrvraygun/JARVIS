---
name: system-update
description: Research, stage, execute, and verify Linux OS, kernel, firmware, driver, package, container, Codex, or agent-workflow updates. Use for update availability, security patching, upgrades, migrations, or self-update proposals; require trusted provenance, compatibility, recovery, explicit approval, and independent validation.
---

# System update

1. Identify installed and target versions, repository/channel, update class, and
   reason. Read [update-gates.md](references/update-gates.md).
2. Use current official advisories and release notes. Verify provenance and note
   held, removed, replaced, or newly installed dependencies.
3. Check compatibility, disk capacity, configuration conflicts, downtime,
   backup/snapshot freshness, recovery environment, and rollback feasibility.
4. Show simulation or transaction plan. Separate security fixes from optional
   feature upgrades. Obtain approval for the exact transaction.
5. Execute without bypassing signature, TLS, repository, or security controls.
6. Validate package integrity, services, boot-critical artifacts, devices, and
   requested behavior. Capture post-state and residual follow-up.

For agent self-updates require a reviewable diff, provenance, evaluation,
independent security review, user approval, backup, and independent validation.
