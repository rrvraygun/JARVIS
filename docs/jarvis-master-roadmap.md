# Jarvis Master Roadmap

**Document role:** canonical roadmap and completion checklist for the Jarvis
project. This file consolidates the architecture plan, delivery phases,
control-plane contracts, TUI milestones, direct-host deployment, recovery,
release, and capability-maturity requirements.

**Snapshot date:** 2026-08-07

> **Current-state note (2026-08-09):** this roadmap is the canonical design
> and delivery history, but portions of its phase-status text predate the
> implemented bounded package-control path. For the current deployed behavior,
> source map, and limitations, read
> [`current-product-state.md`](current-product-state.md) first.

**Important boundary:** this is a planning and status document. It is not an
authorization to install, inspect, mutate, approve, execute, or self-update the
host. Every future state change still requires its own exact policy, evidence,
recovery, approval, execution, and verification gates.

## 1. Product objective

Jarvis is a local-first, evidence-led workstation assistant with two equal
interaction styles:

1. natural-language conversation;
2. a searchable catalog of versioned, typed actions.

Both styles must converge on one immutable task and policy pipeline. The TUI is
only a presentation/consent surface. The broker/control plane owns state,
policy, evidence, approvals, audit, and eventual narrow adapters. Codex App
Server supplies conversation and reasoning, but never becomes a hidden host
executor.

The target product is a safe supervised Fedora workstation console. Optional
VM/lab work validates software contracts but cannot replace physical evidence
for firmware, ACPI, GPU routing, panels, keyboard lighting, battery, thermals,
or suspend/resume.

### 1.1 Unified direct-host/TUI scope

The primary delivery target is now one direct Fedora workstation running Jarvis
in shadow mode. The Textual TUI is the single operator surface for:

- ChatGPT-managed conversation and typed catalog actions;
- bounded H1 platform/compute observations on the actual workstation;
- LUKS/R2 recovery status and audit visibility;
- evidence-led diagnosis of the first physical use case: display brightness and
  keyboard lighting.

The TUI and direct-host control plane advance together: a TUI feature is not
complete until its host-authority state is visible, and a host observation is
not admitted until it has a TUI-visible scope, freshness, evidence, and stop
condition. VM rehearsal remains optional and never blocks this direct-host
shadow track.

## 2. Non-negotiable invariants

- Separate observation, sourced fact, inference, recommendation, proposal,
  approval, execution, validation, and lesson states.
- Default to read-only, least-privilege inspection with bounded scope and one
  attempt. Stop on unexpected output; never retry automatically.
- No raw shell, unrestricted root, arbitrary command, direct privileged channel,
  or hidden executor in the TUI, broker, or model.
- Every mutation is exact-command, target-, state-, policy-, adapter-, and
  approval-bound, with pre-state, rollback/recovery, postconditions, and
  independent review.
- Codex authentication is ChatGPT-managed by default. Never silently use an
  API key or paid API fallback.
- Never persist credentials, tokens, private keys, raw chain-of-thought, or
  unredacted sensitive output.
- Audit and governance failure fail closed for mutation.
- A capability advances only through the maturity model and explicit review;
  repeated successful use does not create authority.
- The agent may stage a change but cannot approve or solely attest to its own
  release or policy transition.

## 3. Architecture and permanent planes

### 3.1 Presentation plane

`jarvis-tui` renders overview, conversation, actions, knowledge, plans,
approvals, timeline, errors, lessons, recovery, and settings. It gathers typed
input and explicit consent but has no shell API, raw executor, privilege, policy
write, or direct database mutation capability.

### 3.2 Broker/session plane

`jarvisd` (initially allowed to be an in-process service) owns sessions, task
records, idempotency, event reduction, App Server correlation, policy calls,
approval binding, recovery, and journal writes. Before supervised mutation it
must be a separate unprivileged process on a private Unix socket.

### 3.3 Codex App Server plane

Use local stdio JSONL App Server with the pinned installed protocol. The current
compatibility target is `codex-cli 0.146.0`. The allowlist is limited to account,
thread, turn, interruption, and required lifecycle methods. Shell/process/file
execution methods are denied or displayed as blocked.

### 3.4 Control, knowledge, and audit plane

Typed registries define actions, procedures, collectors, adapters, evidence,
risks, and recovery. SQLite stores facts, sources, attempts, errors, lessons,
decisions, and approvals. The append-only v2 JSONL ledger is hash chained and
must be independently verifiable.

### 3.5 Adapter/executor plane

Future adapters are fixed executable/argument templates with bounded output,
timeouts, redaction, version identity, and independent verification. A narrow
root-owned service with Polkit or equivalent authorization is preferred over
giving any model-facing process root.

## 4. Status vocabulary

- **Complete:** implementation and required validation for that gate are done.
- **Fixture-complete:** deterministic tests and synthetic scenarios pass, but
  this does not prove live Fedora or physical hardware behavior.
- **Observed:** bounded, read-only evidence was collected on the enrolled host.
- **Pending live acceptance:** implementation exists, but the deliberate live
  acceptance check has not been run.
