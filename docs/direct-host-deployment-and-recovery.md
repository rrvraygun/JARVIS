# Direct Fedora deployment and recovery architecture

## Decision

The single enrolled Fedora Workstation is the primary product environment.
Jarvis will be developed for its actual release, filesystems, boot layout,
hardware, drivers, desktop stack, and installed tools. Generalization to other
machines comes later through new adapter and enrollment revisions.

A full Fedora VM is an optional secondary tool for software-only procedures,
parser failures, policy decisions, and reset behavior when it is representative
and worth the setup cost. It is not a prerequisite for live development on the
enrolled workstation and cannot replace physical evidence for NVIDIA power,
panel routing, brightness, keyboard lighting, ACPI/EC, firmware hotkeys,
battery, or thermals.

No claim of “perfect rollback” is permitted. A recovery guarantee is valid only
for the boundaries actually captured and restored in a test.

## Why one snapshot is insufficient

A Fedora Workstation installed with the defaults commonly has Btrfs root and
home subvolumes, but the project must inspect rather than assume this. Upgraded
or custom installations can use another layout. Btrfs snapshots operate at a
subvolume boundary and do not recursively capture nested subvolumes. A local
snapshot also resides on the same storage device, so it is lost with that
device.

`/boot` and the EFI System Partition are commonly separate filesystems and are
therefore outside a root Btrfs snapshot. A root snapshot also cannot revert a
partition table, disk encryption layout, firmware flash, UEFI NVRAM variable,
or physical-device failure. Package-manager history can reverse recorded
package transactions when the required package state is available, but it does
not restore arbitrary files, boot partitions, firmware, or user data.

The direct-host product therefore needs four recovery levels rather than one
generic snapshot flag.

## Recovery levels

### R0 — record and project copy

Use for read-only work and narrowly scoped project development. Record the
pre-state, proposed delta, result, and a verified independent copy of affected
Jarvis project files. This is not operating-system protection.

### R1 — local filesystem snapshot

Use a backend selected from the observed layout: for example, read-only Btrfs
snapshots of every relevant subvolume or an appropriate LVM snapshot. Record
the full mount/subvolume graph and the explicit exclusions. Reserve free space
and stop if snapshot growth could pressure the active filesystem.

R1 is suitable for ordinary package and configuration changes only when every
touched file is covered. It does not protect against storage-device loss.

### R2 — external encrypted system backup

Replicate read-only snapshots to independent encrypted storage, or use a
reviewed filesystem-aware backup. Capture root, home, and any other relevant
subvolume independently. Capture separate boot and EFI filesystems through a
method appropriate to their observed filesystem and verify integrity.

For Btrfs, read-only snapshots are required for reliable send/receive. A full
send establishes the external base; future incremental sends require the
unchanged parent snapshot on both sides. The external copy must be tested by
receiving/restoring it into a non-production target before it becomes a
recovery prerequisite.

R2 is the floor for kernel, NVIDIA driver, initramfs, boot-argument, display
manager, or graphics-stack changes. Preserve a known working kernel and verify
that the boot selection/recovery path is usable before the change.

### R3 — offline full-device recovery

Before partition, filesystem-layout, bootloader, or encryption-layout work,
create and integrity-check an offline whole-device recovery image on an
independent destination. Maintain bootable Fedora rescue media. Validate target
identity and rehearse restoration on a non-production device or equivalent
controlled environment.

Even R3 cannot promise recovery from firmware flashing or unrelated hardware
failure. Firmware changes remain a separate exceptional workflow.

## Direct-host operating modes

1. **Fixture:** current mode. No host reads or changes.
2. **Shadow:** bounded approved observations, diagnosis, plans, and previews;
   no state changes.
3. **Supervised:** one exact approved state-changing attempt after its recovery
   prerequisites are verified.
4. **Earned safe list:** disabled initially. An exact procedure revision may
   become a promotion candidate only after repeated reviewed success, and the
   owner must approve the policy change.

The model never receives an arbitrary root shell. A future privileged helper
must expose only registered operations with exact targets and parameters. The
policy, approval, snapshot identity, pre-state digest, and recovery evidence
must be enforced outside the model.

## Transaction sequence

Every supervised change follows one closed sequence:

1. obtain fresh state and resolve one exact target;
2. classify every expected effect, including boot, service, device-wake,
   network, and storage implications;
3. determine the minimum recovery level covering every touched boundary;
4. create and verify the recovery artifact before requesting mutation approval;
5. bind the artifact identity, pre-state, procedure revision, target, and exact
   action to the approval;
6. run one attempt—never automatically retry;
7. perform independent post-change validation;
8. stop on unexpected output/effect or failed validation;
9. diagnose before deciding whether restore is safer than a forward fix;
10. require separate approval for restore because restore is destructive too;
11. finalize the immutable audit record.

Automatic rollback is deliberately disabled. A blind rollback after a partial
boot, package, or storage change can destroy new user data or compound the
failure. Jarvis must present what changed, what the recovery artifact covers,
and the exact restore consequences.

## Machine-specific implementation gates

### H1 — bounded read-only enrollment

The first real operation discovers only what is needed to choose the recovery
and deployment design:

- Fedora release, kernel, architecture, and boot mode;
- root/home/var/boot/EFI mount and filesystem classes;
- Btrfs subvolume or LVM topology without personal file contents;
- encryption class without keys or unique identifiers;
- bounded free-space classes;
- installed snapshot, backup, rescue, DNF, and virtualization tool versions;
- installed kernels and boot-recovery capability without changing defaults;
- graphics and lighting provider topology for the first incident, using the
  previously defined device-wake stop rules.

