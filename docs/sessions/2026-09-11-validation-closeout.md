# Closeout corrections — September 11, 2026

Work was performed in the isolated candidate. The active version and installed
helpers were not replaced during these corrections.

## Corrected diagnosis

`/tmp/jarvis-headless-final.log` ended with 36 passed tests in 109.777 seconds.
Earlier claims that the driver was blocked were unsupported because several runs
were interrupted before that time. The unverified global cancellation added to
`on_unmount` was removed; Textual keeps its normal shutdown handling. The new
validation waits for actual completion.

## Normal terminal

The incompatible `run_blocking_once` call was corrected and `App.suspend()` was
moved to the interface thread. Normal mode has a proposal, digest, and approval
separate from isolated execution. The operation is reserved before launch and a
durable receipt is retained. The inherited environment is HMAC-bound with an
ephemeral key and its values are not persisted. State is rechecked after the lock
is acquired, and the reservation is discarded when review is rejected. Normal
execution is not admitted when JARVIS runs as root.

The review-button test passed in 2.726 seconds. The visible PTY/Textual test ran
exactly one `printf`, produced `JARVIS_NORMAL_TERMINAL_OK`, exited 0, and created
review and result captures. Its App Server was a fixture with no real account or
model. The guide preserves that distinction.

## Privileged helpers

Independent review found unvalidated paths, writes without atomic reservation,
requester-controlled recovery values, and a persistent kernel selection that did
not match the requested next boot. Those prototypes were replaced with entries
that load a root-owned installed executor.

The executor requires an independent root-owned review bound to UID and ID, with
request digest, expiry, and R2 evidence linked to pre-state. It cannot create or
infer that approval from model booleans. Reservation and result are separate
records and are never overwritten. A pending result blocks another operation.
Prepared policies use `auth_admin` without persistent authorization; the client
also checks their hashes before invocation.

Selection uses `grub2-reboot` for one boot. Repair generates a new image;
publishing it is another reviewed operation with a prior copy and atomic exchange
that preserves the displaced inode. Review is repeated before reservation and
before the effect.

Updates replay a DNF5 `--store` tree without `ignore`/`skip` or new free
resolution. Internal relative paths, signatures, and NEVRA of referenced RPMs
are validated. The final installed set is compared with the expected set derived
from approved actions, including unaffected packages. Tests use fixtures; no
update or boot change was run.

Format basis: <https://dnf5.readthedocs.io/en/latest/commands/replay.8.html> and
the public `libdnf5/transaction/transaction_sr.cpp` serializer in DNF5.

## Recovery: limit of earlier evidence

The user's output demonstrates an integrity check of the repository and a restore.
The comparator reported six boot/EFI differences against live state. Later
`rsync` runs used `-naiHAX` without `-c`; empty output is not an independent
checksum comparison. Comparing two restores of the same snapshot adds no separate
original source. A temporal cause is plausible, not certified. The sparse test
has no witness. This evidence is not promoted to a current R2 approval for a
future critical change.

## Final evidence

Complete results and the candidate copy are published with the manifest in the
delivery directory. Fixtures, a real PTY, an authenticated turn, and privileged
workstation tests are kept distinct.

The final restricted run of interface, terminal, helpers, and planning completed
61 tests in 113.673 seconds with exit code 0. Bundle validation also passed
without rerunning the TUI. A validation request outside the sandbox was rejected
before execution because of the automatic permission-review quota; it was not a
user prohibition. The first sandbox quality-gate run found stale inventory after
a fixture guard was added; inventory was regenerated before the next validation
without skipping checks.

The restricted full run reached 352 tests, found a real Recovery Specialist
registration defect (missing `recovery_plan`), and hit the sandbox Unix-socket
restriction. The registration was corrected and its five tests passed. A new
limited request for the two `jarvisd` tests outside the sandbox was authorized and
both passed. These failures are not attributed to Textual or hidden by quality-
gate exclusions.
