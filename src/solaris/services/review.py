# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import sqlite3
import time


class ReviewService:
    def __init__(self, db, editorial_repo, engine):
        self.db = db
        self.editorial_repo = editorial_repo
        self.engine = engine

    def run_review(self, scope, session_id: str | None, policy_profile: str, limit: int = 100, mode: str = "boundary") -> dict:
        attempts = 4
        delay_seconds = 0.4
        for attempt in range(attempts):
            try:
                with self.db.transaction() as connection:
                    items = self._load_review_items(
                        connection,
                        scope=scope,
                        session_id=session_id,
                        limit=limit,
                        mode=mode,
                    )
                    return self.engine.review(connection, scope=scope, items=items, policy_profile=policy_profile)
            except sqlite3.OperationalError as exc:
                if not self._is_locked_error(exc) or attempt >= attempts - 1:
                    raise
                time.sleep(delay_seconds * (attempt + 1))
        return {"ok": False, "decisions": [], "states": []}

    def get_review_queue(self, scope, session_id: str | None, limit: int = 100) -> dict:
        del session_id
        with self.db.transaction() as connection:
            return {
                "ok": True,
                "items": self.editorial_repo.list_pending(connection, scope_key=scope.key(), limit=limit),
            }

    def apply_decision(self, req) -> dict:
        with self.db.transaction() as connection:
            current = self.editorial_repo.get_state(connection, artifact_type=req.artifact_type, artifact_id=req.artifact_id)
            remember_state = {
                "pin": "remembered",
                "promote": "remembered",
                "retire": "retired",
                "mark_disputed": "disputed",
                "mark_superseded": "superseded",
            }.get(req.action, (current or {}).get("remember_state", "candidate"))
            activation_state = "active" if req.action in {"pin", "promote"} else "suppressed"
            state = self.editorial_repo.upsert_state(
                connection,
                artifact_type=req.artifact_type,
                artifact_id=req.artifact_id,
                scope=req.scope,
                remember_state=remember_state,
                activation_state=activation_state,
                review_status="reviewed",
                pinned=req.action == "pin" or bool((current or {}).get("pinned")),
                policy_profile=req.policy_profile,
                rationale_json=req.rationale,
            )
            decision = self.editorial_repo.insert_decision(
                connection,
                artifact_type=req.artifact_type,
                artifact_id=req.artifact_id,
                action=req.action,
                previous_state=(current or {}).get("remember_state"),
                new_state=remember_state,
                policy_profile=req.policy_profile,
                policy_version=int(state.get("policy_version") or 1),
                scores={},
                rationale=req.rationale,
                supporting_event_ids=[],
                decided_by="manual_override",
            )
            return {"ok": True, "state": state, "decision": decision}

    def _load_review_items(self, connection, *, scope, session_id: str | None, limit: int, mode: str) -> list[dict]:
        normalized_mode = str(mode or "boundary").strip().casefold()
        limit = max(1, int(limit))
        pending = self.editorial_repo.list_pending(connection, scope_key=scope.key(), limit=limit)
        if session_id:
            pending = self._filter_items_for_session(connection, items=pending, session_id=session_id)

        if normalized_mode == "boundary":
            return pending[:limit]

        existing = self.editorial_repo.list_states_by_scope(
            connection,
            scope_key=scope.key(),
            limit=limit,
            exclude_pinned=True,
        )
        reconsider = [
            {
                "review_id": None,
                "artifact_type": state["artifact_type"],
                "artifact_id": state["artifact_id"],
                "scope": state["scope"],
                "trigger": "reconsider",
                "priority": float(state.get("remember_score") or 0.0),
                "status": "pending",
                "not_before": None,
                "created_at": state.get("updated_at"),
                "reviewed_at": None,
            }
            for state in existing
        ]
        if session_id:
            reconsider = self._filter_items_for_session(connection, items=reconsider, session_id=session_id)

        if normalized_mode == "reconsider":
            return reconsider[:limit]

        if normalized_mode == "full":
            seen = {(item["artifact_type"], item["artifact_id"]) for item in pending}
            merged = list(pending)
            for item in reconsider:
                key = (item["artifact_type"], item["artifact_id"])
                if key in seen:
                    continue
                merged.append(item)
                seen.add(key)
                if len(merged) >= limit:
                    break
            return merged

        return pending

    def _filter_items_for_session(self, connection, *, items: list[dict], session_id: str) -> list[dict]:
        matched: list[dict] = []
        for item in items:
            event_ids = self.engine.evidence_repo.event_ids_for_artifact(
                connection,
                artifact_type=item["artifact_type"],
                artifact_id=item["artifact_id"],
            )
            if not event_ids:
                continue
            events = self.engine.events_repo.get_many(connection, event_ids)
            if any(str(event.get("session_id") or "").strip() == session_id for event in events):
                matched.append(item)
        return matched

    @staticmethod
    def _is_locked_error(exc: sqlite3.OperationalError) -> bool:
        text = str(exc or "").strip().casefold()
        return "database is locked" in text or "database table is locked" in text
