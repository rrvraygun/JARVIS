# JARVIS patch guide

Updated September 11, 2026. This delivery is a code-and-test candidate; it does
not mean that the active installation was replaced.

## Included capabilities

| Component | Capability and scope |
| --- | --- |
| Normal terminal | **Run in normal terminal** in Development, with explicit review of mode, arguments, directory, and user authority. Inherits user I/O and limits; adds no hidden shell or commands. |
| Approvals | Ephemeral decisions, mode-specific digest, durable reservation, and replay rejection. Environment is bound without storing its values. Uncertain results require reconciliation. |
| Cargo | Check, build, test, fmt, and clippy on an isolated copy, without network or the real HOME, with effective limits and process-group checks. |
| Dependencies | Reviewed copy, separate application to existing manifests, retained originals, and content/permission/attribute checks. A separate inverse proposal is required when later edits are incompatible. |
| Downloads | One crates.io download by URL and lockfile checksum, approved separately. Cargo consumes verified files without network. |
| Root | Separate boot and update entries, shared root executor, and Polkit policies without persistent authorization. Requires an exact request, independent review, and current recovery evidence. |
| Boot | Next-boot selection; new initramfs generation and publication through a separate approved operation that preserves the previous image. It does not reboot or test bootability. |
| Updates | Strict replay of a prepared DNF5 transaction with signed files and references inside its tree. Checks the expected installed set. |
| MCP and specialists | Per-process/generation scope, selected specialist respected, fresh observations, and rejection of out-of-scope tools or policies. |
| Interface | Health, Development, Network, Security, and Recovery views; review and detailed data stay outside the clean conversation. |
| Checkpoints | Context preservation; complete recovery only when a linked recoverable operation exists. Chat is not restored before package recovery finishes. |
| Transcripts | Sanitized results, bounded size/count, and seven-day retention for new records. No full environment, credentials, or private reasoning. |
| Recovery | Bounded project copy/restore and planning for the five system boundaries. Full Restic orchestration remains a separate integration. |

## Test the interface and terminal

From the candidate directory, as a normal user:

```bash
.venv/bin/python scripts/smoke-normal-terminal.py --approve-printf-smoke
```

The test opens Textual in a real terminal, shows the normal-mode review, confirms
only a fixed `printf`, and checks its receipt. It uses a synthetic session with
no model, account, network, or root helper. It writes SVG captures and JSON to a
new `/tmp` directory and prints its path. The final marker is
`JARVIS_VISIBLE_SMOKE_PASSED`.

To inspect only the interface without an agent connection:

```bash
PYTHONPATH="$PWD/tui/src" .venv/bin/python -m jarvis_tui --bundle-root "$PWD"
```

The normal `scripts/launch-tui.sh` launcher connects to the App Server and needs
the reviewed profile and normal authentication. Do not copy credentials into the
patch or paste them into the conversation.

The normal terminal uses the user's regular permissions and network. Exit code
zero confirms only the main process; it does not prove the full goal or child
process completion. The normal route is not enabled by running JARVIS as root.

## Reproducible validation

```bash
bash scripts/quality-gate.sh --full
```

Wait for the final result: graphical tests take about two minutes on this host.
Asyncio slow-task messages alone are not a lockup. The exact result for this
delivery is recorded in `VALIDATION.md` beside the candidate.

## Deployment and privileged operations

Prepared files are `jarvis_boot_control.py`, `jarvis_update_control.py`,
`jarvis_privileged_control.py`, and the two `org.jarvis.*-control.policy` files.
The client requires installed files and policies to match the candidate and be
owned by root. The smoke test does not install them.

Protected state is under `/var/lib/jarvis/privileged-control`: approvals,
reservations, results, transactions, and backups. Each independent approval is
bound to a UID, ID, and request digest, expires, and includes R2 evidence linked
to pre-state and recovery-boot confirmation. The agent cannot create or infer
this authority from arguments.

For updates, the administrator prepares a DNF5 `--store` tree with signed local
RPMs and normalized relative paths. RPM transitions are accepted; groups,
environments, and other formats are rejected. `ignore` and `skip` options are
not used to silence differences. Initramfs publication requires a separate review
of the generated image hash. Errors and uncertain results never trigger retries
or automatic rollback.

## Limits of what was tested

Privileged deployment requires exclusive maintenance and immutable transaction
publication; the helper lock does not serialize other administrators. Hashes are
rechecked before effects, without claiming to remove every race with other root
processes.

- The visible test exercises the TUI and a real command; the model is a fixture.
- External downloads and privileged commands use fixtures; no package or boot
  change was applied to the workstation in this closeout.
- Real authentication, per-operation root provisioning, and candidate activation
  still require deployment checks.
- Restic passed the evidence supplied by the user. `rsync` comparisons without
  `-c` do not certify checksum equality. Real recovery boot, partition/UEFI
  reconstruction, and a current full-system restore were not demonstrated.

Correction details: `sessions/2026-09-11-validation-closeout.md`.
