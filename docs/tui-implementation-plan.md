# Jarvis terminal interface architecture and implementation plan

## Decision summary

### Current implementation addendum (2026-08-27)

The phase narrative below remains design history. The current implementation
adds the deterministic-first, approval-gated mutation slice specified by
`tui-mutation-executor.md`: exact current-user filesystem creates and
move-to-Trash use an immutable Python-only plan; exact package install/remove
uses a cache-only preview and registered Polkit helper; every mutation receives
one fresh modal decision; and broader current-user agent work remains behind
typed preflight plus App Server `untrusted` command/file review. Task-admission
schema version 3 represents these pending authorities separately from reads and
agent turns.

Build a hybrid terminal application with two equal entry points:

1. a natural-language composer for open-ended requests and follow-up questions;
2. a searchable catalog of versioned actions with typed parameters.

They are not separate execution systems. Both become one `IntentEnvelope`, enter
one conversation, and pass through the same state, evidence, policy, approval,
execution, verification, audit, and learning gates.

Use a Python frontend for the first implementation, with Textual as the leading
TUI candidate. Keep the frontend replaceable. Put orchestration in a separate
local application service and integrate Codex through `codex app-server` over
its stable JSON-RPC surface. The official Python Codex SDK may wrap that
connection where it exposes the required event and approval APIs; the
application must fall back to the generated App Server schema rather than hide
or approximate missing protocol behavior.

The implemented interactive profile uses typed preflight followed by scoped
execution. It does not create raw root authority; registered Polkit helpers
remain the preferred host-mutation boundary.

The first specialist expansion adds Fedora-first System Health and Cargo
Builder descriptors. Their typed MCP collectors inspect performance,
thermals, services, storage, local network state, Rust/Cargo, and bounded
project manifests. Builds, tests, dependency changes, and generated shell
commands remain subject to the existing exact review and project/host safety
boundaries.

The current specialist expansion also registers read-only Network, Security,
and Recovery inventory tools. They inspect local interfaces/routes/DNS,
SELinux/firewall/Secure Boot posture, and mounts/snapshot/boot recovery signals;
they do not perform external checks or host mutation.

## Subscription-only deployment decision

The initial product must work with the user's existing ChatGPT subscription and
must not require separately billed OpenAI API usage.

- Launch local `codex app-server` and use its ChatGPT-managed authentication.
- On startup, call `account/read`. If authentication is required, offer the
  App Server `account/login/start` ChatGPT flow and display the returned login
  instructions without collecting credentials in Jarvis.
- Reuse Codex's persisted and refreshed authentication. Never copy its tokens
  into Jarvis storage, logs, crash reports, or command-line arguments.
- Do not use the Responses API, the general OpenAI API SDK, or the OpenAI Agents
  SDK in the default product. Those are different integration and billing
  paths.
- The `openai-codex` Python package is acceptable only as a client for local
  Codex App Server under ChatGPT-managed auth. It must not silently switch to an
  API key.
- Do not configure `OPENAI_API_KEY`, `CODEX_API_KEY`, automatic credit purchase,
  or any paid fallback. Adding one later requires an explicit settings change
  and separate user confirmation.

Codex usage still counts against the plan's Codex/agentic allowance. The TUI
therefore needs a local-only operating layer and visible capacity state rather
than assuming the model is always available.

### Usage-aware design without reducing reliability

- Navigation, dashboards, SQLite queries, audit verification, policy
  evaluation, approval verification, and static procedure forms make no model
  call.
- Registered observations collect and store evidence without a model call.
  Invoke Codex only when the user asks for interpretation, diagnosis, planning,
  research, or an action that needs agent judgment.
- Do not poll Codex, create background turns, or start subagents merely to keep
  the interface current.
- Use one Codex thread per incident or coherent job, not one permanent global
  thread. The global Jarvis knowledge base provides durable memory; retrieve
  only relevant facts, sources, errors, and lessons for each turn.
