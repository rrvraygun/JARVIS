# JARVIS codebase map

**Status:** current architecture reference
**Last reviewed:** 2026-08-28
**Generated companion:** `generated/codebase-inventory.md`

```text
User / Textual TUI
  └─ tui/src/jarvis_tui/app.py
       ├─ presentation.py       visible conversation, timeline, and status projections
       ├─ agent_registry.py      reviewed definitions, selection, drafts, activation, rollback
       ├─ agent_coordinator.py   explicit user-selected specialist context and routing
       ├─ broker.py             capture -> assess -> admit -> reserve -> complete
       ├─ models.py             immutable task, plan, assessment, admission data
       ├─ session.py            App Server threads, turns, context, event lifecycle
       ├─ app_server.py         bounded stdio JSON-RPC transport
       ├─ event_reducer.py      protocol normalization and terminal safety
       ├─ event_store.py        locked hash-chained TUI journal
       ├─ local_filesystem.py   bounded list/read/search executor
       ├─ local_mutation.py     approval-gated create/Trash executor
       ├─ package_*.py          inventory, exact planning, Polkit client
       ├─ power_*.py            inventory, telemetry, profiles, and Polkit client
       └─ conversation_manager.py private saved-conversation persistence

Registered authority boundaries
  ├─ vm-lab/scripts/jarvis_package_control.py  root-owned exact DNF helper
  ├─ vm-lab/scripts/jarvis_power_control.py    root-owned allowlisted power helper
  ├─ deployment/host/                           helper installers and Polkit policy
  └─ plugins/jarvis-system-admin/               actions, schemas, knowledge, MCP policy

Specialist plugins
  ├─ plugins/jarvis-system-architect/           general project/system guidance
  ├─ plugins/jarvis-installation-specialist/    Fedora package ownership
  └─ plugins/jarvis-power-expert/                selectable Power specialist

Evidence and rehearsal boundaries
  ├─ schemas/ and tui/schemas/                  public/domain JSON contracts
  ├─ vm-lab/                                    fixture-only controller and VM contracts
  ├─ tests/, tui/tests/, vm-lab/tests/          deterministic regression suites
  ├─ scripts/                                   launch, manifest, validation, quality tools
  └─ runtime/                                   private operational state; excluded from release source
```

## Main responsibilities

| Area | Primary files | Authority boundary |
| --- | --- | --- |
| Conversation | `app.py`, `presentation.py`, `conversation_manager.py` | UI displays state; persistence is private and cannot approve work. |
| Intent/admission | `broker.py`, `models.py`, `preflight.py` | Model output is untrusted until typed broker admission. |
| Agent transport | `session.py`, `app_server.py`, `event_reducer.py` | App Server receives an allowlisted environment and bounded protocol input. |
| Local filesystem | `local_filesystem.py`, `local_mutation.py` | Python-only descriptor-bound reads/writes; mutations consume one approval. |
| Packages/power | `package_*`, `power_*`, root helpers | Preview and one-use review bind exact operations; only Polkit helpers are privileged. |
| Audit/knowledge | `event_store.py`, plugin storage/MCP code | Content-minimizing hash chain and immutable knowledge revisions. |
| Deployment/rehearsal | `deployment/host`, `vm-lab` | Static or fixture-only unless separately installed and approved. |

## Request flow

```text
composer -> capture pending projection -> deterministic planner
  -> local read / local mutation / exact package route
  -> otherwise typed App Server preflight
  -> broker admission
  -> local executor, registered helper, or reviewed agent turn
  -> terminal projection + metadata-only audit
```

The deterministic local-result projection can be synchronized as bounded,
untrusted history for a later agent turn. It never itself grants authority.

## Staged operation modules

`observation_safety.py` bounds collector I/O. `project_snapshot.py` binds the complete
allowed source tree. `operation_workflow.py` owns proposals, ephemeral approvals,
durable reservations, isolated Cargo and new-copy project workflows.
`outcome_verification.py` checks postconditions in a separate read-only process;
`resource_guard.py` checks effective cgroup limits. `tool_scope.py` binds model tool
permissions to the controller process. `domain_views.py` keeps evidence and exact
review outside Conversation. `transcript_store.py` owns bounded sanitized records.
