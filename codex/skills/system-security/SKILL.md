---
name: system-security
description: Assess and harden Linux host exposure, accounts, authentication, services, firewall, updates, encryption, secure boot, logging, backups, supply chain, and Codex permissions. Use for security reviews, vulnerability response, hardening, compromise triage, or policy validation; avoid lockout, evidence destruction, and unsupported claims of security.
---

# System security

1. Define assets, threat model, access path, uptime requirements, and recovery.
2. Read [hardening-order.md](references/hardening-order.md). Inventory exposure and
   controls without collecting secrets.
3. Separate vulnerability, exposure, exploitability, impact, and compensating
   controls. Verify current advisories from primary sources.
4. Prioritize measurable risk reduction. Test access recovery before identity,
   firewall, SSH, encryption, or boot changes.
5. Stage one bounded change with snapshot, approval, validation, and rollback.
6. Preserve forensic evidence during suspected compromise and use an independent
   trusted channel; do not let the possibly compromised host attest to itself.

Never claim the system is secure. State assessed scope, evidence, gaps, and
residual risk.
