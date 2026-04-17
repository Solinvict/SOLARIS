# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.storage.fts import search_event_ids


def lexical_event_search(connection, *, scope_key: str, query: str, limit: int) -> list[str]:
    try:
        return search_event_ids(connection, scope_key=scope_key, query=query, limit=limit)
    except Exception:
        return []
