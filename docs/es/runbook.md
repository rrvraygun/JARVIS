# Installation and operations runbook

This repository remains a reviewable bundle rather than an unrestricted live
agent. The single Fedora workstation is enrolled for bounded read-only
observation, and a verified external R2 recovery artifact exists. No general
host executor or autonomous privilege has been activated. The separately
deployed, Polkit-mediated package helper can apply only the exact,
digest-bound package transactions prepared by the TUI; see
[`current-product-state.md`](current-product-state.md).

## Review

1. Read `AGENTS.md` and `docs/shared-contract.md`.
2. Inspect agent TOML, every selected skill, hooks, and scripts.
3. Run `scripts/validate-bundle.sh`.
4. Review `vm-lab/README.md` and its explicit physical gaps.
5. Review `vm-lab/controller/README.md` and the unapproved enrollment
   proposal before designing any collector.
6. Review `docs/phase-4-l2-full-vm-blueprint.md`, the exact L2 readiness plan,
   and all eight provisioning gates before considering virtualization work.
7. Review `docs/direct-host-deployment-and-recovery.md`,
   `docs/r2-system-recovery-set.md`, and
   `deployment/host/policy.json` before enrolling the workstation.
8. Run tests in `tests/`; do not start with a live privileged host.

## Activation

Copy selected files into a trusted repository's `.codex/` only after review.
Do not blindly merge `codex/jarvis.config.example.toml`; reconcile it with
existing configuration.
Start with only `deep-research`, `system-inventory`, `system-health`,
`system-state`, and `system-knowledge`. Keep mutation skills uninstalled until
their evaluation passes.

## First live operation

Request a read-only inventory. Review every proposed collector and approve only
additional read access that is justified. Inspect redaction and stored state.
Then establish health baselines. Enable one mutating workflow at a time.

Initialize the knowledge store and source/command registries in a private runtime
directory:

```bash
python3 plugins/jarvis-system-admin/scripts/knowledge_store.py \
  --db runtime/knowledge/knowledge.db init
python3 plugins/jarvis-system-admin/scripts/knowledge_store.py \
  --db runtime/knowledge/knowledge.db seed-sources
python3 plugins/jarvis-system-admin/scripts/knowledge_store.py \
  --db runtime/knowledge/knowledge.db seed-catalog
```

Index allowlisted installed documentation without network access:

```bash
python3 plugins/jarvis-system-admin/scripts/index_local_docs.py \
  --output runtime/documentation/local.jsonl
python3 plugins/jarvis-system-admin/scripts/knowledge_store.py \
  --db runtime/knowledge/knowledge.db import-docs \
  runtime/documentation/local.jsonl
```

Preview the Fedora collector before the separately authorized live read-only
inventory:

```bash
python3 plugins/jarvis-system-admin/scripts/collect_fedora_inventory.py \
  --output runtime/state/snapshots/fedora-inventory.json --preview
```

These commands write only inside the project runtime. The collector never uses
privilege, retries, network access, or state-changing commands.

## Separate isolated read-only profile

This bundle includes an activated profile containing only deep research, system
inventory, system health, and system state. Launch it from the target workspace:

```bash
/home/tipexxx/Escritorio/Proyecto/codex-agent-system/scripts/run-readonly.sh
```

This launcher is a deliberately separate diagnostic profile, not the TUI
execution policy. It pins `CODEX_HOME`, strict configuration parsing, a
read-only sandbox, and on-request approvals. It does not grant privilege or
install mutation skills. The TUI execution path instead uses typed preflight
followed by explicit `dangerFullAccess`/`untrusted` turns.

## Emergency stop

Interrupt the active run, deny further approvals, disable the implicated skill
or MCP server, preserve logs, capture read-only evidence, and recover through a
separate trusted channel. Do not allow the affected agent to erase its records or
declare itself repaired.

## Platform development profile

The production-oriented control plane lives in
`plugins/jarvis-system-admin/`. Validate it with the bundle validator before
installing it. The plugin's MCP server exposes policy and audit operations only;
it exposes no shell or host-administration tool.

Use `codex/jarvis.config.example.toml` as a reviewed merge source, not as a blind
replacement. For managed deployments, adapt `codex/requirements.example.toml`
and pin the plugin MCP command identity. Review plugin hooks through `/hooks` and
trust the exact hash only after inspection.

Do not advance a capability beyond its maturity stage in
`docs/capability-maturity.md`. Live inventory and administration are deployment
activities, not part of platform construction or validation.

The VM-lab structure does not authorize workstation enrollment, readiness
checks, virtualization installation, image acquisition, guest creation, or
scenario execution. Each is a later explicit checkpoint. Fixture validation
proves only the project contracts.
The controller registry is a namespace and state contract, not an installed
service. The enrollment proposal is not user consent and must not be interpreted
as permission to observe the workstation.
The original Tier-0 simulator still reads only registered synthetic fixtures;
its candidate facts do not describe the workstation. A separate fixed
`lighting-tier0-readonly` adapter is enabled under H1 for the enrolled Fedora
workstation. Preview it before use, run it once without privilege, and keep its
output under `runtime/state/snapshots/`. It may read only its registered
sysfs/proc fields and must not read connector status, launch a GPU client, call
D-Bus or the network, inspect protected logs, or perform any write. The full-VM
blueprint and L2 readiness plan remain static contracts; neither is permission
to query packages, services, KVM, libvirt, firmware, resources, or storage.

The separate `lighting-tier1-platform-readonly` adapter is also eligible under
H1 after its preview and bundle validation. It is limited to non-secret DMI
model fields, allowlisted platform/module/device names, passive backlight
topology, candidate LED names, and candidate input identity. Serial/UUID
fields, raw events, D-Bus/service activation, logs, subprocesses, network,
connector status, and writes remain forbidden. A successful Tier-1 platform
run is not permission for the later desktop/session or interactive layers.

The `lighting-tier2-wmi-binding-readonly` discriminator may be used only after
Tier-1 establishes that the NVIDIA WMI EC backlight module is relevant. It
reads the fixed brightness GUID instance names, binding names, the read-only
module `force` parameter, and provider names/types. It must never evaluate a
WMI method, bind/unbind a device, write a parameter, or broaden into arbitrary
WMI namespace inspection.

The `lighting-tier3-connector-association-readonly` observer requires an
explicit gate because reading internal eDP connector status may wake display
hardware. It is limited to DRM card identity, internal eDP status, and fixed
backlight-to-PCI symlink association. It cannot write sysfs, call WMI/ACPI,
read input events or logs, call D-Bus, launch GPU clients, or access the
network. The current approval is single-use for the lighting investigation.

The direct-host policy makes the enrolled workstation the primary deployment
target. H1 bounded read-only authority is active; the machine-specific R2 set
has been captured, externally checked, fully restored to an isolated target,
independently compared, and retained read-only. This does not activate general
host execution. Every mutation still requires action-specific recovery,
independent review, and exact command approval. A VM remains optional for
representative software-only rehearsal and never substitutes for physical-host
evidence.
