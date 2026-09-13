# Phase 4 prerequisite: Fedora scenario-lab structure

## Result

The execution-free laboratory prerequisite is implemented and
fixture-validated. It defines the measurable system-twin layers, isolation
rules, official-image lock, clean-baseline and overlay lifecycle, run record,
promotion ceiling, physical gaps, cross-domain control-plane matrix, and the
lighting/NVIDIA diagnostic matrix.

This is not Phase 4 operational completion. Registered observations remain
disabled until a real disposable Fedora guest is separately provisioned and the
exact adapters pass its tests.

No host scan, package query, virtualization readiness probe, image resolution or
download, VM creation/start, hypervisor connection, passthrough, lighting
observation, installation, cleanup, update, repair, privileged action, system
mutation, or agent self-modification occurred.

## Evidence

- 37 curated regression scenarios pass their deterministic oracles.
- The lighting matrix evaluates 64,512 state cases and applies them across four
  external-display contexts: 258,048 logical cases.
- The sysadmin matrix evaluates 60,480 policy/evidence cases and applies them
  across 17 accepted capability domains: 1,028,160 logical cases.
- Every oracle is reachable and every declared pair is covered.
- Ten hardware/firmware/physical gaps remain open by design.
- The future official Fedora image lock is unresolved and acquisition is off.
- The twin template records no host binding, no scan, and no actual hardware or
  software facts.
- Every operational authority flag is false.
- Static tests reject process/network/virtualization imports and executable
  interface keys from machine assets.
- The fixture evidence promotion ceiling is maturity Stage 1.

Counts and state-space digests are pinned in vm-lab/coverage/expected.json;
changing a dimension or oracle fails validation until a reviewed contract
revision updates the expectation.

## What this proves

It proves deterministic handling of the declared policy and failure space,
including never-positive denial, audit failure, target ambiguity/expansion,
stale state, hostile and malformed output, timeout, permission denial, scope
confusion, replay, broadening, surprise effects, mutation blocking, recovery
failure, contradiction, and lighting diagnostic branching.

It does not prove:

- that virtualization is installed or usable on the workstation;
- the current Fedora release, kernel, packages, drivers, hardware, firmware, or
  configuration;
- that a future Fedora image is authentic;
- that a guest reset is actually clean;
- that any Fedora observation adapter behaves correctly;
- that a normal VM reproduces the physical GPU, panel, keyboard, ACPI/EC,
  hotkeys, suspend timing, battery, thermals, or connector wiring;
- that the reported NVIDIA correlation is causal;
- that brightness or keyboard lighting has been observed or repaired.

## Current boundary

vm-lab/scripts/labctl.py reads only versioned project JSON and prints reports.
It has no shell, process, network, hypervisor, privilege, device, host collector,
guest controller, or persistence API. The example run record explicitly states
that no VM started, no host was observed, and no mutation was attempted.

The complete design and future checkpoints are in vm-lab/README.md.

## Subsequent structural checkpoint

The future typed VM-controller boundary and exact read-only workstation-
enrollment proposal are now prepared and fixture-validated in
`phase-4-l1-controller-enrollment.md`. No observation ran. L1 remains
operationally incomplete until the proposal, adapters, encrypted storage,
observation broker, VM rehearsals, and a new explicit enrollment decision pass
their own gates.

The next static checkpoint is documented in
`phase-4-l2-full-vm-blueprint.md`: four Tier-0 fixture parsers, a full Fedora
Workstation design with headless and graphical profiles, eighteen L2 readiness
definitions, and eight closed provisioning gates. It also performed no host
observation or VM action.
