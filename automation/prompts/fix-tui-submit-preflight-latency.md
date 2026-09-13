# Prompt: fix JARVIS TUI submission latency and false preflight denial

You are the primary implementation agent for the repository at:

`/home/tipexxx/Escritorio/Proyecto/codex-agent-system`

You have a 1M-token context window. Use it to build an accurate first-party
codebase map, verify the supplied evidence, implement the fix completely, and
validate the result. Do not stop after proposing a patch. Do not assume the
diagnosis below is correct merely because it is in this prompt; reproduce or
prove each relevant claim from the current checkout.

The detailed, durable plan is in
`docs/tui-submit-preflight-latency-fix-plan.md`. Treat that plan, `AGENTS.md`,
and the current documentation listed by `AGENTS.md` as the task contract. If
they conflict, follow the higher-priority repository instruction and record the
conflict rather than silently choosing a weaker safety policy.

## Objective

Fix the JARVIS Textual TUI behavior in which submitting a natural-language
request pauses or freezes the interface for several seconds, delays rendering
the user's message, and then may display a misleading timeline entry similar
to:

`deny | task | user request admitted as blocked; host authority none`

The canonical acceptance request is:

`list the files inside Escritorio`

For that clear, bounded read, the expected behavior is:

1. The user message appears in the Conversation view immediately.
2. The TUI remains responsive to navigation and redraws.
3. Send is disabled only while that submission is being classified/executed;
   no second task is queued accidentally.
4. The request is resolved deterministically without a model preflight turn,
   without Bash, and without an approval prompt.
5. `Escritorio` is resolved through the current user's XDG desktop mapping (or
   a unique existing locale-compatible fallback), then a bounded, non-recursive
   directory listing is returned.
6. The timeline says what actually happened: captured, resolving, admitted to
   the bounded local-read executor, completed or failed. It must not hard-code
   `host authority none` as though that were the denial reason.
7. No credentials, secret file contents, private keys, browser profiles, raw
   environment data, or terminal-control sequences are exposed or persisted.

## Fixed product decisions

These decisions have already been made by the user. Do not reopen them unless
current code proves one is impossible without a materially different security
boundary:

- Use a deterministic fast path before model preflight.
- While a submission is in flight, disable Send and reject additional Enter
  submissions; do not queue or merge them.
- Optimize the current append-only journal; do not rotate or delete it as part
  of this fix.
- Add a bounded local filesystem read executor for exact natural-language
  `list`, `read`, and `search` requests.
- Permit exact paths readable by the current user only when they are not
  sensitive, protected, special, or ambiguous.
- Clear local reads do not depend on App Server availability and do not create
  a Codex `turn/start` request.
- Ambiguous requests receive one concise clarification question with two or
  three concrete options and no execution authority.
- Keep the one-attempt rule. Do not retry model turns, filesystem operations,
  commands, or failed writes automatically.

## Mandatory repository reading and mapping

Before editing, read `AGENTS.md` completely and follow its documentation map.
At minimum, read these current contracts completely:

- `docs/shared-contract.md`
- `docs/instruction-design-guide.md`
- `docs/system-administrator.md`
- `docs/audit-and-state.md`
- `docs/platform-architecture.md`
- `docs/threat-model.md`
- `docs/requirements-decision-record.md`
- `docs/knowledge-and-learning.md`
- `docs/tui-contract.md`
- `docs/tui-implementation-plan.md`
- `docs/host-inspection-executor.md`
- `docs/current-product-state.md`
- `README.md`

Inventory and inspect all first-party implementation, schemas, tests, launch
scripts, and validation logic relevant to the TUI. Do not waste context by
reading every generated vendor schema or every release-manifest hash line;
inspect the pinned App Server schema sections that govern `turn/start`,
`outputSchema`, sandbox policy, approval policy, events, and interruption.
Treat historical phase documents as history where current-product-state marks
them as superseded.

Record the initial workspace state before editing. Preserve unrelated user
changes. The checkout may expose `.git` as a restricted placeholder, so do not
make Git availability a prerequisite for safe work.

## Current evidence to verify

