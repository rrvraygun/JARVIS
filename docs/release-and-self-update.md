# Release and self-update

1. Build in an isolated branch or worktree, never directly in the active profile.
2. Validate skills, plugin, config, schemas, policy tests, hooks, MCP protocol,
   redaction, ledger integrity, and representative failure fixtures.
3. Generate `release-manifest.json` and review permission/capability diffs.
4. Obtain an independent security review for policy, hook, MCP, approval, audit,
   or privilege changes.
5. Create a versioned immutable release and preserve the previous release.
6. Request approval bound to the release-manifest digest.
7. Activate atomically through a pointer or directory rename.
8. Validate from a separate process. On startup, policy, MCP, or ledger failure,
   block activation and prepare a separately approved exact recovery; never retry or roll back automatically.
9. Record the release, reviewer, approval, activation, and result externally.

The agent may propose and stage an update, but it cannot approve or solely attest
to its own update. Never auto-update from an unpinned branch or mutable URL.
