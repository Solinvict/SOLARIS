# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations


class ReviewQueue:
    def __init__(self, editorial_repo):
        self.editorial_repo = editorial_repo

    def pending(self, connection, *, scope_key: str, limit: int) -> list[dict]:
        return self.editorial_repo.list_pending(connection, scope_key=scope_key, limit=limit)
