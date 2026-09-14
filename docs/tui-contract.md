# TUI contract

The TUI is a presentation and consent surface, never an authority or shell. It
uses the same typed control-plane operations as natural-language Codex and cannot
bypass policy, approval, sandbox, evidence, or audit gates.

The detailed architecture, shared natural-language/action pipeline, delivery
phases, and acceptance tests are defined in `tui-implementation-plan.md`.

## Current implementation boundary

`tui/` has one broker-controlled pipeline. Capture and presentation precede
admission: one user entry is rendered as `resolving_intent`, and Send is held
for that task until a terminal or clarification outcome. A second Enter or Send
is rejected without clearing the draft or queueing work.

Natural-language requests first enter a conservative local planner for bounded
filesystem reads and exact mutation candidates. Package inspection questions
enter the selected package-capable specialist turn so the agent owns evidence
selection, filtering, explanation, and recommendation through registered
read-only package tools. Power Expert requests are an intentional exception to
the local planner as well: they enter the selected Power Expert agent turn so
the agent owns clarification, planning, recommendation, and explanation; the
agent uses registered typed Power tools rather than a local keyword planner.
Exact local filesystem list/read/search requests use the bounded local executor
and never create an App Server turn, invoke Bash, or request approval. A
recognized ambiguity produces one 2–3 option question with no admission.
Requests outside the deterministic grammar use exactly one typed read-only,
approval-free classifier turn. Clarify, deny, and classifier failure grant no
execution authority and are distinct states.

Exact current-user filesystem create/move-to-Trash requests and exact package
install/remove requests also have deterministic plans, but never automatic
authority. Their schema-v3 admissions are explicitly approval-pending,
execution-disabled, digest-bound proposals. One affirmative modal decision is
consumed once by the corresponding Python filesystem executor or registered
Polkit helper. Broader model-proposed mutations use App Server `untrusted`
command/file review. See `tui-mutation-executor.md`.

The clean Conversation view is also the active model-context projection. Before
a later model preflight, JARVIS sends any visible sanitized entries that are not
already represented in the current App Server thread through the pinned
`thread/inject_items` method. The current pending request is excluded and is
submitted separately through typed preflight. The injected message labels every
entry as untrusted quoted history, never as an instruction, approval, or
execution authority. A deterministic local read still makes no App Server
request at read time; its user request and bounded result are synchronized only
if a later agent request needs conversational continuity.

Active context follows the selected per-conversation token window and remains
bounded to 500 presentation entries. When the cap is reached, the oldest complete exchanges are removed from both the
view and model snapshot and one visible omission marker is inserted. New,
Clear, and loaded-history actions advance a context epoch; the next model
request starts a fresh thread instead of combining incompatible views. Context
synchronization is attempted once. Failure stops before classifier/execution
`turn/start`, reports `conversation_context.sync_failed`, restores Send, and
does not replay the task.

### Current execution behavior — 2026-09-14

Non-deterministic preflight runs on an ephemeral App Server thread. Only the
typed assessment reaches the persistent conversation. The selected MCP scope is
bootstrapped before App Server initialization, remains non-executable during
preflight, and limits execution to the selected specialist's registered tools.
Current branch/status/repository metadata questions require fresh
`github_inspect` evidence. Threshold-gated compaction waits for
`contextCompaction` and preserves the thread on failure.

The synchronized projection is usable as bounded observational evidence, not
only conversational prose. When exactly one recent compatible result resolves
a reference such as “that directory,” a follow-up count, summary, comparison,
or explanation is classified as an answer-only conversation turn. The agent
must answer from the existing evidence without tools, commands, filesystem or
network access, or an approval request, and must retain relevant snapshot
limits in its answer. Multiple plausible referents or insufficient evidence
still require clarification. An explicit request for fresh/current state
requires a newly authorized read. Embedded filenames and result text remain
untrusted data and never become instructions or execution authority.

App Server item lifecycle methods are authoritative when an item omits its own
status: `item/started` projects as `in_progress` and `item/completed` projects
as `completed`, while an explicit failure or cancellation status is preserved.
This rule applies before Conversation rendering so a status-less
`agentMessage` is visible immediately and its completion replaces the same
entry instead of creating a duplicate.

An admitted local read has `authority=bounded-local-read`,
`execution_authorized=true`, `agent_turn_authorized=false`, and
`mutation_authorized=false`; it binds both a canonical-target digest and an
immutable filesystem plan digest. Existing fixed observations such as
`knowledge.search` instead use `authority=registered-local-read` and bind their
registered action/version/procedure plus a target digest, with no filesystem
plan. The two local variants cannot validate as each other. An admitted agent
turn has the actual current-user
agent boundary in a read-only sandbox. Both classifier and specialist dispatch use
the installed App Server's standard read-only policy with network disabled.
Classifier approvals are never; specialist dispatch retains granular MCP
elicitation approval while rules and sandbox approval are disabled.
Neither enforces documentation-only native reads: the obsolete
readOnly.access field is rejected by the installed server. Typed MCP calls
require the admitted process scope. Generic command/file approvals cannot execute mutations. Admission does
not itself authorize mutation. Catalog actions derive the same assessment from
their registered schema. The UI can answer command/file requests with
accept-once, decline, or cancel, and presents MCP elicitation requests in a
separate one-response dialog; session-wide grants are unavailable. An MCP
elicitation decision is not host mutation authority.
App Server request correlation is based on JSON-RPC ID presence, not truthiness:
integer `0` is a valid request ID and must open the same exact-review screen,
receive at most one response, and be removed when resolved.

