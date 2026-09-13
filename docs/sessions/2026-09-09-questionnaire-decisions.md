# User decisions — closeout questionnaire

The 15 questions were answered through this conversation's selector. These
decisions define product scope; they are not approvals for commands,
installations, deletions, or system changes.

| No. | Accepted decision |
| --- | --- |
| 1 | Choose an installed kernel for the next boot and repair initramfs for a specific kernel. |
| 2 | Prepare any required update: packages, kernel, graphics, and other components. Each operation keeps an effects review, applicable recovery, and exact approval. |
| 3 | Cover the entire home directory as well as the system, with reviewable cache and temporary exclusions. |
| 4 | When the external disk is connected, prepare the backup and request approval before running it. Connection does not authorize writes. |
| 5 | Keep the latest 10 copies. Cleanup is presented and approved separately. Each set's scope must be visible so system backups are not mixed with rehearsals or projects. |
| 6 | The complete Restic check was not run or its result is unknown; it remains pending. |
| 7 | Test restoration in an isolated destination on the internal disk, subject to sufficient space and compatibility. Do not overwrite the current installation. |
| 8 | Choose concrete service, network, and security targets for each request, with exact review and approval. |
| 9 | Prepare dependency changes in a copy and offer application to the original after reviewing the exact change. |
| 10 | Prepare dependency downloads and request network approval before an isolated build. |
| 11 | Allow any command needed for the goal when it is explained and approved by the user. Do not limit the feature to a fixed catalog. Keep no persistent or global authority, automatic retry, or loss of recovery and verification requirements. |
| 12 | Keep sanitized operational transcripts for seven days with space limits and reviewable cleanup; keep conversation history separate. |
| 13 | Complete restoration only for a recoverable operation. If several exist, offer chat restoration only and do not claim system recovery. |
| 14 | Run a final authenticated test in a separate session using the usual access without copying credentials. |
| 15 | Prepare installation on this workstation and present the exact approvals required after testing and independent review. |

## Scope changes still requiring implementation

- A reviewed general-command boundary with minimum authority and per-operation
  approval. This replaces the fixed functional catalog without changing security
  invariants.
- Exact application to the original project from the reviewed copy, with change
  detection and recovery.
- Approved dependency download followed by an isolated build.
- Seven-day transcript retention.
- Updates for any component and the two concrete boot functions.
- System and home-directory backup, disk detection, a ten-copy retention proposal,
  and isolated restore rehearsal.
- Reviewed installation and final authenticated test.

The earlier evidence of 309 tests belongs to the candidate before these
extensions were implemented. The Restic response does not prove that a check
passed. No selection by itself authorizes a privileged operation.
