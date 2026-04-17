# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sqlite3

from solaris.clock import Clock
from solaris.ids import new_ulid
from solaris.models.session import OpenSessionRequest, SessionRecord
from solaris.storage.db import json_dumps, json_loads


class SessionsRepo:
    def __init__(self, clock: Clock):
        self.clock = clock

    def create(self, connection: sqlite3.Connection, req: OpenSessionRequest) -> SessionRecord:
        session = SessionRecord(
            session_id=new_ulid("sess"),
            parent_session_id=req.parent_session_id,
            kind=req.kind,
            scope=req.scope,
            policy_profile=req.policy_profile,
            policy_context=req.policy_context,
            opened_at=self.clock.iso(),
            closed_at=None,
        )
        connection.execute(
            """
            INSERT INTO sessions(
                session_id, parent_session_id, kind, tenant, namespace, workspace, project,
                scope_key, policy_profile, policy_context_json, opened_at, closed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.session_id,
                session.parent_session_id,
                session.kind,
                session.scope.tenant,
                session.scope.namespace,
                session.scope.workspace,
                session.scope.project,
                session.scope.key(),
                session.policy_profile,
                json_dumps(session.policy_context),
                session.opened_at,
                session.closed_at,
            ),
        )
        return session

    def close(self, connection: sqlite3.Connection, session_id: str) -> dict:
        closed_at = self.clock.iso()
        connection.execute(
            "UPDATE sessions SET closed_at = ? WHERE session_id = ?",
            (closed_at, session_id),
        )
        return {"ok": True, "session_id": session_id, "closed_at": closed_at}

    def get(self, connection: sqlite3.Connection, session_id: str) -> SessionRecord | None:
        row = connection.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return SessionRecord(
            session_id=row["session_id"],
            parent_session_id=row["parent_session_id"],
            kind=row["kind"],
            scope={
                "tenant": row["tenant"],
                "namespace": row["namespace"],
                "workspace": row["workspace"],
                "project": row["project"],
            },
            policy_profile=row["policy_profile"],
            policy_context=json_loads(row["policy_context_json"], {}),
            opened_at=row["opened_at"],
            closed_at=row["closed_at"],
        )

    def preferred_interaction(self, connection: sqlite3.Connection, *, scope_key: str) -> SessionRecord | None:
        row = connection.execute(
            """
            SELECT session_id
            FROM sessions
            WHERE scope_key = ? AND kind = 'interaction' AND closed_at IS NULL
            ORDER BY opened_at DESC
            LIMIT 1
            """,
            (scope_key,),
        ).fetchone()
        if row is None:
            row = connection.execute(
                """
                SELECT session_id
                FROM sessions
                WHERE scope_key = ? AND kind = 'interaction'
                ORDER BY COALESCE(closed_at, opened_at) DESC, opened_at DESC
                LIMIT 1
                """,
                (scope_key,),
            ).fetchone()
        if row is None:
            return None
        return self.get(connection, str(row["session_id"]))

    def continuity_session_id(self, connection: sqlite3.Connection, session_id: str | None) -> str | None:
        if not session_id:
            return None
        record = self.get(connection, session_id)
        if record is None:
            return session_id
        if str(record.kind or "").strip().casefold() == "interaction" and record.parent_session_id:
            return str(record.parent_session_id)
        return session_id
