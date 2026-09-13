# Phase 2 hybrid TUI MVP

> Historical design record. It does not define current TUI authority. See
> `current-product-state.md` and `tui-contract.md`.

## Result

Phase 2 is implemented and fixture-validated. Jarvis now has a navigable
Textual terminal interface that combines free-form requests, versioned catalog
actions, local knowledge search, streamed conversation, plans, and an auditable
timeline. Both request styles enter the same broker admission boundary.

This phase does not add host authority. It did not run the real Codex App
Server, submit a live model turn, inspect Fedora, execute the prepared lighting
pipeline, run a collector, install a project runtime, accept an approval, or
invoke a command. The only Textual installation used while developing this
phase was an isolated disposable virtual environment under `/tmp`.

## Phase 2B status bridge

The TUI now has an explicit `--connect-jarvisd` option for read-only status
projection. It checks the owner-only Unix socket and calls only `health.read`
and `activation.status`. The overview displays the H1 Tier-0 service state and
the local approved scope plus redacted R1/R2 recovery evidence (status,
mismatch count, and proof-gap count); it cannot call `observation.prepare`,
persist facts, execute commands, or mutate policies. It also displays the
redacted Phase 5 rehearsal result and rollback status; this is status
projection only and does not create an executor method. Offline mode remains
the default.

## Delivered interface

The MVP has six keyboard-accessible views:

1. **Overview** shows App Server state, ChatGPT authentication mode, thread and
   turn state, pending server requests, capacity, local registry counts,
   read-only knowledge status, recovered task metadata, and the current safety
   boundary.
2. **Conversation** combines natural-language requests, catalog requests,
   streamed agent messages, terminal task states, safe notices, and blocked
   request warnings.
3. **Actions** is generated from `registry/actions.json`. Search filters the
   catalog, unavailable entries retain their reason, and enabled actions open a
   form generated from their JSON input schema.
4. **Knowledge** queries the existing knowledge database in SQLite read-only
   mode by facts, sources, attempts, errors, lessons, or decisions. A missing
   store is reported and never initialized.
5. **Plan** renders bounded plan deltas, authoritative plan messages, and
   structured step states.
6. **Timeline** projects bounded broker and normalized App Server lifecycle
   events without displaying raw journal payloads.

Global navigation is available through `Ctrl+1` to `Ctrl+6`. `Escape` returns
focus to the composer and `Ctrl+X` requests interruption only when a turn is
active. Plain mode preserves state through explicit labels instead of relying
on color.

## One admission boundary

Free-form and action-form input are both captured as a typed `TaskRecord` and
then receive an immutable `TaskAdmission`. The admission result includes the
route, decision, exact action/procedure identity when present, sandbox policy,
policy digest, and these non-negotiable fields:

```text
host_authority = none
execution_authorized = false
```

The Phase 2 routes are:

| Route | Eligible work | Effect |
|---|---|---|
| `local_read` | Registered non-agent reads such as `knowledge.search` | Query the existing project knowledge store read-only; never contact App Server |
| `agent_conversation` | Natural-language requests and non-mutating registered reasoning actions | May enter the same read-only Codex thread only when both live gates are enabled |
| `blocked` | Any host-mutating action reaching admission | Deny before App Server routing |

An active turn accepts a follow-up through `turn/steer` with the exact
`expectedTurnId`. The follow-up is still captured, admitted, compiled, and
idempotently reserved as its own task. Every task correlated with the turn
receives the authoritative terminal state.

Catalog choice is not extra authority. Parameters, an action version, or a
procedure identifier cannot weaken the route. Likewise, natural language can
never create an execution route.

## App Server authentication behavior

The TUI starts offline. Its cumulative modes remain:

| Invocation flags | App Server | Configured authentication/capacity | Conversation submission |
|---|---:|---:|---:|
| none | off | unavailable | disabled |
| `--connect-app-server` | connected locally | displayed | disabled |
| `--connect-app-server --enable-live-turns` | connected locally | displayed | explicit conversation-only requests enabled |