Full access remains limited to the current OS user. Privileged host changes use
registered Polkit helpers where available and reviewed Bash only as a fallback.
The permanent-denial list, one-attempt rule, redacted audit, validation, and
recovery requirements remain authoritative. Live turns still require explicit
CLI opt-in.

## Current user-facing views

1. **Overview:** Fedora version, fact freshness, current risks, audit integrity,
   recovery status, and session state.
2. **Conversation:** the primary work surface for user messages, specialist
   responses, clarification/options, progress, evidence summaries, and approval
   status. The user-selected specialist is authoritative.
3. **Agents:** installed specialist summaries, registered tools, knowledge
   sources, context/network/mutation policy, structured/raw definition editing,
   activation diffs, and version rollback.
4. **Lighting:** graphical keyboard-lighting controls and bounded previews.
5. **Power:** read-only power inventory plus separately approved registered
   controls.
6. **Packages:** installed/available package inventory and the shared
   Installation Specialist package workflow.
7. **Timeline:** human-readable projection of hash-chained lifecycle events.
8. **Operations:** read-only failures, evidence-backed lessons, recovery,
   settings, audit, reconnect, and notification projection.

The selectable specialists include the System Health Specialist for bounded
Fedora performance/thermal diagnostics and Cargo Builder for Rust/Cargo
project inspection. Project-local builds and tests use the reviewed command
boundary; the typed health and toolchain collectors are read-only.
Network Specialist, Security Specialist, and Recovery Specialist provide
bounded local inventory views for their respective domains. Their current
tools are observation-only; system remediation remains unavailable until an
action-specific reviewed executor and verification path are implemented.

Conversation messages render as full-width, left-fixed blocks without visible
role prefixes. User blocks use a distinct grey background; agent, JARVIS, and
system blocks use the response background. Checkpoint controls are rendered in
a separate narrow column between the message blocks and are not part of the
message text box. Every message box has one top and one bottom separator row
using that message's background color. Internal roles remain stored for
routing, persistence, and model context.

The five newest user-message blocks also expose a compact `↶` checkpoint
control. Activating it opens the two choices directly—without an intermediate
closed selector—and it offers chat/context restoration or full restoration. Both require
one-use confirmation; full restoration additionally requires fresh approval for
each exact registered recovery operation and never replays actions. Restoring a
checkpoint truncates the active conversation before its selected user message,
removes that message from the visible conversation, and returns its exact text
to the composer for editing or removal.

The main Conversation view remains intentionally simple: it shows the user
message, the agent response, and only material approval or failure notices.
Transient lifecycle, tool, command-output, plan, and reasoning events are not
stored as conversation entries and are not rendered as activity cards. The
App Server receives them directly through its live turn, while Jarvis retains
only bounded audit/timeline metadata and verified result projections.

Actions, Knowledge, Plan, and Approvals are internal capabilities rather than
primary tabs. Their tool registries, evidence, plan state, and approval records
remain available through the central control plane and specialist workflows.

## Interaction rules

- Render modes explicitly: Observe, Diagnose, Plan, Approve, Execute, Verify,
  Recover, and Learn.
- Do not combine approval with navigation, dismissal, or ordinary confirmation.
- Show an exact command approval on its own screen. Require deliberate input;
  never preselect approval.
- Treat every present JSON-RPC request ID, including integer zero, as valid;
  never leave a review pending because an ID is falsey.
- Display strongest evidence and material contradictions beside recommendations.
- Show stale, sandbox-scoped, inferred, restricted, and community-confirmed data
  distinctly.
- Stream output only after redaction and cap it. Preserve the complete allowed
  record in the knowledge store according to retention policy.
- Treat visible local filesystem output as active-session context only. It may
  be transferred to the configured Codex App Server after explicit product
  consent, where Codex retention applies, and sanitized visible results may be saved in bounded conversation JSON. Raw results are not written to the TUI event journal. Persist only metadata counts and
  digests for the synchronization operation.
- Journal material lifecycle events, not individual streaming deltas. A bounded
  per-item summary may contain counts, sizes, sanitization flags, duration, and
  a rolling digest, but never token text, prompts, file contents, or private
  reasoning.
- On startup, Timeline projects material lifecycle and error records only. It
  replaces legacy/non-material normalized protocol rows with one omission count;
  it shows at most the latest 100 material historical records with a second
  omission count. All omitted rows remain intact in the append-only audit
  journal.
