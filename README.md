# JARVIS workstation assistant

**Current product state:** [`docs/current-product-state.md`](docs/current-product-state.md)

**Spanish documentation:** [`README.es.md`](README.es.md) · [`docs/es/`](docs/es/README.md)

JARVIS is a local Fedora workstation TUI with bounded host inspection,
package/power/lighting workflows, Codex App Server conversation, and audited
control-plane artifacts. The current source map, deployment boundary, and
feature state are maintained in the current product state document.

The authoritative documentation index is [`docs/README.md`](docs/README.md).
It links the current contracts, generated source inventory, dated audit/session
records, and explicitly historical design material.

## Repository Background

Reviewable Codex bundle containing:

- an adaptive, evidence-led deep researcher;
- a least-privilege system-administration orchestrator;
- modular inventory, health, benchmark, maintenance, update, repair, security,
  and state skills;
- a version-aware Fedora/Bash documentation and operational-learning skill;
- immutable SQLite facts, attempts, errors, lessons, decisions, and approval
  records alongside the hash-chained JSONL audit ledger;
- a Python/Textual TUI and App Server broker with unified natural-language and
  versioned catalog actions;
- immediate pending-request projection plus a deterministic, Python-only,
  bounded local filesystem list/read/search route that does not require App
  Server, Bash, or approval;
- deterministic exact current-user filesystem creates and move-to-Trash plus
  exact package install/remove routes, each held behind a fresh one-use TUI
  confirmation and digest-bound execution reservation;
- bounded, Polkit-mediated package and power helper paths that never expose a
  shell, arbitrary DNF arguments, or App Server host execution;
- a fixture-only Fedora system-twin/scenario laboratory with pinned exhaustive
  declared-state coverage, clean-baseline/isolation contracts, and explicit
  physical-hardware gaps;
- a typed, service-free future VM-controller contract and an unapproved,
  disabled, 90-fact Fedora enrollment proposal with three consent tiers;
- four fixture-only Tier-0 Fedora parsers plus a full Workstation VM blueprint
  and three fixture-only L2 parsers, with headless/graphical profiles, 18 fully
  bound readiness checks, and eight closed provisioning gates;
- a direct-host policy making this one enrolled Fedora workstation the primary
  personal product target, with fixture, shadow, supervised, and disabled
  earned-safe-list modes plus four evidence-based recovery levels;
- a validated, non-executable five-boundary R2 recovery-set plan covering the
  root, home, nested systemd-machines, boot, and EFI filesystems without
  claiming atomic, bare-metal, or bootable recovery;
- a prepared display-brightness and keyboard-lighting diagnostic case;
- operating, audit, security, and evaluation documentation.

This bundle is intentionally not auto-installed. Read `AGENTS.md`, then
`docs/runbook.md`. Validate with:

```bash
./scripts/validate-bundle.sh
```

Validation uses fixtures and isolated temporary files. It performs no live host
scan, installation, cleanup, update, repair, privileged action, or agent
self-modification.

The current typed-preflight and scoped-execution contract is documented in
`docs/tui-contract.md` and `docs/tui-implementation-plan.md`. Older Phase 1 and
Phase 2 documents are retained as design history. The fixture/VM boundaries are
documented in `docs/phase-4-vm-lab-prerequisite.md`,
`docs/phase-4-l1-controller-enrollment.md`, and
`docs/phase-4-l2-full-vm-blueprint.md`.

The Phase 4 laboratory prerequisite validates fixture contracts only. It did
not scan Fedora, install virtualization, download an image, create/start a VM,
or run the lighting workflow. See `vm-lab/README.md`.
The controller/enrollment checkpoint likewise created no service, observer, or
authority and collected no workstation fact.
The full-VM checkpoint adds only synthetic parsers and static designs. It did
not inspect virtualization, select/download Fedora, allocate storage, or create
or start a guest.

The direct-host direction is documented in
`docs/direct-host-deployment-and-recovery.md`, and the prepared R2 system-set
design is in `docs/r2-system-recovery-set.md`. The VM is a secondary rehearsal
environment; the enrolled workstation is the eventual primary deployment and
physical-evidence target. The repository policy files remain the reviewed
unenrolled baseline; the separately installed user service is currently
activated only for the approved one-use H1 Tier-0 read-only scope. Manually
approved bootstrap evidence does not silently grant standing observation,
snapshot, backup, restore, installation, or mutation authority.

The TUI starts offline by default. After installing the reviewed, pinned
`tui/pyproject.toml` dependency into an isolated environment, launch it from
the bundle root with:

```bash
bash scripts/launch-tui.sh
```

The launcher verifies that Python imports `jarvis_tui` from this checkout and
passes a DNF5 package-preview parser self-check before opening the interface.
Add `--plain` after the script command when needed.

`--connect-app-server` reads the configured Codex App Server authentication
state through the local process. It supports ChatGPT-managed and API-key
sessions; API-key credentials are never displayed or recorded. Adding
`--enable-live-turns` explicitly enables conversation submissions. The TUI can
additionally perform only the bounded local inspection and helper operations
described in `docs/current-product-state.md`; it does not expose a general
command or root-execution interface.

Exact local-read forms such as `list the files inside Escritorio` work while
App Server is offline. XDG aliases are parsed without a shell, results are
bounded and terminal-sanitized, and only metadata/digests—not filesystem output
or query text—enter the TUI event journal.

Exact mutation forms such as `create a new directory in Escritorio named
Proyecto2` are also planned without a model turn, but they do not execute
automatically. The TUI shows one exact review dialog and consumes an affirmative
decision once. Broader model-proposed current-user changes use App Server's
graphical command/file approval; privileged package install/remove is available
only through the registered Polkit helper. See
`docs/tui-mutation-executor.md`.

Those visible local results remain active-session-only in JARVIS, but are
included as bounded, untrusted context if a later agent request is submitted.
They are then subject to the configured Codex App Server retention boundary.

`--connect-jarvisd` additionally reads the active H1 Tier-0 service health and
activation projection over its owner-only Unix socket. It calls no observation,
executor, or policy-mutating method; the default remains offline.

After review, launch the isolated read-only profile with:

```bash
./scripts/run-readonly.sh
```
