# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sqlite3

from solaris.ids import new_ulid
from solaris.storage.db import json_dumps, json_loads


def _norm(value: str) -> str:
    return " ".join((value or "").split()).strip().casefold()


class EntitiesRepo:
    @staticmethod
    def _mention_count(connection: sqlite3.Connection, entity_id: str) -> int:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM event_entities WHERE entity_id = ?",
            (entity_id,),
        ).fetchone()
        return int((row["count"] if row is not None else 0) or 0)

    def upsert(
        self,
        connection: sqlite3.Connection,
        *,
        scope,
        canonical_name: str,
        entity_type: str,
        aliases: list[str],
        seen_at: str,
    ) -> dict:
        row = connection.execute(
            """
            SELECT * FROM entities
            WHERE scope_key = ? AND canonical_name_norm = ? AND entity_type = ?
            """,
            (scope.key(), _norm(canonical_name), entity_type),
        ).fetchone()
        if row is not None:
            existing_aliases = set(json_loads(row["aliases_json"], []))
            merged_aliases = sorted(existing_aliases | set(alias for alias in aliases if alias))
            connection.execute(
                "UPDATE entities SET aliases_json = ?, last_seen = ? WHERE entity_id = ?",
                (json_dumps(merged_aliases), seen_at, row["entity_id"]),
            )
            return self.get(connection, str(row["entity_id"])) or {}
        entity_id = new_ulid("ent")
        connection.execute(
            """
            INSERT INTO entities(
                entity_id, tenant, namespace, workspace, project, scope_key,
                canonical_name, canonical_name_norm, entity_type, aliases_json,
                first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                scope.tenant,
                scope.namespace,
                scope.workspace,
                scope.project,
                scope.key(),
                canonical_name,
                _norm(canonical_name),
                entity_type,
                json_dumps(sorted(set(alias for alias in aliases if alias))),
                seen_at,
                seen_at,
            ),
        )
        return self.get(connection, entity_id) or {}

    def get(self, connection: sqlite3.Connection, entity_id: str) -> dict | None:
        row = connection.execute("SELECT * FROM entities WHERE entity_id = ?", (entity_id,)).fetchone()
        if row is None:
            return None
        return {
            "entity_id": row["entity_id"],
            "scope": {
                "tenant": row["tenant"],
                "namespace": row["namespace"],
                "workspace": row["workspace"],
                "project": row["project"],
            },
            "canonical_name": row["canonical_name"],
            "entity_type": row["entity_type"],
            "aliases": json_loads(row["aliases_json"], []),
            "first_seen": row["first_seen"],
            "last_seen": row["last_seen"],
            "mention_count": self._mention_count(connection, str(row["entity_id"])),
        }

    def resolve(self, connection: sqlite3.Connection, *, scope_key: str, canonical_name: str) -> dict | None:
        row = connection.execute(
            """
            SELECT * FROM entities
            WHERE scope_key = ? AND canonical_name_norm = ?
            """,
            (scope_key, _norm(canonical_name)),
        ).fetchone()
        if row is None:
            return None
        return self.get(connection, str(row["entity_id"]))

    def list_by_scope(self, connection: sqlite3.Connection, scope_key: str, *, limit: int = 100) -> list[dict]:
        rows = connection.execute(
            "SELECT entity_id FROM entities WHERE scope_key = ? ORDER BY last_seen DESC LIMIT ?",
            (scope_key, max(1, int(limit))),
        ).fetchall()
        return [self.get(connection, str(row["entity_id"])) for row in rows]

    def search_by_scope(self, connection: sqlite3.Connection, *, scope_key: str, tokens: list[str], limit: int = 100) -> list[dict]:
        clean_tokens = [token for token in (_norm(token) for token in tokens) if token]
        if not clean_tokens:
            return []
        where = " OR ".join("canonical_name_norm LIKE ?" for _ in clean_tokens)
        params: list[object] = [scope_key]
        params.extend(f"%{token}%" for token in clean_tokens)
        params.append(max(1, int(limit)))
        rows = connection.execute(
            f"""
            SELECT entity_id
            FROM entities
            WHERE scope_key = ? AND ({where})
            ORDER BY last_seen DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
        return [self.get(connection, str(row["entity_id"])) for row in rows]

    def link_event(self, connection: sqlite3.Connection, *, event_id: str, entity_id: str) -> None:
        connection.execute(
            "INSERT OR IGNORE INTO event_entities(event_id, entity_id) VALUES (?, ?)",
            (event_id, entity_id),
        )

    def event_ids_for_entity(self, connection: sqlite3.Connection, *, entity_id: str) -> list[str]:
        rows = connection.execute(
            """
            SELECT event_id
            FROM event_entities
            WHERE entity_id = ?
            ORDER BY event_id
            """,
            (entity_id,),
        ).fetchall()
        return [str(row["event_id"]) for row in rows]

    def list_by_session(self, connection: sqlite3.Connection, *, scope_key: str, session_id: str, limit: int = 100) -> list[dict]:
        rows = connection.execute(
            """
            SELECT DISTINCT ent.entity_id, ent.last_seen AS sort_last_seen
            FROM entities ent
            JOIN event_entities ee
              ON ee.entity_id = ent.entity_id
            JOIN events e
              ON e.event_id = ee.event_id
            WHERE ent.scope_key = ? AND e.session_id = ?
            ORDER BY sort_last_seen DESC
            LIMIT ?
            """,
            (scope_key, session_id, max(1, int(limit))),
        ).fetchall()
        return [self.get(connection, str(row["entity_id"])) for row in rows]
