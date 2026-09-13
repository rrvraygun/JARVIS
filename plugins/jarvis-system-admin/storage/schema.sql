PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_revisions (
    source_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    source_class TEXT NOT NULL,
    authority_tier INTEGER NOT NULL CHECK(authority_tier BETWEEN 0 AND 8),
    title TEXT NOT NULL,
    publisher TEXT NOT NULL,
    locator TEXT NOT NULL,
    applicable_versions_json TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content_text TEXT,
    complete INTEGER NOT NULL CHECK(complete IN (0, 1)),
    community_confirmation_required INTEGER NOT NULL CHECK(community_confirmation_required IN (0, 1)),
    previous_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE,
    PRIMARY KEY(source_id, revision)
);

CREATE TABLE IF NOT EXISTS fact_revisions (
    fact_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    machine_scope TEXT NOT NULL CHECK(machine_scope = 'enrolled-workstation'),
    fact_key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    value_type TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    valid_until TEXT,
    collector TEXT NOT NULL,
    collector_version TEXT NOT NULL,
    source_attempt_id TEXT,
    privacy_class TEXT NOT NULL CHECK(privacy_class IN ('public', 'internal', 'restricted', 'secret')),
    prerequisites_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('current', 'superseded', 'suspended')),
    previous_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE,
    PRIMARY KEY(fact_id, revision)
);

CREATE TABLE IF NOT EXISTS command_catalog_revisions (
    command_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    executable TEXT NOT NULL,
    domain TEXT NOT NULL,
    mutates_host INTEGER NOT NULL CHECK(mutates_host IN (0, 1)),
    privilege_possible INTEGER NOT NULL CHECK(privilege_possible IN (0, 1)),
    documentation_methods_json TEXT NOT NULL,
    safe_argument_patterns_json TEXT NOT NULL,
    prohibited_patterns_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active', 'suspended', 'superseded')),
    previous_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE,
    PRIMARY KEY(command_id, revision)
);

