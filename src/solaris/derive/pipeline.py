# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

from solaris.derive.claims import derive_claims
from solaris.derive.entities import derive_entities
from solaris.derive.episodes import episode_title_for_event
from solaris.derive.relations import derive_relations
from solaris.derive.state import derive_state_lease


EPISODE_TOPIC_STOPWORDS = {
    "the",
    "and",
    "for",
    "from",
    "into",
    "that",
    "this",
    "with",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "how",
    "your",
    "about",
}


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _topic_tokens(text: str) -> set[str]:
    tokens = {
        token
        for token in re.findall(r"[A-Za-z0-9_']+", str(text or "").casefold())
        if len(token) >= 4 and token not in EPISODE_TOPIC_STOPWORDS
    }
    normalized: set[str] = set()
    for token in tokens:
        if token.endswith("s") and len(token) >= 6:
            normalized.add(token[:-1])
        normalized.add(token)
    return normalized


@dataclass(slots=True)
class DerivationPipeline:
    sessions_repo: object
    entities_repo: object
    relations_repo: object
    claims_repo: object
    episodes_repo: object
    events_repo: object
    state_repo: object
    evidence_repo: object
    editorial_repo: object

    def _find_related_episode(
        self,
        connection,
        *,
        continuity_session_id: str | None,
        title: str,
        dominant_entities: list[str],
        event_timestamp: str,
        limit: int = 12,
        gap_minutes: int = 10,
    ) -> dict | None:
        if not continuity_session_id:
            return None
        threshold = _parse_iso(event_timestamp) - timedelta(minutes=gap_minutes)
        current_tokens = _topic_tokens(title)
        current_entities = {
            " ".join(str(item or "").split()).strip().casefold()
            for item in list(dominant_entities or [])
            if " ".join(str(item or "").split()).strip()
        }
        if not current_tokens:
            return None
        best_match: dict | None = None
        best_score = 0
        for candidate in self.episodes_repo.list_by_session(connection, session_id=continuity_session_id, limit=limit):
            updated_at = str(candidate.get("updated_at") or candidate.get("end_at") or candidate.get("start_at") or "").strip()
            if not updated_at or _parse_iso(updated_at) < threshold:
                continue
            candidate_title = str(candidate.get("title") or "").strip()
            if not candidate_title or candidate_title.casefold() == title.casefold():
                continue
            candidate_tokens = _topic_tokens(candidate_title)
            if not candidate_tokens:
                continue
            candidate_entities = {
                " ".join(str(item or "").split()).strip().casefold()
                for item in list(candidate.get("dominant_entities") or [])
                if " ".join(str(item or "").split()).strip()
            }
            token_overlap = len(current_tokens & candidate_tokens)
            entity_overlap = len(current_entities & candidate_entities)
            if token_overlap < 2 and not (token_overlap >= 1 and entity_overlap >= 1):
                continue
            score = token_overlap * 2 + entity_overlap
            if score > best_score:
                best_score = score
                best_match = candidate
        return best_match

    def run(self, connection, *, event, event_id: str) -> dict:
        derived: dict[str, list[str] | int] = {
            "entities": [],
            "relations": [],
            "claims": [],
            "episodes": [],
            "state_leases": [],
        }

        state_lease = derive_state_lease(event)
        if state_lease is not None:
            lease = self.state_repo.upsert(
                connection,
                scope=event.scope,
                lease_key=state_lease["lease_key"],
                value_json=state_lease["value_json"],
                ttl_seconds=state_lease["ttl_seconds"],
            )
            derived["state_leases"].append(str(lease["lease_id"]))

        entity_records: list[dict] = []
        for entity in derive_entities(event):
            record = self.entities_repo.upsert(
                connection,
                scope=event.scope,
                canonical_name=entity["name"],
                entity_type=entity.get("type") or "concept",
                aliases=entity.get("aliases") or [],
                seen_at=event.timestamp,
            )
            self.entities_repo.link_event(connection, event_id=event_id, entity_id=record["entity_id"])
            entity_records.append(record)
            derived["entities"].append(str(record["entity_id"]))

        entity_by_name = {item["canonical_name"].casefold(): item for item in entity_records}
        for relation in derive_relations(event, entity_records):
            src = entity_by_name.get(str(relation["src"]).casefold())
            dst = entity_by_name.get(str(relation["dst"]).casefold())
            if src is None or dst is None:
                continue
            record = self.relations_repo.upsert(
                connection,
                scope=event.scope,
                src_entity_id=src["entity_id"],
                relation_type=relation["type"],
                dst_entity_id=dst["entity_id"],
                confidence=float(relation.get("confidence") or 0.6),
                seen_at=event.timestamp,
            )
            self.evidence_repo.link(
                connection,
                artifact_type="relation",
                artifact_id=record["relation_id"],
                scope_key=event.scope.key(),
                event_ids=[event_id],
            )
            self.editorial_repo.upsert_state(connection, artifact_type="relation", artifact_id=record["relation_id"], scope=event.scope)
            self.editorial_repo.enqueue_review(
                connection,
                artifact_type="relation",
                artifact_id=record["relation_id"],
                scope=event.scope,
                trigger="derived_relation",
                priority=0.35,
            )
            derived["relations"].append(str(record["relation_id"]))

        for claim in derive_claims(event, entity_records):
            subject = None
            subject_name = str(claim.get("subject_name") or "").strip()
            if subject_name:
                subject = entity_by_name.get(subject_name.casefold())
                if subject is None:
                    subject = self.entities_repo.upsert(
                        connection,
                        scope=event.scope,
                        canonical_name=subject_name,
                        entity_type="concept",
                        aliases=[],
                        seen_at=event.timestamp,
                    )
                    entity_by_name[subject_name.casefold()] = subject
            record = self.claims_repo.upsert(
                connection,
                scope=event.scope,
                subject_entity_id=(subject or {}).get("entity_id"),
                predicate=claim["predicate"],
                object_text=claim["object_text"],
                canonical_claim=claim["canonical_claim"],
                confidence=float(claim.get("confidence") or 0.5),
                pinned=bool(claim.get("pinned")),
                seen_at=event.timestamp,
            )
            self.evidence_repo.link(
                connection,
                artifact_type="claim",
                artifact_id=record["claim_id"],
                scope_key=event.scope.key(),
                event_ids=[event_id],
            )
            self.claims_repo.refresh_evidence_count(connection, record["claim_id"])
            if claim.get("pinned"):
                self.editorial_repo.upsert_state(
                    connection,
                    artifact_type="claim",
                    artifact_id=record["claim_id"],
                    scope=event.scope,
                    remember_state="remembered",
                    activation_state="active",
                    review_status="reviewed",
                    remember_score=1.0,
                    influence_score=1.0,
                    pinned=True,
                    policy_profile="default_v1",
                    rationale_json={"summary": "Pinned explicit fact assertion."},
                )
            else:
                self.editorial_repo.upsert_state(connection, artifact_type="claim", artifact_id=record["claim_id"], scope=event.scope)
                self.editorial_repo.enqueue_review(
                    connection,
                    artifact_type="claim",
                    artifact_id=record["claim_id"],
                    scope=event.scope,
                    trigger="derived_claim",
                    priority=float(event.scores.importance),
                )
            derived["claims"].append(str(record["claim_id"]))

        if event.session_id:
            continuity_session_id = self.sessions_repo.continuity_session_id(connection, event.session_id)
            title = episode_title_for_event(event, entity_records)
            episode = self.episodes_repo.find_recent_open(
                connection,
                session_id=continuity_session_id,
                scope_key=event.scope.key(),
                title=title,
                event_timestamp=event.timestamp,
            )
            dominant_entities = [item["canonical_name"] for item in entity_records[:4]]
            if episode is None:
                episode = self._find_related_episode(
                    connection,
                    continuity_session_id=continuity_session_id,
                    title=title,
                    dominant_entities=dominant_entities,
                    event_timestamp=event.timestamp,
                )
            if episode is None:
                episode = self.episodes_repo.create(
                    connection,
                    session_id=continuity_session_id,
                    scope=event.scope,
                    title=title,
                    start_at=event.timestamp,
                    dominant_entities=dominant_entities,
                    confidence=float(event.scores.confidence),
                )
            else:
                self.episodes_repo.update(
                    connection,
                    episode_id=episode["episode_id"],
                    updated_at=event.timestamp,
                    dominant_entities=dominant_entities or episode["dominant_entities"],
                    confidence=float(event.scores.confidence),
                )
            self.episodes_repo.link_event(connection, episode_id=episode["episode_id"], event_id=event_id)
            self.evidence_repo.link(
                connection,
                artifact_type="episode",
                artifact_id=episode["episode_id"],
                scope_key=event.scope.key(),
                event_ids=[event_id],
            )
            self.editorial_repo.upsert_state(connection, artifact_type="episode", artifact_id=episode["episode_id"], scope=event.scope)
            self.editorial_repo.enqueue_review(
                connection,
                artifact_type="episode",
                artifact_id=episode["episode_id"],
                scope=event.scope,
                trigger="episode_activity",
                priority=0.3,
            )
            derived["episodes"].append(str(episode["episode_id"]))

        return derived
