# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.retrieval.explain import explain_artifact


class ExplainService:
    def __init__(self, db, claims_repo, relations_repo, episodes_repo, editorial_repo, evidence_repo, events_repo):
        self.db = db
        self.claims_repo = claims_repo
        self.relations_repo = relations_repo
        self.episodes_repo = episodes_repo
        self.editorial_repo = editorial_repo
        self.evidence_repo = evidence_repo
        self.events_repo = events_repo

    def explain(self, req) -> dict:
        with self.db.transaction() as connection:
            artifact = None
            if req.artifact_type == "claim":
                artifact = self.claims_repo.get(connection, req.artifact_id)
            elif req.artifact_type == "relation":
                artifact = self.relations_repo.get(connection, req.artifact_id)
            elif req.artifact_type == "episode":
                artifact = self.episodes_repo.get(connection, req.artifact_id)
            temporal = (
                {
                    key: artifact.get(key)
                    for key in ("valid_from", "valid_until", "superseded_at", "disputed_at", "last_reinforced_at")
                    if artifact and key in artifact
                }
                if req.artifact_type in {"claim", "relation"}
                else {}
            )
            editorial_state = self.editorial_repo.get_state(connection, artifact_type=req.artifact_type, artifact_id=req.artifact_id)
            decisions = self.editorial_repo.list_decisions(connection, artifact_type=req.artifact_type, artifact_id=req.artifact_id)
            event_ids = self.evidence_repo.event_ids_for_artifact(connection, artifact_type=req.artifact_type, artifact_id=req.artifact_id)
            supporting_events = self.events_repo.get_many(connection, event_ids)
            explained = explain_artifact(
                artifact_type=req.artifact_type,
                artifact=artifact,
                editorial_state=editorial_state,
                decisions=decisions,
                supporting_events=supporting_events,
            )
            explained["temporal"] = temporal
            return explained