- **Prepared:** schemas, plans, or procedures exist but have no authority.
- **Planned:** not yet implemented.
- **Blocked/deferred:** deliberately unavailable because a required safety,
  dependency, approval, or evidence condition is missing.

## 5. Delivery roadmap

### Phase 0 — Architecture decisions and fixtures

**Objective:** establish the contracts and make unsafe execution inexpressible.

**Sections and deliverables**

- Boundary model and architecture decision records.
- Canonical schemas: `IntentEnvelope`, `ActionDefinition`, `TaskRecord`, broker
  events, session snapshots, approvals, and protocol compatibility.
- Versioned action/procedure registry with typed UI metadata.
- Fixture conversations, catalog submissions, approvals, disconnects,
  unexpected output, restarts, capacity exhaustion, and malformed protocol data.
- Pinned/generatable Codex App Server schema and wire-value compatibility tests.
- Threat, privacy, terminal-safety, data-lifecycle, and capability-maturity
  contracts.

**Completion criteria**

- All schemas validate and canonical serialization/digests are stable.
- No component can express raw host execution through the declared protocol.
- Fixture coverage includes normal, adversarial, restart, disconnect, and
  degraded-capacity cases.
- Architecture, safety, and release documents agree on the same boundaries.

**Status:** Complete.

### Phase 1 — Read-only broker

**Objective:** create a headless local broker that can converse and recover
without inspecting or changing Fedora.

**Sections and deliverables**

- App Server stdio startup, initialization, ChatGPT-managed auth state/login,
  rate-limit display, thread start/resume, turn start/steer/interrupt.
- Closed client-method allowlist and denied execution/experimental methods.
- Local broker API, append-only UI/task event journal, event normalization,
  correlation, idempotency, and metadata-only crash recovery.
- Read-only capability listing and SQLite knowledge queries that never create a
  missing store.
- Offline and capacity-exhausted behavior with no automatic prompt replay.

**Completion criteria**

- A headless client can connect, authenticate or show login-required state,
  start/resume a thread, stream one turn, steer/interrupt it, and recover from
  disconnect using a fake server and a real separately approved smoke test.
- No Fedora command, API key, privilege, or host mutation is used.
- Duplicate/out-of-order events and uncertain submission fail closed.

**Status:** Live acceptance passed on 2026-08-06; no host authority is exposed.

### Phase 2 — Hybrid TUI MVP

**Objective:** provide one keyboard-accessible Textual interface for
conversation and catalog actions.

**Sections and deliverables**

- Overview: session, auth/capacity, registry, knowledge, safety, and recovery
  status.
- Conversation: natural-language composer, streamed messages, task states,
  warnings, blocked requests, and follow-up steering.
- Actions: registry-generated search and schema-driven typed forms.
- Knowledge: read-only search across facts, sources, attempts, errors, lessons,
  and decisions.
- Plan: bounded plan deltas and authoritative step states.
- Timeline: safe broker/App Server lifecycle projections.
- Terminal sanitization, output caps, plain mode, resize handling, focus and
  crash cleanup.

**Completion criteria**

- Natural-language and catalog requests converge on the same normalized task,
  admission, and no-host-authority policy result.
- Headless interaction tests pass at compact and wide terminal sizes.
- Paste cannot submit hidden approval input; raw tool arguments, output, diffs,
  and reasoning are withheld.
- Local-only views remain usable without App Server or capacity.

**Status:** Implemented and fixture-validated. The pinned Textual dependency is
installed in the project-local `.venv`; all 53 TUI tests and offline startup
pass. The live App Server acceptance is recorded with Phase 1.

### Phase 2B — Direct-host shadow console integration

**Objective:** merge the TUI milestone with the primary Fedora workstation
shadow workflow without adding mutation authority.

**Sections and deliverables**

- Show H1 enrollment state, proposal/source/adapter digests, host-binding state,
  freshness, and explicit unknowns in the TUI.
- Expose only the minimal Tier-0 `platform-identity` and `compute-summary`
  scope through the typed broker facade.
- Keep candidate facts ephemeral until an encrypted, recovery-verified backend
  is explicitly unlocked; show persistence as unavailable otherwise.
- Surface the existing LUKS/R2 recovery foundation and audit-ledger integrity
  as prerequisites for future direct-host work.
- Allow local unencrypted Btrfs snapshots as R1 for routine development only;
  retain R2 as the required protection for kernel, NVIDIA, boot, graphics,
  storage, and encryption changes.
- Link the lighting diagnosis journey to the same evidence, scope, and stop
  conditions while keeping Tier-1/Tier-2/protected/device-waking checks gated.

**Completion criteria:** the TUI can present the exact direct-host proposal,
scope, digests, recovery state, candidate-vs-host fact distinction, and blocked
activation reason; no observation or mutation can start from an unapproved or
stale state.

