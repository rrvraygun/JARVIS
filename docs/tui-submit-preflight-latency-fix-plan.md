# TUI submission, preflight, and local-read fix plan

> **Implementation note (updated 2026-08-26):** the project implementation is tracked
> by [`tui-submit-preflight-latency-root-cause.md`](tui-submit-preflight-latency-root-cause.md).
> This plan remains the acceptance contract. The implementation and headless
> acceptance are fixture-validated; live App Server conversation-context
> continuity remains a user-run acceptance checkpoint.

**Status:** implemented and fixture-validated; live context handoff unverified  
**Prepared:** 2026-08-20  
**Primary prompt:**
`automation/prompts/fix-tui-submit-preflight-latency.md`

## Outcome

Submitting a request must never appear to freeze JARVIS or disappear while
intent resolution runs. Exact, non-sensitive local filesystem reads must use a
bounded deterministic executor instead of paying for a model classifier turn.
Requests with materially different plausible meanings must ask the user to
choose a scope. The UI and audit projection must distinguish capture,
classification, admission, execution, and denial truthfully.

The reference behavior is:

```text
User submits "list the files inside Escritorio"
  -> task captured and rendered immediately
  -> deterministic parser resolves list + XDG Desktop
  -> broker admits bounded local read
  -> executor lists once without shell/model/approval
  -> sanitized bounded result is rendered
  -> one completion summary is journaled
```

## Accepted decisions

| Area | Decision |
| --- | --- |
| Classification | Deterministic fast path before model preflight |
| Concurrent submission | Disable Send briefly; reject, do not queue, a second submission |
| Journal lifecycle | Optimize the existing journal; no rotation/deletion in this change |
| Local read implementation | Bounded local executor |
| Filesystem scope | Exact current-user-readable, non-sensitive paths |
| Operations | Directory list, text-file read, filename/content search |
| Ambiguity | One question with 2-3 concrete options; no inherited authority |
| Failure/retry | One attempt; record and stop; never replay automatically |

Local reads are broker-owned and therefore work without App Server connectivity.
This does not make arbitrary commands, privilege, mutation, or secret discovery
available offline.

## Evidence and diagnosis

### Observed in the current source

- `JarvisTui._dispatch_task()` awaits `session.preflight_task()` before
  `presentation.capture_task()`. Rendering is therefore coupled to classifier
  latency.
- `JarvisPresentation.capture_task()` uses a literal `host authority none`
  timeline string rather than admission data.
- Preflight creates an App Server turn with a read-only sandbox, approval policy
  `never`, and a 90-second completion timeout.
- `PREFLIGHT_OUTPUT_SCHEMA` validates individual field shapes but not the
  decision-specific invariants enforced by `IntentAssessment`.
- `EventJournal.append()` and `append_once()` parse the whole JSONL journal under
  a synchronous lock before every append.
- `process_event()` journals every normalized event. UI delta throttling happens
  later and cannot prevent session/journal cost.
- The local task runner recognizes `knowledge.search` only; the existing
  read-only host controller has no generic filesystem capability.

### Observed runtime evidence

At inspection time, `runtime/tui/events.jsonl` was about 13 MiB with 14,054
records. One task's preflight activity spanned approximately seven seconds and
terminated as a denial with reason `invalid typed preflight: ValueError`. The
raw classifier result was intentionally absent from the journal, so the exact
invalid combination is unknown.

### Root-cause model to prove during implementation

There are three independent causes:

1. **Delayed projection:** user presentation occurs after awaited admission.
2. **False/opaque denial:** the structured-output schema permits combinations
   rejected by the Python domain model, and the exception loses field-level
   context.
3. **Event-loop pressure:** synchronous O(journal-size) parsing plus `fsync` is
   performed for every streamed event.

Model latency is expected external latency. It becomes a UX bug because the UI
does not project the pending task immediately. The clear-directory-list case
should avoid that latency entirely.

## Target architecture

### Admission sequence

```text
capture
  -> render pending task
  -> deterministic preflight
       -> exact local read -> typed local plan -> broker admission -> local executor
       -> deterministic ambiguity -> clarification -> stop
       -> no safe match -> typed model preflight
            -> execute -> broker admission -> existing agent/workflow route
            -> clarify -> clarification -> stop
            -> deny/invalid -> safe reason -> stop
```

