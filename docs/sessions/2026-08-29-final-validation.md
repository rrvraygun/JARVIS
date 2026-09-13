# 2026-08-29 final validation continuation

## Outcome

The 0.7.0-dev stabilization changes completed their available validation:

- Fast quality profile passed: dependency integrity, formatting, lint,
  documentation, generated inventory, strict authority-module typing, and 22
  focused tests.
- Full TUI suite passed outside the restricted sandbox: 223 tests.
- The legacy validator’s non-TUI fixture/contract remainder passed with the
  TUI suite intentionally skipped to avoid duplicate execution.
- The final release manifest verifies 728 entries.

## Independent review

Three earlier read-only Luna reviews completed and their high findings were
remediated. A fresh final three-lane review was requested after the final schema
reconciliation, but each reviewer was blocked by the Codex service usage limit
before inspecting source. This is an external validation limitation, not a
passing review. The primary audit and earlier reviewer evidence remain recorded
in `../audits/2026-08-28-codebase-audit.md`.

## Residual work

Only the medium/low backlog in `../stabilization-backlog.md` remains. No live
host, helper installation, package, power, service, or Polkit activation was
performed.

## Package capability continuation

Package-related classifier turns now receive bounded current installed/cached
available package evidence. Non-exact model targets, including an official
upstream Go release, become an exact-Fedora-root clarification rather than an
internal dispatch failure. This does not add arbitrary downloads or repository
management authority.

The latest user trace showed an indeterminate `golang` execution while the
recovery dialog exposed `rust`/`rustd`. JARVIS now performs a read-only
post-failure recovery-record binding check and reports
`package_helper.recovery_record_mismatch` instead of leaving that discrepancy
implicit.

The root helper also now handles an absent recovery record as a bounded empty
status instead of leaking a Python traceback through the TUI.
The TUI treats that explicit empty status as a pre-execution no-op; only a
nonempty record with different packages produces a recovery-record mismatch.

The root cause of the Go failure was then proven: the privileged helper lacked
the TUI’s DNF5 install-table fallback and rejected an empty resolved set before
writing a recovery record. The helper now shares that bounded parser and its
installer digest has been refreshed. A second binding issue was found in the
raw preview digest: DNF can add non-semantic cache/log diagnostics between the
UI preview and the helper re-preview. Both sides now canonicalize those known
diagnostics before hashing; the installer digest has been updated to the new
helper source hash, so the helper must be rerun after this source change. The
focused package-helper and inventory tests pass (33 tests).

The subsequent `install_set_incomplete` diagnostic identified a second parser
divergence: the helper sometimes saw only heading rows while the TUI saw the
DNF5 Package/Arch table. The helper now unions both bounded views; the package
helper regression suite passes (15 tests).

The bounded evidence then showed false package names (`Repositorios`, `Resumen`)
from an over-broad fallback and omitted an inline root row. That fallback is
now restricted to explicit package-table headers, and inline `Installing:`
rows retain their root package. The helper installer digest was refreshed.

Conversation history persistence was subsequently expanded to retain every
visible Conversation role (`user`, `agent`, `jarvis`, `action`, `system`) and
entry status/identity. Legacy two-role files remain compatible; omitted older
JARVIS/options text cannot be reconstructed.

History reload then exposed a key-format defect: the loader attempted to parse
opaque persisted keys such as `task:<id>` as integer indexes, clearing the
display after reset. Reload bookkeeping now uses the enumerated array position;
26 conversation/presentation tests pass.

The complete visible-role persistence contract is now covered by the focused
tests, including local JARVIS results and clarification Options. Entry status
updates are persisted even when text length is unchanged. The full suite ran
236 tests with only the known sandbox Unix-socket bind test unable to run.

Clarification submissions now keep the original request in its existing entry
and display only the new `User clarification:` answer in the new entry; the
combined request remains internal task text for the classifier. This prevents
repeated original prompts while preserving agent context.

The Conversation composition now applies a one-cell left visual offset to
correct the terminal renderer's odd-cell percentage-rounding bias. Component
sizes, ordering, and internal spacing remain unchanged.

The modular specialist foundation is now active: the user-selected specialist
is persisted, JARVIS Architect and Installation Specialist are selectable, the
Agents tab provides operational summaries and validated structured/raw
definition editing, and the Packages tab shares the Installation Specialist's
bounded package backend. Actions, Knowledge, Plan, and Approvals are no longer
primary tabs; approval remains a modal one-use control-plane decision. Full
visible conversation roles remain part of specialist context, subject to the
existing redaction and size limits.

Power Expert expansion was added on 2026-08-30: sanitized full topology and
software/provider inventory, passive telemetry, persistent AC/battery profile
planning, one atomic multi-control helper transaction with exact pre-state
recovery, live Power-tab updates, and explicit package-recommendation handoff
to Installation Specialist. Vendor-level capabilities remain adapter-gated.

The Agents editor was then refined into a labeled, scrollable structured form
for identity, version, purpose, context limit, network/mutation/selectability
settings, registered tools, knowledge sources, capabilities, and instructions.
Its fixed validation/activation/rollback controls remain visible while editing,
and the catalog highlight now matches the loaded definition.

Conversation rendering hard-wraps right-aligned user entries against the
TextArea's actual wrap width and soft-wraps incoming entries, preventing long
agent/tool output from opening a horizontal scrollbar without splitting the
user label from its content. The selector was widened so
multiword specialist names are not vertically clipped. The Installation
Specialist also has a deterministic cached-catalog search route for
package-availability questions; it remains read-only and does not fall back to
App Server tools, shell, network, or package mutation.
