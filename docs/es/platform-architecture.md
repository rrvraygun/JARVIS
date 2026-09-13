# Jarvis platform architecture

## Planes

1. **Intent plane:** prompt, `AGENTS.md`, agent roles, and skills define outcomes
   and procedures but do not grant authority.
2. **Control plane:** capability registry, procedure versions, policy engine,
   action digests, approvals, and state freshness decide what may proceed.
3. **Tool plane:** narrow MCP tools, shell, package managers, and OS facilities.
   Raw execution is not exposed by the Jarvis MCP server.
4. **Evidence plane:** redacted observations, snapshots, baselines, validation,
   provenance, and reports.
5. **Knowledge plane:** version-aware Fedora facts, local documentation, command
   attempts, error reports, reviewed lessons, and decision summaries.
6. **Audit plane:** locked, fsynced, hash-chained events plus retention and remote
   export integration points.
7. **Recovery plane:** backups, snapshots, rollback procedures, rescue access,
   and independently tested restoration.
8. **Direct-host deployment plane:** one enrolled Fedora Workstation is the
   primary personal-product target. It progresses from fixture to shadow to
   supervised operation only after machine-specific recovery gates.
9. **Scenario-lab plane:** fixture matrices and an isolated disposable Fedora
   guest rehearse exact adapter revisions as a secondary environment. It has no
   production knowledge/audit mount and cannot attest physical hardware
   behavior.

## OpenAI capability map

| Codex feature | Jarvis use |
|---|---|
| `AGENTS.md` | Short durable invariants and documentation map |
| Custom agents | Research, exploration, diagnosis, implementation, review |
| Subagents | Independent evidence/review lanes; never independent authorization |
| Skills | Progressive workflow disclosure by capability |
| Plugin | Versioned installable package for skills and MCP |
| MCP | Typed governance tools with tool-level approval policy |
| Hooks | Secret and catastrophic-action guardrails, lifecycle context |
| Sandbox/approvals | Runtime least privilege and human authorization |
| `requirements.toml` | Organization-managed constraints when deployed centrally |
| `codex exec --json` | Machine-readable read-only automation and evaluation |
| Output schemas | Stable automation results and validation artifacts |
| Scheduled tasks | Observation, drift reports, reminders; no default mutation |
| Worktrees | Isolated agent/plugin changes and self-update staging |
| GitHub Action | CI validation and independent review of the bundle |
| Codex App Server | Fallback typed TUI preflight, agent execution, streaming, interruption, and exact approval transport; never required for deterministic local reads and never Jarvis policy authority |
| Codex SDK | Optional typed App Server wrapper when its exposed events satisfy the TUI contract |

The `system-knowledge` skill owns retrieval and learning workflow. Deterministic
SQLite and indexing scripts own persistence and invariants. The MCP server
exposes typed queries and record operations, never raw system execution.

The specialist registry and coordinator are the user-facing modular-agent
boundary. The user-selected specialist contributes bounded instructions,
knowledge references, context metadata, and registered tool references; it does
not grant authority. Definition edits are staged, validated, diff-reviewed,
one-use approved, and atomically activated with a prior-version archive. The
Packages surface and Installation Specialist share the broker/package backend.

The TUI uses the architecture in `tui-implementation-plan.md`. Natural
language and catalog actions share one task pipeline. Exact local list/read/
search requests may take a digest-bound deterministic executor route before
model preflight. Neither that current-user read route, the frontend, nor App
Server becomes host-administration or mutation authority.

Exact filesystem and package mutations may also be planned deterministically,
but their admissions remain approval-pending. Current-user writes cross a
Python descriptor-bound executor after one modal decision; privileged package
install/remove crosses only the registered root-owned Polkit helper after a
digest-bound DNF preview. Agent turns can propose broader current-user work,
through registered exact-review executors. Agent turns are read-only and generic command/file approvals cannot authorize writes.

## Trust boundaries

Model output is untrusted intent. Web pages, logs, package metadata, repository
files, and MCP results are untrusted data. Hooks are incomplete guardrails.
Authority comes from typed admission, deterministic policy, exact approvals,
Codex's trusted-command gate, hooks, OS permissions, registered procedures, and
validation. Typed preflight grants only the registered scope; agent turns remain read-only. A compromised host cannot be
its own sole attestor; export critical audit evidence to an independent system.
A compromised or contaminated guest cannot promote its own results. Future VM
runs require identity and reset attestations outside the guest.

Recovery is coverage-based, not a boolean. A local filesystem snapshot does not
protect a separate boot/EFI filesystem, firmware state, excluded subvolumes, or
same-device failure. Direct-host action classes require progressively stronger
R0–R3 evidence as defined in `direct-host-deployment-and-recovery.md`.

## Automation policy

Unattended automation may inventory, compare, alert, and prepare change plans.
Mutation requires a separately reviewed machine policy, narrow service identity,
pre-approved exact procedure and targets, recovery, bounded maintenance window,
and post-run notification. Ambiguity fails closed.
