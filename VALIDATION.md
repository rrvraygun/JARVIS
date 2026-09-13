# Recovered delivery — September 11, 2026

Status: persistent candidate tested; not activated or installed as a system
update. The previous active version is preserved and needs no rollback.

## Evidence for this copy

- Code changes were recovered from the editing calls recorded for this task;
  historical commands were not run and credentials were not copied.
- TUI suite: 350 tests in 69.213 seconds, 349 passed and one environmental error
  while creating a local socket inside the sandbox. Both socket-module tests
  passed outside the sandbox. The error is not attributed to Textual.
- The two missing `recovery_plan` tests were restored and passed with specialist
  and root tests (17 tests at that point).
- Independent review added state-change checks before root effects and three
  regression tests; 13 root tests passed.
- Visible test: `printf` ran once, exited 0, and returned to the interface.
  Captures and the receipt are in `runtime/validation/visible-y5i3l9cl/`.
- Ruff passed; mypy passed for the three new execution modules.
- Bundle validation passed with 817 entries before this report was added. The
  final manifest is regenerated after the report.

Logs are stored in the parent directory with the
`jarvis-2026-09-11-recovered-` prefix. A combined rerun outside the sandbox was
rejected before execution by the automatic review quota; it is not reported as
passed.

## Additional corrections

Inventory and manifest generation now exclude paths relative to the candidate:
a parent directory named `runtime` no longer creates an empty delivery. The
verifier rejects empty manifests. The visible test keeps persistent evidence.

## Pending for complete installation

Root helper/policy installation, independent approval provisioning, the
authenticated test, and release activation were not performed. The complete
plan is not finished. The restore rehearsal also does not prove recovery boot or
a complete current workstation copy.

Root deployment must guarantee exclusive maintenance and immutable publication
of prepared transactions: the helper lock does not serialize other administrative
tools. Rechecking hashes reduces concurrent-change risk but does not remove races
with another root administrator. This candidate is not promoted as production-
ready privileged execution software.

## Test the terminal

From this directory:

```bash
.venv/bin/python scripts/smoke-normal-terminal.py --approve-printf-smoke
```

This test uses a simulated model and runs only the displayed fixed `printf`.
The capability guide is `docs/PATCH-GUIDE-2026-09.md`.
