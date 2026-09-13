# R2 system recovery-set runbook

## Current claim

The immutable prepared-plan baseline still describes the state before system
capture. Execution evidence recorded on 2026-08-06 establishes an encrypted
five-boundary Restic snapshot, a full pack-data check with no reported error,
and a complete restore into an isolated Btrfs target. Restic restored 281,428
files/directories and verified 179,720 regular files without a reported
verification failure. The independent comparator then covered 281,425 entries,
including 221,842 regular files and 21,311,943,627 logical bytes. It reported
zero mismatches, equal source/restored manifests, no proof gaps, and passing
content, tree, metadata, link, xattr, ACL, SELinux-label, sparse-file, boot, EFI,
and boundary-separation proofs. The exact restored subvolume subsequently
reported `ro=true`.

The current execution status is
`r2-verified-five-boundary-restore-compared-and-retained-read-only`.
This establishes the external file-level R2 recovery artifact defined by the
direct-host architecture. It does not prove bare-metal reconstruction or
bootability, which are separate R3 and action-specific concerns. R2 is a
recovery prerequisite, not a blanket authorization: before any kernel, NVIDIA,
initramfs, boot, display-manager, or graphics-stack mutation, Jarvis must still
confirm that the artifact is current for the affected state, preserve a known
working kernel, verify the real recovery-boot selection path, and obtain exact
command approval.

The read-only property command was executed before its explicit approval
message. The exact reviewed command ran once and the desired result was
validated, but the later message is recorded only as post-execution
acknowledgement; it is not represented as retroactive authorization. This
governance exception does not change the independently verified file data, but
it remains part of the immutable recovery history.

The machine-specific prepared plan is
`deployment/host/recovery-set-plan.json`. It is intentionally non-executable and
has status `prepared_not_executed`.

## Recovery boundaries

The first system set has five independently declared sources:

1. a new read-only snapshot of the root Btrfs subvolume;
2. a new read-only snapshot of the home Btrfs subvolume;
3. a new read-only snapshot of the nested systemd-machines Btrfs subvolume;
4. the separate ext4 boot filesystem; and
5. the separate vfat EFI System Partition.

A root snapshot is not recursive. It cannot stand in for home or
systemd-machines, and it cannot include boot or EFI. Boot and EFI do not have the
same Btrfs snapshot primitive, so their capture is a bounded live Restic read
after verifying that no package, kernel, initramfs, bootloader, or firmware
transaction is active.

The three Btrfs snapshots are individually point-in-time consistent but are not
atomic as a group. The plan limits creation skew to 120 seconds and invalidates
the set if that budget is exceeded. Application data is crash-consistent unless
an application-specific quiesce operation is later designed and separately
approved.

## Closed execution sequence

Every mutation receives a fresh command-scoped approval. An operation failure or
unexpected warning stops the sequence; no automatic retry, rollback, cleanup,
or snapshot deletion is allowed.

1. Re-resolve the mount and subvolume graph, free-space margin, destination,
   repository identity, lock state, and absence of conflicting transactions.
2. Create one uniquely named root-owned snapshot-set directory.
3. Create and verify the root read-only snapshot.
4. Create and verify the home read-only snapshot.
5. Re-resolve and snapshot the systemd-machines boundary.
6. Confirm all snapshot identities, read-only properties, timestamps, skew, and
   explicit exclusions.
7. Back up exactly the three snapshots plus boot and EFI to one encrypted Restic
   snapshot, using the pseudonymous host and a unique system-set tag.
8. Run `restic check --read-data` and require zero warnings and errors.
9. Inventory the encrypted snapshot through Restic and verify that all five
   approved source aliases are present with no sixth source.
10. Restore the complete set to a separately approved isolated scratch target
    and compare contents and metadata independently.
11. Freeze the validated scratch target read-only and finalize the append-only
    audit and versioned recovery manifest.
12. Retain all snapshots until a separate reviewed retention action is approved.
13. Treat whole-device imaging, partition/filesystem recreation, encryption
    recovery, and offline bare-metal reconstruction as R3. A disposable VM or
    spare device may optionally rehearse those mechanics, but is not an R2 or
    direct-host development prerequisite.

