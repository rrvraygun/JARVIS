# JARVIS Current Product State

**Updated:** 2026-09-13 (root publication candidate; privileged deployment remains separately gated)

This is the operational status document for the repository. Older phase and
planning documents remain useful design history, but do not override this page
for current TUI behavior or deployment state.

## Project Location

The project root is `~/Escritorio/Proyecto/codex-agent-system`.

The active Textual application is in `tui/src/jarvis_tui/`. Run it from the
project root with the source-verifying launcher:

```bash
bash scripts/launch-tui.sh
```

It uses the project `.venv`, enables the local App Server/live-turn flags, and
refuses to start if `jarvis_tui.package_inventory` is not imported from this
checkout. Pass `--connect-jarvisd` or `--plain` after the script command when
needed.

The active stabilization record is `docs/sessions/2026-08-28-stabilization.md`.
Use `bash scripts/quality-gate.sh --fast` for the local fast quality profile;
the complete release gate remains `./scripts/validate-bundle.sh`.

## Source Map

| Area | Primary location | Current role |
| --- | --- | --- |
| TUI layout, tabs, dialogs, submission flow | `tui/src/jarvis_tui/app.py` | Conversation, Agents, packages, power, lighting, timeline, and operations; approvals remain modal. |
| App Server connection | `tui/src/jarvis_tui/app_server.py`, `session.py` | Local Codex App Server authentication, threads, and conversation turns. |
| Broker and audit state | `tui/src/jarvis_tui/preflight.py`, `broker.py`, `event_store.py`, `event_reducer.py` | Deterministic-first intent assessment, typed task admission, incremental hash-chain state, bounded stream summaries, and recovery projections. |
| Bounded filesystem reads | `tui/src/jarvis_tui/local_filesystem.py` | Conservative English/Spanish planning and current-user-only list/read/search through Python filesystem APIs. |
| Approval-gated filesystem mutations | `tui/src/jarvis_tui/local_mutation.py` | Exact directory/empty-text-file creation and same-filesystem move-to-Trash, with immutable review and one-use confirmation. |
| Read-only host inspection | `tui/src/jarvis_tui/local_control.py` | Bounded platform, package, and power inventory collection. |
| Package catalog and details | `tui/src/jarvis_tui/package_inventory.py`, `package_knowledge.py` | Installed RPMs, cached DNF packages, origins, purpose, documentation, relations, and previews. |
| Package privileged client | `tui/src/jarvis_tui/package_control_client.py` | Invokes only the installed root helper through Polkit. |
| Package root helper | `vm-lab/scripts/jarvis_package_control.py` | Exact package-set install/remove and separately approved undo with a durable pre-state journal. |
| Package deployment | `deployment/host/install_jarvis_package_control.sh`, `deployment/host/org.jarvis.package-control.policy` | Hash-bound root helper installation at `/usr/libexec/jarvis-package-control`. |
| Power inventory/control | `tui/src/jarvis_tui/power_inventory.py`, `power_profiles.py`, `power_profile_results.py`, `power_control_client.py`, `vm-lab/scripts/jarvis_power_control.py`, `plugins/jarvis-power-expert/scripts/power_tools.py` | Agent-driven Power recommendations through typed MCP tools, sanitized topology/telemetry, persistent AC/battery profile planning, separately allowlisted atomic profile/single-control mutations, and digest-bound verified application comparisons synchronized to Conversation. |
| Lighting controls | `tui/src/jarvis_tui/lighting_controls.py`, `lighting_widgets.py` | Driver detection, preview, and registered lighting paths. |
| Specialists | `plugins/*/specialist.json`, `tui/src/jarvis_tui/specialists.py`, `tui/src/jarvis_tui/agent_registry.py` | User-selected specialists, validated definitions, persisted selection, and owner-only active overrides. |
| GitHub Agent | `plugins/jarvis-github-agent/`, `plugins/jarvis-system-admin/scripts/mcp_server.py` | Bounded local Git inspection, publication preflight, and non-executable GitHub operation planning. |
| Typed actions and knowledge | `plugins/jarvis-system-admin/` | Registries, schemas, skills, collector definitions, and knowledge storage. |
| Direct-host and VM support | `deployment/host/`, `vm-lab/` | Deployment scripts, policy artifacts, helpers, and rehearsal contracts. |