- Persist a concise, evidence-linked task summary at completion. Resume the
  thread when its context is still useful; otherwise start a clean thread and
  supply the relevant summary.
- Use `model/list` rather than hard-coding a model name. Offer `Standard`,
  `Deep`, and `Independent review` work profiles based on the models and effort
  levels actually available to the signed-in account.
- Default to one agent. Spend extra turns or subagents only for material
  uncertainty, high-risk change review, contradictory evidence, or explicit
  user selection.
- Read current capacity through `account/rateLimits/read` and listen for
  `account/rateLimits/updated`. Display availability without inventing a token
  or task estimate that App Server does not provide.
- When Codex capacity is unavailable, keep local-only views and controls usable,
  preserve the draft request, and let the user resume later. Never switch to a
  paid API credential automatically.

This split preserves quality: deterministic work does not consume agent quota,
while the model is reserved for work where language understanding and reasoning
actually add value.

## Product goals

- Let the user move naturally between conversation and structured actions in
  the same session.
- Make simple, common operations discoverable without requiring the user to
  know Bash or remember exact prompts.
- Preserve the agent's ability to diagnose ambiguous or novel conditions.
- Automatically perform clear risk-0 reads and exact reversible risk-1 project
  creates/modifications.
- Require a deliberate exact approval for risk-2+, deletion, host mutation,
  privilege, downtime, security-sensitive work, and external effects.
- Display what is known, inferred, stale, sandbox-scoped, proposed, approved,
  executed, and verified as different states.
- Keep every operational decision traceable without storing private model
  reasoning.
- Support a later transition from a natural-language-first prototype to a
  dedicated, complete workstation console without replacing the control plane.

## Explicit non-goals for the first implementation

- No unclassified shell prompt inside the TUI.
- No persistent root shell, auto-approved direct `sudo`, or policy-bypass path.
- No direct SQLite writes from views or widgets.
- No procedure-scoped, transaction-scoped, or pre-authorized mutation.
- No automated retry after failed or unexpected output.
- No use of App Server `thread/shellCommand` or experimental `process/*` as a
  host-administration executor.
- No claim that a generated plan, an App Server approval, or a successful exit
  code is equivalent to a verified operational outcome.

## System shape

```text
 keyboard / action catalog / future scheduler
                    |
                    v
        +-------------------------+
        | jarvis-tui              |
        | presentation + consent  |
        +------------+------------+
                     | typed local protocol
                     v
        +-------------------------+
        | jarvisd                 |
        | session + task broker   |
        | policy + event reducer  |
        +---+----------+----------+
            |          |
    JSON-RPC|          |deterministic calls
            v          v
   +----------------+  +----------------------+
   | Codex          |  | Jarvis control plane |
   | app-server     |  | policy / knowledge   |
   | threads/turns  |  | approval / audit     |
   +-------+--------+  +----------+-----------+
           |                      |
           | MCP                  | future narrow adapters only
           +-----------+----------+
                       v
          registered collectors / future executor
```

### `jarvis-tui`

The frontend renders data, gathers parameters, streams events, and captures
explicit consent. It has no shell API, privilege, policy-write capability,
database connection, or raw executor handle. A compromised widget must not be
able to authorize an operation.

### `jarvisd`

The local broker is the application authority boundary. It:

- owns TUI sessions, task state, and idempotency keys;
- starts or connects to Codex App Server;
- maps App Server thread, turn, item, and request IDs to Jarvis IDs;
- validates action schemas and resolves procedure versions;
- calls the deterministic Jarvis policy and approval functions;
- rejects unregistered execution attempts;
- writes redacted decision and audit records through the control plane;
- rebuilds view state from events after a crash;
- eventually invokes only registered executor adapters.

For the prototype it may run in the same process as the frontend behind a
strict interface. Before supervised mutation is added, split it into a separate
unprivileged service reachable through a private Unix socket. The protocol must
remain identical in both deployments.