The following was observed on 2026-08-20 and is supplied to accelerate the
investigation:

- `JarvisTui._dispatch_task()` in `tui/src/jarvis_tui/app.py` awaits
  `session.preflight_task(task)` before calling
  `presentation.capture_task(task, admission)`. This explains why the user
  entry is not rendered until preflight finishes.
- `JarvisPresentation.capture_task()` in
  `tui/src/jarvis_tui/presentation.py` formats the timeline with the literal
  text `host authority none` instead of using the actual admission fields.
- `AppServerSessionController.preflight_task()` in
  `tui/src/jarvis_tui/session.py` starts a separate model turn with
  `sandboxPolicy={"type":"readOnly"}`, `approvalPolicy="never"`, and a
  90-second waiter.
- A runtime request around 2026-08-20T11:10:29Z through 11:10:36Z produced
  roughly seven seconds of preflight activity and ended with
  `invalid typed preflight: ValueError`, risk 4, route `none`, and a blocked
  admission. The raw output is intentionally not persisted, so the exact
  violated invariant is unknown.
- `PREFLIGHT_OUTPUT_SCHEMA` accepts combinations that
  `IntentAssessment.__post_init__()` rejects. Examples include clarification
  with fewer than two options, an execute decision with route `none`, a
  non-explanation execute decision without targets, and a deny decision with a
  non-`none` route.
- `EventJournal.append()` and `append_once()` open the journal, lock it, parse
  every prior JSONL record, append, flush, and `fsync` for each event.
- `AppServerSessionController.process_event()` journals every normalized event,
  including streamed deltas. The TUI drops most deltas only after session-level
  normalization and journaling have already happened.
- `runtime/tui/events.jsonl` contained about 14,054 records and occupied about
  13 MiB when inspected. Whole-file parsing per delta is therefore a strong
  event-loop freeze hypothesis.
- The existing `ReadOnlyLocalControl` provides fixed platform/package/power and
  knowledge reads, but no generic bounded filesystem list/read/search path.
- The current local task dispatcher only handles the registered
  `knowledge.search` action.

Verify these facts with exact source locations and tests. Measure or instrument
the current path sufficiently to distinguish synchronous journal cost, model
latency, and rendering cost. Do not persist raw prompts or model output merely
to improve diagnostics.

## Required implementation

### 1. Split capture/presentation from admission

Introduce an explicit pending task projection. Once input validation and task
capture succeed:

- clear the accepted composer input;
- immediately add one user entry keyed by `task_id` with status
  `resolving_intent`;
- switch to Conversation and render before waiting on network/model work;
- disable Send and guard Enter/button handlers against a second submission;
- preserve any text typed while busy rather than clearing it;
- keep navigation, resize, and cancel handling responsive;
- update the same conversation entry through clarify, deny, local execution,
  agent execution, completion, failure, or cancellation; never duplicate it;
- re-enable submission in a `finally` path for every terminal outcome.

Do not describe a captured request as admitted before admission exists.

### 2. Add deterministic natural-language local-read planning

Add a typed, immutable plan for filesystem reads. It must carry at least:

- operation: `list`, `read`, or `search`;
- original target token and canonical resolved path;
- search mode and query when applicable;
- recursion/depth and result/output limits;
- whether hidden entries were explicitly requested;
- a stable digest or equivalent binding used by admission/audit.

Recognize only conservative, testable English and Spanish forms. Support
common imperative variants such as list/listar, read/leer, and search/buscar,
plus explicit paths and user-directory aliases. Resolve `Escritorio`/Desktop,
Documents/Documentos, and Downloads/Descargas from
`~/.config/user-dirs.dirs` without sourcing a shell file. Use existing
directories as a bounded fallback only when the result is unique. Support the
workspace/project alias. If a recognized read request has a missing target,
multiple plausible targets, unclear recursion, or unclear search semantics,
return a deterministic clarification assessment rather than guessing.

The parser is not a general natural-language policy engine. If it does not
match confidently, fall through to typed model preflight.

### 3. Implement the bounded filesystem executor

Use Python filesystem APIs, never a shell or user-constructed argv. Run
potentially blocking traversal/read work through `asyncio.to_thread()` or an
equivalent non-blocking boundary.

