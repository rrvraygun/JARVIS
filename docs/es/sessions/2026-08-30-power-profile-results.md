# Power profile result visibility — 2026-08-30

## Outcome

Implemented the Power Expert application-result slice. Verified profile helper
responses now produce an atomic, per-user `PowerProfileApplicationRecord` with
pre/requested/resulting values, three-way control comparisons, skipped values,
status, digest, timestamp, and recovery metadata. Restart restoration loads the
latest valid applied record and ignores malformed or digest-mismatched records.

The Power tab labels the automatically selected AC/battery variant, keeps the
applied result separate from the current draft, and uses equal responsive
inventory/settings regions. Verified activation adds a detailed AGENT
confirmation to the conversation, which is persisted through the existing
conversation manager and is available to subsequent Power Expert context.

## Validation evidence

- `PYTHONPATH=tui/src python3 -m unittest tui.tests.test_power_profiles tui.tests.test_power_control_client tui.tests.test_presentation`: 29 passed.
- `PYTHONPATH=tui/src python3 -m unittest discover -s tui/tests -p 'test_*.py' -k power`: 13 passed, 4 skipped.
- Full TUI discovery: 250 tests, 217 passed, 32 skipped, 1 environment error: the read-only test socket bind was denied by the sandbox (`PermissionError: [Errno 1] Operation not permitted`).
- Ruff check and format passed for all changed Python files.
- Documentation contract, regenerated codebase inventory, and regenerated/verified 744-entry release manifest passed.

No host power helper, package manager, service, or privileged operation was
activated. Existing one-use approval and rollback paths remain unchanged.
