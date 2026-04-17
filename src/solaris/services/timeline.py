# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.retrieval.timeline import build_timeline


class TimelineService:
    def __init__(
        self,
        db,
        events_repo,
        episodes_repo,
        claims_repo=None,
        relations_repo=None,
        entities_repo=None,
        editorial_repo=None,
        evidence_repo=None,
    ):
        self.db = db
        self.events_repo = events_repo
        self.episodes_repo = episodes_repo
        self.claims_repo = claims_repo
        self.relations_repo = relations_repo
        self.entities_repo = entities_repo
        self.editorial_repo = editorial_repo
        self.evidence_repo = evidence_repo

    def timeline(self, req) -> dict:
        with self.db.transaction() as connection:
            events = self.events_repo.list_by_scope(connection, req.scope.key(), limit=req.limit)
            if req.episode_id:
                event_ids = set(self.episodes_repo.get_event_ids(connection, req.episode_id))
                events = [item for item in events if item["event_id"] in event_ids]
            claims = []
            relations = []
            episodes = []
            if req.entity_id and self.claims_repo is not None:
                claims = self.claims_repo.list_by_subject_entity(
                    connection,
                    scope_key=req.scope.key(),
                    subject_entity_id=req.entity_id,
                    limit=req.limit,
                )
            if req.entity_id and self.relations_repo is not None:
                relations = self._visible_relations(
                    connection,
                    scope_key=req.scope.key(),
                    focal_entity_id=req.entity_id,
                    limit=req.limit,
                )
            if req.entity_id and self.entities_repo is not None:
                entity_event_ids = self.entities_repo.event_ids_for_entity(connection, entity_id=req.entity_id)
                episodes = self.episodes_repo.list_by_event_ids(
                    connection,
                    scope_key=req.scope.key(),
                    event_ids=entity_event_ids,
                    limit=req.limit,
                )
            return {
                "ok": True,
                "events": build_timeline(events),
                "claims": claims,
                "relations": relations,
                "episodes": episodes,
            }

    def _visible_relations(self, connection, *, scope_key: str, focal_entity_id: str, limit: int) -> list[dict]:
        visible = []
        for relation in self.relations_repo.neighborhood(connection, scope_key=scope_key, entity_id=focal_entity_id):
            enriched = self._enriched_relation(connection, relation=relation, focal_entity_id=focal_entity_id)
            if self._relation_visible(enriched):
                visible.append(enriched)
            if len(visible) >= max(1, int(limit)):
                break
        return visible

    def _enriched_relation(self, connection, *, relation: dict, focal_entity_id: str) -> dict:
        src_entity = self.entities_repo.get(connection, relation["src_entity_id"]) if self.entities_repo is not None else None
        dst_entity = self.entities_repo.get(connection, relation["dst_entity_id"]) if self.entities_repo is not None else None
        if str(relation.get("src_entity_id") or "") == focal_entity_id:
            counterparty = dst_entity
        else:
            counterparty = src_entity
        editorial_state = (
            self.editorial_repo.get_state(connection, artifact_type="relation", artifact_id=relation["relation_id"])
            if self.editorial_repo is not None
            else None
        )
        supporting_event_count = (
            len(
                self.evidence_repo.event_ids_for_artifact(
                    connection,
                    artifact_type="relation",
                    artifact_id=relation["relation_id"],
                )
            )
            if self.evidence_repo is not None
            else 0
        )
        temporal = {
            key: relation.get(key)
            for key in ("valid_from", "valid_until", "superseded_at", "disputed_at", "last_reinforced_at")
            if key in relation
        }
        return {
            **relation,
            "relation": relation,
            "src_entity": src_entity,
            "dst_entity": dst_entity,
            "counterparty_entity": counterparty,
            "editorial_state": editorial_state,
            "supporting_event_count": supporting_event_count,
            "temporal": temporal,
        }

    @staticmethod
    def _relation_visible(relation: dict) -> bool:
        relation_type = str(relation.get("relation_type") or "").strip().casefold()
        editorial_state = relation.get("editorial_state") or {}
        remember_state = str(editorial_state.get("remember_state") or "candidate").strip().casefold()
        activation_state = str(editorial_state.get("activation_state") or "suppressed").strip().casefold()
        if relation_type == "related_to" and remember_state == "candidate" and activation_state == "suppressed":
            return False
        return True
