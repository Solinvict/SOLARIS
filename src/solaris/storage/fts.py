# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import re
import sqlite3


def upsert_event_document(connection: sqlite3.Connection, *, event_id: str, scope_key: str, text: str) -> None:
    connection.execute("DELETE FROM event_fts WHERE event_id = ?", (event_id,))
    connection.execute(
        "INSERT INTO event_fts(event_id, scope_key, content) VALUES (?, ?, ?)",
        (event_id, scope_key, text or ""),
    )


def search_event_ids(connection: sqlite3.Connection, *, scope_key: str, query: str, limit: int) -> list[str]:
    tokens = [token for token in re.findall(r"[A-Za-z0-9_']+", query or "") if token]
    if not tokens:
        return []
    rows = connection.execute(
        """
        SELECT event_id
        FROM event_fts
        WHERE scope_key = ? AND event_fts MATCH ?
        LIMIT ?
        """,
        (scope_key, " ".join(tokens), max(1, int(limit))),
    ).fetchall()
    return [str(row["event_id"]) for row in rows]
