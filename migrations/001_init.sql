-- SPDX-License-Identifier: MPL-2.0

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    parent_session_id TEXT,
    kind TEXT NOT NULL,
    tenant TEXT NOT NULL,
    namespace TEXT NOT NULL,
    workspace TEXT NOT NULL,
    project TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    policy_profile TEXT NOT NULL,
    policy_context_json TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_scope_opened ON sessions(scope_key, opened_at DESC);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    tenant TEXT NOT NULL,
    namespace TEXT NOT NULL,
    workspace TEXT NOT NULL,
    project TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    session_id TEXT,
    source_app TEXT NOT NULL,
    source_module TEXT NOT NULL,
    actor TEXT NOT NULL,
    kind TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    structured_payload_json TEXT NOT NULL,
    hints_json TEXT NOT NULL,
    scores_json TEXT NOT NULL,
    importance REAL NOT NULL,
    confidence REAL NOT NULL,
    idempotency_key TEXT NOT NULL,
    UNIQUE(scope_key, source_app, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_events_scope_time ON events(scope_key, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_session_time ON events(session_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    tenant TEXT NOT NULL,
    namespace TEXT NOT NULL,
    workspace TEXT NOT NULL,
    project TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    canonical_name_norm TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    aliases_json TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    UNIQUE(scope_key, canonical_name_norm, entity_type)
);

CREATE TABLE IF NOT EXISTS event_entities (
    event_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    PRIMARY KEY(event_id, entity_id)
);

CREATE TABLE IF NOT EXISTS relations (
    relation_id TEXT PRIMARY KEY,
    tenant TEXT NOT NULL,
    namespace TEXT NOT NULL,
    workspace TEXT NOT NULL,
    project TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    src_entity_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    dst_entity_id TEXT NOT NULL,
    confidence REAL NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    derivation_version INTEGER NOT NULL,
    UNIQUE(scope_key, src_entity_id, relation_type, dst_entity_id)
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    tenant TEXT NOT NULL,
    namespace TEXT NOT NULL,
    workspace TEXT NOT NULL,
    project TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    subject_entity_id TEXT,
    subject_entity_id_key TEXT NOT NULL,
    predicate TEXT NOT NULL,
    predicate_norm TEXT NOT NULL,
    object_text TEXT NOT NULL,
    object_text_norm TEXT NOT NULL,
    canonical_claim TEXT NOT NULL,
    canonical_claim_norm TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence_count INTEGER NOT NULL,
    pinned INTEGER NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    derivation_version INTEGER NOT NULL,
    UNIQUE(scope_key, subject_entity_id_key, predicate_norm, object_text_norm)
);

CREATE TABLE IF NOT EXISTS episodes (
    episode_id TEXT PRIMARY KEY,
    session_id TEXT,
    tenant TEXT NOT NULL,
    namespace TEXT NOT NULL,
    workspace TEXT NOT NULL,
    project TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    title TEXT NOT NULL,
    title_norm TEXT NOT NULL,
    status TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT,
    summary_text TEXT NOT NULL,
    dominant_entities_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS episode_events (
    episode_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    PRIMARY KEY(episode_id, event_id)
);

CREATE TABLE IF NOT EXISTS state_leases (
    lease_id TEXT PRIMARY KEY,
    tenant TEXT NOT NULL,
    namespace TEXT NOT NULL,
    workspace TEXT NOT NULL,
    project TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    lease_key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    refreshed_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL,
    UNIQUE(scope_key, lease_key)
);

CREATE TABLE IF NOT EXISTS artifact_evidence (
    artifact_type TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    PRIMARY KEY(artifact_type, artifact_id, event_id)
);