No repository refresh, benchmark, package installation, snapshot, mount,
service start, module load, GPU wake, configuration change, or persistence of
unredacted raw output belongs to H1.

### H2 — recovery design

Produce a gap report that chooses R1/R2/R3 backends from actual evidence,
identifies excluded boundaries, calculates space requirements, and defines the
restore test. Unknown remains unknown. If no independent storage exists, R2 and
R3 remain unavailable and high-risk work stays blocked.

### H3/H4 — establish and test recovery

Snapshot creation, backup installation, external media formatting, rescue-media
creation, and restore rehearsals are state-changing/manual operations. Each is
separately planned and approved. No later action may use an untested artifact as
its safety claim.

### H5 — deploy shadow mode

Run Jarvis unprivileged, keep the project in version control, use an isolated
Python environment, and give the broker no shell or sudo access. Store machine
facts and audit data locally with the already designed redaction/encryption
boundaries. Observe and plan before adding any executor.

### H6 — first lighting case

The first physical workflow remains brightness and keyboard-light diagnosis
under the NVIDIA low-power hypothesis. The first operational layer is the fixed
unprivileged `lighting-tier0-readonly` adapter: it reads only bounded existing
provider, adapter, connector-name, and filtered kernel metadata. Diagnosis
may then use the passive `lighting-tier1-platform-readonly` adapter for
non-secret machine identity, relevant platform interfaces, backlight topology,
and candidate hotkey-device identity. Diagnosis stops if an observation may
wake hardware; status polling, vendor GPU clients, protected logs,
desktop/session calls, and interactive event monitoring are not part of these
layers. A repair is a new transaction classified by its actual
effects—package, service, driver, initramfs, boot, desktop, or device—and cannot
execute until the corresponding recovery level is verified.

## Current boundary

The TUI's approval-gated current-user filesystem and exact package transaction
routes are defined in `tui-mutation-executor.md`. Their operation-level Trash
or DNF recovery is not equivalent to the R1–R3 recovery coverage below. A
graphical one-use confirmation does not waive a recovery gate required by the
change's actual blast radius.

The single Fedora workstation has an established R2 recovery foundation: its
Btrfs root, home, and systemd-machines boundaries plus separate boot and EFI
filesystems were captured in an encrypted external Restic snapshot. Repository
data passed a full read check, and the complete five-boundary set was restored
to an isolated local Btrfs target and independently compared with zero
mismatches and no proof gaps. The target is retained read-only. This establishes
the technical R2 artifact; it is not Jarvis enrollment, a blanket mutation
approval, or a claim of R3 whole-device, partition, encryption-layout,
firmware, or bare-metal reconstruction.

The current verified R2 identity is Restic snapshot `d28c9d2e`, tag
`jarvis-r2-system-set-20260807T090408Z`, restored and compared at
`/var/lib/jarvis-r2-restore-20260807T090408Z/data` on 2026-08-07. The
independent comparator matched 285,936 entries, including 226,042 regular
files, with equal SHA-256 manifests, zero mismatches, and no proof gaps.

The direct-host track is primary; the VM is optional rehearsal and is not a
prerequisite for shadow-mode workstation work. Jarvis H1 observation still
requires its separate exact proposal review, typed broker, restricted-storage
backend, audit binding, and one-use activation record. Every repair remains a
new transaction. Ordinary configuration/package work requires fresh R1 coverage
of the touched state; A3 kernel/driver/boot/graphics work requires a current
R2 artifact plus a verified known-working kernel and real recovery-boot
selection path; A4 storage/encryption/bootloader-layout work remains blocked on
R3.

### Local snapshot policy

Local, unencrypted Btrfs snapshots may be used as R1 for routine development
and reversible code/configuration work. They are not an R2 substitute: they do
not protect against disk failure, theft, ransomware, or filesystem-wide loss.
When stored inside the existing LUKS-backed filesystem, they inherit that
at-rest protection; a plaintext external destination does not.

The verified encrypted R2 artifact remains mandatory before kernel, NVIDIA,
initramfs, boot-argument, graphics-stack, storage, encryption, or bootloader
changes. Each R1 operation still needs an explicit target, subvolume scope,
retention rule, and rollback consequence.

The current R1 point is `/var/lib/jarvis-r1-20260807T085200Z`, covering the
`root`, `home`, and `var/lib/machines` subvolumes as read-only snapshots. The
user-provided terminal evidence is recorded in
`runtime/reports/2026-08-07-r1-local-snapshot.json`.

## Technical basis

- Fedora Workstation has used Btrfs by default for new desktop installations
  since Fedora 33, with separate root and home subvolumes; custom and upgraded
  systems may differ.
- Btrfs snapshots are subvolume-scoped and read-only snapshots are the basis
  for full or incremental send/receive replication.
- DNF5 provides transaction history undo and rollback, but this is a package
  transaction mechanism, not a whole-system backup.

Primary references:

- https://docs.fedoraproject.org/en-US/fedora/f33/release-notes/sysadmin/Distribution/
- https://btrfs.readthedocs.io/en/latest/btrfs-subvolume.html
- https://btrfs.readthedocs.io/en/latest/btrfs-send.html
- https://btrfs.readthedocs.io/en/stable/Send-receive.html
- https://dnf5.readthedocs.io/en/latest/commands/history.8.html

Fedora community implementation examples, treated as secondary guidance:

- https://fedoramagazine.org/working-with-btrfs-snapshots/
- https://fedoramagazine.org/btrfs-snapshots-backup-incremental/
- https://fedoramagazine.org/make-use-of-btrfs-snapshots-to-upgrade-fedora-linux-with-easy-fallback/
