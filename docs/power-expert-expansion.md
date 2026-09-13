# Power Expert expansion

**Status:** active implementation
**Updated:** 2026-08-30

## Scope

Power Expert is user-selectable and receives sanitized hardware/software power
evidence, provider state, package evidence, and bounded telemetry. It supports
manual profile design for user goals (`battery`, `performance`, `quiet`,
`thermal`, and `balanced`) with paired AC and battery variants.

The Power tab remains the live dashboard. Conversation is the agent-led entry
point. The user-selected specialist is authoritative; Power Expert does not
switch specialists automatically.

## Inventory and telemetry

The read-only inventory reports CPU/GPU topology, battery/AC supplies,
providers, software tools, firmware model-class facts, supported settings,
provider conflicts, and limitations. Unique identifiers such as serials and
UUIDs are not exposed. Live telemetry reads battery capacity/status/rate,
AC state, passive thermal values, and the active desktop profile. Polling is
bounded and only runs while the Power tab is active.

Provider detection includes the current TuneD/tuned-ppd and kernel paths plus
read-only discovery of TLP and auto-cpufreq. Multiple policy providers are
reported as conflicts and block profile writes until ownership is resolved.

## Profile and mutation contract

Profiles are owner-only, versioned JSON documents with AC/battery variants,
goals, selected allowlisted controls, and a stable digest. The deterministic
planner uses only controls exposed by current reviewed adapters and lists
unsupported values explicitly.

Each transaction also persists a versioned `PowerProfileApplicationRecord`
beside the profile. It binds the profile digest and records the selected AC or
battery variant, exact pre-state, requested values, verified resulting values,
three-way changed-control comparisons, unchanged controls, skipped reasons,
status, timestamp, and recovery metadata. Only an exact helper response whose
post-state matches the requested controls is `applied`; failed or interrupted
transactions remain `failed`/`indeterminate` and are never rendered as success.
Invalid or digest-mismatched records are ignored on restart.

The capability registry is versioned in
`plugins/jarvis-power-expert/registry/power-capabilities.json`, and the profile
wire contract is `registry/power-profile.schema.json`.

Current profile transactions support the reviewed power profile, CPU EPP,
CPU turbo, and Intel/NVIDIA runtime-policy controls. The root-owned helper
captures every control's pre-state, writes one prepared profile recovery record,
applies one exact multi-control transaction, and verifies all post-state. A
single approval covers the immutable validated set. Partial execution remains
indeterminate and requires a separately approved exact pre-state rollback.

Frequency/thermal and vendor-level controls are represented as capability
depths but become executable only through their own fixed reviewed adapters.
Generic sysfs writes and arbitrary vendor commands are not accepted.

## Package recommendations

Power Expert may perform read-only cached Fedora package searches and recommend
RPM packages or group identifiers. It creates a visible pending handoff card;
the user must explicitly select Installation Specialist before package preview,
approval, or mutation. Power Expert does not execute package changes in this
release. Documentation refresh requires explicit network approval.

## TUI behavior

The Power tab shows provider/software/hardware evidence, live telemetry, current
settings, profile drafting, save/preview/activation controls, and handoff state.
Conversation and the selected Power Expert context receive a durable confirmation
containing previous, requested, and resulting settings plus deterministic expected
impact. Existing manual single-control
Power Apply and Undo controls remain available and continue to use the same
approval and recovery boundaries.

Power Expert turns use the registered MCP Power tools under a read-only agent
sandbox. The agent may stage an activation proposal, but the TUI broker must
consume a fresh exact approval before invoking the registered helper; the helper
then performs the separate desktop authorization and post-state verification.

Natural-language Power requests are routed through the selected Power Expert
agent. The agent owns clarification, profile decisions, recommendations, and
explanations, and uses typed Power MCP tools for evidence, drafting, validation,
approval staging, verification, and recovery. Clarification answers remain
separate visible entries and never fall through to a generic shell/search
command approval.

The tab labels the automatically selected variant (`Preview variant` while
drafting, `Applied variant` after verification), keeps the latest applied result
separate from the current draft, and allocates inventory and settings equal
responsive regions with independent scrolling and bounded wrapping.
