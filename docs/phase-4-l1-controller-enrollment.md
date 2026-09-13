# Phase 4 L1 structural checkpoint: controller and enrollment

## Result

The future VM-controller protocol boundary and exact Fedora workstation-
enrollment proposal are prepared and fixture-validated.

This does not mean L1 enrollment occurred. The proposal is unapproved, every
group is disabled, host identity is unresolved, and no observation adapter or
controller service exists.

No host scan, system-specification collection, virtualization readiness check,
network access, installation, image acquisition, VM lifecycle operation,
lighting diagnosis, protected read, device-waking probe, privilege, mutation,
or persistence occurred.

## Delivered contracts

- A controller policy with no transport, service, operational authority,
  persistence, observation, virtualization, network, privilege, or device
  access.
- Eighteen versioned operation definitions with exact parameters, identities,
  states, consent requirements, effects, and future adapter names.
- A closed lifecycle state machine with one attempt, no retry, and explicit
  stop/invalid/reset states.
- Thirty-two offline, non-mutating source definitions.
- Ninety normalized fact definitions across twelve consent-separated groups.
- Tier 0 automatic-read semantics only after exact proposal activation, Tier 1
  group confirmation, and Tier 2 per-probe confirmation.
- A separately deferred L2 virtualization-readiness group.
- Exact output-count, byte, freshness, transformation, privacy, and retention
  boundaries.
- Explicit exclusion of secrets, content, unique identifiers, personal paths,
  networking/VPN, and gaming information.
- A digest-bound, expiring, one-use no-effect request/response fixture.
- A source-catalog digest bound into the proposal and a pending review record
  with no decision, tiers, groups, facts, host binding, or authority.

## Validation evidence

Sixteen controller tests cover:

- absence of operational imports and authority;
- disabled operations, sources, groups, and host binding;
- safe Tier-0 source classification;
- protected/device-waking Tier-2 isolation;
- exact L2 separation;
- no-effect transition and replay rejection;
- rejection of unimplemented operations;
- rejection of extra parameters and executable fields;
- policy/proposal digest mismatch;
- false host-scan and approval claims;
- device-waking source escalation into Tier 0;
- expiry broadening.

The earlier VM-lab matrix and adversarial suite remains independently enforced.

## Remaining L1 work

L1 operational completion still requires:

1. user review and activation of an exact proposal revision;
2. reviewed registered adapters for each selected source;
3. encrypted local storage and explicit restricted-data unlock;
4. the unprivileged observation broker and immutable audit integration;
5. hostile-fixture rehearsal of each adapter; disposable-VM rehearsal is
   optional for the direct-host track and required only when a procedure needs
   representative guest evidence;
6. a new explicit decision to run the bounded enrollment observation;
7. review of the candidate profile before activation.

## Safe implementation progress (2026-08-06)

The bundle now contains a typed facade at
`vm-lab/scripts/observation_broker.py` for the minimal platform/compute
Tier-0 scope. It binds the registry, policy, source-catalog, and proposal
digests; enforces expiry and one-use request IDs; emits synthetic candidate
facts only; and rejects live host mode until the remaining gates are complete.

`vm-lab/scripts/restricted_fact_store.py` provides the storage boundary: facts
remain ephemeral unless a backend independently attests encryption at rest,
atomic writes, and recovery verification. It intentionally provides no
plaintext fallback or home-grown cryptography. Revision v2 includes
`LuksStorageAttestor` and `LuksSqliteFactBackend`: the former rechecks the
canonical path against current mount/device-mapper identity, and the latter
uses owner-controlled `O_NOFOLLOW` opens, transactional SQLite writes, a
durable one-use activation ledger, binding metadata, and record-integrity
verification. The approved adapter/version/source/fact membership is bound by
`vm-lab/enrollment/tier0-approved-fact-scope.json` and enforced again at the
storage boundary. It remains inactive until a concrete user-unlock/recovery
attestation is bound to a live path.

These are implementation prerequisites, not enrollment activation. No host
observation authority, restricted persistence, or controller service has been
enabled. The v2 implementation and fixture tests are recorded in
`runtime/reports/2026-08-07-restricted-storage-backend-v2.json`.

The fresh user-unlock/path evidence and R2 recovery-boundary proof are recorded
in `runtime/reports/2026-08-07-live-luks-storage-attestation.json` and
`runtime/reports/2026-08-07-r2-live-recovery-boundary.json`. These artifacts are
prepared evidence only; they do not create a live activation record.

The next construction revision adds `vm-lab/scripts/activation_authority.py`,
a durable exact-scope user-decision ledger, and
`vm-lab/scripts/live_tier0_observation.py`, a bounded unprivileged collector
for the four approved platform/compute sources. Both are fail-closed behind
the existing disabled policy; the collector cannot consume an authorization or
read host state while `host_observation_enabled` is false. A fresh independent
review is required before any policy or registry promotion.

The current gate assessment and exact recommended initial scope are recorded
in `runtime/reports/2026-08-06-phase4-activation-readiness.json`.

That structural task is now complete for four Tier-0 fixture parsers and the
no-effect broker contract. The full Workstation VM and L2 readiness design is
documented in `phase-4-l2-full-vm-blueprint.md`. No live collector exists; the
no-scan boundary remains unchanged.