## Proof requirements

The one-file rehearsal already proves regular-file encryption, pack integrity,
directory reconstruction, content hashing, mode, and modification time for its
minimal scope. System scope must additionally prove owner/group, ACLs, extended
attributes, SELinux labels or their explicitly disabled-host limitation,
symlinks, hard links, sparse files, boot and EFI contents, nested-subvolume
separation, and full restoration to a non-production target.

The final recovery document must distinguish file restoration from disk
reconstruction. R2 does not include the partition table, LUKS header, filesystem
creation, UEFI NVRAM entries, firmware configuration, or Secure Boot material
outside captured files. Those remain R3 or separate exceptional workflows.

## Independent five-boundary comparator

`deployment/host/verify_restored_boundaries.py` is the second, Restic-independent
verification layer. It has no subprocess, network, or filesystem-write
primitive. Directory and regular-file descriptors use `O_NOATIME`; symlinks are
never followed. The comparator verifies the exact restored tree against the
three retained Btrfs snapshots plus live `/boot` and `/boot/efi`, with EFI
excluded from the boot traversal and checked as its own boundary.

It compares path-set completeness, file type, mode, UID, GID, nanosecond mtime,
symlink targets, hard-link relationships, device identities, all accessible
extended-attribute names and values (including POSIX ACLs, SELinux labels, and
file capabilities), logical sparse-file preservation, and SHA-256 content for
every regular file. It also rejects an unexpected sixth top-level restore root.
The report contains aggregate counts and hashes only. A mismatch includes a
one-way path token, never a file name or content.

The comparison applies three explicit filesystem/backend semantics without
weakening ordinary-path checks:

- Restic 0.19.1 deliberately ignores Unix sockets. They are ephemeral IPC
  endpoints, not recoverable file content, so source sockets absent from an
  otherwise empty restore target are counted as notices rather than missing
  recovery data.
- Restic stores logical file content, not original sparse extent locations.
  `restore --sparse` detects long zero runs and may create holes at different
  positions. Sparse proof therefore requires content, logical size, mtime, and
  at least one real restored sparse witness; it reports but does not fail on
  other allocation-layout differences.
- `--one-file-system` excludes nested Btrfs subvolumes. Descendant Btrfs
  subvolume roots (inode 256) and snapshot boundary stubs (inode 2) are still
  required to exist as directories, but their marker-directory mtime is not
  treated as production-directory restoration evidence. Their independently
  declared recovery boundary remains authoritative.

Every other missing path, mtime difference, type/metadata difference, content
hash difference, unrecognized nested boundary, or unexpected restore entry
still fails closed.

The machine-specific invocation is:

```bash
sudo python3 \
  /home/tipexxx/Escritorio/Proyecto/codex-agent-system/deployment/host/verify_restored_boundaries.py \
  --snapshot-set /var/lib/jarvis-r2-20260806T132342Z-v2 \
  --restore-target /var/lib/jarvis-r2-restore-06bae9b3-v1/data \
  --selinux-expectation disabled-reviewed
```

Exit `0` means every comparison matched and every required feature had at least
one real source witness. Exit `2` means all compared data matched but at least
one required feature lacked a witness. Exit `3` means a mismatch. Exit `4`
means the complete read-only inspection could not safely continue. The
`disabled-reviewed` SELinux expectation may be used only after separate current
host evidence confirms that limitation; it is not an automatic fallback.

## Password and privacy boundary

The Restic password is entered only by the user at an interactive terminal. It
must never be passed in an environment variable, command argument, project
file, audit record, agent message, or as the sole copy on the backup disk.
Machine identity is pseudonymous in persisted records. Raw host inventories
remain prohibited until user-unlocked encrypted local storage exists.

## Stop conditions

Stop before or during the system set if any source/destination identity changes,
the external disk is absent or unsafe, the repository is locked or mismatched,
a new nested boundary appears, snapshot skew exceeds the budget, a conflicting
transaction is active, a source is unreadable or skipped, Restic reports any
warning, output expands beyond the five sources, free space becomes unsafe, or
the audit/knowledge store fails integrity verification.