Minimum safety rules:

- current-user readable only; no privilege helper;
- canonicalize immediately before execution and compare it with the admitted
  target/digest;
- reject devices, sockets, FIFOs, `/proc` process internals, sensitive `/sys`
  areas, credential/key stores, browser profiles, authentication databases,
  secret-bearing filenames, and equivalent protected targets;
- do not follow directory symlinks; reject a file symlink whose canonical target
  becomes sensitive or differs materially from the admitted target;
- exclude hidden entries by default; include them only after an explicit request
  and still skip sensitive descendants;
- reject binary file reads and cap text before terminal rendering;
- sanitize terminal controls and redact credential-like values before display
  or journaling;
- default list is non-recursive and capped at 500 entries;
- cap a direct read at 64 KiB and the rendered text at the existing presentation
  limit, with an explicit truncation marker;
- cap search at depth 8, 2,000 examined regular files, 1 MiB per file, 200
  returned matches, and a short monotonic deadline; report every applied cap;
- do not persist file contents, search text, path contents, or directory
  listings in the event journal. Journal only typed operation metadata, a
  redacted/categorized target, counts, duration, status, and digests.

An exact local read is a real authorized execution route even though it grants
no mutation or privileged authority. Make the admission model express that
without conflating it with an App Server/Bash execution turn. Preserve backward
compatibility where practical, but update the JSON schema, fixtures, reducer,
and docs together if the admission contract changes.

### 4. Repair model-preflight structured output

Keep model preflight only for requests that the deterministic layer cannot
resolve. It remains non-mutating and grants no authority by itself.

Make the wire JSON schema and Python validation enforce the same decision
variants. Prefer a root object with a nested decision payload expressed as
supported `anyOf` branches:

- execute/explain;
- execute/non-explain with at least one exact target and a non-`none` route;
- clarify with route `none`, one non-empty question, and 2-3 options;
- deny with route `none` and no execution authority.

Confirm the chosen schema subset against the pinned Codex App Server version
and existing request builders. Add exhaustive schema/model matrix tests. If a
model response is malformed, fail closed once with a stable diagnostic code
that identifies the violated field/category; do not reduce it to only
`ValueError`, do not retry, and do not persist raw content. Show a safe user
message that distinguishes classifier failure from a policy denial.

Instrument preflight duration and bounded event/count/digest metadata so a
future failure can be diagnosed without recording prompt bodies, file content,
or private reasoning.

### 5. Make the journal append path incremental

Do not rotate, truncate, delete, or rewrite the existing journal.

Refactor `EventJournal` so it performs one full verified scan when a journal is
first loaded, then maintains an in-memory head containing sequence, last hash,
verified byte offset/file identity, and idempotency keys. Under the existing
file lock:

- incrementally validate bytes appended by another writer;
- force a full rescan when file identity, size, or modification evidence
  indicates replacement/truncation/in-place change;
- perform O(1) idempotency lookup after initialization;
- append one hash-linked record and update the cache;
- keep restrictive permissions, locking, flush, and `fsync` for material
  events;
- keep explicit `verify()` capable of a full independent chain scan.

Do not journal each streaming token/delta. Accumulate only count, byte/character
count, truncation/sanitization flags, and a rolling digest per item/turn. Emit
one bounded stream-summary event at authoritative item completion or terminal
turn cleanup. Continue journaling material lifecycle, approval, state, error,
and completion events.

### 6. Make timeline and authority language truthful

Remove hard-coded authority text. Render actual route/authority fields and the
safe reason/code:

- captured/resolving: no admission yet;
- local read: bounded local executor, read-only, no mutation or privilege;
- agent conversation: current-user agent surface plus the actual sandbox and
  approval boundary;
- clarify: no execution authority, question pending;
- deny/policy block: no authority, exact safe reason;
- classifier/schema failure: internal classification failure, not a claim that
  the user's operation was high risk.

Do not expose policy digests or sensitive targets as noise in the default
conversation view; retain bounded evidence in the audit projection.

### 7. Update contracts and release artifacts

