# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sqlite3

from solaris.ids import new_ulid


def _norm(value: str) -> str:
    return " ".join((value or "").split()).strip().casefold()


class ClaimsRepo:
    def upsert(
        self,
        connection: sqlite3.Connection,
        *,
        scope,
        subject_entity_id: str | None,
        predicate: str,
        object_text: str,
        canonical_claim: str,
        confidence: float,
        pinned: bool,
        seen_at: str,
        derivation_version: int = 1,
    ) -> dict:
        subject_key = subject_entity_id or ""
        row = connection.execute(
            """
            SELECT claim_id
            FROM claims
            WHERE scope_key = ? AND subject_entity_id_key = ? AND predicate_norm = ? AND object_text_norm = ?
            """,
            (scope.key(), subject_key, _norm(predicate), _norm(object_text)),
        ).fetchone()
        if row is not None:
            connection.execute(
                """
                UPDATE claims
                SET confidence = MAX(confidence, ?), pinned = MAX(pinned, ?), last_seen = ?,
                    valid_from = COALESCE(valid_from, first_seen, ?)
                WHERE claim_id = ?
                """,
                (float(confidence), int(bool(pinned)), seen_at, seen_at, row["claim_id"]),
            )
            return self.get(connection, str(row["claim_id"])) or {}
        claim_id = new_ulid("clm")
        connection.execute(
            """
            INSERT INTO claims(
                claim_id, tenant, namespace, workspace, project, scope_key, subject_entity_id,
                subject_entity_id_key, predicate, predicate_norm, object_text, object_text_norm,
                canonical_claim, canonical_claim_norm, confidence, evidence_count, pinned,
                first_seen, last_seen, derivation_version, valid_from, valid_until,
                superseded_at, disputed_at, last_reinforced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                claim_id,
                scope.tenant,
                scope.namespace,
                scope.workspace,
                scope.project,
                scope.key(),
                subject_entity_id,
                subject_key,
                predicate,
                _norm(predicate),
                object_text,
                _norm(object_text),
                canonical_claim,
                _norm(canonical_claim),
                float(confidence),
                1,
                int(bool(pinned)),
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
        return self.get(connection, claim_id) or {}

    def apply_temporal_action(self, connection: sqlite3.Connection, *, claim_id: str, action: str, decided_at: str) -> None:
        if action in {"promote", "reinforce", "pin"}:
            connection.execute(
                """
                UPDATE claims
                SET valid_from = COALESCE(valid_from, first_seen, ?),
                    last_reinforced_at = ?
                WHERE claim_id = ?
                """,
                (decided_at, decided_at, claim_id),
            )
        elif action == "mark_disputed":
            connection.execute(
                "UPDATE claims SET disputed_at = COALESCE(disputed_at, ?) WHERE claim_id = ?",
                (decided_at, claim_id),
            )
        elif action == "mark_superseded":
            connection.execute(
                """
                UPDATE claims
                SET superseded_at = COALESCE(superseded_at, ?),
                    valid_until = COALESCE(valid_until, ?)
                WHERE claim_id = ?
                """,
                (decided_at, decided_at, claim_id),
            )

    def refresh_evidence_count(self, connection: sqlite3.Connection, claim_id: str) -> None:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM artifact_evidence
            WHERE artifact_type = 'claim' AND artifact_id = ?
            """,
            (claim_id,),
        ).fetchone()
        connection.execute(
            "UPDATE claims SET evidence_count = ? WHERE claim_id = ?",
            (max(1, int(row["count"]) if row is not None else 0), claim_id),
        )

    def get(self, connection: sqlite3.Connection, claim_id: str) -> dict | None:
        row = connection.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
        if row is None:
            return None
        return {
            "claim_id": row["claim_id"],
            "scope": {
                "tenant": row["tenant"],
                "namespace": row["namespace"],
                "workspace": row["workspace"],
                "project": row["project"],
            },
            "subject_entity_id": row["subject_entity_id"],
            "predicate": row["predicate"],
            "object_text": row["object_text"],
            "canonical_claim": row["canonical_claim"],
            "confidence": row["confidence"],
            "evidence_count": row["evidence_count"],
            "pinned": bool(row["pinned"]),
            "first_seen": row["first_seen"],
            "last_seen": row["last_seen"],
            "derivation_version": row["derivation_version"],
            "valid_from": row["valid_from"],
            "valid_until": row["valid_until"],
            "superseded_at": row["superseded_at"],
            "disputed_at": row["disputed_at"],
            "last_reinforced_at": row["last_reinforced_at"],
        }

    def list_by_scope(self, connection: sqlite3.Connection, scope_key: str, *, limit: int = 100) -> list[dict]:
        rows = connection.execute(
            "SELECT claim_id FROM claims WHERE scope_key = ? ORDER BY last_seen DESC LIMIT ?",
            (scope_key, max(1, int(limit))),
        ).fetchall()
        return [self.get(connection, str(row["claim_id"])) for row in rows]

    def list_by_session(self, connection: sqlite3.Connection, *, scope_key: str, session_id: str, limit: int = 100) -> list[dict]:
        rows = connection.execute(
            """
            SELECT DISTINCT c.claim_id, c.last_seen AS sort_last_seen
            FROM claims c
            JOIN artifact_evidence ae
              ON ae.artifact_type = 'claim' AND ae.artifact_id = c.claim_id AND ae.scope_key = c.scope_key
            JOIN events e
              ON e.event_id = ae.event_id
            WHERE c.scope_key = ? AND e.session_id = ?
            ORDER BY sort_last_seen DESC
            LIMIT ?
            """,
            (scope_key, session_id, max(1, int(limit))),
        ).fetchall()
        return [self.get(connection, str(row["claim_id"])) for row in rows]

    def list_by_subject_entity(
        self,
        connection: sqlite3.Connection,
        *,
        scope_key: str,
        subject_entity_id: str,
        limit: int = 100,
    ) -> list[dict]:
        rows = connection.execute(
            """
            SELECT claim_id
            FROM claims
            WHERE scope_key = ? AND subject_entity_id = ?
            ORDER BY last_seen DESC
            LIMIT ?
            """,
            (scope_key, subject_entity_id, max(1, int(limit))),
        ).fetchall()
        return [self.get(connection, str(row["claim_id"])) for row in rows]