### Codex App Server

App Server supplies authentication, persistent threads, turns, item streaming,
plans, user-input requests, command/file approval requests, interruption, and
error events. Generate JSON or TypeScript schemas from the exact installed
Codex version and pin the compatible protocol in tests.

Use the stable API by default. Experimental capabilities require a separate
architecture decision, feature flag, compatibility test, and visible degraded
mode when unavailable.

For the subscription-only build, the broker launches App Server over its
default stdio JSONL transport. This avoids exposing a network listener and does
not depend on the experimental WebSocket transport. A separate TUI process may
talk to `jarvisd` through Jarvis's own private Unix-socket protocol; App Server
can remain a broker-owned child process.

### Jarvis MCP and control plane

Codex uses the existing MCP server for typed knowledge and governance tools.
The broker must still enforce policy outside the model. An instruction such as
"call the policy tool first" improves agent behavior but is not a security
boundary.

Add future observation and execution tools only after their adapter contracts
are complete:

- `observe_registered`: fixed executable/argument templates, read-only,
  bounded output, timeout, redaction, one attempt;
- `propose_action`: validates and stores an exact action context but cannot run
  it;
- `execute_approved_action`: accepts only a valid, unexpired, unconsumed,
  state-bound approval and a registered adapter revision;
- `verify_action`: runs independent validation and records the outcome.

## One pipeline for both interaction styles

### Natural-language path

1. The user submits text.
2. The broker records the text source as `natural_language` and sends it to the
   active Codex thread.
3. Codex may answer conversationally or propose a structured task.
4. The broker validates every proposed capability, procedure, parameter, and
   target. Unknown or ambiguous values return to clarification or planning.
5. The ordinary policy and lifecycle gates apply.

### Action-catalog path

1. The user selects a registered action and completes its typed form.
2. The broker records the source as `catalog_action`, resolves the exact action
   and procedure versions, and validates the fields locally.
3. It compiles a canonical, human-readable request plus structured metadata and
   sends that request into the same active Codex thread.
4. Codex receives the current conversation context and can diagnose, explain,
   plan, or ask for missing information.
5. The same policy and lifecycle gates apply.

A catalog entry is therefore an intent template, not stored Bash. Selecting
"Diagnose brightness" asks the agent to follow the registered brightness
diagnosis procedure; it does not immediately run a remembered command.

### Contextual transitions

Agent output may include validated action suggestions. For example:

```text
User: My brightness controls stopped working.
Agent: Three causes fit the current evidence.
Suggested actions:
  [Collect display/backlight evidence]  [Inspect recent updates]  [Keep planning]
```

Selecting a suggestion creates a structured follow-up in the same thread. The
user can then return to free text without losing the diagnosis or its evidence
links.

## Core data contracts

The following names describe contracts, not final storage syntax.

### `IntentEnvelope`

```json
{
  "intent_id": "uuid",
  "session_id": "uuid",
  "source": "natural_language | catalog_action | contextual_action | automation",
  "requested_mode": "observe | diagnose | plan | execute | verify | recover | learn",
  "text": "optional user text",
  "action_id": "optional registry id",
  "action_version": "optional exact version",
  "parameters": {},
  "constraints": [],
  "created_at": "RFC3339 timestamp"
}
```

### `ActionDefinition`

```json
{
  "id": "health.brightness.diagnose",
  "version": "1.0.0",
  "title": "Diagnose brightness controls",
  "capability": "health",
  "procedure": "health.assess@1.0.0",
  "mode": "diagnose",
  "input_schema": {},
  "required_facts": [],
  "risk_floor": 0,
  "mutates_host": false,
  "availability": "enabled | disabled | unavailable",
  "unavailable_reason": null
}
```

The registry owns action definitions and their UI metadata. The TUI builds its
menus from the registry so displayed capabilities cannot drift from policy.
Disabled and immature actions remain visible with a reason; hiding them would
make system limits hard to understand.