**Status:** Read-only TUI-to-`jarvisd` status and recovery projection is
implemented. The
TUI opt-in flag `--connect-jarvisd` calls only `health.read` and
`activation.status` over the owner-only Unix socket; it cannot start an
observation or mutate host state. The typed broker and v2 transactional
LUKS-backed SQLite storage remain fixture-tested, with mount/device identity
checks, owner-controlled no-follow path handling, durable one-use activation
binding, and record-integrity verification. H1 Tier-0 is live for the
approved platform/compute scope; restricted fact persistence remains disabled.

### Phase 3 — Exact approvals without host mutation

**Objective:** implement deliberate, exact Jarvis approvals using only a no-op
simulator.

**Sections and deliverables**

- Distinct rendering and lifecycles for Codex requests versus Jarvis approvals.
- Immutable command/procedure/adapter binding with session/task IDs, exact
  executable and `argv[]`, working directory, targets, policy digest, state
  digest, nonce, expiry, and one-use semantics.
- Two-step approval interaction with no default approval focus and paste
  rejection.
- Accept, decline, cancel, expire, supersede, amend, restart, stale-state,
  concurrent-request, replay, and cross-session tests.
- Safe preview that cannot execute or answer an App Server request.

**Completion criteria**

- Adversarial tests cannot broaden, forge, confuse, reuse, or replay an
  approval.
- Approval decisions never become host execution or App Server responses.
- Any mismatch, expiry, audit failure, or unexpected state stops progression.

**Status:** Complete and fixture-validated; simulator only.

### Phase 4 — Registered read-only observations

**Objective:** add bounded evidence collection to the direct-host shadow
console, first from fixtures and then from explicitly enrolled workstation
adapters. The workstation is primary; VM work is optional rehearsal.

#### 4A. Fedora scenario-lab prerequisite

- Define fixture-only Fedora system-twin profiles, scenario matrices, reset and
  isolation contracts, physical gaps, and coverage digests.
- Keep VM work optional and software-focused; never treat it as physical
  hardware evidence.

**Completion criteria:** declared scenarios parse, validate, isolate, reset, and
reject undeclared state; coverage remains explicitly Stage 1.

**Status:** Fixture-complete.

#### 4B. L1 controller and workstation enrollment contract

- Define disabled typed controller operations and lifecycle state machine.
- Define source catalog, 90-fact enrollment proposal, three consent tiers,
  exact request/response fixtures, and no-authority review state.

**Completion criteria:** contracts validate, all operations/sources/groups are
disabled until explicit transition, host binding is unresolved until approved,
and no controller service exists.

**Status:** Structural checkpoint complete; enrollment authority remains off.

**Implementation update (2026-08-06):** a typed fixture-only broker facade now
enforces minimal Tier-0 scope, digest binding, expiry, replay rejection, and
live-mode denial. Restricted facts remain ephemeral until an independently
attested encrypted backend is supplied; activation is still off.

#### 4C. L2 full Fedora Workstation VM blueprint

- Define one full Workstation image with headless and graphical boot profiles.
- Define readiness checks, image/domain locks, provisioning gates, fresh
  overlays, reset, and graphical integration boundaries.
- Add fixture-only Tier-0 parsers for OS, kernel/architecture, CPU topology,
  memory/NUMA, and declared scenario responses.

**Completion criteria:** all parsers and schemas reject malformed, duplicate,
  inconsistent, non-UTF-8, secret, or undeclared data; no VM is downloaded,
  provisioned, started, or treated as physical evidence.

**Status:** Blueprint and fixture checkpoint complete; actual VM remains
optional and unprovisioned.

#### 4D. Direct-host H-gates

- H1: bounded read-only enrollment and source binding.
- H2: layered recovery design.
- H3/H4: establish and test recovery boundaries.
- H5: shadow/read-only operating mode.
- H6: first bounded lighting case.

**Completion criteria:** every live read is registered, bounded, redacted,
one-attempt, freshness-labeled, attributed, and audit-linked; protected reads,
session activation, input monitoring, connector status, and physical writes
remain separately gated.

**Status:** Direct-host recovery evidence and lighting adapters exist in the
runtime records. The user-confirmed display-brightness and keyboard-light
repairs are recorded; H1 activation and a fresh enrolled-host observation are
still pending.

#### 4E. First lighting use case

- Diagnose display brightness, keyboard lighting, hotkeys, desktop integration,
  GPU topology, runtime power, and version/change history as separate layers.
- Keep Tier-0 sysfs/proc reads separate from Tier-1 platform/provider,
  Tier-2 WMI-binding, Tier-3 connector association, UPower/session, and any
  mutation.
- Prepare repair plans with exact target, validation, rollback, and independent
  review.

**Completion criteria:** the evidence distinguishes provider presence,
requested/actual behavior, input event path, desktop integration, and physical
effect; no hypothesis is promoted merely from correlation.

**Status:** Prepared and partially observed; the original manual symptom is
user-confirmed resolved, while Jarvis's machine-evidence record remains
read-only and must not infer current service state from that confirmation.

### Phase 5 — Supervised mutation foundation

**Objective:** authorize one narrow reversible mutation behind a separate OS
authorization boundary.

