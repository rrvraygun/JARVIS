# Data lifecycle

## Classes

- Public reference
- Internal operational
- Restricted system metadata: encrypted and user-unlocked only
- Secret: encrypted and user-unlocked only when a narrowly approved procedure
  truly requires persistence; otherwise never stored
- Incident/legal hold

## Lifecycle

`collect allowlist -> redact -> validate -> classify -> store -> hash -> replicate
when configured -> retain -> rotate -> destroy by approved exact policy`

Use atomic writes for current state and immutable-by-convention snapshot paths.
Record collector and schema versions. State expires by capability; stale data can
inform history but cannot authorize a live change. Preserve approval and audit
records longer than disposable diagnostic output. Rotation must add an event and
manifest; it must not silently break the hash chain.

Do not collect full environments, command histories, browser profiles, credential
stores, private keys, authentication tokens, or unrestricted `/proc` data.

TUI filesystem-mutation audit events store categorized targets and binding
digests, never path/name text, file content, Trash names, or rendered results.
Package events store operation/count/status and binding digests, never the DNF
preview body or package names. In-memory one-use approvals expire with the
process and are not durable authorization. Root-helper recovery records are
owner-specific protected operational state and may authorize only a separately
approved undo after current-state verification.

Until encryption is configured, reject restricted/secret writes. Sanitized raw
output retention is size- and diagnostic-value-aware: prefer a short period,
then retain the content hash, relevant reviewed extract, and linked lesson or
error. Remote replication is an interface only until an approved append-only
sink exists.
