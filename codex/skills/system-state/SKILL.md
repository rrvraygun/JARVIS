---
name: system-state
description: Create, compare, validate, redact, retain, and integrity-check structured system snapshots and append-only administration audit events. Use before and after material administration, for baselines, drift detection, change history, recovery evidence, or when persistent dynamic system knowledge is required.
---

# System state

1. Read [schema.md](references/schema.md) and select a bounded collector.
2. Create records in a user-approved runtime directory with mode `0700`; create
   files with mode `0600` and UTC timestamps.
3. Redact before persistence. Store commands and metadata, not secret-bearing raw
   dumps. Record unavailable evidence explicitly.
4. Append audit events; never rewrite prior events as if history changed.
5. Generate an integrity manifest after the artifact set is closed.
6. Compare snapshots by schema and collector version. Label incompatible fields.
7. Apply approved retention without removing records under incident/legal hold.

Use `append-event.sh` only with a prepared JSON event that contains no secrets.
Local hashes detect drift but do not protect against a privileged attacker.
