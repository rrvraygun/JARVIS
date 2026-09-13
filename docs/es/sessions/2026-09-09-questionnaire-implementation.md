# Questionnaire implementation — 2026-09-09

Work remains in the isolated candidate. The verified 309-test snapshot is preserved separately; these changes require new validation and do not activate anything.

Implemented in this continuation: seven-day transcript expiry; general explicit argv in the existing read-only/offline project sandbox; reviewed executable digest; isolated Python guard; cross-process locked reservations shared with Cargo; trusted cgroup launch receipt and read-only settlement checks; existing-manifest application from a verified dependency workspace with retained displaced originals, partial-state reporting and metadata verification.

Independent reviews identified and prompted fixes for reservation races, cgroup settlement, and preservation of group/attributes. Initial six-module typing check found an Any return in settlement's pre-launch branch; this was recorded before correcting the explicit boolean return. Scope/recovery expansion remains incomplete: general host/root/network commands, dependency downloads, automated inverse project recovery, update/boot helpers and system backup orchestration are not claimed complete.

Focused tests and real isolated command smoke passed during development. Final results will be appended after the current checks. No actual user project, persistent service, package, DNS/firewall, boot configuration or external backup contents were modified.

## Download and inverse recovery continuation

Dependency recovery now returns a new inverse copy proposal only when current hashes and metadata remain attributable to the reviewed change. Preparing it does not restore files: copy execution, verification and application each keep their separate review boundary. The round-trip and rejection of later user edits passed tests.

One locked crates.io archive can now be proposed for an exact HTTPS download with SHA-256, a new destination, 8 MiB and 30-second bounds, no redirects/proxies/authentication/retry. Verified archives may be mounted read-only for an offline Cargo build; extraction is confined and bounded. A real Cargo test with a synthetic vendored dependency passed; network transport was a fixture, not a real download. Forty-six focused tests passed, including redirects, interrupted/oversized downloads, bad checksums, traversal, links, duplicates and expansion limits.

The nine-module type check then found three annotation errors: reused stream variable type and unpacked argv types. They were recorded before correcting variable naming and explicit argument indexes. No functional validation was represented as passing from that failed typing run.

## Recovery and boot continuation — 2026-09-10

The user completed the R2 repository check (`no errors were found`) and restored
snapshot `0b203a54` twice to new internal destinations. Root/home/machines passed
the independent comparator. Boot/EFI matched a same-snapshot restore under two
read-only `rsync -naiHAX --delete` comparisons; the first comparator's six
differences were temporal drift against live boot files. A Btrfs destination
shape correction was required and the first ensayo was retained.

Added `boot_plan.py` for exact read-only planning of selecting a concrete
installed kernel or repairing its initramfs. It requires the named image and
initramfs to exist, binds both paths and an exact one-use approval, and blocks
when current R2 recovery is unverified. It never changes boot files or claims
bootability. The privileged executor, recovery-boot path check and actual
approved operation remain pending.

General host/root/network command execution, broad update/boot helpers and system backup orchestration remain outstanding. No such mutations were executed.

Added `update_plan.py` for exact Fedora NEVRA sets. It accepts any required
package set, classifies kernel/graphics/boot families, requires current R2
recovery for critical sets, binds one-use approval and keeps bootability as an
unproven claim. It is planning-only; package helper installation, transactions,
initramfs work and rollback tests remain pending. Forty-three focused planning
tests pass.
