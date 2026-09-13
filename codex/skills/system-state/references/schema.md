# State and event schema

State records require schema version, UTC collection time, approved host ID,
collector/version, coverage, privilege, redactions, source commands, exit status,
and data. Change events require ID, objective, risk, approval reference, exact
targets, before/after state, command result, validation, rollback, residual risk,
and status (`planned`, `approved`, `running`, `succeeded`, `failed`, `rolled_back`).
Never store credential values or claim a planned event executed.
