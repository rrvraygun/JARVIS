# Phase 5 host-adapter candidate — power-profile selection

This is a design-only candidate for the first real workstation adapter. It is
not implemented, registered, or reachable from the TUI.

Provider discovery found no `powerprofilesctl` binary or standalone
power-profiles-daemon. TuneD and `tuned-ppd` are now active, and the custom
`jarvis-balanced` profile verifies successfully. The standard
`org.freedesktop.UPower.PowerProfiles` API reports `balanced` through the
`balanced=jarvis-balanced` mapping. Setup evidence is recorded in
`runtime/reports/2026-08-07-power-profile-provider-activation.json`.
The Jarvis mutation adapter is still not implemented, registered, or reachable
from the TUI.

## Read-only status adapter

The first construction step is complete in
`vm-lab/scripts/power_profile_status.py`. It is bound to the fixed system-bus
name, object path, and `org.freedesktop.DBus.Properties.GetAll` call. It
normalizes only the three PPD profile names and the fixed `tuned` driver,
accepts only TuneD's defined degraded-state values, rejects unknown or
inconsistent provider responses, and emits a redacted `read_only` status object.
It has no
`Set`, `HoldProfile`, `ReleaseProfile`, subprocess, filesystem-write, or TUI
mutation path. Focused coverage is in
`vm-lab/tests/test_power_profile_status.py`. The adapter is not registered with
the live broker or executor pending independent review.

## Disposable transition rehearsal

The in-memory simulator at
`vm-lab/scripts/phase5_power_profile_rehearsal.py` exercises
`balanced -> performance -> balanced` and `balanced -> power-saver -> balanced`
with exact postcondition and rollback checks. It has no D-Bus, filesystem,
executor, or host path. The successful rehearsal is recorded in
`runtime/reports/2026-08-07-power-profile-transition-rehearsal.json` and does
not authorize a live profile change.

## Exact operation

- operation ID: `jarvis.powerprofile.select`
- revision: `1.0.0`
- target: the current local user session's power-profile service only
- parameters: exactly one enum: `power-saver`, `balanced`, or `performance`
- effect: request that one profile through the platform's typed power-profile
  interface; no arbitrary executable or argument expansion
- rollback: read and record the pre-state, then request that exact profile with
  a new approval if rollback is needed
- validation: read the active profile after the operation and require exact
  equality with the approved enum

## Required gates before implementation

1. observe the installed power-profile provider and supported profile enum
   without changing state;
2. bind the adapter to a fixed provider API and exact user-session target;
3. define the OS authorization/Polkit boundary and recovery evidence;
4. rehearse profile transitions in a disposable environment or documented
   provider simulator;
5. obtain a fresh independent review and explicit approval for one profile
   change;
6. perform one supervised attempt, verify the postcondition, and record the
   prior profile for rollback.

The candidate must reject unknown profiles, provider drift, target drift,
stale pre-state, unsupported rollback, and any request that could wake devices,
change kernel settings, alter persistence, or broaden into arbitrary commands.

## Host-compatible TuneD profile

The Fedora generic `balanced` profile is active on this Acer Nitro 5, but its
verification includes hardware interfaces that this Intel P-state host does
not expose (the conservative governor module, per-CPU boost, ACPI platform
profile, and ALPM on every SCSI host). The reproducible host profile at
`vm-lab/profiles/tuned/jarvis-balanced/tuned.conf` deliberately manages only
the controls observed here: the `powersave` governor, `balance_performance`
energy-performance preference, and the audio timeout. It does not alter
NVIDIA settings, disk ALPM, turbo policy, kernel parameters, or external
devices. Because the standard PPD API exposes the name `balanced`, its
`[profiles]` mapping must point `balanced=jarvis-balanced`; otherwise PPD
correctly reports the custom TuneD name as `unknown`.

## Defined OS authorization boundary

The approved boundary is recorded in
`vm-lab/controller/power-profile-authorization-policy.json` and validated by
`vm-lab/scripts/power_profile_authorization.py`:

- the caller must be the current active user session and the TUI must provide
  an explicit confirmation; the existing provider Polkit permission is used,
  with no separate password prompt required;
- all three standard profiles are allowed, with exactly one transition per
  60-second, one-use authorization stored in the existing durable authority
  ledger;
- the only future mutation is the fixed PPD `ActiveProfile` property through
  `org.freedesktop.UPower.PowerProfiles`; no sudo, shell, `tuned-adm`, direct
  sysfs, NVIDIA control, holds, automatic switching, or arbitrary parameters;
- battery, thermal-degradation, and provider-degraded states generate user
  notifications but do not block the request;
- a failed postcondition stops and explains the problem. Rollback is never
  automatic and requires a separate new approval.

This is an admission contract only. The policy and validator do not call
D-Bus, Polkit, the ledger, or the TUI, and the mutation adapter remains
unregistered.

## Prepared supervised adapter

`vm-lab/scripts/power_profile_mutation.py` implements the fixed D-Bus
`ActiveProfile` transition against an injected transport for testing and a
fixed system-bus transport for a future deployment. It reads and validates the
pre-state, performs one exact setter call, validates the post-state, and sends
notify-only warnings through a best-effort callback before the setter so they
remain visible even if the mutation or postcondition fails. Notification
delivery itself never blocks the approved operation. The adapter stops without
automatic rollback on setter or postcondition failure. It does not consume the authority ledger itself;
the executor must consume the durable one-use approval before any future
registration. The adapter is not registered with the executor, broker,
service, or TUI.
