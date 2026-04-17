# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sqlite3
from datetime import timedelta

from solaris.clock import Clock
from solaris.ids import new_ulid
from solaris.storage.db import json_dumps, json_loads


class StateLeasesRepo:
    def __init__(self, clock: Clock):
        self.clock = clock

    def upsert(self, connection: sqlite3.Connection, *, scope, lease_key: str, value_json: dict, ttl_seconds: int) -> dict:
        now = self.clock.now()
        now_iso = now.isoformat()
        expires_at = (now + timedelta(seconds=max(1, int(ttl_seconds)))).isoformat()
        row = connection.execute(
            "SELECT lease_id FROM state_leases WHERE scope_key = ? AND lease_key = ?",
            (scope.key(), lease_key),
        ).fetchone()
        if row is not None:
            connection.execute(
                """
                UPDATE state_leases
                SET value_json = ?, refreshed_at = ?, expires_at = ?, status = 'active'
                WHERE lease_id = ?
                """,
                (json_dumps(value_json), now_iso, expires_at, row["lease_id"]),
            )
            return self.get(connection, str(row["lease_id"])) or {}
        lease_id = new_ulid("lease")
        connection.execute(
            """
            INSERT INTO state_leases(
                lease_id, tenant, namespace, workspace, project, scope_key, lease_key,
                value_json, issued_at, refreshed_at, expires_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (
                lease_id,
                scope.tenant,
                scope.namespace,
                scope.workspace,
                scope.project,
                scope.key(),
                lease_key,
                json_dumps(value_json),
                now_iso,
                now_iso,
                expires_at,
            ),
        )
        return self.get(connection, lease_id) or {}

    def expire(self, connection: sqlite3.Connection) -> int:
        rowcount = connection.execute(
            "UPDATE state_leases SET status = 'expired' WHERE status = 'active' AND expires_at <= ?",
            (self.clock.iso(),),
        ).rowcount
        return int(rowcount or 0)

    def get(self, connection: sqlite3.Connection, lease_id: str) -> dict | None:
        row = connection.execute("SELECT * FROM state_leases WHERE lease_id = ?", (lease_id,)).fetchone()
        if row is None:
            return None
        return {
            "lease_id": row["lease_id"],
            "scope": {
                "tenant": row["tenant"],
                "namespace": row["namespace"],
                "workspace": row["workspace"],
                "project": row["project"],
            },
            "lease_key": row["lease_key"],
            "value_json": json_loads(row["value_json"], {}),
            "issued_at": row["issued_at"],
            "refreshed_at": row["refreshed_at"],
            "expires_at": row["expires_at"],
            "status": row["status"],
        }

    def list_active(self, connection: sqlite3.Connection, scope_key: str, *, limit: int = 20) -> list[dict]:
        self.expire(connection)
        rows = connection.execute(
            """
            SELECT lease_id
            FROM state_leases
            WHERE scope_key = ? AND status = 'active'
            ORDER BY refreshed_at DESC
            LIMIT ?
            """,
            (scope_key, max(1, int(limit))),
        ).fetchall()
        return [self.get(connection, str(row["lease_id"])) for row in rows]
