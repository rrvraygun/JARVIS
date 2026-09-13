# External backup target — 2026-09-08

## User decision

The user connected their external disk for identification and chose controlled
system backups as the disaster-recovery method. A complete uncompressed disk
image is not required for this primary goal. Reuse of the existing Restic
repository is the candidate approach; no backup write or repository unlock has
been performed in this session.

## Observed today

Host metadata reads identified a USB Fujitsu MJA2500BH G2:

- observed device name: `/dev/sda` (not a permanent identity);
- device capacity: 500,107,862,016 bytes;
- partition: `/dev/sda1`, NTFS, already mounted as
  `/run/media/tipexxx/LG_EXT_HDD` when inspected;
- available space: 404,781,572,096 bytes;
- existing used space: 95,323,643,904 bytes; existing data must be preserved;
- the known `JARVIS_BACKUP/restic-repository` directory exists, including a
  regular 155-byte `config` file. Presence is not proof of current integrity or
  decrypted repository identity.

The restricted environment exposed sysfs metadata but not the `/dev/sda` node.
Read-only host queries outside that isolation supplied partition/mount data.
No format, mount, repair, partition, backup or restore command was executed.

Fedora `/` and `/home` are Btrfs and share a filesystem. `df` reported
88,891,998,208 used bytes for that shared filesystem; those two rows must not be
added together. `/boot` is separate ext4 and EFI is separate vfat. Filesystem
used space is an estimate for planning, not a bound on logical backup size.

## Historical evidence, not revalidated today

`deployment/host/recovery-set-plan.json` names an NTFS-backed Restic repository
with identity prefix `e372e10c`, format 2 and compression auto. The source runbook
records a previous five-boundary encrypted backup and restore comparison.
The original runtime report dated 2026-08-07 records snapshot prefix `0b203a54`
and user-terminal evidence. None of those records proves today's repository
integrity, snapshot freshness or bootability.

## Controlled recovery plan

Use the existing encrypted Restic repository if the user can unlock and verify
it. Keep the password exclusively in the user's interactive terminal, following
`../r2-system-recovery-set.md`; never pass it through chat, arguments, environment
variables, project files or logs.

Re-resolve all source subvolumes, including the historically declared nested
systemd-machines boundary. Prepare each read-only source snapshot with a separate
exact approval. Include boot and EFI with conflict/quiescence checks. Perform a
new controlled backup, full pack-data verification and isolated restoration with
the existing independent comparator. Record exclusions and the difference between
file restoration and a tested boot/rebuild procedure. Source snapshots are not
atomic across boundaries; preserve the existing skew limit and stop conditions.

Unresolved: current repository identity/integrity after unlock, current snapshot
set, complete subvolume graph, exact restore-test destination and boot/rebuild
procedure. No existing data on the external disk may be replaced to resolve them.

## User-reported repository listing — 2026-09-09

The pasted listing contains four unique snapshots (it was pasted twice): 00dfdb85, 06bae9b3, d28c9d2e and 0b203a54. Latest: 2026-08-07 12:41:37 local, 20.035 GiB, five declared boundaries. This establishes user-reported readable snapshot metadata, not a fresh integrity or restore proof. Result of `restic --no-cache check --read-data` remains pending. No password was shared or stored.
