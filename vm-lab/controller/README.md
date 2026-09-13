# Future VM-controller and enrollment boundary

## Status

The controller policy remains disabled, but the bounded user-scoped H1 service
and private transport have now been constructed as prepared artifacts. The
service is not installed, started, or granted host-observation authority.
There is no hypervisor client, privilege mechanism, device interface, network
client, or restricted-fact persistence path. All 18 future operations remain
disabled. Only profile.enrollment.prepare may be evaluated by the in-memory
simulator, and its result is explicitly no-effect.

The prepared H1 promotion templates in this directory describe the required
user-scoped service identity and private Unix JSONL transport. They are checked
by `vm-lab/scripts/h1_activation_contract.py`, but are not installed, started,
or treated as authority. The validator also binds the exact user decision
packet, pins its artifact digest, directly verifies the current controller and
broker policy files remain disabled, and requires the transport to remain
`prepared_unbound`.

The activation ledger is owner- and mode-checked, descriptor-checked, locked,
and post-open identity-verified. It is the sole explicitly permitted service
write: a one-use approval-consumption record at the exact authority-ledger
path. It is not application fact persistence. Python's standard SQLite
interface still leaves a same-user pathname/journal-sidecar race; this is
explicitly recorded as a residual blocker, not treated as solved. H1 promotion
therefore remains disabled until the prepared service revision and its runtime
policy are independently reviewed.

The current construction includes an unwired alternative,
`vm-lab/scripts/descriptor_bound_authority.py`. It uses one verified regular
file, descriptor-bound writes, hash-chained frames, fsync, and no SQLite
journal sidecars. It is a prototype only: the live collector still uses the
existing disabled SQLite path until this alternative receives independent
review and an explicit backend-selection decision.

The in-file checkpoint detects truncation that leaves the latest checkpoint
behind, but cannot detect restoration of an older complete file snapshot. That
requires an external authenticated monotonic checkpoint and remains an
activation blocker.

The exact workstation-enrollment proposal is prepared but unapproved. It has no
host binding and records that no scan occurred.

## Boundary

~~~text
TUI: display and deliberate consent
                  |
                  v
Broker: typed request, policy and digest checks
                  |
                  v
Future controller: registered operation IDs only
        |                       |
        v                       v
Future observation broker   Future isolated VM service
        |                       |
        v                       v
Enrolled Fedora host        Disposable untrusted guest
~~~

The model can propose an operation ID and parameters. It cannot receive a raw
shell, process handle, hypervisor socket, domain-definition writer, arbitrary
image path, passthrough handle, host device, credential, or production
audit/knowledge mount.

The deterministic authority boundary must independently verify the operation
revision, target, parameter allowlist, current state, expected next state,
policy/proposal/host/image/domain/scenario digests as applicable, exact
approval, expiry, attempt number, and one-use idempotency key.

## Defined operations

The registry reserves typed identities for:

- preparing, authorizing, observing, stopping, finalizing, and reviewing a
  workstation profile;
- resolving official image metadata, acquiring a locked object, and verifying
  signature/checksum identity;
- planning a domain and creating/attesting a powered-off clean baseline;
- creating one scenario overlay, starting/cancelling one run, exporting bounded
  evidence, disposing of the overlay, and independently reverifying the base.

Defining these names grants no authority. Every operation except the no-effect
proposal transition is unimplemented, disabled, and linked only to a future
adapter identifier.

## Enrollment consent tiers

The proposal contains 90 normalized fact definitions across 32 sources and 12
groups:

| Tier | Future behavior | Examples | Current state |
|---|---|---|---|
| 0 | Automatic only after the user activates the exact proposal revision | Fedora/kernel identity, aggregate CPU/memory | Disabled |
| 1 | Separate group confirmation | Hardware classes, lighting topology, storage, packages, services, recovery, local documentation | Disabled |
| 2 | Per-probe confirmation | Protected current-boot evidence, GPU runtime-power reads, device-health reads | Disabled |

Activating the proposal in the future would not authorize Tier 1 or Tier 2.
Tier 0 also requires reviewed registered adapters before it can be admitted.
Any changed proposal digest invalidates activation.
The proposal also binds the exact source-catalog digest. The included review
record is deliberately pending and carries no approved tier, group, fact, host
binding, decision, or authority.

The L2 virtualization-readiness group is deliberately separate. Completing L1
cannot start it automatically.

## Field-level proposal

The proposal specifies for every group:

- purpose and lifecycle phase;
- consent tier and admission mode;
- privacy and possible-effect classification;
- allowlisted source IDs;
- normalized facts and mandatory transformation;
- maximum records and bytes;
- freshness;
- normalized and raw retention.

The source catalog describes exact local interface classes but contains no
executable or argument representation. Each source is offline, non-mutating,
currently disabled, and requires a later registered adapter.

The global exclusion list covers credentials, secrets, histories, file
contents, user/host/network identity, VPN configuration, serials, filesystem
identifiers, personal paths, container secrets, backup destinations/content,
and gaming data.

## What happens for a future Fedora request

For a request such as “diagnose brightness”:

1. The broker creates a typed task and retrieves only fresh, relevant reviewed
   facts.
2. Missing facts remain unknown. The agent may propose exact enrollment or
   incident probes by group/fact/source ID.
3. Deterministic policy evaluates tier, privacy, possible effect, freshness,
   output limits, and required consent.
4. Only an activated Tier-0 registered read may be automatically admitted.
   Tier 1 and Tier 2 pause at their respective confirmation boundary.
5. One attempt produces bounded, redacted observations. A timeout, malformed or
   hostile result, permission boundary, unexpected output/effect, or audit
   failure stops progression.
6. Evidence becomes a candidate profile and requires user review before it can
   become active knowledge.
7. Diagnosis can then recommend or plan. State-changing repair remains a
   separate exact command approval and future executor concern.

The current project can perform only step 1 with existing static/fixture data
and can simulate the proposal-state contract. It cannot perform steps 2–7 on
the workstation.

## Validation

From the bundle root:

~~~bash
python3 vm-lab/scripts/controller_contract.py
python3 vm-lab/tests/test_controller_contract.py
~~~

These commands read project JSON, perform in-memory validation, and print a
report. They do not inspect Fedora or contact virtualization.

## Activation prerequisites

Before any real controller or enrollment observation exists:

1. review the proposal and source catalog;
2. create fixed read-only adapter contracts with exact bounds and surprise
   conditions;
3. threat-model and implement an unprivileged observation broker;
4. implement encrypted local storage and explicit unlock for restricted facts;
5. add an immutable external audit-integrity path;
6. rehearse each adapter against hostile fixtures and the disposable Fedora VM;
7. perform independent security review;
8. create a new user decision that activates only the approved revision.

The bounded service construction does not satisfy activation by itself. A
fresh activation-specific independent review and a final one-use runtime gate
remain required.

Independent reviews are launched without inheriting the implementation
conversation by `automation/run-independent-review.sh`. The helper invokes a
fresh ephemeral Codex process with read-only sandboxing and no approvals. It
does not install, activate, or mutate any host or service state.
