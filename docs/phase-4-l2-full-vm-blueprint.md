# Phase 4 L2 structural checkpoint: full Fedora Workstation VM

## Result

The non-operational blueprint for a full Fedora Workstation system-twin is
prepared and fixture-validated. It keeps one complete Workstation installation
and defines two boot profiles over the same locked baseline:

- `headless_system_validation` for system, service, storage, security, log,
  package-state, container, and Bash-oriented tests;
- `graphical_workstation_validation` for GDM, GNOME Shell, Wayland, desktop
  portals, UPower, power profiles, PipeWire/WirePlumber, and virtual
  display/input/audio behavior.

The headless profile is not a Fedora Server or minimal-container substitute.
Both profiles retain the full Workstation payload. This prevents a fast test
path from silently losing the desktop packages, policy, services, or
integration points that later graphical cases need.

No host readiness observation, package query, installation, service change,
module load, network access, Fedora image selection or download, storage
allocation, hypervisor connection, VM definition, VM start, guest installation,
snapshot, passthrough, benchmark, lighting diagnosis, or workstation mutation
occurred.

## Fixture-only observation prerequisite

Four source-bound Tier-0 parser adapters are now registered for:

1. Fedora `/etc/os-release` identity;
2. kernel release and system architecture;
3. CPU architecture, vendor/model family, core/thread counts, and virtualization
   extension class;
4. total memory and NUMA node count.

They parse only the registered synthetic fixture set. They expose no live
collector, command, arbitrary file reference, shell, network, privilege,
device, persistence, retry, or host-fact promotion path. Their request binds
the adapter registry, broker policy, source catalog, and enrollment proposal by
SHA-256. Their fourteen outputs use the exact fact IDs and source bindings from
the enrollment proposal and are labeled synthetic candidate facts, never host
facts.

The parsers reject duplicate fields, malformed numeric values, inconsistent
CPU topology, unsupported architecture, non-UTF-8 data, NUL/DEL/terminal escape
controls, active shell syntax, unexpected object fields, arbitrary parameters,
unknown adapters, digest drift, duplicate adapters, and in-process request
replay. One attempt is the hard limit.

## VM architecture

The blueprint requires:

- an official supported Fedora Workstation artifact with verified signed
  checksum and locked image digest;
- UEFI-preferred firmware, VirtIO storage, virtual graphics, and no physical
  passthrough;
- a cleanly powered-off, read-only golden base;
- one fresh external overlay per scenario and no reuse after any result;
- no runtime network, host filesystem share, clipboard, drag/drop, host USB,
  GPU passthrough, credentials, or production audit/knowledge mount;
- a provisioning-network window only through a separate visible checkpoint,
  removed before baseline attestation;
- registered operations and scenarios, one attempt, fixed timeouts and output
  limits, terminal-safety rejection, redaction, outside-guest validation, and
  immutable run records;
- resource selection only from fresh reviewed readiness evidence. The design
  stops instead of silently reducing the guest when the full-Workstation safety
  floor cannot be met.

The future local display/control channel is a design identity, not an endpoint.
No socket, service, transport, guest agent, or controller authority was added.

## CLI/headless versus graphical evidence

The headless profile is preferable for deterministic system tests because it
uses fewer moving parts and does not require a running graphical session. It
can validate systemd services, the kernel, SELinux, storage, package state,
logs, and terminal procedures.

It cannot validate GDM login, GNOME/Wayland session behavior, desktop portals,
graphical settings exposure, desktop power integration, graphical input, or
virtual display/audio behavior. Those require the graphical profile.

Neither profile can prove physical panel luminance, keyboard LED output, real
NVIDIA power rails, mux/display wiring, firmware hotkeys, embedded-controller
behavior, battery response, or real thermals. Those remain physical-workstation
gaps requiring a later, separate observation decision.

## Readiness and provisioning gates

The L2 readiness plan defines eighteen bounded, non-mutating facts covering
Fedora/architecture compatibility, CPU virtualization extensions, safe memory
capacity, KVM presence/access, kernel support, QEMU/libvirt/virt-install and
firmware availability, service state, optional graphical manager, current-user
access class without identity, storage capacity/filesystem class without
personal paths, SELinux, cgroup mode, and sanitized conflict class.

Three additional fixture-only parsers now bind the virtualization-stack,
storage-capacity/filesystem, and SELinux sources. Together with the four
Tier-0 parsers, every one of the eighteen readiness checks has an exact adapter,
source, parser, result type, bound, and synthetic test result. No live backend
exists.

The plan explicitly excludes repository refresh, connectivity tests, installation,
service starts, module loading, permission/group changes, passthrough probes,
benchmarks, guest names/definitions, unique identifiers, personal paths,
secrets, and content. Approval is false, the live backend is unresolved, and
`host_scan_performed` is false.

The provisioning sequence is closed and ordered:

1. P0 — implement and fixture-validate the exact L2 adapters (complete for
   parser contracts; no live backend);
2. P1 — obtain fresh group confirmation for the read-only readiness
   observation;
3. P2 — if evidence shows a gap, separately approve each host installation or
   configuration command;
4. P3 — approve official metadata resolution and image acquisition as distinct
   network/state-changing actions;
5. P4 — approve exact storage and locked-domain creation actions;
6. P5 — approve VM start and full Workstation installation, with explicit
   installer participation if required;
7. P6 — seal and attest the powered-off baseline and rehearse reset;
8. P7 — run only registered scenarios through fresh overlays.

P1 is now the current boundary and is blocked on fresh user authorization plus
a separate live-backend implementation, review, and VM rehearsal. P2 through
P7 remain blocked. The contracts do not imply consent for any later gate.

## Validation evidence

- Four registered Tier-0 fixture parsers emit fourteen exact synthetic facts.
- Twelve parser/broker adversarial tests pass.
- Three L2 fixture parsers bind all eighteen readiness checks, with twelve
  additional adversarial tests.
- The full blueprint defines two complete-Workstation boot profiles.
- The L2 plan defines eighteen exact readiness checks.
- Eight ordered provisioning gates are present; P0 is complete, P1 is blocked
  on authorization, and P2-P7 are blocked.
- Ten blueprint adversarial tests reject reduced guests, guessed resources,
  passthrough, runtime networking, shares, arbitrary model shell access, false
  adapter/scan claims, and premature gate activation.
- Static tests reject operational imports and executable interface fields.

## Current boundary

The project can validate the contracts and synthetic fixtures. It still cannot
inspect the workstation or operate a hypervisor. P0 fixture-parser work is
complete. Adding any live collection backend remains a separate review
boundary under the existing no-scan instruction.

No VM installation or manual installer action is needed yet. Work stops at the
first user-visible operational boundary: whether to authorize implementation
and later execution of the exact bounded read-only readiness observation. Only
actual P1 results could show whether P2 installation or configuration work is
needed.
