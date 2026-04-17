# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations


class EntityService:
    def __init__(self, db, entities_repo, relations_repo, editorial_repo, evidence_repo):
        self.db = db
        self.entities_repo = entities_repo
        self.relations_repo = relations_repo
        self.editorial_repo = editorial_repo
        self.evidence_repo = evidence_repo

    def resolve(self, req) -> dict:
        with self.db.transaction() as connection:
            entity = None
            if req.entity_id:
                entity = self.entities_repo.get(connection, req.entity_id)
            elif req.canonical_name:
                entity = self.entities_repo.resolve(connection, scope_key=req.scope.key(), canonical_name=req.canonical_name)
            if entity is None:
                return {"ok": False, "entity": None, "relations": []}
            relations = (
                self._visible_relations(connection, scope_key=req.scope.key(), focal_entity_id=entity["entity_id"])
                if req.include_relations
                else []
            )
            return {"ok": True, "entity": entity, "relations": relations}

    def _visible_relations(self, connection, *, scope_key: str, focal_entity_id: str) -> list[dict]:
        visible = []
        for relation in self.relations_repo.neighborhood(connection, scope_key=scope_key, entity_id=focal_entity_id):
            enriched = self._enriched_relation(connection, relation=relation, focal_entity_id=focal_entity_id)
            if self._relation_visible(enriched):
                visible.append(enriched)
        return visible

    def _enriched_relation(self, connection, *, relation: dict, focal_entity_id: str) -> dict:
        src_entity = self.entities_repo.get(connection, relation["src_entity_id"])
        dst_entity = self.entities_repo.get(connection, relation["dst_entity_id"])
        if str(relation.get("src_entity_id") or "") == focal_entity_id:
            counterparty = dst_entity
        else:
            counterparty = src_entity
        editorial_state = self.editorial_repo.get_state(
            connection,
            artifact_type="relation",
            artifact_id=relation["relation_id"],
        )
        supporting_event_count = len(
            self.evidence_repo.event_ids_for_artifact(
                connection,
                artifact_type="relation",
                artifact_id=relation["relation_id"],
            )
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