**Sections and deliverables**

- Root-owned executor service with Polkit/equivalent authorization.
- Registered adapter protocol with fixed executable, arguments, target set,
  timeout, output bounds, environment allowlist, and version.
- Pre-change evidence, exact command approval, action-specific rollback,
  postcondition validation, independent review, and audit finalization.
- Fixture and isolated scratch/representative VM rehearsal before first host
  use.

**Completion criteria**

- One and only one reversible adapter reaches maturity Stage 4.
- Recovery is tested and evidence-linked.
- TUI/broker/model cannot call arbitrary commands or broaden the adapter.
- Approval is one-use, exact, unexpired, state-bound, and independently
  verified.

**Status:** Admission foundation implemented and independently approved as
fail-closed. `vm-lab/scripts/phase5_executor.py` has no enabled adapter or
host-mutation path; no supervised executor is installed.

### Phase 6 — Complete operational console

**Objective:** finish the workstation console without weakening boundaries.

**Sections and deliverables**

- Errors: immutable attempts, diagnosis revisions, constraints, and sanitized
  output.
- Lessons: evidence counts, candidate revisions, activation/suspension, and
  user-only promotion.
- Recovery: boundaries, snapshots, backup/restore tests, RPO/RTO, and gaps.
- Settings: versioned policy, safe defaults, full diffs, and high-risk review.
- Audit integrity, encryption state, remote-sink status, and recovery views.
- Evidence-linked recommendations and redacted incident/maintenance exports.
- Optional desktop notifications that cannot approve work.
- Accessibility, keyboard-only, resize, plain mode, privacy, crash recovery,
  and reconnect acceptance tests.

**Completion criteria**

- Every view in `docs/tui-contract.md` is functional and tested.
- Reports are redacted, exportable, evidence-linked, and reproducible.
- Crash/reconnect/audit/locked-store failures fail closed.
- The console accurately labels simulated, unimplemented, stale, inferred,
  sandbox-scoped, and live evidence.

**Status:** Complete for the constructed, read-only release gate. Errors/
attempts, lessons, recovery, settings, audit, notifications, reconnect state,
locked-store failures, and explicit local redacted-export delivery are visible
and tested in the Operations view. Mutation, execution, fact persistence, and
approval authority remain outside the TUI; deployment and live acceptance are
separate gates.

### Phase 7 — Increasing bounded autonomy

**Objective:** selectively automate only procedure-specific, mature, revocable
workflows.

**Sections and deliverables**

- Gather independent evidence over repeated successful supervised procedures.
- Promote versioned procedure revisions through capability maturity review.
- Define narrow Stage 5 policies, monitoring, stop conditions, revocation, and
  recovery.
- Keep the pre-authorized safe list disabled until a specific procedure earns
  Stage 5 and receives explicit user approval.

**Completion criteria**

- Automation is procedure-specific, bounded, auditable, monitored, revocable,
  and recoverable.
- No lesson, repeated success, model confidence, or active session creates
  broad authority.
- Security, boot, firmware, identity, encryption, storage, and remote-access
  actions never skip independent review.

**Status:** Planned and initially disabled. Optional; not required for a safe
supervised release.

## 6. Capability maturity gates

| Stage | Meaning | Permitted use | Promotion evidence |
|---|---|---|---|
| 0 — Defined | Contracts/instructions exist | Documentation only | Reviewed schemas and policy |
| 1 — Validated | Static/unit/fixture tests pass | Fixture use | Deterministic tests and coverage |
| 2 — Rehearsed | Representative isolated rehearsal passes | Lab/scratch target | Reset, isolation, and repeatable result |
| 3 — Observed | Read-only production evidence works | Live observation | Bounded, redacted, audited evidence |
| 4 — Supervised | Recovery-tested mutation works | Exact human approval | Pre-state, rollback, postcondition, independent review |
| 5 — Automated | Repeated evidence and external audit | Narrow pre-approved policy | Explicit policy transition, monitoring, revocation |

Each adapter advances independently. A completed phase does not promote every
capability in that phase.

## 7. Recovery and direct-host roadmap

The workstation recovery model has four boundaries:

- **R0:** record and independently copy affected project files; not OS
  protection.
- **R1:** local filesystem/subvolume snapshot; cannot cover other subvolumes,
  `/boot`, EFI, partitioning, firmware, or device failure.
- **R2:** external encrypted system backup covering the declared root, home,
  nested machines, boot, and EFI boundaries with independent comparison and
  restore proof.
- **R3:** offline full-device recovery for partition/device loss; requires
  separate bootable-media and hardware testing.

Recovery completion requires topology resolution, secret/privacy boundaries,
preflight, exact approval, one attempt, audit finalization, independent
comparison, and a tested restore. An untested backup is never presented as
recoverable.

## 8. Cross-cutting validation roadmap

### Contract and unit tests

- Schema/canonicalization, digest stability, risk monotonicity, approval
  expiry/replay/state binding, reducer determinism/idempotency, sanitization,
  registry-to-menu generation, and disabled-state reasons.