The App Server child receives only an explicit process/authentication environment
allowlist. Protocol lines, nesting, collection sizes, and queued events are
bounded before normalization. Model-proposed network commands remain behind the
same exact graphical command approval as other external effects.

## Available Behavior

### Global agent settings and context views

The Agents view exposes one global model selector, one reasoning-effort selector
and one context-window selector for all specialists. The values persist in
`runtime/jarvis-model.json` and apply to new turns. Context choices are Auto,
8k, 16k, 32k, 64k, 128k, 256k, 512k, 800k, 1M and 1.05M tokens. Health,
Development, Network, Security and Recovery each expose Clean and Raw evidence
views; Clean presents bounded fields with `[i]` explanations and Raw retains
the complete JSON.

The Conversation activity projection includes token usage when the App Server
sends `thread/tokenUsage/updated`, and shows `unavailable` until then. New
conversations and checkpoint restores reset used context to zero. Specialists
do not inherit previous conversation history.

### Conversation and specialist context

- Conversation history persists every role shown in the Conversation view
  (`user`, `agent`, `jarvis`, `action`, and `system`), including clarification
  questions and their Options text, with bounded status/task/turn identity.
  Older records created before this schema change remain readable but cannot
  recover content that was never persisted.
- History reload uses each saved message's array position for bookkeeping;
  persisted task/local keys are opaque identifiers and are never parsed as
  numeric indexes.
- Conversation presentation follows a messaging layout: `YOU` and user
  clarification entries are right-aligned; all incoming `AGENT`, `JARVIS`,
  `ACTION`, and `SYSTEM` entries remain visible and left-aligned.
- The Conversation tab uses a centered 92%-wide composition with a one-cell
  renderer-rounding correction, a uniform-width right action rail, symmetric
  6% balance gaps around the chat, and a top-left specialist selector without a
  separate label.

- An accepted submission is projected in Conversation as
  `resolving_intent` before classification. Send and additional Enter
  submissions are disabled for that one in-flight task; navigation, redraw,
  resize, and cancellation remain available. Text typed while busy is kept and
  is not queued.
- Exact bounded local filesystem list/read/search requests first use the
  deterministic planner. They do not depend on App Server availability, create
  a Codex turn, invoke Bash, or request approval. Other natural-language
  requests still use exactly one typed, non-mutating App Server preflight when
  live turns are enabled.
- The sanitized clean Conversation view is the active context for later agent
  requests, including bounded local-read requests and results. Missing visible
  entries are injected once as explicitly untrusted history before the next
  typed preflight; the current request remains separate. This synchronization
  uses no Bash and grants no authority.
- A follow-up may derive a count, summary, comparison, or explanation from one
  recent compatible Conversation result. Singular references such as “the
  directory” resolve to that result, and the answer-only agent turn is told not
  to use tools or request approval. Ambiguous references still clarify; an
  explicit freshness request requires a new bounded read.
- Active conversation context follows the global token-window setting (Auto, 8k,
  16k, 32k, 64k, 128k, 256k, 512k, 800k, 1M or 1.05M) and remains bounded to
  500 presentation entries. Oldest complete exchanges are pruned from both
  together with a visible omission marker. New, Clear, and loaded-history actions start a new context
  epoch and therefore a fresh App Server thread on the next model request.
- Visible local-read results are persisted in the conversation after terminal
  sanitization/redaction so specialist transcripts and history reloads retain
  the user-visible workflow. Raw filesystem output remains excluded from the
  event journal, and sensitive filenames/content are rejected before rendering
  or persistence.
- Status-less App Server `agentMessage` lifecycle events derive their state
  from `item/started` and `item/completed`. The started reply renders as
  in-progress immediately, and completion updates that same Conversation entry.
- Desktop/Escritorio, Documents/Documentos, and Downloads/Descargas resolve by
  parsing `~/.config/user-dirs.dirs` as data, never by sourcing it. A
  locale-compatible fallback is used only when exactly one existing directory
  matches. Workspace/project and explicit path forms are also supported.
