# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sqlite3

from solaris.clock import Clock
from solaris.ids import new_ulid
from solaris.models.event import MemoryEvent
from solaris.storage.db import json_dumps, json_loads
from solaris.storage.fts import upsert_event_document


class EventsRepo:
    def __init__(self, clock: Clock, *, fts_enabled: bool = True):
        self.clock = clock
        self.fts_enabled = fts_enabled

    def insert(self, connection: sqlite3.Connection, event: MemoryEvent) -> tuple[str, bool]:
        event_id = event.event_id or new_ulid("evt")
        try:
            connection.execute(
                """
                INSERT INTO events(
                    event_id, schema_version, timestamp, ingested_at,
                    tenant, namespace, workspace, project, scope_key,
                    session_id, source_app, source_module, actor, kind,
                    raw_text, normalized_text, structured_payload_json, hints_json,
                    scores_json, importance, confidence, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    event.schema_version,
                    event.timestamp,
                    self.clock.iso(),
                    event.scope.tenant,
                    event.scope.namespace,
                    event.scope.workspace,
                    event.scope.project,
                    event.scope.key(),
                    event.session_id,
                    event.source_app,
                    event.source_module,
                    event.actor,
                    event.kind,
                    event.raw_text,
                    event.normalized_text,
                    json_dumps(event.structured_payload),
                    json_dumps(event.hints.model_dump(mode="json")),
                    json_dumps(event.scores.model_dump(mode="json")),
                    float(event.scores.importance),
                    float(event.scores.confidence),
                    event.idempotency_key,
                ),
            )
            inserted = True
        except sqlite3.IntegrityError:
            row = connection.execute(
                """
                SELECT event_id
                FROM events
                WHERE scope_key = ? AND source_app = ? AND idempotency_key = ?
                """,
                (event.scope.key(), event.source_app, event.idempotency_key),
            ).fetchone()
            event_id = str(row["event_id"]) if row is not None else event_id
            inserted = False

        if inserted and self.fts_enabled:
            upsert_event_document(
                connection,
                event_id=event_id,
                scope_key=event.scope.key(),
                text="\n".join([event.raw_text or "", event.normalized_text or ""]).strip(),
            )
        return event_id, inserted

    def get(self, connection: sqlite3.Connection, event_id: str) -> dict | None:
        row = connection.execute("SELECT * FROM events WHERE event_id = ?", (event_id,)).fetchone()
        return self._row_to_dict(row)

    def get_many(self, connection: sqlite3.Connection, event_ids: list[str]) -> list[dict]:
        if not event_ids:
            return []
        placeholders = ",".join("?" for _ in event_ids)
        rows = connection.execute(
            f"SELECT * FROM events WHERE event_id IN ({placeholders}) ORDER BY timestamp DESC",
            tuple(event_ids),
        ).fetchall()
        return [item for item in (self._row_to_dict(row) for row in rows) if item]

    def list_by_scope(self, connection: sqlite3.Connection, scope_key: str, *, limit: int = 50) -> list[dict]:
        rows = connection.execute(
            "SELECT * FROM events WHERE scope_key = ? ORDER BY timestamp DESC LIMIT ?",
            (scope_key, max(1, int(limit))),
        ).fetchall()
        return [item for item in (self._row_to_dict(row) for row in rows) if item]

    def list_by_session(self, connection: sqlite3.Connection, session_id: str, *, limit: int = 100) -> list[dict]:
        rows = connection.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, max(1, int(limit))),
        ).fetchall()
        return [item for item in (self._row_to_dict(row) for row in rows) if item]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        return {
            "event_id": row["event_id"],
            "schema_version": row["schema_version"],
            "timestamp": row["timestamp"],
            "ingested_at": row["ingested_at"],
            "scope": {
                "tenant": row["tenant"],
                "namespace": row["namespace"],
                "workspace": row["workspace"],
                "project": row["project"],
            },
            "scope_key": row["scope_key"],
            "session_id": row["session_id"],
            "source_app": row["source_app"],
            "source_module": row["source_module"],
            "actor": row["actor"],
            "kind": row["kind"],
            "raw_text": row["raw_text"],
            "normalized_text": row["normalized_text"],
            "structured_payload": json_loads(row["structured_payload_json"], {}),
            "hints": json_loads(row["hints_json"], {}),
            "scores": json_loads(row["scores_json"], {}),
            "importance": row["importance"],
            "confidence": row["confidence"],
            "idempotency_key": row["idempotency_key"],
        }