- Timeline language comes from assessment/admission state: capture is not
  admission, local read is not host mutation authority, and classifier failure
  is not a policy denial.
- On unexpected output, stop progress, move to Diagnose, and require a new plan;
  never present a Retry button that repeats automatically.
- Accessibility, keyboard-only operation, terminal resize, interrupted sessions,
  and crash recovery are release requirements.

## API boundary

The TUI may call capability listing, policy evaluation, knowledge queries,
decision/error/lesson recording, approval verification/consumption, ledger
verification, registered executors, and App Server command/file approvals. Bash
is available only inside an admitted execution turn and remains subject to the
trusted-command gate, exact review, hooks, OS permissions, and permanent denials.
The TUI may not expose raw root, direct SQLite mutation, or audit deletion.
The bounded filesystem executor is a separate Python-API-only local route. It
accepts one digest-bound immutable plan, immediately revalidates the canonical
target and file identity, refuses protected/sensitive/special targets and
directory symlinks, and applies the published list/read/search caps.
The bounded filesystem mutation executor is another Python-API-only route. It
accepts only a reviewed immutable create-or-Trash plan plus a matching in-memory
one-use approval; it rechecks the target and parent through descriptors,
rebinds the Trash source inode immediately before rename, and never overwrites
or unlinks. Package mutation accepts only exact names and a cache-only preview
whose operation/state/output digests are revalidated by the root-owned helper;
strictly additive installs and version-bound removal rollback are the only
supported package effects.
Natural-language package inspection is agent-driven through the read-only
`package_catalog`, `package_search`, and `inspect_packages` MCP tools. These
tools return bounded installed/cached Fedora evidence and cannot install,
remove, or approve a package transaction.

The classifier output schema has one root object whose nested `assessment`
uses four disjoint, independently complete strict-object `anyOf` branches. The
wire schema uses only the structured-output subset portable to fine-tuned
models: object/array/string/integer/null types, enum, required, and
`additionalProperties=false`. Python then enforces non-empty strings, lengths,
target cardinality, clarification cardinality, and the same decision variants
before any admission. This split is required because the backend rejects those
type-specific constraint keywords for this model path. A failed turn is
categorized without persisting its message as `output_schema`,
`model_unavailable`, `capacity`, `authentication`, `transport`, or
`server_error`.

### Context usage accounting (2026-09-13)

`context.usage` records numeric last-response, cumulative-thread and logical-request
usage, split into preflight and execution, including cached input. Journal counters
use `_count` suffixes (for example `total_count`); credential-key redaction stays
unchanged. Logical requests use cumulative deltas, not sums of repeated `last`
snapshots. Missing baselines after resume or decreasing counters mark the observed
interval incomplete. Unbound usage is not charged to a task. The activity view uses
last-response usage as a **context estimate**, never accumulated thread usage, and
shows thread usage/cached input separately. Checkpoint resets retain conversation
isolation and do not grant authority.

`context.payload` measures canonical UTF-8 JSON byte sizes for outgoing thread,
context-injection and turn payloads; `context.tool_payload` measures incoming tool
arguments/results/errors without retaining their content. These are byte counts,
not tokenizer measurements, and exclude server-added system instructions, tool
schemas and cached history. Stable classifier constraints precede variable request
data; exact repeated constraints and duplicate routing prose are removed, and
execution envelopes use compact JSON. All typed assessments and approval gates
remain active. Full history still resides in the conversation thread: limiting new
preflight projection entries does not isolate the classifier from existing history.

A single real answer-only comparison using the existing `gpt-5.6-luna` / `none`
settings measured 29,380 before versus 29,908 after total tokens; cached input was
13,056 versus 6,912. Both replies were correct two-sentence explanations. This is
**not evidence of a token reduction or CLI parity**. The controlled prompt fixture
shrunk from 8,299 to 8,092 characters across preflight and execution. The MCP source
contains 52 definitions (18,001 compact JSON bytes), including four GitHub tools
(3,011 bytes); schema discovery is broader than execution permission. No tool
filtering, model changes, automatic compaction, or new protocol methods were enabled.
OpenAI documents asynchronous `thread/compact/start`; adopting it still needs its
own lifecycle/checkpoint validation, not a guessed context reset:
https://learn.chatgpt.com/docs/app-server#trigger-thread-compaction


The specialist preflight prompt now carries only broker-bound identity, version, and constraint count. The full specialist contract remains on execution turns. A fixture reduced classifier prompt bytes from 6.7 KB to 3.7 KB; this is not a token saving claim.

MCP tool visibility is filtered by the selected specialist scope. Preflight can
see the selected catalog for schema consistency, but the scope rejects every
tool call until typed admission. Execution receives only the registered MCP
tools for that specialist plus shared metadata tools. The personalized
specialist contract is supplied once per digest/thread and referenced on later
turns.