### Integration tests

- Fake and real pinned App Server streams; reconnect, resume, steer,
  interrupt, compaction, capacity, locked database, failed MCP, corrupt ledger,
  and approval-request separation.

### TUI tests

- Headless keyboard workflows at compact/wide sizes, focus safety, paste
  rejection, reachable cancel, plain-mode semantics, terminal restoration, and
  crash cleanup.

### Security tests

- Prompt injection in logs/docs/MCP output; terminal escapes/hyperlinks;
  argument injection; forged/stale/replayed/broadened approvals;
  path/symlink replacement; and proof that no compromised frontend has a raw
  privileged channel.

### Release tests

- Syntax/metadata, plugin/skill/config/schema/policy/hook/MCP validation,
  redaction, ledger integrity, representative read-only cases, independent
  security review, release-manifest generation, and separate-process startup
  validation.

## 9. Release and self-update sequence

1. Build in an isolated worktree or branch.
2. Run all deterministic tests and inspect the complete diff.
3. Generate and review the release manifest and capability/permission diff.
4. Obtain independent security review for policy, hooks, MCP, approval, audit,
   or privilege changes.
5. Create an immutable versioned release while preserving the previous one.
6. Request approval bound to the manifest digest.
7. Activate atomically using a pointer or directory rename.
8. Validate from a separate process and roll back on startup, policy, MCP, or
   ledger failure.
9. Record release, reviewer, approval, activation, and result externally.

## 10. Historical master status — 2026-08-07

This snapshot is retained as evidence and is superseded for current TUI
authority by `current-product-state.md` and `tui-contract.md`.

- Phases 0–3: implemented and fixture-validated.
- Phase 1 live App Server acceptance: passed on 2026-08-06 for the pinned
  `codex-cli 0.146.0`; account/capacity reads, thread lifecycle, one
  conversation-only read-only turn, steer/interrupt, reconnect/resume, and
  clean disconnect are recorded in the runtime report. No host authority was
  used.
- Phase 2 live TUI launch: offline startup and all 53 TUI tests validated in
  the project-local `.venv` with pinned `textual==8.2.8`; live App Server
  acceptance is recorded with Phase 1.
- Phase 3: simulator only; no host execution.
- Phase 4: structural/fixture contracts and prepared bounded lighting
  observations are present; the direct-host shadow track is primary and VM
  remains optional and unprovisioned.
- Phase 5: admission-only executor foundation is implemented and independently
  approved; no adapter, OS authorization, or supervised executor is installed.
- Phase 6: complete for the constructed read-only console. The Operations
  projection now covers failure, lesson, recovery, settings, audit-integrity,
  locked-store, reconnect, and notification states. Redacted exports have an
  explicit local no-overwrite delivery boundary. Full local VM-lab and TUI
  suites pass; deployment and live acceptance remain separate decisions.
- Phase 7: disabled and not required for supervised release.
- Bounded useful-host expansion (prepared 2026-08-07): passive lighting/DRM
  observation and deterministic diagnosis contracts are implemented and tested;
  lighting repair and power-profile operations are represented in the catalog
  but remain unregistered and disabled. Credentials, arbitrary network access,
  protected logs, and device-waking probes remain unavailable.
- TUI lighting controls (constructed 2026-08-07): graphical effect, brightness,
  speed, direction, color, and zone controls generate a typed preview of the
  Acer RGB driver interface. The Apply action remains disabled and cannot call
  the driver directly.
- Codex CLI target: `0.146.0`; App Server connection and live turns remain
  explicit opt-in.
- Runtime v2 audit ledger: verified valid with 85 events at the snapshot.
- Knowledge database: present and recently updated.
- Local R1 snapshot: completed 2026-08-07 at
  `/var/lib/jarvis-r1-20260807T085200Z`, covering read-only `root`, `home`,
  and `var/lib/machines` snapshots; boot/EFI remain outside R1.
- Fresh encrypted R2 system set: completed and independently verified
  2026-08-07. Restic snapshot `d28c9d2e` with tag
  `jarvis-r2-system-set-20260807T090408Z` passed `check --read-data`, restored
  into `/var/lib/jarvis-r2-restore-20260807T090408Z/data`, and matched all five
  boundaries with zero mismatches and no proof gaps; the restored target is
  retained read-only. Bootability and bare-metal reconstruction remain outside
  this file-level R2 proof.
- Release manifest: regenerated and verified with 650 entries after the
  lighting, TUI-control, roadmap, broker, storage-gate, and live-acceptance
  updates.
- The user's confirmed successful display-brightness and keyboard-RGB repairs
  are recorded in `docs/use-case-lighting-controls.md`; a fresh enrolled-host
  observation is still required before asserting current service/module state.
- H1 runtime-gate construction: prepared-only contracts now pin exact decision,
  policy, service, transport, adapter, and storage bindings; autonomous fresh
  review execution is available through `automation/run-independent-review.sh`.
  The final independent review passed artifact/test checks but keeps activation
  blocked because Python's standard SQLite interface does not eliminate the
  same-UID database/journal pathname race. This is recorded in
  `runtime/reports/2026-08-07-h1-runtime-independent-review-final.json`.