Capture is not admission. Model output is not authority. A local read plan is
data, not a shell command. Broker admission remains the only route decision.

### Proposed source layout

Use local patterns and naming discovered during implementation. The expected
smallest coherent layout is:

- `tui/src/jarvis_tui/local_filesystem.py`: typed plan, deterministic parser,
  XDG/path resolver, policy checks, and bounded executor.
- `tui/src/jarvis_tui/preflight.py`: deterministic-preflight result plus aligned
  model wire schema/prompt.
- `tui/src/jarvis_tui/models.py`: local plan and admission/domain contract.
- `tui/src/jarvis_tui/broker.py`: plan binding, admission, and metadata-only
  audit events.
- `tui/src/jarvis_tui/session.py`: fallback model preflight and stream-summary
  accumulation.
- `tui/src/jarvis_tui/event_store.py`: incremental verified journal head.
- `tui/src/jarvis_tui/presentation.py` and `app.py`: immediate pending state,
  busy guard, truthful timeline, and result rendering.
- Corresponding schemas, fixtures, tests, current docs, and release manifest.

If an existing module provides a cleaner boundary, extend it rather than
creating a duplicate abstraction.

## Workstream 1: immediate, responsive submission

Add a presentation operation such as `capture_pending_task(task)` that creates
one keyed user/action entry with status `resolving_intent`. Admission later
updates that entry and adds an admission timeline event; it does not create a
second user entry.

The submission handler must:

1. Validate and capture the input.
2. Clear only the accepted input.
3. Set a single `_submission_busy` state.
4. Disable the Send button and guard both Enter and button paths.
5. Render the pending entry and yield to Textual before awaiting classification.
6. Run classification/execution in a worker without synchronous whole-journal
   scans on the event loop.
7. Restore Send in `finally`, including clarify, deny, exception, timeout,
   disconnect, and cancellation.

Navigation and resize remain enabled. The composer may remain editable, but a
busy submission never consumes or clears the draft. Cancel must interrupt an
active classifier/turn once and settle the task without automatic replay.

## Workstream 2: deterministic local-read planning

### Typed plan

Add an immutable `LocalFilesystemReadPlan` (exact name may follow repository
style) containing:

- schema version and plan ID;
- operation enum: `list`, `read`, `search`;
- user-supplied target label;
- canonical target path;
- search mode: filename or text, and bounded query;
- recursive flag, maximum depth, item/file/match/byte limits;
- include-hidden flag;
- target metadata captured at planning time where safe;
- stable plan/target digest.

Bind it to `TaskRecord` or its assessment/admission by typed field, not an
unstructured dictionary. Re-resolve and verify the target immediately before
execution. A changed target invalidates the plan and stops.

### Conservative grammar

Recognize only clear imperative/query forms:

- English list: `list files in PATH`, `show the contents of DIRECTORY`.
- Spanish list: `lista/listar los archivos en/de PATH`,
  `muestra el contenido de DIRECTORIO`.
- English read: `read FILE`, `show the contents of FILE` when resolution proves
  it is a regular file.
- Spanish read: `lee/leer ARCHIVO`, `muestra el contenido de ARCHIVO`.
- Filename search: `find files named QUERY in PATH` and Spanish equivalents.
- Content search: `search for QUERY in PATH` and Spanish equivalents when the
  query and root are syntactically distinct.

Quoted paths and spaces must be parsed as data. Shell operators, substitutions,
redirects, and commands remain inert text and should generally prevent a fast
match. The planner may fall back to model preflight; it never executes them.

### Alias resolution

Parse `~/.config/user-dirs.dirs` as a strict data format without sourcing it.
Resolve at least Desktop/Escritorio, Documents/Documentos,
Downloads/Descargas, home, and current project/workspace. Prefer the configured
XDG path. If there is no configured value, select an existing conventional
directory only when exactly one candidate exists. Otherwise clarify.

Do not log the full personal path. The UI may show the resolved path to the
current user after terminal sanitization; the journal stores a category and
digest.

## Workstream 3: filesystem safety and bounded execution

The executor uses `pathlib`, `os.scandir`, and bounded text I/O in a worker
thread. It never invokes a shell, subprocess, privilege helper, package helper,
or App Server.