The transport accepts the configured ChatGPT-managed or API-key authentication
mode. API-key values are never presented in the TUI, journal, or diagnostics.
ChatGPT capacity exhaustion prevents new turn submission; API-key capacity is
provider-managed and therefore reported as unavailable locally. Captured prompts
are never replayed automatically after an offline, capacity, timeout, disconnect,
or uncertain-submission state.

The two opt-in flags are implemented but were not exercised against the real
App Server in this phase. That live acceptance remains a separate user-approved
check.

## Presentation and privacy controls

- Every terminal-bound string is sanitized and capped.
- ANSI/OSC terminal controls, C1 controls, bidirectional controls, and malicious
  hyperlinks cannot be emitted as active terminal instructions.
- Agent-message deltas aggregate by item and an authoritative completed message
  replaces the partial projection.
- Safe tool lifecycle metadata may show an item type and status. Tool arguments,
  queries, results, command output, diffs, and arbitrary item payloads are not
  rendered.
- Raw reasoning is always withheld.
- A command, file-change, permission, MCP elicitation, or user-input request is
  displayed as blocked. Phase 2 has no approval response method.
- Knowledge query text is represented in the UI but only its digest, kind,
  limit, and result count enter the broker journal.
- The overview caches local integrity status; streamed tokens do not repeatedly
  query or integrity-check the database.
- SQLite connections are explicitly closed after every local read.

## Failure and recovery behavior

- Task admission is append-once and deterministic per task.
- Turn start and follow-up steering reserve separate idempotency keys before
  transmission.
- An uncertain operation blocks the task and requires deliberate resubmission;
  it is never retried automatically.
- Disconnect, protocol error, unexpected tool activity, or an unhandled server
  request blocks all tasks correlated with the turn.
- On terminal shutdown the App Server child is stopped if it was explicitly
  started. The UI owns no collector or executor process.
- Journal recovery restores only non-sensitive state and correlation metadata,
  never prompt bodies.

## Validation evidence

The deterministic test suite covers:

- equivalent no-host-authority admission for natural-language and catalog
  lighting-diagnosis requests;
- local-read isolation from App Server;
- schema-generated modal submission and form validation;
- follow-up steering and shared terminal-state correlation;
- streamed-message replacement and structured plans;
- blocked approval requests, withheld reasoning, withheld command/diff output,
  and metadata-only safe tool lifecycle rendering;
- semantic plain-mode status, keyboard navigation, compact and wide layouts;
- catalog-to-conversation and knowledge-view interactions through Textual's
  headless `run_test`/Pilot harness;
- closed read-only SQLite connections, terminal sanitization, journal
  integrity, reconnect, idempotency, and no replay.

The project validator runs the dependency-independent TUI tests with the system
Python. The real headless UI tests run when the pinned `textual==8.2.8`
dependency is installed; release validation for Phase 2 was also run inside the
isolated test environment.

## Deferred by design

Phase 2 deliberately contains no:

- Fedora scan or system specification collection;
- display-brightness or keyboard-lighting diagnosis;
- shell, arbitrary command input, command executor, collector, or privileged
  service;
- package installation, cleanup, update, repair, configuration change, data
  deletion, or self-modification;
- approval acceptance UI or App Server approval response;
- safe-list promotion or unattended automation;
- claim that the prepared lighting use case has been diagnosed on the actual
  workstation.

This historical boundary was superseded by the typed-preflight and exact App
Server approval contract in `tui-contract.md`.

## Primary references

- [Codex App Server](https://learn.chatgpt.com/docs/app-server)
- [Codex authentication](https://learn.chatgpt.com/docs/auth)
- [Codex approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security)
- [Codex with ChatGPT plans](https://help.openai.com/en/articles/11369540-using-codex-with-chatgpt)
- [Textual testing](https://textual.textualize.io/guide/testing/)
- [Textual workers](https://textual.textualize.io/guide/workers/)
- [Textual `TabbedContent`](https://textual.textualize.io/widgets/tabbed_content/)