- The local reader is current-user-only, descriptor-safe, non-recursive for a
  default listing, bounded, terminal-sanitized, credential-value-redacted, and
  denied for sensitive/special/ambiguous targets. File contents, listings,
  paths, and search text are not written to the TUI event journal.
- Sensitive filename matching is locale-aware and rejects credential-bearing
  English and Spanish labels, including concatenated `contraseña`/`contrasena`
  prefixes, before listing, searching, rendering, or context synchronization.
- Exact filesystem creates and moves to Trash use a separate deterministic
  current-user executor. They may target writable, non-protected paths outside
  the project, but always wait for a fresh exact modal confirmation, reserve
  once, revalidate descriptor identity, and never use Bash.
- Every mutation requires a fresh one-use decision. Model-proposed
  current-user mutations use registered one-use operations; generic App Server command/file approvals are rejected; privileged work is limited to registered Polkit helpers. Power Expert
  turns use a read-only sandbox and typed MCP tools. Session-wide approval is
  not exposed.
- Command/file approval requests preserve present JSON-RPC IDs exactly,
  including integer `0`; the exact-review modal supports accept-once, decline,
  and cancel, and terminal resolution removes the pending request.
- The user selects the active specialist explicitly. The coordinator never
  changes specialists automatically; an out-of-scope request is clarified or
  declined.
- The Agents tab exposes operational summaries and both structured/raw
  definition editing. Activation requires validation, an exact diff, one fresh
  approval, and retains the previous active definition for rollback.
- Nine specialists are selectable: JARVIS Architect, Installation Specialist, Power Expert, System Health Specialist, Cargo Builder, Network Specialist, Security Specialist, Recovery Specialist, and GitHub Agent.
- GitHub Agent is selectable in both Agents and Conversation. Its initial tools inspect
  a user-selected repository's local Git state, publication risks, ignored paths,
  conflicts, remotes, likely secret-bearing filenames, and large changed files.
  It neither reads file contents nor contacts GitHub during inspection. It can
  prepare local init, branch, commit, fast-forward pull, and push operations for
  the existing one-use TUI review; each write needs a fresh exact approval.
  Remote repository, issue, pull-request, release, and Actions operations remain
  plans until the configured guarded connector is independently checked for the
  active profile.
- It supplies bounded host-inspection evidence to a conversation request. The
  model receives formatted evidence, not terminal or root access.

### Read-only host inspection

- Platform: operating system, kernel, and architecture.
- Packages: installed RPMs and cached DNF repository metadata.
- Power: TuneD/tuned-ppd, CPU governor/EPP/P-state interfaces, platform
  profile, Intel/NVIDIA runtime power, power supplies, Powertop presence, and
  related driver/module evidence.
- Power Expert is selectable and reports sanitized hardware/software topology,
  provider conflicts, bounded telemetry, available control capabilities, and
  persistent AC/battery profile plans. Profile activation remains manually
  approved and uses one atomic helper transaction; partial results require
  separately approved exact pre-state recovery.
- Package catalog data is stored at
  `runtime/knowledge/package-catalog.json.gz` with owner-only permissions.

### Package inventory and recommendations

- Installed, cached-available, combined, and update candidate views.
- Bounded filtering, pagination, category/purpose/origin/state details, local
  RPM documentation, dependency/relationship queries, and DNF history.
- Cached recommendations are evidence-labeled. Same-purpose matches are an
  inference, not an RPM conflict claim.
- Official web-documentation refresh is not an automatic capability.

The Packages tab and Installation Specialist use the same package inventory and
mutation backend. Package actions remain available from Packages while the
specialist owns package-specific context, tool references, and explanations.
Natural-language package inspection is routed through the selected
Installation Specialist or Power Expert and its registered read-only package
MCP tools. The Packages tab remains a separate local inventory view, and exact
install/remove requests retain their approval-gated registered workflow.

### Approval-gated package installation and removal

