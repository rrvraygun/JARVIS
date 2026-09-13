# Fedora Jarvis requirements decision record

Status: accepted design baseline. Changes require a new revision and explicit
user decision; they do not silently alter the original record.

## Authority

- Automatically permit bounded, allowlisted, unprivileged read-only commands.
- Require fresh user approval for every state-changing command.
- Define command, procedure, and transaction approval scopes. Enable command
  scope only; retain the other scopes as disabled future extensions.
- Define a pre-authorized safe list but keep it disabled.
- Require fresh approval for every privileged command. `sudo`, `su`, `doas`, and
  `pkexec` are never autonomous.
- Permanently deny actions whose purpose or likely effect is only harmful:
  destroying or forging audit/recovery evidence, bypassing policy, wiping disks,
  capturing credentials, installing covert persistence, concealing errors,
  falsifying verification, executing untrusted remote content, unsafe
  self-modification, unresolved-target destruction, or overwriting user data,
  backups, policy, audit history, or unknown content.

## System scope

- Enroll one Fedora Workstation only.
- Cover graphics, development tools, virtualization, containers, audio,
  servers/databases, backups, security, storage, health, updates, installation,
  removal, maintenance, repair, and performance analysis.
- Exclude gaming optimization and user VPN administration. Network platform
  facts may still be inspected when required for system correctness or security.
- Detect RPM/DNF, Flatpak, rpm-ostree, storage, encryption, boot, snapshot, and
  virtualization characteristics through an approved read-only inventory.
- Label facts changed or hidden by the Codex sandbox as observer-scoped rather
  than claiming they describe the host.

## Evidence and documentation

- Prefer installed-version local help/man pages, Fedora primary sources, and
  matching upstream documentation.
- Use curated and community sources only when primary sources are insufficient.
  Community evidence requires user confirmation before it influences an action.
- Maintain a comprehensive offline local documentation cache and version index.
- Support Bash first. Cover man/help, exit codes, environment, parsing, quoting,
  pipes, redirection, SELinux, systemd, DNF/RPM, Flatpak, containers,
  NetworkManager, firewalld, Btrfs/LVM, logs, kernel, firmware, drivers,
  virtualization, audio, backups, and recovery.
- Keep installed-version documentation authoritative; index newer information
  separately.

## Attempts, errors, and lessons

- Do not retry automatically. Permit one attempt only.
- Record failures and unexpected output as observations.
- Promote only reviewed lessons backed by a working, verified solution.
- Automation may nominate a lesson after repeated matching verified successes;
  only the user may activate it.
- Preserve immutable history. Globally prefer an active lesson on the enrolled
  workstation only while prerequisites match. Suspend it after a version change,
  conflict, unexpected effect, or validation failure.
- Record verified successes, timing, version constraints, side effects,
  prerequisites, and validation results under the same promotion controls.
- Persist concise decision summaries, never private chain-of-thought.

## Data and privacy

- Combine SQLite structured state, Git-managed reviewed declarations, and
  hash-chained JSONL audit events.
- Plan an encrypted append-only remote integrity/backup sink. It is not enabled
  until the user supplies and approves a destination and credential mechanism.
- Keep raw output briefly according to size and diagnostic value; retain hashes,
  audit events, and confirmed lessons longer.
- Encryption is mandatory before definitive release. Until an encrypted store is
  configured and explicitly unlocked, do not persist restricted or secret data.
- Redact credentials, tokens, keys, cookies, authorization values, usernames,
  hostnames, personal paths, local addresses, serials, and machine identifiers.
- Provide human-readable history, export, and user-approved complete erasure.

## Safety and verification

- Require rollback for every mutation at risk score 0 or greater by default.
  The threshold is versioned policy and may be changed only explicitly.
- Refuse reversible execution without rollback. If truly irreversible, require
  a specific declaration and elevated approval rather than claiming rollback.
- Require independent review for every mutation.
- Require dry-run or simulation whenever supported.
- Require post-action validation. On failure, capture output, diagnose, and ask
  for approval before any state-changing recovery.
- Prefer atomic maintenance transactions, while requiring separate approval for
  each state-changing command under the initial policy.

## Interface evolution

- Initial interface: natural-language Codex request plus terminal reports.
- No unattended monitoring initially.
- Future interface: dedicated TUI presenting facts, evidence, plans, approvals,
  actions, verification, history, lessons, and recovery.
- Portability interfaces may support other Linux systems later, but Fedora
  Workstation behavior is the only initial implementation target.
- Optimize for safety first, increasing autonomy only for specific, versioned,
  repeatedly verified procedures.

## Direct-host deployment clarification

- Treat the one enrolled Fedora Workstation as the primary product target; the
  VM is a secondary software rehearsal environment.
- Do not treat a same-device snapshot, package-history rollback, or successful
  VM test as complete workstation recovery.
- Select the snapshot/backup backend only after bounded read-only discovery of
  the actual filesystem, subvolume/LVM, boot, EFI, encryption, and storage
  layout.
- Require R0 record coverage for read-only/project work, R1 local snapshot
  coverage for ordinary package/configuration changes, R2 external encrypted
  system backup for kernel/driver/boot/graphics changes, and R3 offline
  full-device recovery for storage/encryption/bootloader-layout changes. Before
  each A3 mutation, separately verify a known-working kernel and the real
  recovery-boot selection path; this action-specific boot gate is not a VM
  requirement and is not a claim that R2 provides bare-metal reconstruction.
- Begin live development in shadow mode. Supervised mutation remains blocked
  until the required recovery artifact and a restore rehearsal are verified.

## Accepted TUI mutation integration revision — 2026-08-27

This revision records the user's explicit product decision without rewriting
the baseline above:

- deterministic exact reads remain automatic and approval-free;
- every filesystem or package mutation requires a fresh graphical one-use
  confirmation;
- exact current-user-writable, non-protected filesystem targets are not limited
  to the project branch;
- deletion means a bounded move to the current user's Trash, never permanent
  unlink;
- privileged package install/remove uses only the registered root-owned Polkit
  helper, an exact cache-only DNF preview, durable pre-state, and separately
  approved undo; and
- model turns may propose broader current-user work, but typed admission grants
  no mutation by itself and each command/file boundary remains `untrusted`.

## 2026-09-08 — controlled disaster-recovery backups

The user selected their existing external disk and clarified that controlled
system backups are sufficient for the primary disaster-recovery goal; a complete
uncompressed image is not mandatory. The current candidate uses the previously
registered encrypted Restic approach, retaining existing external-disk data and
requiring fresh integrity and restoration evidence. See
[specific target observations](sessions/2026-09-08-external-backup-target.md).
Partition/firmware operations retain their separate exact approval and recovery
requirements. A historical file-restore report is not a current bootability proof.

## Accepted completion questionnaire — 2026-09-09

The user answered all 15 scope questions. The authoritative exact decisions are recorded in `sessions/2026-09-09-questionnaire-decisions.md`. They expand general reviewed commands, original-project dependency application, approved dependency downloads, seven-day transcripts, all necessary updates, two explicit boot operations, full home/system backup and installation on this workstation. These are scope decisions, not action-specific execution approvals. Restic full-check evidence is still missing. Full checkpoint restoration remains limited to one recoverable operation.
