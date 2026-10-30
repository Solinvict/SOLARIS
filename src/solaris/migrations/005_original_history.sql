CREATE TABLE IF NOT EXISTS original_history(
 event_id TEXT PRIMARY KEY REFERENCES events(event_id),
 scope_key TEXT NOT NULL, investigation_id TEXT NOT NULL, sequence INTEGER NOT NULL,
 envelope_json TEXT NOT NULL, envelope_sha256 TEXT NOT NULL,
 UNIQUE(scope_key, investigation_id, sequence)
);
CREATE INDEX IF NOT EXISTS original_history_trace ON original_history(scope_key, investigation_id, sequence);
CREATE TABLE IF NOT EXISTS original_artifacts(sha256 TEXT PRIMARY KEY, content BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS original_artifact_links(event_id TEXT NOT NULL REFERENCES original_history(event_id),sha256 TEXT NOT NULL REFERENCES original_artifacts(sha256),PRIMARY KEY(event_id,sha256));
CREATE TABLE IF NOT EXISTS original_projection_attempts(id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL REFERENCES original_history(event_id),status TEXT NOT NULL,error TEXT,timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