The Packages view and conservative natural-language planner support exact-name
installation and removal through a registered fixed helper. Natural-language
exact package requests retain deterministic roots but use one typed
agent-planning preflight before one cache-only DNF preview. Quoted names and
named “related to” roots are normalized before that handoff. DNF determines
dependencies; there is one final exact approval, not a dependency-choice
dialogue. The agent may clarify once, but cannot propose `sudo`/`dnf`/Bash for
the mutation; only the registered helper executes it.

Before package-related model preflight, JARVIS performs one bounded read-only
RPM/database and cached-DNF catalog refresh. The classifier receives only
counts, freshness, and up to 24 sanitized installed/available candidate records
for the request. It uses that evidence to ask for exact Fedora roots or offer
concrete candidates; it does not authorize a transaction. Official upstream
release downloads, repository changes, and arbitrary package-manager commands
remain unsupported.

Language aliases use observed Fedora package names before generic utilities:
for example, a request for the Go language toolchain prioritizes cached
`golang` over unrelated `go-*` tools. Numbered clarification replies are bound
to the displayed option text before the next classification turn.

Short greetings use a deterministic conversation route. A newly entered
deterministic package request supersedes an unrelated pending clarification
instead of being concatenated into model-preflight text.

Before displaying one final authorization, JARVIS automatically verifies:

1. names are exact bounded RPM package tokens;
2. the hash-bound root helper is installed and executable;
3. a cache-only DNF simulation resolves the transaction and binds current RPM
   pre-state; and
4. install previews are strictly additive (no removal, upgrade, downgrade,
   reinstall, or replacement), while removal previews use `--no-autoremove`,
   enumerate the removal set, and contain no protected package.

The review dialog shows requested packages, prior installed state, resolved
removals, and the bounded DNF preview. Approval starts
Polkit authentication and passes only the operation, package names, and digest-bound pre-state
to the root helper. The helper records a root-owned per-user journal before DNF
runs, verifies post-state, and supports separately approved undo.
The Packages-tab and natural-language paths consume the same broker approval
and execution-reservation records before invoking the helper. Once invocation
begins, an error or lost response is reported as indeterminate and points to
the authoritative recovery record; it is never described as a safe no-op.
If a post-failure status read finds that record bound to a different package
set, the timeline reports `package_helper.recovery_record_mismatch` and blocks
further approval until that record is reconciled.
Known helper refusals that occur before a durable transaction record is written
are reported as safe pre-execution no-ops; only post-record or unknown failures
remain indeterminate.
When no recovery record exists, the helper returns an explicit empty status;
the Packages view does not open a meaningless rollback approval dialog.
An empty authoritative status after a lost/uncertain invocation does not prove completion or absence of later effects. JARVIS reports `package_helper.no_recovery_record`, retains an indeterminate outcome, and requires reconciliation of the original helper. Known explicit pre-execution refusals remain distinct safe no-ops.

The action registry also contains disabled metadata for the prepared power
profile candidate. This satisfies catalog consistency only: it does not
register the candidate adapter, enable the capability, invoke D-Bus, or grant
power-profile mutation authority.

Deploy the current helper before using this feature:

```bash
sudo ./deployment/host/install_jarvis_package_control.sh
```

The helper is not a shell or arbitrary-DNF executor. It accepts no shell
fragments, repository URLs, or user-provided DNF options.

## Current Limitations

- The direct package workflow covers exact-name install/remove only. Updates,
  repository enablement, arbitrary DNF options, broad package goals, and
  automatic official-documentation retrieval are not enabled by this flow.
- Agent-definition editing is limited to reviewed installed agents and
  registered tools. New executable modules, arbitrary commands, and direct
  privilege grants cannot be created from the Agents editor.
- Reinstall the root helper after its hash-bound source or installer changes.
- Power discovery is broad, but only separately allowlisted controls can write.
  A displayed inventory row is not automatically writable.
- Power telemetry polls only while the Power tab is active. TLP, auto-cpufreq,
  frequency/thermal, and vendor controls are detected or represented as
  capabilities but require fixed reviewed adapters before mutation.
- Power Expert package recommendations create an explicit Installation
  Specialist handoff; they do not install or remove packages directly.
- Lighting support depends on detected and registered hardware drivers.
- The deterministic language grammar is intentionally narrow. Recognized but
  ambiguous local-read wording yields one question with 2–3 concrete options;
  unrecognized wording falls through to model preflight.
