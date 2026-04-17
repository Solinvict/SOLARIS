-- SPDX-License-Identifier: MPL-2.0

CREATE VIRTUAL TABLE IF NOT EXISTS event_fts USING fts5(
    event_id UNINDEXED,
    scope_key UNINDEXED,
    content
);