### `TaskRecord`

A task binds the normalized intent to:

- Codex `threadId`, `turnId`, and relevant `itemId` values;
- exact capability, action, and procedure versions;
- evidence and state snapshot digests;
- policy result and material warnings;
- proposed commands and action digests;
- approval request, decision, nonce, expiry, and consumption state;
- execution attempt IDs;
- validation and recovery results;
- final concise decision summary.

The record stores no private chain-of-thought.

## Task state machine

```text
captured
   -> resolving_intent
   -> needs_clarification ------+
   -> preflight                 |
   -> planning <---------------+
   -> blocked
   -> awaiting_approval
   -> approved
   -> executing
   -> verifying
   -> completed

From planning/executing/verifying:
   -> diagnosing_unexpected_result -> replanning
   -> recovery_planning -> awaiting_recovery_approval
   -> cancelled | failed
```

Only the broker changes task state. UI navigation never changes task state.
Every transition has an event ID, timestamp, actor, reason code, and links to
its input evidence.

## Approval model in the TUI

Codex sandbox approval and Jarvis operational approval are separate:

- **Codex approval** decides whether an App Server tool or command may cross its
  current sandbox/tool boundary.
- **Jarvis approval** authorizes one exact operational command under the
  versioned Jarvis policy and current system-state digest.

One screen may explain that both gates apply, but one decision must never be
silently copied into the other. A state-changing action cannot proceed merely
because App Server emitted an approval request and the user accepted it.

The initial Jarvis approval screen shows:

- exact executable and `argv[]`, with a separate escaped Bash rendering;
- working directory, environment-key allowlist, and exact targets;
- capability, procedure, and adapter versions;
- mutation, privilege, network, external-effect, downtime, destructive,
  irreversible, and self-update flags;
- computed risk and policy reasons;
- evidence/state age and state digest;
- expected output and effects, timeout, validation, rollback, and dry run;
- nonce, expiry, scope, and one-time-use status.

No approval choice is focused by default. Approve, reject, cancel, and inspect
use distinct keys. Pasted input cannot confirm an approval. Procedure and
transaction choices are displayed as disabled until policy explicitly enables
them.

## Recommended screen model

```text
+------------------+-----------------------------------------------+
| Overview         | Session: Brightness diagnosis                |
| System           |-----------------------------------------------|
| Actions          | conversation / plan / evidence cards         |
| Knowledge        |                                               |
| Errors           |                                               |
| Lessons          |                                               |
| Plans            |-----------------------------------------------|
| Approvals        | prompt > Ask or choose an action...           |
| Timeline         +-----------------------------------------------+
| Recovery         | OBSERVE | policy OK | facts: 12m | audit OK   |
| Settings         | Codex connected | no pending approval         |
+------------------+-----------------------------------------------+
```

The layout collapses into one pane plus a command palette on narrow terminals.
Every color has a text or symbol equivalent. Keyboard-only use, resize, screen
reader-friendly plain output, and recovery after terminal loss are acceptance
requirements.

### Essential interaction elements

- Composer with multi-line editing and explicit submit.
- Action palette searchable by outcome, symptom, capability, and risk.
- Typed parameter forms generated from JSON Schema.
- Conversation stream with separate user, agent, tool, evidence, warning, and
  final-answer cards.
- Plan view driven by App Server plan events but reconciled to the final plan
  item.
- Evidence inspector linking claims to local facts, documents, attempts, and
  source provenance.
- Exact approval screen, never a generic "Are you sure?" dialog.
- Live output view with stdout/stderr separation, size limits, redaction, and a
  clear observation-scope label.
- Persistent cancel/interrupt control.
- Recovery banner for disconnected App Server, unresolved request, corrupt
  audit chain, locked encryption, or stale state.

## Command and output safety

- Internally represent commands as executable plus `argv[]`; never construct
  shell text by concatenating user input.
