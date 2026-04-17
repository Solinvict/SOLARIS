# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sqlite3

from solaris.clock import Clock
from solaris.ids import new_ulid
from solaris.models.common import ActivationState, RememberState, ReviewStatus
from solaris.storage.db import json_dumps, json_loads


class EditorialRepo:
    def __init__(self, clock: Clock):
        self.clock = clock

    def get_state(self, connection: sqlite3.Connection, *, artifact_type: str, artifact_id: str) -> dict | None:
        row = connection.execute(
            "SELECT * FROM artifact_editorial_state WHERE artifact_type = ? AND artifact_id = ?",
            (artifact_type, artifact_id),
        ).fetchone()
        return self._state_row_to_dict(row)

    def upsert_state(
        self,
        connection: sqlite3.Connection,
        *,
        artifact_type: str,
        artifact_id: str,
        scope,
        remember_state: str = RememberState.candidate.value,
        activation_state: str = ActivationState.suppressed.value,
        review_status: str = ReviewStatus.pending.value,
        remember_score: float = 0.0,
        influence_score: float = 0.0,
        pinned: bool = False,
        protected: bool = False,
        last_reviewed_at: str | None = None,
        next_review_at: str | None = None,
        policy_profile: str = "default_v1",
        policy_version: int = 1,
        rationale_json: dict | None = None,
    ) -> dict:
        existing = self.get_state(connection, artifact_type=artifact_type, artifact_id=artifact_id)
        updated_at = self.clock.iso()
        if existing is None:
            connection.execute(
                """
                INSERT INTO artifact_editorial_state(
                    artifact_type, artifact_id, tenant, namespace, workspace, project, scope_key,
                    remember_state, activation_state, review_status, remember_score, influence_score,
                    pinned, protected, last_reviewed_at, next_review_at, policy_profile, policy_version,
                    rationale_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_type,
                    artifact_id,
                    scope.tenant,
                    scope.namespace,
                    scope.workspace,
                    scope.project,
                    scope.key(),
                    remember_state,
                    activation_state,
                    review_status,
                    float(remember_score),
                    float(influence_score),
                    int(bool(pinned)),
                    int(bool(protected)),
                    last_reviewed_at,
                    next_review_at,
                    policy_profile,
                    int(policy_version),
                    json_dumps(rationale_json or {}),
                    updated_at,
                ),
            )
        else:
            connection.execute(
                """
                UPDATE artifact_editorial_state
                SET remember_state = ?, activation_state = ?, review_status = ?, remember_score = ?,
                    influence_score = ?, pinned = ?, protected = ?, last_reviewed_at = ?, next_review_at = ?,
                    policy_profile = ?, policy_version = ?, rationale_json = ?, updated_at = ?
                WHERE artifact_type = ? AND artifact_id = ?
                """,
                (
                    remember_state,
                    activation_state,
                    review_status,
                    float(remember_score),
                    float(influence_score),
                    int(bool(pinned)),
                    int(bool(protected)),
                    last_reviewed_at,
                    next_review_at,
                    policy_profile,
                    int(policy_version),
                    json_dumps(rationale_json or {}),
                    updated_at,
                    artifact_type,
                    artifact_id,
                ),
            )
        return self.get_state(connection, artifact_type=artifact_type, artifact_id=artifact_id) or {}

    def enqueue_review(self, connection: sqlite3.Connection, *, artifact_type: str, artifact_id: str, scope, trigger: str, priority: float = 0.5, not_before: str | None = None) -> str:
        review_id = new_ulid("rev")
        try:
            connection.execute(
                """
                INSERT INTO review_queue(
                    review_id, artifact_type, artifact_id, tenant, namespace, workspace, project,
                    scope_key, trigger, priority, status, not_before, created_at, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, NULL)
                """,
                (
                    review_id,
                    artifact_type,
                    artifact_id,
                    scope.tenant,
                    scope.namespace,
                    scope.workspace,
                    scope.project,
                    scope.key(),
                    trigger,
                    float(priority),
                    not_before,
                    self.clock.iso(),
                ),
            )
        except sqlite3.IntegrityError:
            row = connection.execute(
                """
                SELECT review_id
                FROM review_queue
                WHERE scope_key = ? AND artifact_type = ? AND artifact_id = ? AND trigger = ? AND status = 'pending'
                """,
                (scope.key(), artifact_type, artifact_id, trigger),
            ).fetchone()
            return str(row["review_id"]) if row is not None else review_id
        return review_id

    def list_pending(self, connection: sqlite3.Connection, *, scope_key: str, limit: int = 100) -> list[dict]:
        rows = connection.execute(
            """
            SELECT * FROM review_queue
            WHERE scope_key = ? AND status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
            """,
            (scope_key, max(1, int(limit))),
        ).fetchall()
        return [self._queue_row_to_dict(row) for row in rows]

    def list_states_by_scope(
        self,
        connection: sqlite3.Connection,
        *,
        scope_key: str,
        limit: int = 100,
        exclude_pinned: bool = False,
    ) -> list[dict]:
        query = """
            SELECT *
            FROM artifact_editorial_state
            WHERE scope_key = ?
        """
        params: list[object] = [scope_key]
        if exclude_pinned:
            query += " AND pinned = 0"
        query += """
            ORDER BY
                CASE remember_state
                    WHEN 'remembered' THEN 0
                    WHEN 'candidate' THEN 1
                    WHEN 'disputed' THEN 2
                    WHEN 'superseded' THEN 3
                    WHEN 'retired' THEN 4
                    ELSE 5
                END,
                updated_at DESC
            LIMIT ?
        """
        params.append(max(1, int(limit)))
        rows = connection.execute(query, tuple(params)).fetchall()
        return [self._state_row_to_dict(row) for row in rows if row is not None]

    def mark_reviewed(self, connection: sqlite3.Connection, review_id: str) -> None:
        connection.execute(
            "UPDATE review_queue SET status = 'reviewed', reviewed_at = ? WHERE review_id = ?",
            (self.clock.iso(), review_id),
        )

    def insert_decision(
        self,
        connection: sqlite3.Connection,
        *,
        artifact_type: str,
        artifact_id: str,
        action: str,
        previous_state: str | None,
        new_state: str | None,
        policy_profile: str,
        policy_version: int,
        scores: dict,
        rationale: dict,
        supporting_event_ids: list[str],
        decided_by: str,
    ) -> dict:
        decision_id = new_ulid("ed")
        decided_at = self.clock.iso()
        connection.execute(
            """
            INSERT INTO editorial_decisions(
                decision_id, artifact_type, artifact_id, action, previous_state, new_state,
                policy_profile, policy_version, scores_json, rationale_json,
                supporting_event_ids_json, decided_by, decided_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                artifact_type,
                artifact_id,
                action,
                previous_state,
                new_state,
                policy_profile,
                int(policy_version),
                json_dumps(scores),
                json_dumps(rationale),
                json_dumps(supporting_event_ids),
                decided_by,
                decided_at,
            ),
        )
        return {
            "decision_id": decision_id,
            "artifact_type": artifact_type,
            "artifact_id": artifact_id,
            "action": action,
            "previous_state": previous_state,
            "new_state": new_state,
            "policy_profile": policy_profile,
            "policy_version": int(policy_version),
            "scores": scores,
            "rationale": rationale,
            "supporting_event_ids": supporting_event_ids,
            "decided_by": decided_by,
            "decided_at": decided_at,
        }

    def list_decisions(self, connection: sqlite3.Connection, *, artifact_type: str, artifact_id: str) -> list[dict]:
        rows = connection.execute(
            """
            SELECT * FROM editorial_decisions
            WHERE artifact_type = ? AND artifact_id = ?
            ORDER BY decided_at DESC
            """,
            (artifact_type, artifact_id),
        ).fetchall()
        return [
            {
                "decision_id": row["decision_id"],
                "artifact_type": row["artifact_type"],
                "artifact_id": row["artifact_id"],
                "action": row["action"],
                "previous_state": row["previous_state"],
                "new_state": row["new_state"],
                "policy_profile": row["policy_profile"],
                "policy_version": row["policy_version"],
                "scores": json_loads(row["scores_json"], {}),
                "rationale": json_loads(row["rationale_json"], {}),
                "supporting_event_ids": json_loads(row["supporting_event_ids_json"], []),
                "decided_by": row["decided_by"],
                "decided_at": row["decided_at"],
            }
            for row in rows
        ]

    @staticmethod
    def _queue_row_to_dict(row: sqlite3.Row) -> dict:
        return {
            "review_id": row["review_id"],
            "artifact_type": row["artifact_type"],
            "artifact_id": row["artifact_id"],
            "scope": {
                "tenant": row["tenant"],
                "namespace": row["namespace"],
                "workspace": row["workspace"],
                "project": row["project"],
            },
            "trigger": row["trigger"],
            "priority": row["priority"],
            "status": row["status"],
            "not_before": row["not_before"],
            "created_at": row["created_at"],
            "reviewed_at": row["reviewed_at"],
        }

    @staticmethod
    def _state_row_to_dict(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        return {
            "artifact_type": row["artifact_type"],
            "artifact_id": row["artifact_id"],
            "scope": {
                "tenant": row["tenant"],
                "namespace": row["namespace"],
                "workspace": row["workspace"],
                "project": row["project"],
            },
            "remember_state": row["remember_state"],
            "activation_state": row["activation_state"],
            "review_status": row["review_status"],
            "remember_score": row["remember_score"],
            "influence_score": row["influence_score"],
            "pinned": bool(row["pinned"]),
            "protected": bool(row["protected"]),
            "last_reviewed_at": row["last_reviewed_at"],
            "next_review_at": row["next_review_at"],
            "policy_profile": row["policy_profile"],
            "policy_version": row["policy_version"],
            "rationale_json": json_loads(row["rationale_json"], {}),
            "updated_at": row["updated_at"],
        }
