# 2026-08-28 codebase audit

**Scope:** all first-party implementation, schemas, fixtures, tests, launchers,
deployment artifacts, and current documentation. Pinned vendor schemas were
reviewed only at integration surfaces. Runtime files were assessed only for
layout, size, permissions, and integrity behavior; no private raw content was
read or copied.

## Evidence baseline

- Source rollback archive: `/tmp/jarvis-stabilization-baseline.x0G3KA/source-before-stabilization.tar.gz`
- Archive SHA-256: `e1cf151f58eb89ae2e9e96b7d525c58da1da2ca8d52772d86ca1044310147892`
- Pre-change release manifest: 715 entries verified.
- The existing fixture validator reached 214 TUI tests but failed because the
  sandbox denied a Unix-socket bind; 26 headless Textual tests were skipped
  because it used system Python rather than the project virtual environment.
- The focused Unix-socket test passed outside the sandbox.

## Strengths observed

- Typed task assessment/admission separates model intent from authority.
- Local filesystem plans use bounded, descriptor-aware, terminal-sanitized
  current-user execution.
- Package and power operations cross narrow Polkit helper boundaries with
  one-use approvals and recovery records.
- The TUI journal uses a locked hash chain, incremental head validation, and
  stream summaries rather than raw delta persistence.
- Fixtures cover local filesystem, package parsing, approvals, journal
  integrity, terminal safety, recovery, and VM contract behavior.

## Findings and remediation status

| Severity | Finding | Evidence | Status |
| --- | --- | --- | --- |
| High | A cancelled coroutine could abandon an already-running mutation thread. | `async_boundary.py` detached work by default. | Fixed for package, power, lighting, and local-mutation calls: cancellation settles for at most 30 seconds, then reports an indeterminate outcome-pending state. |
| High | An obsolete helper offered broad `sudo dnf`, repository, and update operations. | Former `vm-lab/scripts/jarvis_sudo_helper.py`. | Removed; final validation proves no references remain. |
| High | Entire process environment crossed into Codex App Server. | Former `app_server_environment()` copied `os.environ`. | Fixed with explicit allowlist; values remain unlogged. |
| High | Some network commands could be automatically accepted. | Former session network-read heuristic. | Removed; every App Server command request remains pending for exact approval. |
| High | Clipboard fallback persisted rendered conversation text in `/tmp`. | Former `_do_clipboard_copy()`. | Fixed; unavailable clipboard reports no persisted fallback. |
| High | Conversation storage rewrote files synchronously/in-place during render. | Former manager autosave plus render bridge. | Atomic private writes and asynchronous app persistence now queue immutable snapshots; focused persistence tests pass. |
| High | App Server protocol data was hashed before global bounds. | `event_reducer.py`, stdio reader. | Fixed with line, depth, value-count, queue, and metadata-sanitization boundaries. |
| High | Root power helper followed pathname writes. | Former `_write_targets()` used `Path.write_text`. | Fixed with no-follow descriptor identity checks. |
| Medium | Generic control-plane ledger appended after trusting only the tail. | `jarvisctl.append_event()`. | Fixed: full chain verification occurs under the append lock. |
| Medium | MCP server returned raw exception strings. | `mcp_server.py`. | Fixed to stable `request_failed`; store-root/payload hardening remains open. |
| Medium | `app.py`, `session.py`, and `broker.py` remain multi-responsibility modules. | 3,000+/1,300+/1,200+ lines. | In progress; workflow extraction is gated by characterization tests. |
| Medium | Current documentation has historical/current drift. | Current docs and phase records conflict. | In progress; authority index, map, generated inventory, backlog, and session record added. |
| Medium | Validation depended on external absolute paths and skipped UI coverage. | `scripts/validate-bundle.sh`. | In progress; locked tools and project-local quality configuration added. |
| High | VM-controller schema permitted only a superseded contract-only state while policy documented H1 Tier-0 read-only activation. | `vm-lab/schemas/controller-policy.schema.json`, `vm-lab/controller/policy.json`. | Fixed with two exact schema variants; both retain mutation, privilege, network, and virtualization denials. |
| High | Tier-0 observation schemas and action registry omitted the documented H1 read-only status. | Observation schemas and `action-definition.schema.json`. | Fixed with exact fixture-only/H1 variants and the registered one-use read-only action status. |
| High | TUI DNF5 install previews could resolve a package table while the root helper parsed no install roots and rejected before DNF. | TUI `package_inventory.py` had a table fallback absent from `jarvis_package_control.py`. | Fixed with matching bounded install-table parsing; helper fixture passes. |

Independent Luna reviews also found and closed a catalog-package lifecycle gap
(capture/bind now precedes DNF preview), package-undo cancellation drift, and
the persistence queue’s live-object race. The final review still records
medium-only work in the backlog.

## Remaining backlog policy

Medium and low findings remain in `../stabilization-backlog.md`. They are not
silenced: each must have an owner, evidence, and a concrete acceptance test or
documented reason to defer it.