CREATE TABLE IF NOT EXISTS command_attempts (
    attempt_id TEXT PRIMARY KEY,
    requested_at TEXT NOT NULL,
    executable TEXT NOT NULL,
    argv_json TEXT NOT NULL,
    cwd_class TEXT NOT NULL,
    environment_keys_json TEXT NOT NULL,
    purpose TEXT NOT NULL,
    expected_json TEXT NOT NULL,
    actual_json TEXT NOT NULL,
    exit_code INTEGER,
    timed_out INTEGER NOT NULL CHECK(timed_out IN (0, 1)),
    outcome TEXT NOT NULL CHECK(outcome IN ('success', 'failure', 'unexpected', 'unavailable', 'blocked')),
    output_hash TEXT NOT NULL,
    output_excerpt TEXT,
    output_bytes INTEGER NOT NULL,
    privacy_class TEXT NOT NULL CHECK(privacy_class IN ('public', 'internal', 'restricted', 'secret')),
    evidence_json TEXT NOT NULL,
    action_digest TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS error_reports (
    error_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES command_attempts(attempt_id),
    created_at TEXT NOT NULL,
    error_class TEXT NOT NULL,
    expected_json TEXT NOT NULL,
    observed_json TEXT NOT NULL,
    diagnosis_status TEXT NOT NULL CHECK(diagnosis_status IN ('unreviewed', 'diagnosed', 'resolved', 'superseded')),
    candidate_cause TEXT,
    working_solution_attempt_id TEXT REFERENCES command_attempts(attempt_id),
    report_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS error_report_revisions (
    error_id TEXT NOT NULL REFERENCES error_reports(error_id),
    revision INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    diagnosis_status TEXT NOT NULL CHECK(diagnosis_status IN ('unreviewed', 'diagnosed', 'resolved', 'superseded')),
    candidate_cause TEXT,
    working_solution_attempt_id TEXT REFERENCES command_attempts(attempt_id),
    reason TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE,
    PRIMARY KEY(error_id, revision)
);

CREATE TABLE IF NOT EXISTS lesson_revisions (
    lesson_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('draft', 'candidate', 'approved', 'suspended', 'superseded', 'rejected')),
    title TEXT NOT NULL,
    guidance TEXT NOT NULL,
    scope TEXT NOT NULL CHECK(scope = 'enrolled-workstation'),
    prerequisites_json TEXT NOT NULL,
    exclusions_json TEXT NOT NULL,
    validation_json TEXT NOT NULL,
    source_error_ids_json TEXT NOT NULL,
    success_threshold INTEGER NOT NULL CHECK(success_threshold >= 1),
    user_decision_id TEXT,
    reason TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE,
    PRIMARY KEY(lesson_id, revision)
);

CREATE TABLE IF NOT EXISTS lesson_evidence (
    evidence_id TEXT PRIMARY KEY,
    lesson_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL REFERENCES command_attempts(attempt_id),
    recorded_at TEXT NOT NULL,
    evidence_type TEXT NOT NULL CHECK(evidence_type IN ('matching-success', 'conflict', 'version-change', 'unexpected-effect')),
    prerequisites_match INTEGER NOT NULL CHECK(prerequisites_match IN (0, 1)),
    independently_verified INTEGER NOT NULL CHECK(independently_verified IN (0, 1)),
    details_json TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS decision_records (
    decision_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    objective TEXT NOT NULL,
    facts_json TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    alternatives_json TEXT NOT NULL,
    selected_action_json TEXT NOT NULL,
    risk_json TEXT NOT NULL,
    validation_json TEXT NOT NULL,
    outcome_json TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS approval_records (
    approval_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL CHECK(scope IN ('command', 'procedure', 'transaction')),
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    approver TEXT NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('approved', 'denied', 'revoked')),
    action_digest TEXT NOT NULL,
    state_digest TEXT NOT NULL,
    targets_json TEXT NOT NULL,
    nonce TEXT NOT NULL UNIQUE,
    scope_reference TEXT NOT NULL,
    approval_json TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS approval_uses (
    use_id TEXT PRIMARY KEY,
    approval_id TEXT NOT NULL REFERENCES approval_records(approval_id),
    used_at TEXT NOT NULL,
    action_digest TEXT NOT NULL,
    result TEXT NOT NULL CHECK(result IN ('consumed', 'rejected')),
    reason TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS remote_export_receipts (
    export_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    sink_id TEXT NOT NULL,
    ledger_tail_hash TEXT NOT NULL,
    database_digest TEXT NOT NULL,
    receipt_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('prepared', 'accepted', 'failed')),
    record_hash TEXT NOT NULL UNIQUE
);

CREATE VIEW IF NOT EXISTS current_facts AS
SELECT f.*
FROM fact_revisions f
JOIN (
    SELECT fact_id, MAX(revision) AS revision
    FROM fact_revisions GROUP BY fact_id
) latest USING(fact_id, revision)
WHERE f.status = 'current';

CREATE VIEW IF NOT EXISTS current_lessons AS
SELECT l.*
FROM lesson_revisions l
JOIN (
    SELECT lesson_id, MAX(revision) AS revision
    FROM lesson_revisions GROUP BY lesson_id
) latest USING(lesson_id, revision);

CREATE VIEW IF NOT EXISTS current_error_reports AS
SELECT e.error_id, e.attempt_id, e.created_at AS observed_at, e.error_class,
       e.expected_json, e.observed_json, r.revision, r.created_at,
       r.diagnosis_status, r.candidate_cause, r.working_solution_attempt_id,
       r.reason, r.record_hash
FROM error_reports e
JOIN error_report_revisions r USING(error_id)
JOIN (
    SELECT error_id, MAX(revision) AS revision
    FROM error_report_revisions GROUP BY error_id
) latest USING(error_id, revision);

CREATE TRIGGER IF NOT EXISTS source_revisions_no_update
BEFORE UPDATE ON source_revisions BEGIN SELECT RAISE(ABORT, 'immutable source revision'); END;
CREATE TRIGGER IF NOT EXISTS source_revisions_no_delete
BEFORE DELETE ON source_revisions BEGIN SELECT RAISE(ABORT, 'immutable source revision'); END;
CREATE TRIGGER IF NOT EXISTS fact_revisions_no_update
BEFORE UPDATE ON fact_revisions BEGIN SELECT RAISE(ABORT, 'immutable fact revision'); END;
CREATE TRIGGER IF NOT EXISTS fact_revisions_no_delete
BEFORE DELETE ON fact_revisions BEGIN SELECT RAISE(ABORT, 'immutable fact revision'); END;
CREATE TRIGGER IF NOT EXISTS command_catalog_revisions_no_update
BEFORE UPDATE ON command_catalog_revisions BEGIN SELECT RAISE(ABORT, 'immutable command catalog revision'); END;
CREATE TRIGGER IF NOT EXISTS command_catalog_revisions_no_delete
BEFORE DELETE ON command_catalog_revisions BEGIN SELECT RAISE(ABORT, 'immutable command catalog revision'); END;
CREATE TRIGGER IF NOT EXISTS command_attempts_no_update
BEFORE UPDATE ON command_attempts BEGIN SELECT RAISE(ABORT, 'immutable command attempt'); END;
CREATE TRIGGER IF NOT EXISTS command_attempts_no_delete
BEFORE DELETE ON command_attempts BEGIN SELECT RAISE(ABORT, 'immutable command attempt'); END;
CREATE TRIGGER IF NOT EXISTS error_reports_no_update
BEFORE UPDATE ON error_reports BEGIN SELECT RAISE(ABORT, 'immutable error report'); END;
CREATE TRIGGER IF NOT EXISTS error_reports_no_delete
BEFORE DELETE ON error_reports BEGIN SELECT RAISE(ABORT, 'immutable error report'); END;
CREATE TRIGGER IF NOT EXISTS error_report_revisions_no_update
BEFORE UPDATE ON error_report_revisions BEGIN SELECT RAISE(ABORT, 'immutable error report revision'); END;
CREATE TRIGGER IF NOT EXISTS error_report_revisions_no_delete
BEFORE DELETE ON error_report_revisions BEGIN SELECT RAISE(ABORT, 'immutable error report revision'); END;
CREATE TRIGGER IF NOT EXISTS lesson_revisions_no_update
BEFORE UPDATE ON lesson_revisions BEGIN SELECT RAISE(ABORT, 'immutable lesson revision'); END;
CREATE TRIGGER IF NOT EXISTS lesson_revisions_no_delete
BEFORE DELETE ON lesson_revisions BEGIN SELECT RAISE(ABORT, 'immutable lesson revision'); END;
CREATE TRIGGER IF NOT EXISTS lesson_evidence_no_update
BEFORE UPDATE ON lesson_evidence BEGIN SELECT RAISE(ABORT, 'immutable lesson evidence'); END;
CREATE TRIGGER IF NOT EXISTS lesson_evidence_no_delete
BEFORE DELETE ON lesson_evidence BEGIN SELECT RAISE(ABORT, 'immutable lesson evidence'); END;
CREATE TRIGGER IF NOT EXISTS decision_records_no_update
BEFORE UPDATE ON decision_records BEGIN SELECT RAISE(ABORT, 'immutable decision record'); END;
CREATE TRIGGER IF NOT EXISTS decision_records_no_delete
BEFORE DELETE ON decision_records BEGIN SELECT RAISE(ABORT, 'immutable decision record'); END;
CREATE TRIGGER IF NOT EXISTS approval_records_no_update
BEFORE UPDATE ON approval_records BEGIN SELECT RAISE(ABORT, 'immutable approval record'); END;
CREATE TRIGGER IF NOT EXISTS approval_records_no_delete
BEFORE DELETE ON approval_records BEGIN SELECT RAISE(ABORT, 'immutable approval record'); END;
CREATE TRIGGER IF NOT EXISTS approval_uses_no_update
BEFORE UPDATE ON approval_uses BEGIN SELECT RAISE(ABORT, 'immutable approval use'); END;
CREATE TRIGGER IF NOT EXISTS approval_uses_no_delete
BEFORE DELETE ON approval_uses BEGIN SELECT RAISE(ABORT, 'immutable approval use'); END;
CREATE TRIGGER IF NOT EXISTS remote_export_receipts_no_update
BEFORE UPDATE ON remote_export_receipts BEGIN SELECT RAISE(ABORT, 'immutable remote export receipt'); END;
CREATE TRIGGER IF NOT EXISTS remote_export_receipts_no_delete
BEFORE DELETE ON remote_export_receipts BEGIN SELECT RAISE(ABORT, 'immutable remote export receipt'); END;

INSERT OR IGNORE INTO metadata(key, value) VALUES ('schema_version', '2');
INSERT OR IGNORE INTO metadata(key, value) VALUES ('encryption_state', 'not-configured');
INSERT OR IGNORE INTO metadata(key, value) VALUES ('machine_scope', 'enrolled-workstation');
