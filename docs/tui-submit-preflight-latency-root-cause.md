# TUI submission/preflight latency root-cause note

**Observed:** 2026-08-20  
**Scope:** fixture/read-only inspection plus the existing TUI journal; no live
filesystem request or App Server prompt was replayed for diagnosis.

## Proven causes

1. `JarvisTui._dispatch_task()` awaited `session.preflight_task()` before the
   old `capture_task()` projection. Therefore the Conversation view had no user
   entry to render during model latency. Rendering could not be the cause of
   that missing first paint because it had not yet been requested.
2. Every unmatched natural-language request created a separate App Server
   classifier turn with `readOnly`, `never`, and a 90-second waiter. The
   supplied 11:10:29Z–11:10:36Z journal window contains a roughly seven-second
   classifier lifecycle before the blocked projection.
3. The old `EventJournal.append()` and `append_once()` reparsed the complete
   JSONL prefix for every event. The inspected live journal was 13,212,831
   bytes/14,054 records. A copied synthetic valid 14,000-record chain took
   0.104779 seconds to verify and one old-style append path took 0.048719
   seconds on this host. The same live window contained dense normalized App
   Server events, and `process_event()` journaled deltas before UI throttling.
   This proves synchronous prefix work was an event-loop pressure source
   distinct from the network/model wait.
4. The preflight wire schema allowed cross-field combinations rejected by
   `IntentAssessment`, so a schema-conforming response could collapse to the
   undiagnostic `ValueError` path. The historical raw output was correctly not
   persisted, so the exact violated field in that one event remains unknown.
5. `JarvisPresentation.capture_task()` rendered the literal phrase
   `host authority none`; it did not derive the explanation from the assessment
   or admission and therefore could falsely imply that lack of host authority
   was the denial reason.
6. The pinned Codex App Server 0.146.0 `turn/start` contract exposes
   `outputSchema` as an object. The pinned protocol schema family itself uses
   `anyOf`, item-count, and string-length keywords, and the local request-builder
   contract test verifies the nested schema is transmitted unchanged. That was
   transport-level evidence only. A later live report at journal sequences
   14059–14081 produced a server `systemError` before classifier output, proving
   that transport acceptance did not establish backend acceptance of the exact
   schema shape. The raw 360-character error was correctly represented only by
   length/digest, so attributing that event solely to one schema keyword would
   exceed retained evidence.

## Disproven or bounded hypotheses

- The initial missing user message was not caused by Conversation rendering:
  presentation was invoked only after awaited preflight.
- The observed multi-second interval cannot be attributed solely to journal
  parsing: the model turn itself occupied most of the timestamp window. Journal
  work instead explains repeated event-loop stalls during streaming.
- The inspected evidence does not establish which model field caused the
  historical validation exception; claiming one would exceed the retained
  evidence.

## Implemented correction

The pending projection now precedes asynchronous classification; a busy guard
prevents queueing; exact bounded local reads use a deterministic executor; the
fallback schema and Python model share decision variants and stable failure
codes; the journal keeps an incrementally verified head and coalesces deltas;
and Timeline authority text is derived from typed state. Validation evidence is
reported by the implementation completion record rather than inferred from
files being present.

Follow-up runtime evidence showed that the new process coalesced stream events
correctly (zero stream records for the failed turn), while Timeline startup had
replayed 500 legacy normalized rows from the unchanged journal. Startup
projection now retains only the latest 100 material lifecycle/error records and
bounded counts for older material and legacy/non-material protocol rows.

A second live report at sequences 14086–14108 categorized the backend failure
as `output_schema`, proving the first compatibility correction was insufficient.
The current OpenAI Structured Outputs guide states that every nested `anyOf`
schema must independently satisfy the supported subset and that fine-tuned
models may reject string-length, numeric-range, and array-cardinality keywords.
The wire schema now uses four complete strict-object branches without those
keywords; Python preserves the stronger semantic/cardinality checks and fails
closed once with a stable code. A one-attempt live probe through pinned App
Server 0.146.0 then completed with `decision=execute` and
`route=conversation`. Server error text is reduced in memory to a stable
non-sensitive category before being discarded.

A later live approval request exposed an independent correlation defect. App
Server emitted `item/commandExecution/requestApproval` with integer request ID
`0`; the reducer retained it, but session registration and the TUI modal guard
tested the ID for truthiness. Timeline therefore showed a pending request while
no review screen appeared. Those paths, plus resolved-request cleanup, now test
ID presence explicitly. Regression coverage proves that ID `0` is registered,
shown for exact review, answered once, and removed without journaling the
command text.

An independent read-only review then identified five defects that were repaired
before validation: prefix tamper combined with append, unbounded directory
sorting, material event-journal I/O on the event loop, missing one-use local
execution reservation, and nullable filesystem admission bindings.

## 2026-08-26 conversation-continuity follow-up

Live evidence for an unanswered greeting showed a completed 38-character App
Server agent item in the journal. The agent had answered; this disproved a
classifier or model-silence explanation. The Conversation renderer hashed only
entry key and text length. `item/started` and `item/completed` carried the same
text length while only status changed, so the completed item could be skipped
after the in-progress version had been filtered from the clean view. Rendering
now binds key, status, length, and content digest and forces terminal agent-item
and turn repaint.

The deterministic local-read request/result was also absent from the App Server
thread by design, so later agent turns lacked that visible context. The active
clean Conversation projection is now bounded to 64,000 sanitized characters,
prunes oldest complete exchanges from view/context together, and synchronizes
missing prior entries once through pinned `thread/inject_items` before the next
preflight. The payload is framed as untrusted history and grants no authority;
the current request remains separate. The injected payload is not separately
persisted by JARVIS, deterministic local results stay out of conversation JSON,
and raw context stays out of audit records; ordinary user/agent messages retain
their existing conversation-history behavior. The live Desktop sample also
proved a locale-sensitive filename gap; concatenated Spanish credential labels
are now filtered before display or synchronization.
