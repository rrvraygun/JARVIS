# Changelog

All notable changes to JARVIS are recorded here. Dates use Europe/Madrid local
time where the source record supplied local timestamps.

## [Unreleased] — 2026-09-13

### Added

- GitHub Agent, selectable in Agents and Conversation, with bounded local Git
  inspection, publication preflight, and exact operation plans.
- Exact GitHub Agent plans can open the existing one-use TUI review for local
  repository initialization, SSH cloning, branch/worktree creation, commits,
  fast-forward pulls, and pushes. Remote GitHub API operations remain plan-only
  until their connector is integrated.
- A guarded GitHub CLI adapter with structured validation for repositories, PRs,
  issues, releases, Actions artifacts and reruns; unavailable connectors fail
  closed without a remote request.
- English is now the primary documentation language. A mirrored Spanish
  documentation tree is available under `docs/es/`.
- Clean domain views for Health, Development, Network, Security and Recovery,
  with a Raw JSON view retained behind a per-domain selector.
- Per-field `[i]` explanations that open a short floating information dialog.
- Global model selection for all specialists: GPT-6 Astra, GPT-5.6 Sol, GPT-5.6
  Terra, GPT-5.6 Luna and GPT-5.5.
- Global reasoning-effort selection: None, Minimal, Low, Medium, High, Xhigh,
  Max and Ultra.
- Global context-window selection: Auto, 8k, 16k, 32k, 64k, 128k, 256k, 512k,
  800k, 1M and 1.05M tokens.
- Persistent global settings in `runtime/jarvis-model.json`, applied to new
  turns without changing an active turn.
- Live context marker below agent activity, showing used/window/remaining
  percentage when App Server token usage is available and `unavailable` before
  the first usage event.
- Nested App Server token-usage parsing for `thread/tokenUsage/updated`, including
  `tokenUsage.total.totalTokens` and `modelContextWindow`.
- Context usage reset to zero after checkpoint restoration and new conversations.
- Normal terminal execution mode with inherited user terminal I/O and no JARVIS
  runtime/resource limits, separate from isolated Cargo workflows.
- Root-reviewed boot and DNF transaction helper contracts with Polkit policies,
  exact one-use reservations, immutable receipts and independent recovery review.
- Persistent authenticated App Server probe and visible harmless normal-terminal
  smoke test.
- Live activity panel inside Conversation with stream fragments, tool name,
  query, status and elapsed time.

### Changed

- App Server preflight now uses the current `readOnly` protocol with
  `networkAccess=false`; obsolete `readOnly.access` was removed.
- Initialization declares `experimentalApi=true` for granular approval support.
- Package inspection routes automatically expose the Installation Specialist's
  existing `inspect_packages` read-only capability and bind complete query terms.
- Missing observations remain activity status and no longer inject duplicated
  canned text into the conversation.
- Conversation checkpoint controls use a stable modal chooser and no longer
  alter conversation geometry.
- Conversation action rail is grouped below the specialist selector; its position
  remains fixed when the selector opens.
- Release manifest and source inventory correctly resolve exclusions relative to
  the bundle root and reject empty manifests.

### Validation

- App Server, session, broker, activity, Clean/Raw and specialist tests pass in
  the staged candidate; the release manifest is regenerated after documentation
  changes.
- Restic repository integrity check supplied by the user completed with no errors;
  no package, boot or disk mutation was performed during development.

### Known limits

- GitHub publication uses the repository's SSH remote and the `main` branch.
- Real privileged package/boot mutations and a full authenticated agent turn
  remain separate deployment tests; fixture tests do not certify them.
- Context usage is unavailable until the App Server sends a usage event; the UI
  does not estimate usage from characters.

## Historical records

Earlier phase and audit records remain under `docs/` and `docs/sessions/`. They
describe design decisions and evidence at their recorded dates. Consult
`docs/current-product-state.md` for current behavior.
