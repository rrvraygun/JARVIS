# Governed operations candidate — historical record, 2026-09-08

> Historical snapshot. Current behavior is defined by `current-product-state.md`,
> `tui-contract.md` and the root `CHANGELOG.md`; this file is retained for audit
> provenance and is not a deployment specification.

This is a staged candidate, not an activated release. The active checkout and its
runtime profile have not been replaced. An implementation is not a promotion.

## Implemented boundaries

The agent plans through typed MCP tools. The TUI reviews the exact proposal and
issues an ephemeral approval. The executor consumes that object once, reserves a
durable operation ID before effects, revalidates state, and records the outcome.
No model-facing apply or approval endpoint exists. Declining creates no execution
reservation. Process failure, timeout, state drift and output overflow never retry.

Proposals bind ID, domain, operation, targets, argv, allowed environment, timeout,
output limit, privilege, network effect, rollback limitations, pre-state and
postconditions. The review must fit its display limit before approval is offered.
A result's independent verification is a separate artifact with the same ID and
digest and the complete required check set.

| Domain | Implemented operation | Practical limit |
| --- | --- | --- |
| Development | Cargo check/build/test/fmt check/clippy | Exact snapshot, offline empty cache, systemd user resource controller and bubblewrap required. No fallback. |
| Development | Cargo.toml/Cargo.lock change | Creates a new workspace. A separately approved apply_dependencies operation can replace existing manifests in the original, retaining displaced files. TOML and exact-file checks do not prove dependency resolution or a successful build. |
| Recovery | Text-project backup and restore | New destination only; R0, not binary-data, disk, boot or full-system recovery. |
| Network | One TCP reachability attempt | Exact canonical IP and port, no DNS or application data, separate one-use approval. Remote logging cannot be undone. |
| Health | Service restart/enable/disable helper and client | No helper deployed or units enrolled. Root-owned expiring R1 policy required. Complex dependency/drop-in/install mechanisms rejected. |
| Network | Saved IPv4 DNS configuration | Fixed helper/client prepared; exact connection UUID and values, root enrollment and current R1 required. Not deployed. |
| Security | Default SELinux file label / simple runtime firewall service | Fixed helper/client prepared; no hardlinks, recursive relabeling or service expansion. Not deployed. |
| Security | Updates and boot changes | Blocked proposals; no executor yet. |
| Recovery | R1–R3 system recovery | Existing contracts/evidence gates; not implemented by the text-project copy backend. |

## Snapshot and resource limits

This backend requires a known text-project marker. Project snapshots reject links, special files, unowned/group-writable files,
secret-shaped content, binary content and unsafe paths. They bind hashes for the
entire allowed tree before review, not only the Cargo manifests. Limits are 2,000
entries, depth eight, 1 MiB per file and 8 MiB per tree. Hidden files, sensitive-name candidates, target,
node_modules and runtime are excluded and explicitly listed. At most sixteen
snapshots may be prepared before reviewed cleanup is required.

Cargo receives a read-only source snapshot, read-only /usr, private /tmp and build
tmpfs, no user home and separate namespaces. systemd-run requests MemoryMax=1G,
TasksMax=32, CPUQuota=100%, RuntimeMaxSec=120 and LimitFSIZE=256M. A guard checks the
effective cgroup memory/process/CPU values before executing bubblewrap. A real minimal Cargo test passed through these controls on 2026-09-09 in host context. This does not establish support for dependency-bearing projects or all restricted environments. Build exit status does not prove hardware safety.

## Tool scope and evidence

The controller generates a process scope ID, passes it to the fixed MCP command,
and publishes permissions after admission. Scope includes controller PID/start
identity and expiry. It is revoked on terminal events, interrupt, disconnect and
failed/cancelled turn startup. Explanation turns receive no MCP scope.

Tool schemas remain discoverable for App Server caching; each invocation checks
the live specialist scope. A schema is not authority. Lesson activation and
model-authored approval/audit attribution are unavailable on this surface.

Current-state evidence is tied to task and scope, required tool class and declared
arguments. Expected argument values are stored as hashes. Package inspection must
first use the exact bounded original request as query with fresh collection;
refresh=false, stale results, telemetry or unrelated queries cannot unlock it.
Further focused searches are permitted. Semantic relevance of a model's final
interpretation still needs evaluation; the receipt alone is not proof of it.

Native turn reads are restricted to project documentation; other inspection goes
through bounded tools. Preflight has no explicit readable roots. The candidate
profile disables apps, plugins and hooks and permits one fixed MCP server. Startup
checks the effective config/read result as well as the profile. Runtime support
for these settings and platform defaults remains an integration acceptance gate.

## Transcript and recovery semantics

