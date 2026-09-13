# Threat model

## Protected assets

System availability, user data, credentials, configuration integrity, recovery
capability, audit history, approvals, agent policy, and trusted update sources.

## Adversaries and failures

- Prompt injection in web pages, docs, logs, package metadata, filenames, and MCP
  output
- Compromised package repository, plugin, skill, hook, MCP server, or dependency
- Over-broad or stale human approval
- Agent hallucination, target confusion, unsafe generalization, or premature
  completion
- Privilege escalation and confused-deputy behavior
- Concurrent agents changing overlapping resources
- Partial execution, power loss, disk exhaustion, network loss, and rollback
  failure
- Local attacker altering state or audit files
- Compromised host forging its own health and recovery evidence
- Sensitive data leakage through prompts, transcripts, logs, snapshots, or
  notifications
- Contaminated VM baselines, writable golden images, stale overlays, forged
  guest evidence, host-share leakage, passthrough escape, and false claims that
  virtual hardware represents the physical workstation

## Controls

Registered capabilities, versioned procedures, default deny, exact targets,
fresh-state checks, digest-bound expiring approvals, independent review,
least-privilege tool identities, sandboxing, OS permissions, MCP allowlists,
hook guardrails, redaction, hash-chained audit, external integrity export,
worktree staging, disposable rehearsal, recovery tests, and post-change
validation.
The VM lab additionally requires an official signed image lock, powered-off
read-only golden base, one external overlay per scenario, runtime networking
off, no host shares/credentials/production stores/passthrough, outside-guest
identity and reset attestations, and explicit physical-gap records.

Visible local-read results are terminal-sanitized, credential-value-redacted,
and sensitive filenames are removed before model synchronization. The active
Conversation snapshot is bounded and injected as untrusted quoted history; it
cannot grant broker admission, mutation, privilege, or approval. The current
request remains separately typed and policy-bound. Sanitized visible context is persisted in the bounded conversation store; raw content remains excluded from audit. Configured Codex retention is a separate data boundary.

Filesystem mutation plans bind parent and target identity, refuse symlinked,
hidden, sensitive, special, protected, ambiguous, or overwrite targets, and
consume one in-memory approval. “Delete” is implemented as a same-filesystem
move to current-user Trash. Package plans bind exact names, RPM pre-state, and
a cache-only DNF preview; install rejects removals, removal disables autoremove
and rejects protected resolved packages, and the root helper independently
rechecks the binding before one fixed command. Neither path accepts shell
syntax or standing approval.

## Residual risk

No agent can guarantee a perfect or fully known system. Local hash chains do not
defeat a privileged attacker. Hooks do not cover every tool path. Tests cannot
represent every hardware and failure combination. Human approvals can be wrong.
High-assurance deployments require independent backups, remote signed logs,
separate recovery credentials, and periodic human/security review.
