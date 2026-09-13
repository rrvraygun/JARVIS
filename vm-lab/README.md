# Fedora system-twin and scenario laboratory

## Current result

This directory is the execution-free prerequisite for Jarvis Phase 4. It
defines how a future disposable Fedora guest will be identified, isolated,
reset, exercised, and prevented from making claims that only the physical
workstation can support.

The current mode is fixture-only. It can parse JSON, expand declared state
matrices, evaluate deterministic oracles, validate the future controller,
enrollment, Tier-0 observation, full-VM blueprint, readiness, and provisioning
contracts, and print ephemeral reports. It has
no process, shell, network, hypervisor, privilege, device, host-observation,
guest-creation, or persistence interface. No Fedora image has been selected or
downloaded, no host has been scanned, and no VM has been created or started.

## What “mirror the real system” can mean

A useful system twin is layered, not a promise of identical hardware:

| Layer | What can be matched | Evidence needed | Current state |
|---|---|---|---|
| Contract logic | Policy, approvals, stop rules, parsers, redaction, audit transitions | Deterministic fixtures | Implemented |
| Software twin | Fedora release, kernel, packages, desktop, services, configuration classes, drivers and filesystem behavior supported by the guest | Approved workstation enrollment plus locked guest build | Unknown |
| Virtual hardware | CPU topology, memory, disks, firmware mode and deliberately modeled virtual devices/failures | Locked domain definition plus VM rehearsal | Unknown |
| Physical hardware | Real NVIDIA power rails, panel wiring, ACPI/EC methods, firmware hotkeys, keyboard LEDs, battery and thermals | Controlled tests on the enrolled workstation | Not representable by a normal VM |

The VM can reproduce many software-visible states and inject missing devices,
malformed values, failures, timeouts, permission boundaries, stale state, and
unexpected output. It cannot prove physical luminance, real keyboard lighting,
actual GPU D3cold/off state, mux wiring, embedded-controller behavior, or
vendor firmware timing. Those claims remain listed in
coverage/physical-gaps.json.

“All possible scenarios” is therefore defined precisely as:

1. every combination in a versioned declared state space;
2. every curated regression case for known high-risk behavior;
3. every required isolation, reset, and promotion invariant;
4. an explicit open-gap record for everything the lab cannot represent.

It does not mean every possible kernel bug, device, firmware version, timing
race, or physical failure in the real world.

## Contracts

- policy/lab-policy.json — current authority (all operational flags off),
  future containment, clean-baseline, reset, evidence, and promotion rules.
- profiles/fedora-workstation-template.json — an honest unobserved twin
  template. User-declared Fedora/Bash scope is present; actual hardware and
  software facts remain unknown.
- images/fedora-workstation-image-lock.template.json — fields that a future
  official Fedora image lock must resolve and verify. It is unresolved and
  acquisition is disabled.
- matrices/lighting-controls.json — lighting/NVIDIA diagnostic state space and
  fail-closed oracles.
- matrices/sysadmin-control-plane.json — evidence, target, approval, audit,
  failure, risk, and intent handling applied across the 17 accepted domains.
- scenarios/catalog.json — named regressions for audit failure, stale state,
  hostile output, package surprises, scope confusion, recovery failure,
  never-positive actions, and the first lighting incident.
- coverage/expected.json — pinned counts and state-space digests. Any change
  requires an intentional versioned review.
- coverage/physical-gaps.json — claims a normal VM cannot close and the future
  physical evidence required for each.
- schemas/ — versioned twin, image, matrix, catalog, run, and report formats.
- fixtures/run-record.json — a truthful fixture run: unresolved VM identity,
  no VM start, no host observation, and no mutation.
- scripts/labctl.py — dependency-free fixture validator and oracle evaluator.
  It only reads source JSON and writes its report to standard output.
- controller/ — the typed future service boundary, operation registry, and
  lifecycle. No service or transport exists.
- enrollment/ — 32 source definitions and the unapproved 90-fact Fedora
  proposal split into Tier 0, Tier 1, Tier 2, and a separate L2 group.
- scripts/controller_contract.py — in-memory no-effect contract validation.
- observation/ — four digest-bound Tier-0 parser definitions and a broker
  policy with every live authority disabled.
- fixtures/observations/ — a synthetic Fedora Workstation parser fixture set;
  it never represents the host.
- scripts/observation_contract.py — reads only registered fixture files and
  emits fourteen ephemeral synthetic candidate facts.