Sanitized operation transcripts are distinct from Conversation and audit. Typed
field checks reject reasoning, raw environments and sensitive keys, including
nested variants. Limits are 128 entries and 64 KiB serialized per entry, with a
seven-day read expiry for new records. Expired content is withheld; deletion/rotation still requires
review. A full transcript budget cannot hide an already durable operation result.

The independent verifier runs under read-only bubblewrap. If it cannot start or
its identity/digest/check set is invalid, verification remains unknown. TCP
verification validates a recorded attempt only; it does not make another remote
connection. Services require both a successful bound receipt and fresh state/link
checks. New-copy operations retain partial destinations on failure; originals
are never overwritten, and cleanup is a separate reviewed action.

## Activation gates

Before release: complete deterministic checks, independent review of the exact
candidate, real negative permission tests and App Server/MCP integration. Before
host service use: install reviewed helper/Polkit artifacts and enroll exact units
with independently reviewed, current recovery evidence. No template grants this.
System updates, boot changes and automated full-system capture/restore orchestration remain unimplemented executors. The existing manual five-boundary Restic runbook and comparator are retained; the user chose controlled backups on the detected external disk. See `sessions/2026-09-08-external-backup-target.md`.

Protocol basis: [official App Server documentation](https://learn.chatgpt.com/docs/app-server)
for restricted read roots, config/read and per-turn policies. Local implementation
and tests provide the evidence for the candidate's behavior; protocol documentation
does not establish successful live integration.

## Checkpoint recovery and verification receipts

New checkpoints use schema 2; schema 1 remains readable for chat/context only.
Full recovery rejects legacy history and untracked, incomplete or unsupported
mutations. Every Power, lighting and registered operation records a reservation
before dispatch. A single package transaction requires its matching successful
receipt and current authoritative recovery record. Conversation restoration
happens only after separately approved undo succeeds and no concurrent mutation
appears. Other operation families require their own recovery workflow; no generic
system rollback is claimed.

Tool observations carry a unique scope generation captured before collection.
Replacing or revoking a turn prevents late results from unlocking the next turn.
Operation receipt verification is derived consistently for UI, MCP and transcripts.
The immutable raw execution record is not itself an independent verification.

## Questionnaire implementation continuation

The general isolated `command` operation accepts a bounded exact argv rooted at
/usr/bin, including interpreter code shown in review. It binds the resolved
executable hash, snapshot, environment and resources. No host, root or network
execution is implied. Its verdict explicitly verifies process facts, not the
user's overall objective. Arbitrary host/root/network commands remain pending.

Cargo and general commands share a file lock around pending-history validation
and durable reservation. The trusted Python guard runs with `-I` and writes a
bound cgroup identity before invoking bubblewrap. Settlement requires the same
boot and an absent cgroup or matching identity with `populated=0`; after a reboot,
old execution is necessarily terminated. Missing launch receipts remain uncertain.
A durable pre-launch outcome with no launch request permits subsequent work; a
reservation without an outcome does not. Older unversioned execution histories
need explicit reconciliation before this new boundary can run.

`apply_dependencies` derives only from a verified unchanged dependency workspace.
It replaces existing manifests one at a time using Linux atomic exchange and
retains displaced files. A group of two replacements is not atomic. State drift,
metadata failure or partial exchange retains evidence and stops without retries,
automatic rollback or cleanup. External editors do not honor a JARVIS lock:
a raced change is retained and reported, not silently discarded. Recovery of a
partial operation requires inspecting retained candidates and the snapshot; no
automatic rollback is performed. Recovery can prepare a new inverse dependency-copy proposal, with separate execution, verification and application approvals, only while current changes remain attributable. New manifest creation is separate.

### Approved dependency downloads

`fetch_dependency` proposes one package/version from an existing crates.io
Cargo.lock entry. It exposes the exact static.crates.io URL, checksum, private new
file, 8 MiB byte limit and 30-second process deadline. The fixed HTTPS worker
makes one request, follows no redirects and uses no proxy or credentials.
Interrupted/invalid archives remain for reviewed cleanup. No project code executes
in the download process.

A Cargo operation can select a complete set of verified download IDs matching the
current lockfile. Archive hashes are checked again and mounted read-only into the
offline sandbox. A bound extraction worker rejects traversal, links, duplicate
files and oversized/overexpanded archives and creates checksum metadata for a
Cargo directory source. Inputs remain read-only; build code gets no network.
This supports crates.io lockfiles within the declared limits, not arbitrary Git
or private registries. A matching checksum is not a claim of benign package code.

Protocol basis: [Cargo source replacement](https://doc.rust-lang.org/cargo/reference/source-replacement.html).
The synthetic dependency integration test validates offline compilation; no real
registry download has yet been performed under a user-approved operation.