- A sidecar-free descriptor-bound authority-ledger prototype is prepared and
  independently exercised, but remains unwired. Its in-file checkpoint detects
  truncation with the checkpoint retained; complete snapshot rollback still
  requires an external authenticated monotonic checkpoint and remains blocked.
- The TPM checkpoint contract and fixture-only HMAC emulator are prepared and
  independently reviewed. The real TPM NV index, protected key, and backend
  integration remain intentionally unconfigured and blocked pending a separate
  privileged setup decision and final activation review.
- H1 Tier-0 runtime activation: completed 2026-08-07 after fresh independent
  approval. `jarvisd.service` is active as a user-scoped service; the exact
  four approved adapters expose 14 read-only facts, with no fact persistence,
  mutation, privilege, network, or device access. A follow-up observation also
  passed and is recorded in
  `runtime/reports/2026-08-07-h1-followup-observation-20260807T162422Z.json`.
- Phase 2B TUI status bridge: complete for read-only status projection. The
  TUI remains offline by default and requires explicit `--connect-jarvisd` to
  display H1 service state; it has no observation or executor method.
- Phase 5 admission foundation: complete for exact operation/parameter/target/
  policy binding, expiry, and trusted one-use-ledger integration. The executor
  remains disabled and no real command, persistence, or policy mutation path
  exists. Independent review verdict: APPROVE for the prepared foundation.
- Phase 6 operational projection: the TUI now displays redacted Phase 5
  rehearsal status and rollback evidence alongside H1/recovery status; it
  remains read-only and cannot submit execution requests.
- Phase 5 host power-provider setup: TuneD and `tuned-ppd` are active with the
  hardware-compatible `jarvis-balanced` profile; `tuned-adm verify` passes and
  the standard PPD API reports `balanced`. Evidence is in
  `runtime/reports/2026-08-07-power-profile-provider-activation.json`. The
  read-only provider-status adapter is now constructed, tested, and independently
  approved in `runtime/reports/2026-08-07-power-profile-status-adapter-review.json`,
  but remains unregistered and unreachable from the TUI. The mutation adapter
  remains unimplemented pending authorization, rehearsal, and independent review.

## 11. Recommended next sequence

1. [Completed 2026-08-06] Install `textual==8.2.8` in an isolated environment
   and launch the TUI in offline mode; the 53-test TUI suite passes.
2. [Completed 2026-08-06] Run the pinned real App Server smoke test with
   explicit consent; verify account/capacity, thread start/resume, one
   conversation turn, interruption, and disconnect recovery.
3. [Completed 2026-08-06] Record the final user-confirmed lighting success and
   keyboard RGB driver setup as a bounded, non-secret deployment note.
4. [Completed 2026-08-06] Reconcile the lighting documentation and regenerate
   the release manifest.
5. Continue Phase 2B/4D direct-host shadow integration: replace the residual
   SQLite pathname/journal race with a descriptor-aware storage boundary,
   rerun autonomous review, then (only after a separate final user decision)
   consider one bounded Tier-0 observation. No activation is implied here.
6. [Completed 2026-08-07] Create the local R1 snapshot set and refresh the
   encrypted R2 system set; verify repository data, full restore, and all five
   boundaries independently.
7. [Completed 2026-08-07] The disposable-only
   `jarvis.rehearsal.marker@1.0.0` candidate was independently approved and
   exercised once with explicit user authorization. The present→absent
   transition, target binding, empty final marker, and temporary-root cleanup
   passed; evidence is in
   `runtime/reports/2026-08-07-phase5-rehearsal-marker.json`. It remains
   unregistered and disabled.
8. [Provider setup completed 2026-08-07] TuneD/PPD provider discovery,
   hardware-compatible profile selection, and D-Bus identity verification are
   complete. Next, review the power-profile selection candidate in
   `docs/phase-5-host-adapter-power-profile-candidate.md`; do not implement or
   register the mutating adapter until OS authorization, rehearsal, and a fresh
   independent review are complete.
9. [Read-only status adapter approved 2026-08-07] The fixed GetAll-only provider
   reader and focused tests passed a fresh independent review. Keep it
   unregistered until a separate integration decision is made.
10. [Disposable transition rehearsal approved and completed 2026-08-07] The in-memory
    `balanced -> performance -> balanced` and power-saver transitions passed
    exact postcondition and rollback checks with zero D-Bus calls, filesystem
    writes, or executor invocation. Evidence is in
    `runtime/reports/2026-08-07-power-profile-transition-rehearsal.json`; the
    fresh review is recorded in
    `runtime/reports/2026-08-07-power-profile-transition-rehearsal-review.json`.