- blueprints/fedora-workstation-full.json — one full Workstation guest with
  headless and graphical boot profiles, strict isolation, reset, evidence, and
  physical-gap boundaries.
- readiness/adapter-registry.json and scripts/readiness_contract.py — three
  fixture-only L2 parsers which, together with Tier 0, bind all eighteen
  readiness checks. No live backend or approval exists.
- readiness/fedora-kvm-readiness-plan.json — eighteen L2 readiness checks,
  with fixture parsers complete and every live backend disabled.
- blueprints/provisioning-gates.json — eight ordered gates from L2 adapter
  construction through disposable scenario overlays. Structural P0 is
  complete; P1 is blocked on fresh authorization and P2-P7 remain blocked.

## Current coverage

The pinned fixture set evaluates:

| Matrix | Evaluated state cases | Contexts | Logical declared cases |
|---|---:|---:|---:|
| Lighting controls | 64,512 | 4 external-display states | 258,048 |
| Sysadmin control plane | 60,480 | 17 capability domains | 1,028,160 |

There are 37 named regression cases, every oracle has at least one witness, and
every pair of declared values occurs in the Cartesian space. Ten physical gaps
remain open. These counts prove deterministic coverage of the declarations,
not Fedora, guest, or hardware correctness.

Local fixture validation:

~~~bash
python3 vm-lab/scripts/labctl.py validate
python3 vm-lab/scripts/labctl.py run-fixtures
python3 vm-lab/scripts/labctl.py coverage
python3 vm-lab/tests/test_vm_lab.py
python3 vm-lab/scripts/controller_contract.py
python3 vm-lab/tests/test_controller_contract.py
python3 vm-lab/scripts/observation_contract.py
python3 vm-lab/tests/test_observation_contract.py
python3 vm-lab/scripts/vm_blueprint_contract.py
python3 vm-lab/tests/test_vm_blueprint_contract.py
python3 vm-lab/scripts/readiness_contract.py
python3 vm-lab/tests/test_readiness_contract.py
~~~

These commands do not inspect or change Fedora. They only read project files;
reports are printed to standard output.

## Future laboratory checkpoints

Every checkpoint is a separate user-visible decision. None is authorized by
this structure.

### L0 — structural review (complete)

- Validate contracts, schemas, fixture oracles, pinned counts, and absence of
  execution interfaces.
- Confirm fixture evidence cannot promote beyond maturity Stage 1.
- Keep registered observations and every mutation disabled.

### L1 — approved workstation enrollment (contract prepared; observation pending)

- Present the exact proposed read-only facts, sources, bounds, redaction, and
  possible device-wake effects before any collection.
- Collect only after the user approves that observation phase.
- Bind each fact to observer scope, timestamp, version, source, and freshness.
- Store sensitive facts only in the future encrypted local store, unlocked by
  fresh user confirmation. Never transfer credentials or restricted host data
  to the guest.
- Produce a diff between user-declared, host-observed, and unknown facts. Never
  fill unknowns by inference.

The field-level proposal, controller boundary, four Tier-0 fixture parsers, and
full Workstation VM design are now prepared and fixture-validated. They do not
grant approval or perform enrollment. See controller/README.md,
../docs/phase-4-l1-controller-enrollment.md, and
../docs/phase-4-l2-full-vm-blueprint.md.

### L2 — virtualization readiness

- The exact eighteen-check fixture adapter set is complete. It has no live host
  authority. A live backend requires a fresh user decision, review, and VM
  rehearsal before the bounded observation can be presented for execution.
- Observe the exact Fedora virtualization stack and constraints without
  installing or changing anything.
- Decide whether KVM/QEMU/libvirt and required firmware are already available.
- If something is missing, prepare a separate state-changing installation plan
  with exact per-command approval, rollback, validation, and independent review.
- Device passthrough remains off. A later passthrough proposal needs its own
  threat model and cannot be treated as ordinary VM setup.

### L3 — official image lock

- Select a supported Fedora Workstation artifact only from the Fedora Project.
- Pin release, architecture, official locator, signed checksum document,
  independently verified signing-key fingerprint, image SHA-256, and
  verification timestamp.
- Pin QEMU, libvirt, machine type, firmware image, and domain-definition
  digests.
- Fail closed if the signature, checksum, release status, or any identity field
  is unresolved. Image download and verification are distinct approval-visible
  operations.

### L4 — isolated golden baseline

- Build a clean, powered-off golden base and make it non-writable.
- Use VirtIO/minimal emulation unless a scenario explicitly tests another
  virtual device.
