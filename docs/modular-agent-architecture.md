# Modular specialist architecture

**Status:** active implementation
**Updated:** 2026-08-29

## Purpose

JARVIS is a user-selected specialist system. The user chooses the specialist
from the Conversation selector; a request never silently changes specialists.
Each specialist supplies bounded instructions, knowledge references, registered
tool references, context policy, network policy, and mutation policy. The
central broker/control plane remains the only authority that can admit,
approve, reserve, or execute an operation.

## Current specialists

| Specialist | Selection | Responsibility |
| --- | --- | --- |
| JARVIS Architect | selectable | General project, system, and specialist-design guidance |
| Installation Specialist | selectable | Fedora package inventory, explanations, exact DNF install/remove, verification, recovery, and rollback |
| Power Expert | selectable | Hardware/software power inventory, telemetry, profile planning, approved profile changes, and package recommendations with Installation Specialist handoff |

Specialist descriptors live in reviewed local plugins at
`plugins/*/specialist.json`. The TUI loads them through
`tui/src/jarvis_tui/agent_registry.py`. Invalid descriptors and unregistered
tool references are ignored or rejected fail-closed.

## User surfaces

The normal workspace retains Overview, Conversation, Lighting, Power,
Packages, Timeline, and Operations. Actions, Knowledge, Plan, and Approvals
are no longer primary tabs:

- registered actions are internal tool metadata;
- knowledge is specialist-owned retrieval and evidence;
- plan/progress is projected in Conversation and status records;
- approval remains a modal one-use control-plane decision.

The Agents tab appears immediately after Conversation. It shows operational
agent summaries, registered tools, knowledge references, context policy,
network/mutation policy, and version state. It offers both structured and raw
JSON definition editing.

## Definition lifecycle

Only reviewed installed agent IDs may be edited. An edit is first held as an
in-memory draft, then validated for schema, bounds, policy values, and
registered-tool references. The exact diff is shown in a confirmation modal.
One fresh approval atomically activates the definition. The previous active
definition is archived under the owner-only runtime state directory and can be
restored with another one-use approval.

The editor can select existing registered tools but cannot create executable
commands or bypass central privilege, network, approval, audit, or recovery
rules. Agent definitions are configuration, not authority.

## Context contract

The selected specialist receives the complete bounded visible Conversation
transcript plus its specialist-specific context prompt and bounded evidence.
The transcript contains all visible roles, including user messages,
clarifications, JARVIS questions/options, action results, system status, and
agent responses. Persisted specialist transcripts use existing conversation
limits and terminal redaction. Private reasoning, credentials, tokens, and
unredacted sensitive environment data are never persisted.

The selected specialist ID and version are attached to the task context and the
last selection is restored from owner-only runtime state after restart.

## Installation Specialist contract

The Packages tab and package-related Conversation operations use the same
bounded package backend. The Installation Specialist is limited to the current
Fedora workflow: exact RPM roots, installed/cached catalog inspection,
cache-only DNF previews, additive-install and bounded-removal checks, the
registered root helper, exact one-use approval, post-state verification, and
separately approved recovery/rollback. Official upstream downloads, repository
changes, arbitrary DNF options, and other package managers remain outside this
specialist until separately designed.

Natural-language package inspections use the selected specialist and fresh typed
MCP evidence. The Packages view remains a separate local inventory surface. The
model-facing MCP rejects tools outside its broker-owned process scope, even when
an agent knows the tool name. Scope is established after admission and revoked
at turn completion. No model-facing tool can activate a lesson.

## Extension rules

New specialists enter through reviewed local plugins. A descriptor may declare
network access only through its explicit policy value; undeclared network use
is not available. Handoffs, when later added, pass through the coordinator and
preserve the visible transcript. One specialist cannot grant authority to
another.
