# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.session import CloseSessionRequest, OpenSessionRequest


class SessionService:
    def __init__(self, db, sessions_repo, episodes_repo):
        self.db = db
        self.sessions_repo = sessions_repo
        self.episodes_repo = episodes_repo

    def open_session(self, req: OpenSessionRequest):
        with self.db.transaction() as connection:
            return self.sessions_repo.create(connection, req)

    def close_session(self, req: CloseSessionRequest) -> dict:
        with self.db.transaction() as connection:
            result = self.sessions_repo.close(connection, req.session_id)
            result["episodes_closed"] = self.episodes_repo.close_by_session(
                connection,
                session_id=req.session_id,
                closed_at=result["closed_at"],
            )
            return result