- Show shell syntax only as an escaped rendering for review.
- Treat command output, logs, documentation, package metadata, terminal titles,
  hyperlinks, and pasted text as untrusted data.
- Strip or visibly escape ANSI CSI/OSC/control sequences before rendering to
  prevent terminal escape injection.
- Do not make URLs or file paths executable on click by default.
- Cap live display and storage independently. Truncation must be visible and
  preserve the digest of the complete allowed record.
- Never auto-submit pasted text and warn before accepting a large or multi-line
  paste.
- If output violates an expectation, record the single attempt, stop, enter
  Diagnose, and require a new plan and approval. Do not expose a Retry button.

## Session and persistence behavior

- One Jarvis session normally maps to one resumed Codex thread.
- Store thread and turn identifiers, but treat Codex rollout history as context,
  not the audit authority.
- Persist UI/task events before acknowledging state-changing transitions.
- On restart, reconstruct the last safe view from the event sequence and query
  App Server for thread status.
- Never assume a pending request remains valid after reconnect. Reconcile it
  through App Server and Jarvis approval state.
- Expire unconsumed approvals on state mismatch, process restart when required,
  policy revision, adapter revision, or timeout.
- Keep authentication material in Codex's supported credential store. Do not
  copy tokens into the Jarvis database, logs, environment display, or crash
  reports.

## Failure and degraded modes

| Failure | Required behavior |
|---|---|
| App Server unavailable | Conversation disabled; local history remains readable |
| App Server disconnects mid-turn | Mark uncertain, reconnect, read thread state, never replay input automatically |
| Broker restarts | Rebuild from events; approvals stay unconsumed or expire according to policy |
| TUI crashes | Restore terminal; no execution is triggered by shutdown |
| Jarvis MCP unavailable | Fail closed for operational tasks |
| Knowledge database locked | Show read-only degraded mode; do not create substitute storage |
| Audit verification fails | Block mutation and show recovery guidance |
| Evidence stale | Permit explanation; block action until refreshed or explicitly handled by policy |
| Output unexpected | Record once, diagnose, replan; no automatic retry |
| Schema/version mismatch | Refuse unsupported feature and show required/observed versions |

## Technology decision

### Recommended first implementation: Python + Textual

Reasons:

- the control plane, knowledge store, tests, and official Codex Python SDK are
  already Python-compatible;
- Textual is asynchronous and provides headless interaction testing, which fits
  streamed App Server events and approval-state tests;
- typed Python domain objects can be shared by the broker and prototype UI;
- it minimizes integration work while the security and interaction contracts
  are still changing.

This is a delivery choice, not a trust decision. Textual code remains outside
the authority boundary.

### Later alternative: Rust + Ratatui

Consider a Ratatui frontend after the protocol stabilizes if a small native
binary, tighter resource use, or long-term terminal portability justifies a
rewrite. Ratatui offers a test backend and strong terminal primitives, but a
rewrite now would duplicate the existing Python integration and slow validation
of the more important policy and approval design.

### Not selected initially: TypeScript + Ink

Ink aligns with the TypeScript Codex SDK and React skills, but adds a second
application runtime without a clear advantage over Textual for this Python-heavy
bundle. Reconsider only if the application later standardizes on a TypeScript
backend.

## Delivery phases

### Phase 0: architecture decisions and fixtures

- Approve this boundary model and write architecture decision records.
- Define `IntentEnvelope`, `ActionDefinition`, `TaskRecord`, event, and broker
  protocol schemas.
- Extend existing procedure registry with typed UI metadata.
- Create fixture conversations, action selections, approvals, unexpected
  output, disconnects, and restarts.
- Pin the minimum compatible Codex/App Server protocol and generate schemas.

Exit: schema validation passes and no component can express raw execution.

### Phase 1: read-only broker

- Implement App Server startup over stdio, initialization, ChatGPT-managed
  auth-state display/login, rate-limit display, thread start/resume, turn
  start/steer/interrupt, and event normalization.