- Timeline startup replay omits legacy stream deltas and non-material protocol
  chatter from the human projection, caps material history at the latest 100
  records, reports bounded omission counts, and leaves the append-only journal
  unchanged. New stream deltas produce one metadata-only summary at item or
  turn completion.
- Search remains bounded to depth 8, 2,000 examined regular files, 1 MiB per
  file, 200 matches, and a short monotonic deadline. It is not a home-indexing
  or secret-discovery feature.
- Agent turns are read-only and cannot escalate. Mutations require registered executors; there is no generic Bash fallback. The new runtime profile must be reviewed and activated separately.

## Validation and Support

Focused TUI package/control tests are in `tui/tests/`. Run the bundle static
validator with:

```bash
./scripts/validate-bundle.sh
```

The validator does not install packages or alter the workstation. For package
transaction failures, use the Conversation result and Timeline: the client
shows the root helper's bounded error detail.

## 2026-09-07 staged implementation

This candidate is separate from the active checkout. See
[specific acceptance and remaining work](sessions/2026-09-08-implementation.md).

- Health and extended collectors cap bytes while reading, stop on overflow or timeout,
  redact before returning, and label fresh observations. Project manifest reads reject
  symlinks, special/unowned files, oversized content, and unsafe roots.
- Each App Server process receives its own MCP scope identifier. The broker publishes
  permissions only after admission and revokes them on terminal events, interruption,
  or disconnect. MCP schemas are discoverable, but every dispatch checks the live
  specialist scope. A discovered schema never grants authority. Lesson activation
  is unavailable through the model-facing MCP.
- `operation_plan` prepares a digest-bound proposal; no MCP apply/approve tool exists.
  A dedicated review consumes an ephemeral decision and reserves a durable attempt
  before effects. Applying existing dependency manifests to an original project
  requires its own proposal and preserves displaced files.
- Cargo runs the approved source snapshot under bubblewrap and a transient systemd
  user service. A guard requires effective cgroup v2 memory/process/CPU limits before
  launching code. It has no network, home, or writable source mount. An empty Cargo
  cache means external dependencies can be unavailable. Separately approved,
  checksum-bound downloads can be consumed through an offline directory source.
- Cargo dependency proposals create a separate workspace with exact reviewed files.
  Backup/restore copies bounded text-project trees to a new destination only. These
  are R0 project operations, not full-system, binary-data, boot, or disk recovery.
- Operation results and verification records are separate. The verifier runs in a
  read-only bubblewrap process. If that sandbox cannot start, the result is unknown,
  never independently verified. Build exit status alone does not prove hardware safety.
- Health, Development, Network, Security, and Recovery views collect evidence only
  on request and review the operation ID supplied by the agent. Conversation remains
  free of activity cards; material results enter its existing persisted context.
- Sanitized operational transcripts have explicit type/field, size, count, and expiry
  limits. Reasoning and secret/environment fields are rejected. Expired content is
  withheld; deletion/rotation requires a separately reviewed policy.
- Service helper code exists but is not deployed/enrolled. Exact TCP checks have a one-use executor. Narrow DNS, SELinux-label and firewall helpers are prepared but not deployed. Update and boot helpers now require exact independent root review and fresh recovery evidence; deployment is not automatic. System recovery orchestration remains separate from the text-project copy backend.

## Terminal and validation closeout — 2026-09-11

Normal terminal mode has its own proposal, digest, ephemeral environment binding,
approval, reservation and result. Textual suspends/resumes on its UI thread;
the child inherits real terminal descriptors and runs without application-imposed
resource or runtime limits. The user explicitly sees host access and network
authority; the mode never inherits claims from the isolated proposal. Root TUI
processes cannot use this route. Only foreground exit is attested.

The earlier claim of a permanently hung Textual suite was not supported:
the retained log completed 36 tests in 109.777 seconds. A new real PTY smoke
exercised the review button, one printf and UI resumption. See
`sessions/2026-09-11-validation-closeout.md` and `PATCH-GUIDE-2026-09.md`.
