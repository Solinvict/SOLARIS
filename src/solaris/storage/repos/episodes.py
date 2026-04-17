# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from solaris.ids import new_ulid
from solaris.storage.db import json_dumps, json_loads


def _norm(value: str) -> str:
    return " ".join((value or "").split()).strip().casefold()


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class EpisodesRepo:
    def find_recent_open(
        self,
        connection: sqlite3.Connection,
        *,
        session_id: str | None,
        scope_key: str,
        title: str,
        event_timestamp: str,
        gap_minutes: int = 20,
    ) -> dict | None:
        if not session_id:
            return None
        threshold = (_parse_iso(event_timestamp) - timedelta(minutes=gap_minutes)).isoformat()
        row = connection.execute(
            """
            SELECT episode_id
            FROM episodes
            WHERE session_id = ? AND scope_key = ? AND status = 'open' AND title_norm = ? AND updated_at >= ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (session_id, scope_key, _norm(title), threshold),
        ).fetchone()
        if row is None:
            return None
        return self.get(connection, str(row["episode_id"]))

    def create(
        self,
        connection: sqlite3.Connection,
        *,
        session_id: str | None,
        scope,
        title: str,
        start_at: str,
        dominant_entities: list[str],
        confidence: float,
    ) -> dict:
        episode_id = new_ulid("ep")
        connection.execute(
            """
            INSERT INTO episodes(
                episode_id, session_id, tenant, namespace, workspace, project, scope_key,
                title, title_norm, status, start_at, end_at, summary_text, dominant_entities_json,
                confidence, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, NULL, '', ?, ?, ?)
            """,
            (
                episode_id,
                session_id,
                scope.tenant,
                scope.namespace,
                scope.workspace,
                scope.project,
                scope.key(),
                title,
                _norm(title),
                start_at,
                json_dumps(dominant_entities),
                float(confidence),
                start_at,
            ),
        )
        return self.get(connection, episode_id) or {}

    def update(self, connection: sqlite3.Connection, *, episode_id: str, updated_at: str, dominant_entities: list[str], confidence: float) -> None:
        connection.execute(
            """
            UPDATE episodes
            SET dominant_entities_json = ?, confidence = MAX(confidence, ?), updated_at = ?
            WHERE episode_id = ?
            """,
            (json_dumps(dominant_entities), float(confidence), updated_at, episode_id),
        )

    def link_event(self, connection: sqlite3.Connection, *, episode_id: str, event_id: str) -> None:
        connection.execute(
            "INSERT OR IGNORE INTO episode_events(episode_id, event_id) VALUES (?, ?)",
            (episode_id, event_id),
        )

    def close_by_session(self, connection: sqlite3.Connection, *, session_id: str, closed_at: str) -> int:
        rowcount = connection.execute(
            """
            UPDATE episodes
            SET status = 'closed', end_at = ?, updated_at = ?
            WHERE session_id = ? AND status = 'open'
            """,
            (closed_at, closed_at, session_id),
        ).rowcount
        return int(rowcount or 0)

    def get(self, connection: sqlite3.Connection, episode_id: str) -> dict | None:
        row = connection.execute("SELECT * FROM episodes WHERE episode_id = ?", (episode_id,)).fetchone()
        if row is None:
            return None
        return {
            "episode_id": row["episode_id"],
            "scope": {
                "tenant": row["tenant"],
                "namespace": row["namespace"],
                "workspace": row["workspace"],
                "project": row["project"],
            },
            "session_id": row["session_id"],
            "title": row["title"],
            "status": row["status"],
            "start_at": row["start_at"],
            "end_at": row["end_at"],
            "summary_text": row["summary_text"],
            "dominant_entities": json_loads(row["dominant_entities_json"], []),
            "confidence": row["confidence"],
            "updated_at": row["updated_at"],
        }

    def get_event_ids(self, connection: sqlite3.Connection, episode_id: str) -> list[str]:
        rows = connection.execute(
            "SELECT event_id FROM episode_events WHERE episode_id = ?",
            (episode_id,),
        ).fetchall()
        return [str(row["event_id"]) for row in rows]

    def list_by_scope(self, connection: sqlite3.Connection, scope_key: str, *, limit: int = 100) -> list[dict]:
        rows = connection.execute(
            "SELECT episode_id FROM episodes WHERE scope_key = ? ORDER BY updated_at DESC LIMIT ?",
            (scope_key, max(1, int(limit))),
        ).fetchall()
        return [self.get(connection, str(row["episode_id"])) for row in rows]

    def list_by_session(self, connection: sqlite3.Connection, *, session_id: str, limit: int = 100) -> list[dict]:
        rows = connection.execute(
            "SELECT episode_id FROM episodes WHERE session_id = ? ORDER BY updated_at DESC LIMIT ?",
            (session_id, max(1, int(limit))),
        ).fetchall()
        return [self.get(connection, str(row["episode_id"])) for row in rows]

    def list_by_event_ids(
        self,
        connection: sqlite3.Connection,
        *,
        scope_key: str,
        event_ids: list[str],
        limit: int = 100,
    ) -> list[dict]:
        if not event_ids:
            return []
        placeholders = ",".join("?" for _ in event_ids)
        rows = connection.execute(
            f"""
            SELECT DISTINCT ep.episode_id, ep.updated_at AS sort_updated_at
            FROM episodes ep
            JOIN episode_events ee
              ON ee.episode_id = ep.episode_id
            WHERE ep.scope_key = ? AND ee.event_id IN ({placeholders})
            ORDER BY sort_updated_at DESC
            LIMIT ?
            """,
            tuple([scope_key, *event_ids, max(1, int(limit))]),
        ).fetchall()
        return [self.get(connection, str(row["episode_id"])) for row in rows]