Update current documentation and schemas to match behavior. Do not edit
historical design records to pretend the behavior always existed. Add the
changed/new first-party artifacts to `release-manifest.json` by using the
repository generator, then verify it.

## Required tests

Add focused tests before or with each change. At minimum cover:

1. A delayed fake preflight: the user entry is visible and Send is disabled
   before the fake completes; navigation still works.
2. `list the files inside Escritorio`: direct local route, no App Server
   request, no approval, bounded output, one conversation entry.
3. English/Spanish aliases, absolute paths, workspace-relative paths, unique and
   ambiguous XDG fallbacks.
4. File read success, oversized/truncated text, binary rejection, permission
   failure, special-file rejection, sensitive target denial, symlink escape
   denial, and terminal-control sanitization.
5. Filename and content search, explicit recursion, caps/deadline, hidden-file
   default, and no sensitive descent.
6. Ambiguous read wording produces one question with 2-3 options and no local
   execution or model execution when deterministically recognizable as
   ambiguous.
7. Non-fast-path requests still use exactly one typed model preflight.
8. Every valid preflight decision branch satisfies both JSON schema and
   `IntentAssessment`; every invalid cross-field combination is rejected with
   a stable code.
9. A malformed model output blocks safely without retry and displays
   classifier failure rather than a false policy denial.
10. Timeline projections use the actual admission values and never the old
    literal string.
11. A synthetic 14,000-record journal initializes once; subsequent appends do
    not parse the full prefix. Test this structurally with counters/injected
    parsing, not only a flaky wall-clock threshold.
12. Hundreds of deltas produce bounded in-memory accumulation and one summary
    event rather than hundreds of fsynced journal records.
13. Cancellation, timeout, disconnect, and exceptions always restore the Send
    state and never replay the task.
14. Existing approval, package, power, lighting, recovery, privacy, and journal
    tamper-detection tests remain green.

Run focused TUI tests first, then the complete TUI suite, then
`./scripts/validate-bundle.sh`. The validator is fixture-based and is not
authority to scan or mutate the live workstation. Run each command once and
record unexpected output before diagnosis; do not rerun automatically.

## Scope and non-goals

- Do not add a general shell executor.
- Do not auto-approve mutations, privilege, network effects, or external
  actions.
- Do not broaden the local reader into secret discovery or unrestricted home
  indexing.
- Do not remove typed preflight for non-fast-path execution-capable turns.
- Do not rotate or delete the existing journal.
- Do not change package, power, lighting, Polkit, deployment, VM, or recovery
  authority except where a shared schema/test must remain compatible.
- Do not store private reasoning or raw model output.
- Do not hide failures by weakening unrelated tests or security assertions.

## Working method

1. Restate the objective and fixed decisions.
2. Map the full first-party architecture and preserve unrelated changes.
3. Reproduce/instrument the defect with fixtures or a copied synthetic journal;
   do not mutate the live journal for diagnosis.
4. Write a short evidence-backed root-cause note.
5. Implement in narrow commits/patch groups: contracts, deterministic planner
   and executor, broker/session routing, presentation state, journal streaming,
   tests, documentation/manifests.
6. Run an independent review pass over authorization, symlink/path handling,
   secret leakage, event-loop blocking, state cleanup, and schema compatibility.
7. Validate the exact acceptance request and representative failure paths.

Use subagents only if the runtime supports them and only for bounded read-only
analysis or independent review. They cannot grant authority, approve work, or
replace your own inspection of repository instructions. Avoid concurrent edits
to overlapping files.

## Completion report

Do not claim completion merely because files were written. Report:

- root causes proven and any hypotheses disproven;
- all changed artifacts and public schema/API changes;
- commands actually run, once each, with exit status and material output;
- focused, full-suite, validator, and manual/headless acceptance results;
- unverified items and why they remain unverified;
- assumptions;
- privacy/security review findings;
- residual risks;
- rollback status and how to revert the project-only change safely.

If a material product choice remains after exhaustive inspection, ask one short
question with 2-3 concrete options. Do not ask for information available in the
repository, and do not replace implementation with a questionnaire.