### Denied target classes

Reject at planning and re-check at execution:

- credential/key stores such as `.ssh`, `.gnupg`, cloud/Kubernetes/container
  auth locations, keyrings, and password stores;
- browser profiles, cookies, login databases, authentication databases, and
  token/session stores;
- private-key/certificate containers and secret-bearing filenames such as
  non-example `.env`, `credentials`, `id_rsa`, `id_ed25519`, `*.key`, `*.pem`,
  `*.p12`, and `*.pfx`;
- `/dev`, sensitive process internals under `/proc`, security-sensitive `/sys`
  paths, sockets, FIFOs, devices, and other non-regular file types;
- paths that become denied after symlink or canonical resolution.

The deny rules are defense in depth, not a claim to identify every secret.
Apply the repository's content redaction before rendering. Never journal
returned file/list/search content.

### Bounds

| Operation | Bounds |
| --- | --- |
| List | Non-recursive by default; 500 entries; hidden excluded unless explicit |
| Read | Regular text file; read at most 64 KiB; render at most 16,000 sanitized characters |
| Search | Depth 8; 2,000 regular files; 1 MiB/file; 200 matches; monotonic deadline |

Return structured result metadata including truncation, skipped/denied counts,
duration, and limitations. Permission errors and disappearing files are normal
typed failures, not reasons to retry.

## Workstream 4: aligned fallback preflight

Replace the flat cross-field-permissive wire contract with a root object whose
payload uses supported `anyOf` decision variants. Include separate execute
branches for explanations and target-requiring operations so target presence is
schema-enforced. Clarify requires exactly one question and 2-3 options. Deny
cannot carry an executable route.

`IntentAssessment.from_dict()` must report stable errors such as:

- `preflight.invalid_json`
- `preflight.invalid_shape`
- `preflight.invalid_decision_variant`
- `preflight.missing_target`
- `preflight.invalid_route`
- `preflight.invalid_clarification`

Exact naming can follow existing conventions, but codes must be stable, tested,
safe to display, and more useful than the Python exception class. Raw output
stays memory-only and is discarded after a bounded digest/count summary.

The model preflight remains one read-only/no-approval classifier turn. The
change removes that turn for deterministic local reads; it does not remove the
typed-preflight invariant for other execution-capable requests.

## Workstream 5: admission contract clarity

The current `execution_authorized` and `host_authority` fields conflate an App
Server execution turn with deterministic local work. Revise the contract in one
coherent schema version. A recommended compatible shape is:

- retain `route` as `local_read`, `agent_conversation`, or `blocked`;
- define `execution_authorized=true` for an admitted local read or admitted
  agent turn;
- add `agent_turn_authorized`, true only for `agent_conversation`;
- add `mutation_authorized`, false at admission unless a later exact approval
  and policy state explicitly establishes it;
- use an authority enum or equivalent value that distinguishes `none`,
  `bounded-local-read`, and `current-user-agent`;
- retain sandbox policy only when an App Server turn will actually start.

If compatibility analysis favors retaining the old fields, add the new explicit
fields and deprecate rather than silently changing old semantics. Update
`task-admission.schema.json`, fixtures, broker tests, presentation, recovery,
and docs together.

## Workstream 6: incremental event journal and stream summaries

### Journal head

On first access, scan and verify the existing chain once and cache:

- inode/file identity and modification evidence;
- verified byte offset;
- record count/next sequence;
- last event hash;
- idempotency keys needed for O(1) lookup;
- optionally parsed records for repeated `read()` projections if memory bounds
  are acceptable.

For append, take the exclusive lock and compare current file state with the
cache. Validate only a newly appended suffix. Replacement, truncation, or
in-place modification triggers a full verified rescan or a fail-closed error.
Append exactly one canonical hash-linked line, flush, `fsync`, and update cache.
Explicit `verify()` still scans the complete chain and must continue detecting
tampering.

### Delta coalescing

Do not append a record for every `agent_delta`/stream chunk. Maintain bounded
per-turn/item accumulators containing only:

- event count;
- character/byte count;
- rolling digest;
- sanitization/truncation indicator;
- start/end monotonic duration.

