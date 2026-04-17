# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sqlite3

from solaris.ids import new_ulid


def _norm(value: str) -> str:
    return " ".join(str(value or "").split()).strip().casefold()


class RelationsRepo:
    def upsert(
        self,
        connection: sqlite3.Connection,
        *,
        scope,
        src_entity_id: str,
        relation_type: str,
        dst_entity_id: str,
        confidence: float,
        seen_at: str,
        derivation_version: int = 1,
    ) -> dict:
        row = connection.execute(
            """
            SELECT relation_id
            FROM relations
            WHERE scope_key = ? AND src_entity_id = ? AND relation_type = ? AND dst_entity_id = ?
            """,
            (scope.key(), src_entity_id, relation_type, dst_entity_id),
        ).fetchone()
        if row is not None:
            connection.execute(
                """
                UPDATE relations
                SET confidence = MAX(confidence, ?), last_seen = ?, valid_from = COALESCE(valid_from, first_seen, ?)
                WHERE relation_id = ?
                """,
                (float(confidence), seen_at, seen_at, row["relation_id"]),
            )
            return self.get(connection, str(row["relation_id"])) or {}
        relation_id = new_ulid("rel")
        connection.execute(
            """
            INSERT INTO relations(
                relation_id, tenant, namespace, workspace, project, scope_key,
                src_entity_id, relation_type, dst_entity_id, confidence,
                first_seen, last_seen, derivation_version, valid_from, valid_until,
                superseded_at, disputed_at, last_reinforced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relation_id,
                scope.tenant,
                scope.namespace,
                scope.workspace,
                scope.project,
                scope.key(),
                src_entity_id,
                relation_type,
                dst_entity_id,
                float(confidence),
                seen_at,
                seen_at,
                derivation_version,
                seen_at,
                None,
                None,
                None,
                None,
            ),
        )
        return self.get(connection, relation_id) or {}

    def apply_temporal_action(self, connection: sqlite3.Connection, *, relation_id: str, action: str, decided_at: str) -> None:
        if action in {"promote", "reinforce", "pin"}:
            connection.execute(
                """
                UPDATE relations
                SET valid_from = COALESCE(valid_from, first_seen, ?),
                    last_reinforced_at = ?
                WHERE relation_id = ?
                """,
                (decided_at, decided_at, relation_id),
            )
        elif action == "mark_disputed":
            connection.execute(
                "UPDATE relations SET disputed_at = COALESCE(disputed_at, ?) WHERE relation_id = ?",
                (decided_at, relation_id),
            )
        elif action == "mark_superseded":
            connection.execute(
                """
                UPDATE relations
                SET superseded_at = COALESCE(superseded_at, ?),
                    valid_until = COALESCE(valid_until, ?)
                WHERE relation_id = ?
                """,
                (decided_at, decided_at, relation_id),
            )

    def get(self, connection: sqlite3.Connection, relation_id: str) -> dict | None:
        row = connection.execute("SELECT * FROM relations WHERE relation_id = ?", (relation_id,)).fetchone()
        if row is None:
            return None
        return {
            "relation_id": row["relation_id"],
            "scope": {
                "tenant": row["tenant"],
                "namespace": row["namespace"],
                "workspace": row["workspace"],
                "project": row["project"],
            },
            "src_entity_id": row["src_entity_id"],
            "relation_type": row["relation_type"],
            "dst_entity_id": row["dst_entity_id"],
            "confidence": row["confidence"],
            "first_seen": row["first_seen"],
            "last_seen": row["last_seen"],
            "derivation_version": row["derivation_version"],
            "valid_from": row["valid_from"],
            "valid_until": row["valid_until"],
            "superseded_at": row["superseded_at"],
            "disputed_at": row["disputed_at"],
            "last_reinforced_at": row["last_reinforced_at"],
        }

    def neighborhood(self, connection: sqlite3.Connection, *, scope_key: str, entity_id: str) -> list[dict]:
        rows = connection.execute(
            """
            SELECT relation_id FROM relations
            WHERE scope_key = ? AND (src_entity_id = ? OR dst_entity_id = ?)
            ORDER BY last_seen DESC
            """,
            (scope_key, entity_id, entity_id),
        ).fetchall()
        return [self.get(connection, str(row["relation_id"])) for row in rows]

    def list_by_scope(self, connection: sqlite3.Connection, scope_key: str, *, limit: int = 100) -> list[dict]:
        rows = connection.execute(
            "SELECT relation_id FROM relations WHERE scope_key = ? ORDER BY last_seen DESC LIMIT ?",
            (scope_key, max(1, int(limit))),
        ).fetchall()
        return [self.get(connection, str(row["relation_id"])) for row in rows]

    def search_by_scope(
        self,
        connection: sqlite3.Connection,
        *,
        scope_key: str,
        tokens: list[str],
        relation_type: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        clean_tokens = [token for token in (_norm(token) for token in tokens) if token]
        clean_relation_type = _norm(relation_type or "")
        if not clean_tokens and not clean_relation_type:
            return []
        where_parts = ["r.scope_key = ?"]
        params: list[object] = [scope_key]
        if clean_relation_type:
            where_parts.append("r.relation_type = ?")
            params.append(clean_relation_type)
        if clean_tokens:
            token_clauses = []
            for token in clean_tokens:
                token_clauses.append("(src.canonical_name_norm LIKE ? OR dst.canonical_name_norm LIKE ?)")
                params.extend((f"%{token}%", f"%{token}%"))
            where_parts.append("(" + " AND ".join(token_clauses) + ")")
        params.append(max(1, int(limit)))
        rows = connection.execute(
            f"""
            SELECT DISTINCT r.relation_id, r.last_seen AS sort_last_seen
            FROM relations r
            JOIN entities src
              ON src.entity_id = r.src_entity_id
            JOIN entities dst
              ON dst.entity_id = r.dst_entity_id
            WHERE {" AND ".join(where_parts)}
            ORDER BY sort_last_seen DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
        return [self.get(connection, str(row["relation_id"])) for row in rows]

    def list_by_session(self, connection: sqlite3.Connection, *, scope_key: str, session_id: str, limit: int = 100) -> list[dict]:
        rows = connection.execute(
            """
            SELECT DISTINCT r.relation_id, r.last_seen AS sort_last_seen
            FROM relations r
            JOIN artifact_evidence ae
              ON ae.artifact_type = 'relation' AND ae.artifact_id = r.relation_id AND ae.scope_key = r.scope_key
            JOIN events e
              ON e.event_id = ae.event_id
            WHERE r.scope_key = ? AND e.session_id = ?
            ORDER BY sort_last_seen DESC
            LIMIT ?
            """,
            (scope_key, session_id, max(1, int(limit))),
        ).fetchall()
        return [self.get(connection, str(row["relation_id"])) for row in rows]
