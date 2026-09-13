# Phase 1 read-only broker

> Historical design record. It does not define current TUI authority. See
> `current-product-state.md` and `tui-contract.md`.

## Result

Phase 1 is implemented and fixture-validated. It adds a broker-owned Codex App
Server session without adding a Fedora collector, command runner, host executor,
approval-acceptance path, or privileged service. The default TUI remains fully
offline. No live App Server session or Codex turn was used during implementation
or validation.

The live integration acceptance check is intentionally deferred until the user
chooses to run it. This distinction matters: fixture completion proves broker
logic and failure handling; it does not claim that the installed Codex version,
current ChatGPT account, or a real network session has been exercised.

## Delivered surface

### App Server transport

The stdio JSONL client implements initialization and a closed allowlist:

- `account/read`, managed `account/login/start`, login cancellation, and
  `account/rateLimits/read`;
- `thread/start` and `thread/resume`;
- `turn/start`, `turn/steer`, and `turn/interrupt`.

It strips `OPENAI_API_KEY` and `CODEX_API_KEY` from the child environment. Only
an account whose App Server type is `chatgpt` becomes ready. There is no paid
API fallback.

The transport denies every method outside that list. In particular, Jarvis has
no transport path to `thread/shellCommand`, `command/*`, `process/*`, `fs/*`,
thread deletion, raw history injection, or dynamic tools. Stderr is drained to
avoid process deadlock, requests have timeouts, and stream closure becomes a
normalized disconnect event.

### Session controller

The controller owns connection, authentication, capacity, thread, turn, and
pending-request state. It supports:

- ChatGPT login-required, ready, capacity-limited, unsupported-auth,
  disconnected, and failed states;
- documented rate-limit buckets without persisting credentials or opaque reset
  credit IDs;
- read-only thread creation and explicit thread resumption;
- a conversation-only turn with `approvalPolicy: on-request` and
  `sandboxPolicy: {type: readOnly}`;
- steering with `expectedTurnId` and interruption with both thread and turn IDs;
- correlation of responses and notifications even when a completion event
  arrives before the corresponding request response.

Live turn submission is disabled in both the controller and CLI by default.
The compiled Phase 1 prompt also prohibits terminal, collector, executor,
filesystem-write, and host-inspection tools. The sandbox is defense in depth;
it is not treated as an authorization to inspect the workstation.

### Event reduction and privacy

The reducer maps App Server messages into typed, display-safe events. It:

- correlates thread, turn, item, request, and Jarvis task IDs;
- deduplicates replayable lifecycle events while preserving identical streamed
  text chunks that may both be legitimate;
- caps display text and neutralizes ANSI, OSC hyperlink, C1, and bidirectional
  terminal controls;
- withholds raw reasoning, command output, and diffs;
- records only content digests, lengths, metadata keys, correlation IDs, and
  state transitions in the hash-chained journal.

An App Server command, file, permission, MCP elicitation, or user-input request
becomes a pending object. Phase 1 exposes no acceptance method. Unexpected tool
items, command output, and diffs block the task. Interruption is the only
available way to stop such a turn.

### Recovery and idempotency

Before `turn/start`, the broker atomically appends an idempotency reservation.
The same Jarvis task cannot be submitted twice. A crash after reservation but
before a confirmed response recovers as `blocked` and `uncertain_operation`;
the prompt is never automatically replayed.

The journal can reconstruct non-sensitive task state, thread/turn correlation,
and whether the user must resubmit. A known Codex thread ID can be recovered
without loading it. Resumption is separate from prompt submission.

### Local deterministic reads

The broker can list the capability and action registries and query the existing
knowledge database through a SQLite `mode=ro` and `query_only` connection. A
missing database is reported and never created. These reads do not call the
model and do not inspect Fedora.

## CLI gates

The command modes are deliberately cumulative:

| Invocation mode | App Server | Account/capacity read | Turn submission |
|---|---:|---:|---:|
| no flags | off | no | no |
| `--connect-app-server` | on | yes | no |
| both `--connect-app-server --enable-live-turns` | on | yes | yes, conversation-only |

The final mode spends ChatGPT Codex allowance and is not part of automated
validation. None of these modes exposes a host executor.

## Validation evidence

The Phase 1 suite uses a fake App Server and temporary stores. It covers:

- ChatGPT-only authentication and API-key environment removal;
- method allowlist enforcement;
- thread start/resume, turn start/steer/interrupt, and completion;
- off-by-default live turns and read-only request construction;
- rate-limit normalization;
- duplicate and out-of-order event handling;
- pending approval correlation with no accept path;
- forced disconnect, uncertain recovery, and no replay;
- journal tamper detection and content non-persistence;
- terminal injection neutralization;
- non-creating, read-only registry and knowledge access.

The project-wide validator remains the release gate. It validates source
schemas, fixtures, skills, plugin metadata, control-plane tests, the TUI tests,
Python compilation, and the deterministic release manifest.

## Official protocol basis

- [Codex App Server](https://learn.chatgpt.com/docs/app-server)
- [Codex authentication](https://learn.chatgpt.com/docs/auth)
- [Codex approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security)
- [Codex access through ChatGPT plans](https://help.openai.com/en/articles/11369540-using-codex-with-chatgpt)

Only the stable protocol surface is used. Experimental App Server capabilities
are intentionally absent from this phase.

The exact stable JSON Schema generated by `codex-cli 0.146.0` is vendored under
`tui/vendor/codex-app-server-schema/0.146.0/`. The compatibility record pins the
allowed methods and the installed-version wire spellings. In particular, the
generated schema requires `approvalPolicy: "on-request"` and the legacy thread
sandbox value `"read-only"`; turn sandbox policy uses `{ "type": "readOnly" }`.
The generated schema takes precedence if prose examples differ.

## Live acceptance result (2026-08-06)

The pinned `codex-cli 0.146.0` App Server passed the explicit live smoke test
recorded in
`runtime/reports/2026-08-06-jarvis-live-app-server-acceptance.json`:
ChatGPT-managed account and rate-limit reads, thread start, one
conversation-only read-only turn, steering, interruption, clean disconnect,
reconnect, and resume of the populated thread. No host command, collector,
filesystem write, or hardware change was performed.

The test also established an ordering rule: a newly-created empty thread may
not yet have a resumable rollout. Resume acceptance must therefore follow a
populated turn, not an empty `thread/start` alone.