- Disable runtime networking, host filesystem shares, clipboard, drag/drop,
  host USB, GPU passthrough, credentials, and production audit/knowledge mounts.
- Permit provisioning network only at its separate checkpoint, then remove it
  before scenario execution.
- Record the baseline and domain digests. A running/crash-consistent snapshot
  is not accepted as the clean baseline.

### L5 — one fresh overlay per scenario

- Create a new external overlay bound to one scenario/run ID.
- Attest baseline identity, domain identity, and overlay freshness before use.
- Run one attempt with fixed inputs, timeout, output cap, redaction,
  postconditions, surprise conditions, and evidence locations.
- Stop on timeout, malformed/hostile output, unexpected effect, target drift,
  policy drift, audit failure, or ambiguous result. Never retry automatically.
- Dispose of the overlay after the evidence record is finalized. Never reuse an
  ambiguous or failed overlay.
- Re-attest the immutable base digest after reset.

### L6 — VM rehearsal and promotion

- Rehearse registered read-only adapters before any live workstation use.
- Test missing tools, unsupported versions, permission denial, nonzero exit,
  timeout, malformed/truncated/hostile output, extra effects, stale state,
  contradiction, audit failure, disk pressure, interruption, and reset failure.
- A clean VM rehearsal can justify maturity Stage 2 for the exact adapter
  revision only. It does not promote a procedure family or hardware claim.
- Promotion requires an immutable run record, independent review, and explicit
  owner approval. Fixture or VM output never auto-promotes knowledge.

### L7 — physical gap closure

- Start only after safe VM rehearsal and a separate live-observation decision.
- Use the smallest discriminating physical observation; do not toggle GPU or
  power mode during diagnosis unless an exact state-changing plan is separately
  approved.
- Require user participation for hotkeys and visible lighting results.
- Preserve contradiction and uncertainty. A correlation cannot be promoted to
  causation without a mechanism and controlled evidence.
- Hardware-specific maturity remains blocked while any relevant physical gap is
  open.

## Reset and snapshot semantics

The future lab uses a powered-off clean base plus disposable external overlays.
This avoids treating a running snapshot—which may be only crash-consistent—as a
known-clean operating-system state. Snapshot availability is not a recovery
proof: reset must verify base identity, overlay disposal, audit finalization,
and the ability to reproduce the initial state.

The lab never mounts the authoritative Jarvis audit or knowledge stores into a
guest. Run records leave the guest through a narrow, future reviewed evidence
export and are treated as untrusted until validated outside the guest.

## Lighting scenario boundary

The first real use case remains diagnostic:

1. preserve “controls fail when NVIDIA is off” as a user report and hypothesis;
2. compare display providers, keyboard LED providers, desktop exposure,
   topology context, GPU-state evidence, and external-display report;
3. stop on permission boundaries, malformed/hostile results, timeouts,
   nonzero results, or any unexpected effect such as waking a device;
4. strengthen or weaken hypotheses without claiming causality;
5. close physical gaps only through separately approved workstation evidence;
6. prepare a repair only after diagnosis; do not execute it in this phase.

The matrix includes absent/multiple/malformed providers, desktop conflicts,
reported NVIDIA states, correlation states, output failures, protected
evidence, external-display contexts, and physical-evidence labels. It never
changes brightness, keyboard lighting, GPU state, power policy, drivers,
services, packages, boot parameters, or files.

## Future service boundary

When an actual VM runner is designed, it must be a separate unprivileged
laboratory service with a typed protocol. The TUI and model may request a
registered scenario by ID but must not receive a shell, hypervisor socket, raw
domain-definition write path, arbitrary image path, or passthrough handle.
Provision, start, stop, reset, export, and dispose operations each need fixed
schemas, exact targets, idempotency, audit events, and independent policy.

The future service is not present here. Adding it is a new architecture and
security checkpoint, not an implied continuation of scripts/labctl.py.

## Primary technical basis

- Fedora virtualization documentation:
  https://docs.fedoraproject.org/en-US/quick-docs/virtualization-getting-started/
- QEMU device and VirtIO documentation:
  https://www.qemu.org/docs/master/system/device-emulation.html
  and https://www.qemu.org/docs/master/system/devices/virtio/index.html
- QEMU Machine Protocol reference:
  https://www.qemu.org/docs/master/interop/qemu-qmp-ref.html
- libvirt snapshot format and semantics:
  https://libvirt.org/formatsnapshot.html
- Linux backlight, LED, and hybrid-graphics references are listed in
  ../docs/use-case-lighting-controls.md.
