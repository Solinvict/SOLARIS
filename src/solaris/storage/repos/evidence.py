# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sqlite3


class EvidenceRepo:
    def link(self, connection: sqlite3.Connection, *, artifact_type: str, artifact_id: str, scope_key: str, event_ids: list[str]) -> int:
        inserted = 0
        for event_id in event_ids:
            rowcount = connection.execute(
                """
                INSERT OR IGNORE INTO artifact_evidence(artifact_type, artifact_id, event_id, scope_key)
                VALUES (?, ?, ?, ?)
                """,
                (artifact_type, artifact_id, event_id, scope_key),
            ).rowcount
            inserted += int(rowcount or 0)
        return inserted

    def event_ids_for_artifact(self, connection: sqlite3.Connection, *, artifact_type: str, artifact_id: str) -> list[str]:
        rows = connection.execute(
            """
            SELECT event_id
            FROM artifact_evidence
            WHERE artifact_type = ? AND artifact_id = ?
            ORDER BY event_id
            """,
            (artifact_type, artifact_id),
        ).fetchall()
        return [str(row["event_id"]) for row in rows]

    def artifacts_for_event_ids(
        self,
        connection: sqlite3.Connection,
        *,
        event_ids: list[str],
        artifact_types: list[str] | None = None,
    ) -> list[dict]:
        if not event_ids:
            return []
        event_placeholders = ",".join("?" for _ in event_ids)
        params: list[object] = list(event_ids)
        query = f"""
            SELECT DISTINCT artifact_type, artifact_id
            FROM artifact_evidence
            WHERE event_id IN ({event_placeholders})
        """
        if artifact_types:
            artifact_placeholders = ",".join("?" for _ in artifact_types)
            query += f" AND artifact_type IN ({artifact_placeholders})"
            params.extend(artifact_types)
        query += " ORDER BY artifact_type, artifact_id"
        rows = connection.execute(query, tuple(params)).fetchall()
        return [
            {
                "artifact_type": str(row["artifact_type"]),
                "artifact_id": str(row["artifact_id"]),
            }
            for row in rows
        ]