- Implement the local broker API and append-only UI/task event journal.
- Connect read-only knowledge queries and current capability listing.
- Add strict event correlation and idempotency.

Exit: a headless client can converse, resume, cancel, and recover from a forced
disconnect without running Fedora commands or using an API key.

### Phase 2: hybrid TUI MVP

- Build overview, conversation, actions, knowledge, plan, and timeline views.
- Add natural-language input and schema-generated action forms.
- Compile catalog selections into the same Codex thread.
- Render streamed agent messages, plans, tool items, warnings, and final states.
- Add terminal sanitization, output caps, resize handling, and crash cleanup.

Exit: equivalent natural-language and catalog requests converge on an
equivalent normalized task and policy result.

### Phase 3: approvals without host mutation

- Render App Server requests and Jarvis approvals as distinct objects.
- Implement the exact approval screen and nonce/digest/expiry lifecycle.
- Use simulated adapters only; test accept, reject, cancel, timeout, replay,
  stale state, amendments, and concurrent requests.
- Reject raw or unregistered command attempts.

Exit: adversarial tests cannot bypass, reuse, broaden, or confuse an approval.

### Phase 4: registered read-only observations

- Add `observe_registered` behind the existing collector registry.
- Automatically admit only commands proven by deterministic policy to be
  low-risk and read-only.
- Record attempt, output expectations, observation scope, and freshness.
- Start with fixtures, then use only bounded enrolled read-only adapters on the
  actual workstation. A disposable Fedora VM is optional for representative
  software-only observations and cannot substitute for physical hardware
  evidence.

Exit: every observation is bounded, redacted, attributed, auditable, and stops
after unexpected output.

### Phase 5: supervised mutation foundation

- Design a narrow executor service and adapter protocol.
- Prefer a root-owned service with Polkit or an equivalent OS authorization
  boundary over giving the TUI, broker, or model a root shell.
- Implement one reversible, low-blast-radius typed adapter behind the external
  authorization boundary. Rehearse it with fixtures and an isolated scratch
  target or optional representative VM, then require action-specific recovery
  and exact approval for its first supervised workstation use.
- Require command-scoped Jarvis approval, pre-change evidence, recovery,
  postcondition validation, and independent review.

Exit: the single adapter meets capability stage 4. No other mutation inherits
that maturity.

### Phase 6: complete operational console

- Add errors, lessons, recovery, settings, audit integrity, encryption state,
  and remote-sink status views.
- Add contextual recommended actions and cross-link every recommendation to
  evidence and procedure revisions.
- Add exportable, redacted incident and maintenance reports.
- Add optional desktop notifications without allowing them to approve work.

Exit: all views in `tui-contract.md` meet functional, accessibility, privacy,
and recovery acceptance tests.

### Phase 7: increasing autonomy

- Observe successful procedures long enough to build independent evidence.
- Promote only explicit procedure revisions through the capability maturity
  model.
- Keep the pre-authorized safe list off until a stage-5 policy is approved.
- Never infer broad authority from repeated use or from an active lesson.

Exit: autonomy is procedure-specific, bounded, revocable, monitored, and
recoverable.

## Test strategy

### Unit and property tests

- Schema validation and canonical serialization.
- Command/action digest stability.
- Risk classification and policy monotonicity.
- Approval expiry, replay rejection, target binding, and state binding.
- Event reducer determinism and idempotency.
- ANSI/control-sequence neutralization and redaction.
- Registry-to-menu generation and disabled-state reasons.

### Integration tests

- Fake App Server event streams, including out-of-order and duplicate events.
- Real App Server with a temporary Codex home and generated versioned schemas.
- Natural-language and action-catalog convergence.
- Thread resume, turn steering, interruption, compaction, and reconnect.
- App Server approval and Jarvis approval displayed without scope confusion.
- Locked database, failed MCP startup, and corrupt audit-chain behavior.

