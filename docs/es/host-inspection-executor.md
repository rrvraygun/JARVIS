# Read-only Host Inspection Executor

> **Status note (2026-08-09):** this document covers the distinct read-only
> inspection executor. The package-control helper is not part of this executor;
> its current scope and deployment requirements are in
> [`current-product-state.md`](current-product-state.md).

## Scope

The TUI broker may request a bounded local host inspection before starting an
agent conversation. This is an explicit read-only control-plane operation, not
an App Server tool and not host execution authority.

The executor accepts the user's request text and selects only fixed collectors:

- `platform`: `/etc/os-release` and `os.uname()`.
- `power`: the existing Power inventory, related installed RPM metadata, and
  loaded/exposed kernel-module names.
- `packages`: RPM database and cached DNF repository metadata. It never
  refreshes repositories or starts a transaction.

No user-provided command, path, executable, shell fragment, or repository URL
is accepted by the executor.

## Distinct bounded filesystem reader

The fixed host-inspection collectors above remain unchanged. Exact
current-user filesystem requests use the separate
`tui/src/jarvis_tui/local_filesystem.py` planner/executor. That route accepts a
typed path plan but never a command or argv. It supports only conservative
English/Spanish `list`, `read`, and `search` forms, XDG user-directory aliases,
workspace aliases, and unambiguous explicit paths.

The plan binds the original target token, requested and canonical paths,
device/inode/type identity, operation, search mode/query digest, hidden and
recursion choices, caps, and an overall plan digest. Execution revalidates the
binding immediately, uses descriptor-relative `O_NOFOLLOW` opens and Python
filesystem APIs in a worker thread, and performs one operation attempt. It
denies sensitive stores, secret-bearing names, special trees/files, directory
symlinks, binary reads, broad system searches, and broad recursive home reads.

Default list is non-recursive with at most 500 entries. Direct reads consume at
most 64 KiB before the presentation cap. Search is limited to depth 8, 2,000
regular files, 1 MiB per file, 200 matches, and a short monotonic deadline.
Hidden entries require explicit wording and sensitive descendants remain
excluded. Audit events contain only categorized/digested targets, counts,
duration, status, and applied caps—not paths, queries, listings, matches, or
file contents.

This read authority never upgrades into write authority. Exact creates,
move-to-Trash, and package transactions use the distinct approval-gated
contracts in `tui-mutation-executor.md`.

## Package Knowledge

Package scans are persisted at `runtime/knowledge/package-catalog.json.gz`,
mode `0600`, as a gzip JSON catalog. Each record preserves package identity,
version, state, origin/repository, vendor, summary, category, and classified
purpose. Queries return bounded ranked matches and label same-purpose installed
packages as an inference, never an RPM conflict.

Installed packages can expose shipped RPM documentation on demand. Official
documentation is intentionally not fetched implicitly: its refresh requires a
future explicit network-approved operation, with source provenance and
freshness recorded separately.

## Agent Boundary

The formatted report is input evidence for the agent conversation. The model
cannot invoke collectors, a terminal, filesystem writes, package transactions,
or privileged helpers. The broker journals only collector identity, selected
scopes, counts, and status; it does not journal raw package lists or request
text.