Flush one summary when the authoritative item completes and clean up on turn
completion, cancellation, error, or disconnect. Never retain private reasoning,
raw command output, prompt content, or file content in the accumulator/journal.

## Workstream 7: truthful presentation

Timeline entries are state transitions, not decorative prose:

- `captured`: request recorded; no admission yet;
- `resolving_intent`: deterministic/model classification in progress;
- `needs_clarification`: no authority; show the bounded question;
- `admitted/local_read`: bounded local read, no mutation/privilege;
- `admitted/agent_conversation`: actual current-user authority and sandbox;
- `blocked`: policy reason;
- `classifier_failed`: invalid classifier result, explicitly not a risk
  determination;
- terminal result: completed/failed/cancelled with safe limitations.

Render admission values rather than literals. Keep the clean Conversation view
short; place bounded diagnostic evidence in Timeline.

## Verification strategy

### Unit tests

- Parser table for English/Spanish positive, negative, and ambiguous forms.
- XDG parsing without shell evaluation, unique fallback, and ambiguity.
- Path policy for hidden, sensitive, symlink, permission, special, binary,
  oversized, disappearing, and terminal-control cases.
- List/read/search caps and deterministic ordering where promised.
- JSON-schema/domain-model decision matrix.
- Stable classifier error codes and no raw-output journal leakage.
- Incremental journal cache, external suffix, replacement/truncation,
  idempotency, permissions, tamper detection, and one-time prefix scan.
- Delta summary count/digest and cleanup.

### Headless TUI tests

- Delayed fake preflight proves immediate pending rendering before completion.
- Send/Enter busy guard and `finally` restoration.
- Navigation and resize during pending classification.
- Exact `Escritorio` request uses local route with zero App Server requests.
- No duplicate user entry across state transitions.
- Clarify, deny, classifier failure, cancellation, timeout, and disconnect.
- Timeline uses actual route/authority/reason.

### Regression and acceptance

Run once each, in this order:

1. New focused parser/executor/journal tests.
2. Existing preflight, broker, session, presentation, App Server, and headless
   TUI tests.
3. Complete `tui/tests` discovery.
4. `./scripts/validate-bundle.sh`.
5. A manual or faithful headless acceptance of
   `list the files inside Escritorio` with an existing controlled fixture.

Do not perform the acceptance against a sensitive real directory merely to
prove it works. A temporary XDG fixture is preferred. Do not rerun a failed
command automatically; record its output, diagnose, change the code if
authorized, and report any unrerun validation.

## Acceptance criteria

The change is complete only when all of these are demonstrated:

- pending user text is projected before any awaited model work;
- the exact Desktop-list request produces no model turn, shell, or approval;
- the UI remains responsive under delayed fake classification and large
  synthetic journal conditions;
- ambiguous inputs never receive execution authority;
- sensitive/special/symlink escape cases fail closed;
- schema-valid model output cannot violate `IntentAssessment` decision
  invariants;
- malformed output reports a safe stable classifier error once;
- journal append cost after initialization does not scale with the full prefix;
- stream deltas do not generate one fsynced record each;
- existing journal integrity and idempotency behavior remains intact;
- timeline authority and reason are derived from typed state, not hard-coded;
- all changed current contracts, schemas, fixtures, tests, and release hashes
  agree;
- completion evidence names anything not verified.

## Non-goals and residual risk

This fix does not create arbitrary shell access, privileged inspection,
mutation autonomy, network autonomy, unrestricted home indexing, or perfect
secret detection. Model fallback still has external latency, but the pending UI
must remain responsive and truthful. Local file reads can encounter content not
predictable from filenames; target denial, strict bounds, redaction, and
content-free auditing reduce but do not eliminate that risk.

## Rollback

All intended changes are project-only and reversible by restoring the changed
source, schema, fixture, test, documentation, and manifest files. Do not modify,
truncate, rotate, or delete `runtime/tui/events.jsonl` during implementation or
rollback. No host package, service, Polkit helper, or external system change is
part of this plan.

## Completion record required from the implementation agent

Report changed artifacts, commands actually run and their results, unverified
items, assumptions, residual risks, and rollback status. Separate observed
facts from inference. Do not claim the TUI is responsive or the acceptance case
passes without headless or manual evidence.