### TUI tests

- Headless keyboard workflows and snapshots at several terminal sizes.
- No default focus on approval.
- Paste cannot submit or approve.
- Cancel remains reachable while output streams.
- Plain/no-color mode carries all state semantics.
- Terminal mode and cursor are restored after normal exit and simulated crash.

### Security tests

- Prompt injection in logs, package descriptions, documentation, and MCP output.
- Escape-sequence and malicious hyperlink output.
- Action parameter injection and argument-boundary preservation.
- Forged, stale, replayed, broadened, and cross-session approvals.
- Symlink/path replacement between planning and execution.
- Broker/TUI compromise simulations proving no raw privileged channel exists.

## Release acceptance criteria

- Both input styles share one normalized task pipeline and conversation.
- The action catalog is registry-generated and version-aware.
- A frontend process cannot execute a host command or mutate authority stores.
- Every proposed action has an exact target, risk, evidence, validation, and
  recovery status.
- Every state change requires an exact command approval in the initial release.
- App Server and Jarvis approvals cannot be mistaken for each other.
- No unexpected result causes automatic retry or progression.
- Crash/reconnect tests leave no ambiguous execution or consumed approval.
- Audit failure, stale state, locked secrets, or unavailable governance fails
  closed for mutation.
- Documentation states which capabilities remain simulated, unimplemented, or
  unverified on the live workstation.

## First implementation slice

The smallest useful slice should contain only:

1. a private local broker;
2. App Server connect/start, thread start/resume, one streamed turn, and cancel;
3. a Textual shell with Overview, Conversation, Actions, and Timeline;
4. natural-language input;
5. three non-executing actions: explain system status, search local knowledge,
   and prepare a health-check plan;
6. normalized task and UI-event schemas;
7. fake-server, headless-TUI, redaction, and reconnect tests.

It also includes an offline/capacity-exhausted fixture proving that all local
views still work and that queued prompts are not replayed automatically.

That slice validates the interaction model before introducing even read-only
host collectors.

### Implemented preparation checkpoint

This checkpoint was superseded on 2026-08-18 by the unified authority pipeline.
The older phase documents are design history and do not define current TUI
runtime behavior. Current authority is defined by `tui-contract.md`,
`shared-contract.md`, and the code/configuration named below.

The repository now contains:

- typed intent, action, task, and broker-event schemas;
- the stable App Server JSON Schema generated from and pinned to
  `codex-cli 0.146.0`, plus compatibility tests for every allowed method and
  security-relevant wire value;
- registry-generated action discovery and schema-driven parameter capture;
- one normalization path for natural-language and catalog requests;
- an App Server stdio client supporting managed ChatGPT or API-key auth and
  denying every method outside the pinned account/thread/turn allowlist;
- thread start/resume, typed preflight, opt-in execution turns, exact
  command/file responses, and interruption; active-turn steering is disabled;
- active clean-Conversation context synchronized through the pinned
  `thread/inject_items` method, with a 64,000-character cap, whole-exchange
  pruning, fresh-thread epochs, and no local-result persistence in JARVIS;
- normalized event reduction, lifecycle-derived status for status-less items,
  terminal neutralization, correlation, and out-of-order/duplicate handling;
- atomic task submission reservations, metadata-only recovery, and no automatic
  prompt replay;
- read-only capability, action, and knowledge access that never initializes a
  missing store;
- a private hash-chained broker journal and terminal-output neutralization;
- the initial Textual Overview, Actions, Conversation/Timeline, Composer, and
  status layout;
- the complete Phase 2 Overview, Conversation, Actions, Knowledge, Plan, and
  Timeline views, deterministic presentation state, schema-generated modal
  forms, keyboard navigation, plain mode, and headless interaction tests;
- deterministic typed assessment and admission with local-read, scoped
  execution, clarification, and blocked outcomes;