11. [Authorization boundary defined 2026-08-07] The exact current-session,
    TUI-confirmed, 60-second one-use PPD/Polkit boundary and notify-only warning
    policy are encoded in
    `vm-lab/controller/power-profile-authorization-policy.json` and validated
    by `vm-lab/scripts/power_profile_authorization.py`. A fresh independent
    review approved the boundary; the live mutation path remains unregistered.
    Evidence is in
    `runtime/reports/2026-08-07-power-profile-authorization-boundary-review.json`.
12. [Independently approved 2026-08-07] The prepared supervised adapter in
    `vm-lab/scripts/power_profile_mutation.py` passed a fresh independent review.
    It binds the fixed PPD transport, advertised-profile precondition, TUI and
    active-session gates, best-effort pre-mutation notifications, one setter,
    postcondition validation, and no-rollback/new-approval failure semantics.
    It remains unregistered and has no live-execution authorization. Evidence
    is in `runtime/reports/2026-08-07-power-profile-mutation-adapter-review.json`.
13. [Independently approved 2026-08-07] The prepared executor bridge in
    `vm-lab/scripts/power_profile_executor_bridge.py` binds exact parameters,
    fixed target, checked-in policy digest, expiry, trusted adapter revision,
    and one-use approval before calling the reviewed adapter. It remains
    unregistered and disabled. Evidence is in
    `runtime/reports/2026-08-07-power-profile-executor-bridge-review.json`.
14. [Pass with conditions: independently reviewed 2026-08-07] Bound the bridge
    to the prepared descriptor-bound `PowerProfileAuthorityLedger`, with exact
    schema/journal/synchronous validation, reopen/replay, duplicate, corruption,
    and ledger-failure tests. The review found no blocking code defect, but its
    sandbox could not create temporary directories for five ledger tests; the
    local writable run passed all 39 focused tests. A subsequent fresh writable
    rerun passed 39/39 with a clean disposable directory. Keep live execution
    disabled until a separate deployment decision is made. Evidence is in
    `runtime/reports/2026-08-07-power-profile-durable-ledger-binding-review.json`
    and `runtime/reports/2026-08-07-power-profile-focused-writable-rerun.json`.
15. [Completed 2026-08-07] Reconcile the active H1 Tier-0 policy contracts with
   controller, broker, observation, VM-blueprint, readiness, service, and
   fixture expectations without widening authority. The full VM-lab suite
   passes 181 tests; the TUI presentation/headless slice passes 17 tests
   (four Textual tests skipped when the optional dependency is unavailable).
16. [Completed 2026-08-07] Construct the Phase 6 read-only Operations view with
   immutable failure projection, evidence-backed lesson policy, recovery
   boundaries, safe settings, audit status, and notifications. It has no
   observation, command, persistence, policy-mutation, or approval path.
17. [Completed 2026-08-07] Add a deterministic bounded redacted operational
   export payload. It is generated in memory only; no automatic file write,
   remote sink, or approval path exists.
18. [Completed 2026-08-07] Complete Phase 6 operational views and acceptance
   tests: explicit local redacted-export delivery, locked-store/audit-integrity
   fail-closed projections, reconnect/crash-safe status labeling, compact and
   wide keyboard acceptance, and notification-only display integration. No
   deployment or authority widening occurred.
19. Leave Phase 7 automation disabled until a specific procedure earns Stage 5.
20. [Reviewed with conditions 2026-08-07] Construct bounded lighting/DRM
    observation and diagnosis, graphical preview controls, and exact disabled
    lighting-repair and power-profile operation bindings. The fresh review
    found no high or medium security findings; its full TUI reproduction was
    limited by sandbox AF_UNIX permissions. Evidence is in
    `runtime/reports/2026-08-07-bounded-authority-expansion-v1.json`.
21. [Completed one-use promotion 2026-08-07] Promote and execute exactly one
    passive lighting observation through the owner-only Jarvisd method. The
    durable authorization was consumed after the bounded read; the result was
    ephemeral and no facts or hardware state were persisted or mutated. The
    no-connector-status/device-wake boundary held. Lighting repair and
    power-profile mutation remain disabled and require separate reviews and
    approvals for any future promotion.
22. [Constructed 2026-08-07] Add a fail-closed lighting-repair executor
    boundary with exact diagnosis/plan/review bindings, one-use semantics, and
    explicit new-approval rollback requirements. It cannot mutate the host.
23. [Constructed 2026-08-07] Complete the supervised TuneD/PPD executor
    contract and add TUI-only mutation approval previews for lighting repair and
    power profiles. Both remain simulation-only and unregistered. Separate
    read-only review packets are in `runtime/review-prompts/`; evidence is in
    `runtime/reports/2026-08-07-mutation-construction-v1.json`.
24. [Completed 2026-08-08] Resolve the TUI AF_UNIX validation limitation with
    a writable run: 70 tests passed and five optional Textual tests were
    skipped. Bind both mutation paths to explicit one-use approval fields,
    independent-review digests, and new-approval rollback rules. Select the
    first proposed live target as a TuneD/PPD transition to `balanced`; capture
    the actual pre-profile at activation time and stop on stale/no-op state.
    No deployment or host mutation was performed.
