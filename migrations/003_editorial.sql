-- SPDX-License-Identifier: MPL-2.0

CREATE TABLE IF NOT EXISTS artifact_editorial_state (
    artifact_type TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    tenant TEXT NOT NULL,
    namespace TEXT NOT NULL,
    workspace TEXT NOT NULL,
    project TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    remember_state TEXT NOT NULL,
    activation_state TEXT NOT NULL,
    review_status TEXT NOT NULL,
    remember_score REAL NOT NULL,
    influence_score REAL NOT NULL,
    pinned INTEGER NOT NULL,
    protected INTEGER NOT NULL,
    last_reviewed_at TEXT,
    next_review_at TEXT,
    policy_profile TEXT NOT NULL,
    policy_version INTEGER NOT NULL,
    rationale_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(artifact_type, artifact_id)
);

CREATE TABLE IF NOT EXISTS editorial_decisions (
    decision_id TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    action TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT,
    policy_profile TEXT NOT NULL,
    policy_version INTEGER NOT NULL,
    scores_json TEXT NOT NULL,
    rationale_json TEXT NOT NULL,
    supporting_event_ids_json TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    decided_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_queue (
    review_id TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    tenant TEXT NOT NULL,
    namespace TEXT NOT NULL,
    workspace TEXT NOT NULL,
    project TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    trigger TEXT NOT NULL,
    priority REAL NOT NULL,
    status TEXT NOT NULL,
    not_before TEXT,
    created_at TEXT NOT NULL,
    reviewed_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_review_queue_pending_unique
    ON review_queue(scope_key, artifact_type, artifact_id, trigger)
    WHERE status = 'pending';