- `dangerFullAccess` as the current OS user with Codex `untrusted` review,
  automatic exact network reads, one-use risk-2+ confirmation, target matching,
  permanent denials, and no persistent approval choices;
- one Approvals view for real App Server command/file requests; the former
  simulation surface is no longer wired into the TUI;
- a prepared display-brightness/keyboard-lighting use case and fixtures;
- a fixture-only Fedora system-twin/scenario laboratory with an unobserved host
  profile, unresolved official-image lock, isolation/reset/promotion policies,
  37 curated regressions, 64,512 lighting state cases, 60,480 control-plane
  state cases, and ten explicitly open physical gaps.
- a contract-only future VM controller with 18 disabled typed operations and an
  unapproved 90-fact workstation-enrollment proposal across 32 disabled,
  offline, non-mutating source definitions and three consent tiers.

Real App Server validation and privileged-helper deployment remain environment
checkpoints. Fixture validation covers App Server approval responses and typed
admission. Actual VM provisioning is optional rather than a completion gate.
Connection and execution submission remain off by default and require separate
explicit CLI flags.

## Roadmap from the current checkpoint to completion

| Phase | Status | Completion gate |
|---|---|---|
| 0 — architecture and fixtures | complete | schemas and execution-free fixtures validate |
| 1 — read-only broker | fixture-complete; live acceptance deferred | explicit user-run smoke test confirms connect, resume, stream, interrupt, and disconnect against the installed App Server without a Fedora command |
| 2 — hybrid TUI MVP | complete; fixture-validated | all core views and headless interaction tests pass; natural language and catalog actions converge on the same no-host-authority boundary |
| 3 — approvals without mutation | complete; fixture-validated | adversarial simulated-approval tests prove exact scope, expiry, state/policy/adapter binding, amendment invalidation, deliberate input, and replay rejection |
| 4 — registered observations | L0 and L1 contracts fixture-complete; workstation H1 enrolled; typed TUI adapter integration pending | fixtures plus bounded real-host evidence prove redacted one-attempt observations that stop on surprises; optional VM coverage is capability-specific |
| 5 — supervised mutation | planned | one reversible typed adapter reaches maturity stage 4 behind a separate OS authorization boundary with verified recovery and exact approval; VM rehearsal is optional when representative |
| 6 — operational console | planned | every contract view passes function, accessibility, privacy, integrity, and crash-recovery acceptance tests |
| 7 — bounded autonomy | planned, initially off | only procedure-specific stage-5 policies can enter a revocable safe list after reviewed evidence and explicit user approval |

The definitive product is complete only when the Phase 6 console gates pass and
the chosen operational adapters have individually passed Phase 5. Phase 7 is an
optional maturity track, not a prerequisite for a safe supervised release. No
capability becomes trusted merely because an earlier phase completed.

The Phase 4 structural evidence and remaining L1–L7 checkpoints are documented
in `phase-4-vm-lab-prerequisite.md` and `../vm-lab/README.md`. Fixture
coverage is capped at maturity Stage 1; it cannot substitute for a real guest or
physical workstation evidence.
The controller/enrollment sub-checkpoint is documented in
`phase-4-l1-controller-enrollment.md`; its prepared proposal grants no
observation authority.

## Official and primary references

- Codex App Server: https://learn.chatgpt.com/docs/app-server
- Codex Python and TypeScript SDKs: https://learn.chatgpt.com/docs/codex-sdk
- Codex access through ChatGPT plans:
  https://help.openai.com/en/articles/11369540-using-codex-with-chatgpt
- Flexible usage and credits (optional, not enabled by this design):
  https://help.openai.com/en/articles/12642688
- Codex approval and sandbox model:
  https://learn.chatgpt.com/docs/agent-approvals-security
- Codex MCP configuration: https://learn.chatgpt.com/docs/extend/mcp
- Textual testing: https://textual.textualize.io/guide/testing/
- Ratatui concepts and test backend: https://ratatui.rs/concepts/backends/