25. [Constructed 2026-08-08] Add the bounded energy-control framework covering
    read-only Powertop summaries, CPU EPP/turbo, Intel/NVIDIA runtime power
    controls, and TuneD/PPD profiles. Controls are allowlisted, thermal-gated,
    one-use, rollback-bound, and previewed in the TUI. The executor remains
    disabled pending an independent energy-specific review and deployment
    decision. Evidence is in
    `runtime/reports/2026-08-08-energy-control-framework-v1.json`.
26. [Constructed 2026-08-08] Add a read-only RPM package inventory to the TUI
    with full, alphabetical, category, and purpose-oriented views. Packages
    are classified for NVIDIA/GPU, Intel, GNOME, lighting, kernel, development,
    virtualization, audio, network, security, and other purposes. The provider
    is fixed, non-shell, timeout-limited, bounded, and mutation-free. Evidence
    is in `runtime/reports/2026-08-08-package-inventory-v1.json`; independent
    review remains required before treating the scan as a live Jarvis fact.
27. [Constructed 2026-08-08] Enrich package inventory with bounded local
    dependency/reverse-dependency queries, installed-file ownership, DNF
    transaction history, and repository-origin data. Advisory queries are
    explicitly network-gated and disabled by default. Evidence remains
    ephemeral in the TUI pending independent review.
28. [Constructed pending review 2026-08-08] Expand package inventory into Installed/Available/
    Combined/Updates modes with versions, repositories, authoritative RPM
    conflicts, alternatives, dependency graphs, ownership, transaction history,
    and explicitly network-gated advisories. The full plan is in
    `docs/package-availability-and-compatibility-plan.md`. Cached available,
    combined, and update views, bounded pagination, authoritative relationship
    types, and evidence-labelled recommendation records are implemented.
    Network refresh, advisories, and package transactions remain disabled.
29. [Completed 2026-08-08] Make the Packages tab load the installed RPM
    inventory automatically in a background worker on first open, cache it for
    the TUI session, and turn the manual Scan button into Refresh. A live local
    read observed 2,257 installed packages; the actual Textual headless test
    verifies automatic loading.
30. [Completed 2026-08-08] Repair the Packages TUI rendering regression that
    treated a complete text result as an iterable of characters. Replace the
    unstructured inventory log with a zebra-striped, keyboard-selectable table,
    two compact toolbars, a guaranteed ten-row minimum table viewport, a compact
    status summary, and a separate details panel. Selecting a row now fills the
    exact package-name field and presents its state, category, origin, and
    inferred purpose without another scan. The same field now performs a real
    case-insensitive filter on Enter across names, versions, summaries,
    categories, purposes, origins, and installation states; submitting an empty
    field clears the filter.
31. [Constructed and integrated read-only 2026-08-08] Add a dedicated Power
    tab with automatic bounded discovery of TuneD/tuned-ppd, Intel P-state and
    CPU frequency controls, ACPI platform profiles, Intel/NVIDIA DRM runtime
    power, exposed i915/NVIDIA module parameters, power supplies, Powertop
    installation, and NVIDIA kernel-driver presence. The section menu displays
    current values, advertised choices, and exact evidence sources. Device-
    waking probes, privilege, network access, and all mutations remain disabled.
    Evidence is in `runtime/reports/2026-08-08-power-inventory-v1.json`.
32. [Constructed and tested pending review/deployment 2026-08-08] Add supervised
    live changes for the five allowlisted power controls: desktop power profile,
    CPU EPP, CPU turbo, Intel GPU runtime PM, and NVIDIA GPU runtime PM. Every
    operation binds an observed pre-state, changes one setting, verifies its
    postcondition, and replaces the single durable last-change undo record.
    Undo requires a new TUI confirmation and desktop authorization, rejects
    drift, and restores only the captured pre-state. An interrupted or partial
    apply is exposed as a separate reviewed recovery using the fsynced prepared
    record; it never rolls back automatically. The root helper has no
    shell, arbitrary path/value, network, or automatic rollback surface.
    Profile and turbo changes fail closed without readable thermal evidence and
    are blocked at or above 90°C.
    Evidence is in `runtime/reports/2026-08-08-power-live-control-v1.json`.

## 12. Source documents

- `docs/platform-architecture.md`
- `docs/tui-implementation-plan.md`
- `docs/tui-contract.md`
- `docs/phase-1-read-only-broker.md`
- `docs/phase-2-hybrid-tui.md`
- `vm-lab/scripts/observation_broker.py`
- `vm-lab/scripts/restricted_fact_store.py`
- `runtime/reports/2026-08-06-phase4-activation-readiness.json`
- `docs/phase-4-vm-lab-prerequisite.md`
- `docs/phase-4-l1-controller-enrollment.md`
- `docs/phase-4-l2-full-vm-blueprint.md`
- `docs/direct-host-deployment-and-recovery.md`
- `docs/r2-system-recovery-set.md`
- `docs/capability-maturity.md`
- `docs/release-and-self-update.md`
- `docs/evaluation.md`
- `docs/runbook.md`
