# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from datetime import datetime, timezone
import re

from solaris.retrieval.bundle import build_bundle
from solaris.retrieval.ranking import lexical_overlap, score_item
from solaris.retrieval.search import lexical_event_search


class QueryService:
    THIS_SESSION_SCOPE = "this_session"
    RECENT_SCOPE = "recent"
    PROJECT_SCOPE = "project"
    IDENTITY_SCOPE = "identity"
    TOPIC_SCOPE = "topic"
    ARCHIVE_SCOPE = "archive"
    ARCHAEOLOGY_SCOPE = "archaeology"
    SESSION_QUERY_MARKERS = (
        "this session",
        "current session",
        "this conversation",
        "current conversation",
        "in this session",
        "in this conversation",
        "latest interaction",
        "just now",
    )
    RECENT_QUERY_MARKERS = (
        "recently",
        "lately",
        "what have we been discussing",
        "what have we been talking about",
        "what have we talked about",
        "what were we discussing",
        "what were we talking about",
        "what have we been working on",
    )
    PROJECT_QUERY_MARKERS = (
        "this project",
        "the project",
        "this workspace",
        "the workspace",
        "the codebase",
        "this repo",
        "the repo",
        "what are we working on",
        "what am i working on",
    )
    PROJECT_EVENT_MARKERS = (
        "project",
        "workspace",
        "codebase",
        "repo",
        "repository",
    )
    IDENTITY_QUERY_MARKERS = (
        "what is my name",
        "who am i",
        "where do i live",
        "what do you know about me",
        "what do you remember about me",
        "what is my",
        "where am i from",
    )
    ARCHIVE_QUERY_MARKERS = (
        "archive",
        "archived",
        "full record",
        "historical record",
        "history of",
        "everything we have",
    )
    ARCHAEOLOGY_QUERY_MARKERS = (
        "archaeology",
        "walk the chain",
        "full trail",
        "everything including retired",
        "show me everything",
    )
    CLAIM_QUERY_MARKERS = (
        "what is ",
        "what are ",
        "who is ",
        "who are ",
        "where is ",
        "where are ",
        "where do i",
        "what do you remember about",
        "what do i remember about",
        "what do we know about",
    )
    EVIDENCE_QUERY_MARKERS = (
        "why do you think",
        "what is the evidence",
        "show evidence",
        "show the evidence",
        "show source",
        "show the source",
        "where did that come from",
        "what supports that",
        "prove it",
        "with evidence",
        "with sources",
        "with provenance",
    )
    RELATIONSHIP_QUERY_MARKERS = (
        "how is",
        "related to",
        "what depends on",
        "what caused",
        "what uses",
        "depends on",
        "blocked by",
        "failed due to",
    )
    RELATIONSHIP_VERB_TOKENS = {
        "related",
        "depends",
        "depend",
        "caused",
        "causes",
        "uses",
        "using",
        "blocked",
        "failure",
        "failed",
    }
    LOW_SIGNAL_EVENT_TEXTS = {
        "ready",
        "good information",
        "ok",
        "okay",
        "yes",
        "no",
        "thanks",
        "thank you",
    }
    GENERIC_EPISODE_TITLES = {"conversation", "message", "activity", "system", "note"}
    QUESTION_STARTERS = {
        "what",
        "why",
        "how",
        "when",
        "where",
        "who",
        "which",
        "is",
        "are",
        "am",
        "do",
        "does",
        "did",
        "can",
        "could",
        "would",
        "should",
        "will",
        "have",
        "has",
        "tell",
        "explain",
        "summarize",
        "remind",
        "check",
    }
    QUERY_CONTENT_STOPWORDS = QUESTION_STARTERS | {
        "a",
        "an",
        "and",
        "about",
        "all",
        "am",
        "any",
        "be",
        "been",
        "being",
        "can",
        "currently",
        "current",
        "did",
        "do",
        "does",
        "for",
        "from",
        "get",
        "give",
        "had",
        "has",
        "have",
        "i",
        "in",
        "it",
        "just",
        "know",
        "me",
        "my",
        "now",
        "of",
        "on",
        "or",
        "our",
        "please",
        "remember",
        "session",
        "something",
        "talk",
        "talked",
        "talking",
        "tell",
        "that",
        "the",
        "them",
        "this",
        "those",
        "to",
        "us",
        "we",
        "were",
        "with",
        "you",
        "your",
    }
    LOW_SIGNAL_ENTITY_NAMES = QUERY_CONTENT_STOPWORDS | {
        "user",
        "likely",
        "mode",
        "well",
        "right",
        "good",
        "said",
        "give",
        "more",
        "something",
        "actually",
        "yeah",
        "sorry",
        "conversation",
    }
    INTERPRETIVE_EVENT_PREFIXES = (
        "the user is ",
        "you are asking ",
        "the operator is ",
        "the operator wants ",
        "the operator may be ",
    )

    def __init__(
        self,
        db,
        sessions_repo,
        events_repo,
        entities_repo,
        relations_repo,
        claims_repo,
        episodes_repo,
        state_repo,
        editorial_repo,
        evidence_repo,
        *,
        divergence_weight_threshold: float = 0.2,
    ):
        self.db = db
        self.sessions_repo = sessions_repo
        self.events_repo = events_repo
        self.entities_repo = entities_repo
        self.relations_repo = relations_repo
        self.claims_repo = claims_repo
        self.episodes_repo = episodes_repo
        self.state_repo = state_repo
        self.editorial_repo = editorial_repo
        self.evidence_repo = evidence_repo
        self.divergence_weight_threshold = max(0.0, float(divergence_weight_threshold))

    def query(self, req):
        with self.db.transaction() as connection:
            scope_key = req.scope.key()
            scope_intent = self._query_scope_intent(req.query)
            session_focused = scope_intent == self.THIS_SESSION_SCOPE
            recent_focused = scope_intent == self.RECENT_SCOPE
            identity_focused = scope_intent == self.IDENTITY_SCOPE
            project_focused = scope_intent == self.PROJECT_SCOPE
            archive_relaxed = req.recall_mode == "archive" or scope_intent in {self.ARCHIVE_SCOPE, self.ARCHAEOLOGY_SCOPE}
            effective_recall_mode = "archive" if archive_relaxed else req.recall_mode
            relation_focused = self._query_prefers_relationship_focus(req.query)
            relation_query_shape = self._relation_query_shape(req.query) if relation_focused else None
            claim_focused = identity_focused or (self._query_prefers_claim_answer(req.query) and not relation_focused)
            evidence_requested = self._query_requests_evidence(req.query)
            preferred_session_id = self._preferred_session_id(connection, scope_key=scope_key, query=req.query)
            preferred_episode_session_id = (
                self.sessions_repo.continuity_session_id(connection, preferred_session_id) if preferred_session_id else None
            )
            query_meta = {
                "scope_intent": scope_intent,
                "preferred_session_id": preferred_session_id,
                "preferred_episode_session_id": preferred_episode_session_id,
                "session_narrowing_applied": bool(session_focused and preferred_session_id),
                "archive_relaxation_applied": bool(archive_relaxed),
                "identity_focus_applied": bool(identity_focused),
                "project_focus_applied": bool(project_focused),
                "recent_focus_applied": bool(recent_focused),
                "relation_focus_applied": bool(relation_focused),
                "relation_candidate_relaxation_applied": False,
                "recent_episode_candidate_relaxation_applied": False,
                "relation_query_shape": relation_query_shape or {},
            }
            state_leases = self.state_repo.list_active(connection, scope_key, limit=req.budget.state) if "state" in req.modes else []
            claim_limit = max(req.budget.claims * 3, req.budget.claims)
            episode_limit = max(req.budget.episodes * 3, req.budget.episodes)
            entity_limit = max(req.budget.entities * 3, req.budget.entities)
            relation_limit = max(req.budget.relations * 3, req.budget.relations)

            session_claims = (
                self.claims_repo.list_by_session(connection, scope_key=scope_key, session_id=preferred_session_id, limit=claim_limit)
                if preferred_session_id
                else []
            )
            claims = (
                session_claims[:claim_limit]
                if session_focused and preferred_session_id
                else self._merge_preferred(
                    session_claims,
                    self.claims_repo.list_by_scope(connection, scope_key, limit=claim_limit),
                    key="claim_id",
                    limit=claim_limit,
                )
            )

            session_episodes = (
                self.episodes_repo.list_by_session(connection, session_id=preferred_episode_session_id, limit=episode_limit)
                if preferred_episode_session_id
                else []
            )
            episodes = (
                session_episodes[:episode_limit]
                if session_focused and preferred_episode_session_id and session_episodes
                else self._merge_preferred(
                    session_episodes,
                    self.episodes_repo.list_by_scope(connection, scope_key, limit=episode_limit),
                    key="episode_id",
                    limit=episode_limit,
                )
            )

            if "graph" in req.modes:
                query_entity_tokens = sorted(self._content_tokens(req.query))
                relation_search_tokens = (
                    list(relation_query_shape.get("target_tokens") or [])
                    if relation_query_shape
                    else query_entity_tokens
                )
                relation_search_type = str(relation_query_shape.get("relation_type") or "").strip() if relation_query_shape else None
                session_entities = (
                    self.entities_repo.list_by_session(connection, scope_key=scope_key, session_id=preferred_session_id, limit=entity_limit)
                    if preferred_session_id
                    else []
                )
                matched_entities = (
                    self.entities_repo.search_by_scope(connection, scope_key=scope_key, tokens=query_entity_tokens, limit=entity_limit)
                    if query_entity_tokens
                    else []
                )
                entities = self._merge_preferred(
                    session_entities + matched_entities,
                    self.entities_repo.list_by_scope(connection, scope_key, limit=entity_limit),
                    key="entity_id",
                    limit=entity_limit,
                )
                session_relations = (
                    self.relations_repo.list_by_session(connection, scope_key=scope_key, session_id=preferred_session_id, limit=relation_limit)
                    if preferred_session_id
                    else []
                )
                matched_relations = (
                    self.relations_repo.search_by_scope(
                        connection,
                        scope_key=scope_key,
                        tokens=relation_search_tokens,
                        relation_type=relation_search_type,
                        limit=relation_limit,
                    )
                    if relation_focused and relation_search_tokens
                    else []
                )
                relations = (
                    session_relations[: req.budget.relations]
                    if session_focused and preferred_session_id
                    else self._merge_preferred(
                        session_relations + matched_relations,
                        self.relations_repo.list_by_scope(connection, scope_key, limit=relation_limit),
                        key="relation_id",
                        limit=relation_limit,
                    )
                )
            else:
                entities = []
                relations = []

            session_claim_ids = {item["claim_id"] for item in session_claims}
            session_episode_ids = {item["episode_id"] for item in session_episodes}
            session_relation_ids = {item["relation_id"] for item in session_relations} if "graph" in req.modes else set()
            claim_recency_ranks = self._recency_ranks(claims, lambda item: str(item.get("last_seen") or ""))
            episode_recency_ranks = self._recency_ranks(
                episodes,
                lambda item: str(item.get("updated_at") or item.get("end_at") or item.get("start_at") or ""),
            )
            entity_recency_ranks = self._recency_ranks(entities, lambda item: str(item.get("last_seen") or ""))
            relation_recency_ranks = self._recency_ranks(relations, lambda item: str(item.get("last_seen") or ""))
            episode_event_counts = {
                item["episode_id"]: len(self.episodes_repo.get_event_ids(connection, item["episode_id"]))
                for item in episodes
            }
            relation_entity_ids = {
                str(item.get("src_entity_id") or "").strip()
                for item in relations
                if str(item.get("src_entity_id") or "").strip()
            } | {
                str(item.get("dst_entity_id") or "").strip()
                for item in relations
                if str(item.get("dst_entity_id") or "").strip()
            }
            relation_entity_map = {
                entity_id: self.entities_repo.get(connection, entity_id)
                for entity_id in relation_entity_ids
            }

            ranked_claims = []
            for item in claims:
                editorial = self.editorial_repo.get_state(connection, artifact_type="claim", artifact_id=item["claim_id"])
                if not self._allow_editorial(editorial, effective_recall_mode):
                    continue
                if effective_recall_mode == "default" and self._claim_is_low_quality(item):
                    continue
                session_bonus = 1.0 if item["claim_id"] in session_claim_ids else 0.0
                lexical_match = lexical_overlap(req.query, item["canonical_claim"])
                content_match = self._content_overlap(req.query, item["canonical_claim"])
                if recent_focused and session_bonus <= 0 and int(item.get("evidence_count") or 0) < 2 and not bool(item.get("pinned")):
                    continue
                if (
                    claim_focused
                    and effective_recall_mode == "default"
                    and session_bonus <= 0
                    and not bool(item.get("pinned"))
                    and self._topical_match(
                        lexical_match=lexical_match,
                        content_match=content_match,
                        content_required=bool(self._content_tokens(req.query)),
                    )
                    < 0.15
                ):
                    continue
                recency_bonus = self._rank_bonus(
                    claim_recency_ranks.get(item["claim_id"], len(claims)),
                    len(claims),
                    max_bonus=0.35 if recent_focused else 0.2,
                )
                quality_penalty = self._claim_quality_penalty(item=item, recall_mode=effective_recall_mode)
                if identity_focused:
                    quality_penalty += self._identity_claim_bonus(item=item)
                query_bonus = self._claim_query_bonus(
                    item=item,
                    editorial=editorial,
                    claim_focused=claim_focused,
                    recent_focused=recent_focused,
                    topical_match=self._topical_match(
                        lexical_match=lexical_match,
                        content_match=content_match,
                        content_required=bool(self._content_tokens(req.query)),
                    ),
                )
                ranked_claims.append(
                    (
                        score_item(
                            query=req.query,
                            text=item["canonical_claim"],
                            recency_bias=0.1,
                            importance=item["evidence_count"] / 3.0,
                            confidence=item["confidence"],
                            editorial_state=editorial,
                            recall_mode=effective_recall_mode,
                        )
                        + session_bonus
                        + recency_bonus
                        + quality_penalty
                        + query_bonus,
                        item,
                        editorial,
                        session_bonus,
                    )
                )
            ranked_claims.sort(key=lambda item: item[0], reverse=True)

            ranked_episodes = []
            for item in episodes:
                editorial = self.editorial_repo.get_state(connection, artifact_type="episode", artifact_id=item["episode_id"])
                episode_candidate_relaxed = self._allow_recent_episode_editorial(
                    editorial=editorial,
                    recall_mode=effective_recall_mode,
                    recent_focused=recent_focused,
                    episode=item,
                    event_count=episode_event_counts.get(item["episode_id"], 0),
                )
                if not episode_candidate_relaxed and not self._allow_editorial(editorial, effective_recall_mode):
                    continue
                if episode_candidate_relaxed:
                    query_meta["recent_episode_candidate_relaxation_applied"] = True
                session_bonus = 1.0 if item["episode_id"] in session_episode_ids else 0.0
                recency_bonus = self._rank_bonus(
                    episode_recency_ranks.get(item["episode_id"], len(episodes)),
                    len(episodes),
                    max_bonus=0.8 if recent_focused else 0.2,
                )
                quality_penalty = self._episode_quality_penalty(
                    episode=item,
                    event_count=episode_event_counts.get(item["episode_id"], 0),
                    recall_mode=req.recall_mode,
                    session_bonus=session_bonus,
                    recent_focused=recent_focused,
                )
                ranked_episodes.append(
                    (
                        score_item(
                            query=req.query,
                            text=f"{item['title']} {item['summary_text']}",
                            recency_bias=0.1,
                            importance=item["confidence"],
                            confidence=item["confidence"],
                            editorial_state=editorial,
                            recall_mode=effective_recall_mode,
                        )
                        + session_bonus
                        + recency_bonus
                        + quality_penalty,
                        item,
                        editorial,
                        session_bonus,
                    )
                )
            ranked_episodes.sort(key=lambda item: item[0], reverse=True)

            session_entity_ids = {item["entity_id"] for item in session_entities} if "graph" in req.modes else set()
            ranked_entities = []
            for item in entities:
                lexical_match = lexical_overlap(req.query, self._entity_search_text(item))
                content_match = self._content_overlap(req.query, self._entity_search_text(item))
                topical_match = self._topical_match(
                    lexical_match=lexical_match,
                    content_match=content_match,
                    content_required=bool(self._content_tokens(req.query)),
                )
                session_bonus = 0.5 if item["entity_id"] in session_entity_ids else 0.0
                mention_bonus = min(0.6, float(item.get("mention_count") or 0) / 25.0)
                recency_bonus = self._rank_bonus(
                    entity_recency_ranks.get(item["entity_id"], len(entities)),
                    len(entities),
                    max_bonus=0.2,
                )
                quality_penalty = self._entity_quality_penalty(
                    entity=item,
                    recall_mode=effective_recall_mode,
                    claim_focused=claim_focused,
                    recent_focused=recent_focused,
                )
                if effective_recall_mode == "default" and quality_penalty <= -0.9:
                    continue
                if claim_focused and effective_recall_mode == "default" and topical_match < 0.15:
                    continue
                ranked_entities.append(
                    (
                        topical_match + session_bonus + mention_bonus + recency_bonus + quality_penalty,
                        item,
                    )
                )
            ranked_entities.sort(key=lambda item: item[0], reverse=True)

            ranked_relations = []
            for item in relations:
                editorial = self.editorial_repo.get_state(connection, artifact_type="relation", artifact_id=item["relation_id"])
                display = self._display_relation(item=item, entity_map=relation_entity_map)
                relation_text = self._relation_search_text(display)
                lexical_match = lexical_overlap(req.query, relation_text)
                content_match = self._content_overlap(req.query, relation_text)
                topical_match = self._topical_match(
                    lexical_match=lexical_match,
                    content_match=content_match,
                    content_required=bool(self._content_tokens(req.query)),
                )
                relation_structure = self._relation_query_bonus(display, relation_query_shape)
                relation_candidate_relaxed = self._allow_relation_editorial(
                    editorial=editorial,
                    recall_mode=effective_recall_mode,
                    relation=item,
                    relation_focused=relation_focused,
                    topical_match=max(topical_match, relation_structure.get("topical_match_override") or 0.0),
                )
                if not relation_candidate_relaxed and not self._allow_editorial(editorial, effective_recall_mode):
                    continue
                if relation_focused and not relation_structure["allow"]:
                    continue
                if relation_focused and max(topical_match, relation_structure.get("topical_match_override") or 0.0) < 0.15:
                    continue
                session_bonus = 0.7 if item["relation_id"] in session_relation_ids else 0.0
                recency_bonus = self._rank_bonus(
                    relation_recency_ranks.get(item["relation_id"], len(relations)),
                    len(relations),
                    max_bonus=0.2,
                )
                quality_penalty = self._relation_quality_penalty(
                    relation=item,
                    editorial=editorial,
                    recall_mode=effective_recall_mode,
                )
                query_bonus = (
                    (0.6 if relation_focused and topical_match > 0.0 else 0.0)
                    + float(relation_structure.get("bonus") or 0.0)
                    + float(relation_structure.get("penalty") or 0.0)
                )
                if relation_candidate_relaxed:
                    query_meta["relation_candidate_relaxation_applied"] = True
                ranked_relations.append(
                    (
                        score_item(
                            query=req.query,
                            text=relation_text,
                            recency_bias=0.1,
                            importance=float(item.get("confidence") or 0.0),
                            confidence=float(item.get("confidence") or 0.0),
                            editorial_state=editorial,
                            recall_mode=effective_recall_mode,
                        )
                        + session_bonus
                        + recency_bonus
                        + quality_penalty
                        + query_bonus,
                        display,
                        editorial,
                        session_bonus,
                    )
                )
            ranked_relations.sort(key=lambda item: item[0], reverse=True)

            selected_claims = [item for _, item, _, _ in ranked_claims[: req.budget.claims]]
            selected_episodes = [item for _, item, _, _ in ranked_episodes[: req.budget.episodes]]
            selected_entities = [item for _, item in ranked_entities[: req.budget.entities]]
            selected_relations = [item for _, item, _, _ in ranked_relations[: req.budget.relations]]
            if effective_recall_mode == "archive":
                selected_claims = selected_claims[: max(1, req.budget.claims // 2)]
                selected_episodes = selected_episodes[: max(1, req.budget.episodes // 2)]
                selected_entities = selected_entities[: max(1, req.budget.entities // 2)]
                selected_relations = selected_relations[: max(1, req.budget.relations // 2)]
            if relation_focused and effective_recall_mode == "default":
                selected_entities = []

            suppress_supporting_graph = bool(
                claim_focused and not relation_focused and effective_recall_mode == "default" and selected_claims and not evidence_requested
            )
            if suppress_supporting_graph:
                selected_entities = []
                selected_relations = []
                selected_episodes = []

            events = (
                []
                if suppress_supporting_graph
                else self._select_events(
                    connection,
                    scope_key=scope_key,
                    query=req.query,
                    preferred_session_id=preferred_session_id,
                    limit=req.budget.events,
                    recall_mode=effective_recall_mode,
                    session_focused=session_focused,
                    recent_focused=recent_focused,
                    claim_focused=claim_focused,
                    identity_focused=identity_focused,
                    project_focused=project_focused,
                )
            )
            recorded = self._build_recorded_view(
                connection,
                archive_events=events,
                surfaced_claims=selected_claims,
                surfaced_episodes=selected_episodes,
                surfaced_relations=selected_relations,
            )

            explanations = []
            if req.include_explanations:
                for score, item, editorial, session_bonus in ranked_claims[: req.budget.claims]:
                    why = f"Matched query and editorial state {str((editorial or {}).get('remember_state') or 'candidate')}."
                    if session_bonus > 0:
                        why += " Supported by the preferred interaction session."
                    explanations.append(
                        {
                            "artifact_type": "claim",
                            "artifact_id": item["claim_id"],
                            "score": score,
                            "why": why,
                        }
                    )
                for score, item, editorial, session_bonus in ranked_episodes[: req.budget.episodes]:
                    why = f"Episode title or summary matched query with editorial state {str((editorial or {}).get('remember_state') or 'candidate')}."
                    if session_bonus > 0:
                        why += " Episode belongs to the preferred interaction session."
                    explanations.append(
                        {
                            "artifact_type": "episode",
                            "artifact_id": item["episode_id"],
                            "score": score,
                            "why": why,
                        }
                    )
                for score, item, editorial, session_bonus in ranked_relations[: req.budget.relations]:
                    why = f"Relation matched query with editorial state {str((editorial or {}).get('remember_state') or 'candidate')}."
                    if relation_focused:
                        why += " Relation-focused retrieval logic was applied."
                    if session_bonus > 0:
                        why += " Relation is supported by the preferred interaction session."
                    explanations.append(
                        {
                            "artifact_type": "relation",
                            "artifact_id": item["relation_id"],
                            "score": score,
                            "why": why,
                        }
                    )
                explanations.append(
                    {
                        "artifact_type": "query",
                        "artifact_id": "scope_intent",
                        "score": 0.0,
                        "why": (
                            f"Detected scope intent '{scope_intent}'. "
                            f"Session narrowing applied={query_meta['session_narrowing_applied']}. "
                            f"Archive relaxation applied={query_meta['archive_relaxation_applied']}. "
                            f"Relation focus applied={query_meta['relation_focus_applied']}."
                        ),
                    }
                )

            return build_bundle(
                claims=selected_claims,
                state_leases=state_leases,
                episodes=selected_episodes,
                events=events,
                entities=selected_entities,
                relations=selected_relations,
                explanations=explanations,
                recorded=recorded,
                divergence_summary=recorded.get("divergence_summary") or {},
                meta=query_meta,
            )

    def _build_recorded_view(
        self,
        connection,
        *,
        archive_events: list[dict],
        surfaced_claims: list[dict],
        surfaced_episodes: list[dict],
        surfaced_relations: list[dict],
    ) -> dict:
        divergences, provenance = self._compute_divergences(
            connection,
            archive_events=archive_events,
            surfaced_claims=surfaced_claims,
            surfaced_episodes=surfaced_episodes,
            surfaced_relations=surfaced_relations,
        )
        return {
            "events": archive_events,
            "provenance": provenance,
            "divergences": divergences,
            "divergence_summary": {
                "count": len(divergences),
                "notable": [
                    item
                    for item in divergences
                    if str(item.get("remember_state") or "").strip().casefold() in {"retired", "superseded"}
                ][:5],
            },
        }

    def _compute_divergences(
        self,
        connection,
        *,
        archive_events: list[dict],
        surfaced_claims: list[dict],
        surfaced_episodes: list[dict],
        surfaced_relations: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        event_ids = [str(item.get("event_id") or "").strip() for item in archive_events if str(item.get("event_id") or "").strip()]
        if not event_ids:
            return [], []

        surfaced_ids = {
            ("claim", str(item.get("claim_id") or "").strip())
            for item in surfaced_claims
            if str(item.get("claim_id") or "").strip()
        } | {
            ("episode", str(item.get("episode_id") or "").strip())
            for item in surfaced_episodes
            if str(item.get("episode_id") or "").strip()
        } | {
            ("relation", str(item.get("relation_id") or "").strip())
            for item in surfaced_relations
            if str(item.get("relation_id") or "").strip()
        }
        supported = self.evidence_repo.artifacts_for_event_ids(
            connection,
            event_ids=event_ids,
            artifact_types=["claim", "episode", "relation"],
        )
        divergences: list[dict] = []
        provenance: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for supported_artifact in supported:
            artifact_type = str(supported_artifact.get("artifact_type") or "").strip()
            artifact_id = str(supported_artifact.get("artifact_id") or "").strip()
            key = (artifact_type, artifact_id)
            if not artifact_type or not artifact_id or key in seen:
                continue
            seen.add(key)
            artifact = self._artifact_for(connection, artifact_type=artifact_type, artifact_id=artifact_id)
            if not artifact:
                continue
            editorial = self.editorial_repo.get_state(connection, artifact_type=artifact_type, artifact_id=artifact_id) or {}
            supporting_event_ids = self.evidence_repo.event_ids_for_artifact(
                connection,
                artifact_type=artifact_type,
                artifact_id=artifact_id,
            )
            item = self._divergence_item(
                artifact_type=artifact_type,
                artifact=artifact,
                editorial=editorial,
                supporting_event_ids=supporting_event_ids,
            )
            provenance.append(item)
            remember_state = str(editorial.get("remember_state") or "").strip().casefold()
            activation_state = str(editorial.get("activation_state") or "").strip().casefold()
            influence_score = float(editorial.get("influence_score") or 0.0)
            active_in_belief = (
                key in surfaced_ids
                or (
                    remember_state == "remembered"
                    and activation_state == "active"
                    and influence_score >= self.divergence_weight_threshold
                )
            )
            if not active_in_belief or remember_state in {"retired", "superseded", "disputed"}:
                divergences.append(item)
        return divergences, provenance

    def _artifact_for(self, connection, *, artifact_type: str, artifact_id: str) -> dict | None:
        if artifact_type == "claim":
            return self.claims_repo.get(connection, artifact_id)
        if artifact_type == "episode":
            return self.episodes_repo.get(connection, artifact_id)
        if artifact_type == "relation":
            relation = self.relations_repo.get(connection, artifact_id)
            if not relation:
                return None
            src_entity = self.entities_repo.get(connection, str(relation.get("src_entity_id") or "").strip())
            dst_entity = self.entities_repo.get(connection, str(relation.get("dst_entity_id") or "").strip())
            relation["src_entity"] = src_entity
            relation["dst_entity"] = dst_entity
            return relation
        return None

    def _divergence_item(self, *, artifact_type: str, artifact: dict, editorial: dict, supporting_event_ids: list[str]) -> dict:
        label = (
            str(artifact.get("canonical_claim") or "").strip()
            or str(artifact.get("title") or "").strip()
            or self._relation_label(artifact)
            or artifact_type
        )
        return {
            "artifact_type": artifact_type,
            "artifact_id": artifact.get("claim_id") or artifact.get("episode_id") or artifact.get("relation_id"),
            "label": label,
            "remember_state": str(editorial.get("remember_state") or "unreviewed"),
            "activation_state": str(editorial.get("activation_state") or "unknown"),
            "remember_score": float(editorial.get("remember_score") or 0.0),
            "influence_score": float(editorial.get("influence_score") or 0.0),
            "supporting_event_ids": list(supporting_event_ids),
        }

    def _relation_label(self, relation: dict) -> str:
        src_name = str((((relation.get("src_entity") or {}) or {}).get("canonical_name")) or "").strip()
        dst_name = str((((relation.get("dst_entity") or {}) or {}).get("canonical_name")) or "").strip()
        relation_type = str(relation.get("relation_type") or "").strip()
        if src_name and relation_type and dst_name:
            return f"{src_name} {relation_type} {dst_name}"
        return ""

    @staticmethod
    def _allow_editorial(editorial_state: dict | None, recall_mode: str) -> bool:
        if recall_mode == "archive":
            return True
        if editorial_state is None:
            return recall_mode == "deep"
        remember_state = str(editorial_state.get("remember_state") or "candidate")
        activation_state = str(editorial_state.get("activation_state") or "suppressed")
        if remember_state in {"retired", "superseded"} and recall_mode != "deep":
            return False
        if remember_state == "candidate" and recall_mode == "default" and activation_state == "suppressed":
            return False
        return True

    @staticmethod
    def _allow_relation_editorial(
        *,
        editorial: dict | None,
        recall_mode: str,
        relation: dict,
        relation_focused: bool,
        topical_match: float,
    ) -> bool:
        if recall_mode != "default" or not relation_focused:
            return False
        relation_type = str(relation.get("relation_type") or "").strip().casefold()
        if relation_type == "related_to":
            return False
        remember_state = str((editorial or {}).get("remember_state") or "candidate").strip().casefold()
        activation_state = str((editorial or {}).get("activation_state") or "suppressed").strip().casefold()
        confidence = float(relation.get("confidence") or 0.0)
        return (
            remember_state == "candidate"
            and activation_state == "suppressed"
            and topical_match >= 0.2
            and confidence >= 0.65
        )

    @staticmethod
    def _allow_recent_episode_editorial(
        *,
        editorial: dict | None,
        recall_mode: str,
        recent_focused: bool,
        episode: dict,
        event_count: int,
    ) -> bool:
        if recall_mode != "default" or not recent_focused:
            return False
        remember_state = str((editorial or {}).get("remember_state") or "candidate").strip().casefold()
        activation_state = str((editorial or {}).get("activation_state") or "suppressed").strip().casefold()
        confidence = float(episode.get("confidence") or 0.0)
        return (
            remember_state == "candidate"
            and activation_state == "suppressed"
            and event_count >= 1
            and confidence >= 0.9
        )

    @classmethod
    def _relation_query_shape(cls, query: str) -> dict | None:
        normalized = " ".join(str(query or "").split()).strip().casefold()
        patterns = (
            (r"^what uses (?P<target>.+)$", "uses", "dst"),
            (r"^what depends on (?P<target>.+)$", "depends_on", "dst"),
            (r"^what caused (?P<target>.+)$", "causes", "dst"),
            (r"^what causes (?P<target>.+)$", "causes", "dst"),
            (r"^what is blocked by (?P<target>.+)$", "blocked_by", "dst"),
            (r"^what failed due to (?P<target>.+)$", "failed_due_to", "dst"),
        )
        for pattern, relation_type, target_role in patterns:
            match = re.match(pattern, normalized)
            if match is None:
                continue
            target_text = " ".join((match.group("target") or "").split()).strip()
            target_tokens = sorted(cls._content_tokens(target_text))
            if not target_tokens:
                return None
            return {
                "relation_type": relation_type,
                "target_role": target_role,
                "target_text": target_text,
                "target_tokens": target_tokens,
            }
        return None

    @classmethod
    def _relation_query_bonus(cls, relation: dict, shape: dict | None) -> dict:
        if not shape:
            return {"allow": True, "bonus": 0.0, "penalty": 0.0, "topical_match_override": 0.0}
        relation_type = str(relation.get("relation_type") or "").strip().casefold()
        src_name = str(((relation.get("src_entity") or {}).get("canonical_name")) or "").strip()
        dst_name = str(((relation.get("dst_entity") or {}).get("canonical_name")) or "").strip()
        target_role = str(shape.get("target_role") or "dst")
        target_name = dst_name if target_role == "dst" else src_name
        target_tokens = set(shape.get("target_tokens") or [])
        target_text = str(shape.get("target_text") or "").strip()
        target_match = cls._relation_target_match_score(target_name=target_name, target_text=target_text, target_tokens=target_tokens)
        type_match = relation_type == str(shape.get("relation_type") or "").strip().casefold()
        if target_match <= 0.0 or not type_match:
            return {"allow": False, "bonus": 0.0, "penalty": 0.0, "topical_match_override": 0.0}
        return {
            "allow": True,
            "bonus": 0.45 + (0.85 if target_match >= 0.5 else 0.35),
            "penalty": 0.0,
            "topical_match_override": target_match,
        }

    @classmethod
    def _relation_target_match_score(cls, *, target_name: str, target_text: str, target_tokens: set[str]) -> float:
        normalized_target_name = " ".join(str(target_name or "").split()).strip().casefold()
        normalized_target_text = " ".join(str(target_text or "").split()).strip().casefold()
        if not normalized_target_name or not target_tokens:
            return 0.0
        name_tokens = cls._content_tokens(normalized_target_name)
        if normalized_target_name == normalized_target_text:
            return 1.0
        if normalized_target_text and normalized_target_text in normalized_target_name:
            return 0.95
        if target_tokens <= name_tokens:
            return 0.85
        if len(target_tokens) == 1:
            return cls._content_overlap(" ".join(sorted(target_tokens)), normalized_target_name)
        return 0.0

    @classmethod
    def _query_prefers_interaction_session(cls, query: str) -> bool:
        normalized = " ".join(str(query or "").split()).strip().casefold()
        if not normalized:
            return False
        if any(marker in normalized for marker in cls.SESSION_QUERY_MARKERS):
            return True
        tokens = set(re.findall(r"[A-Za-z0-9_']+", normalized))
        if "session" in tokens and {"this", "current", "latest"} & tokens:
            return True
        if "conversation" in tokens and {"this", "current"} & tokens:
            return True
        return "just" in tokens and "now" in tokens

    @classmethod
    def _query_prefers_project_scope(cls, query: str) -> bool:
        normalized = " ".join(str(query or "").split()).strip().casefold()
        if not normalized:
            return False
        if any(marker in normalized for marker in cls.PROJECT_QUERY_MARKERS):
            return True
        tokens = set(re.findall(r"[A-Za-z0-9_']+", normalized))
        return bool({"project", "workspace", "codebase", "repo"} & tokens)

    @classmethod
    def _query_prefers_identity_scope(cls, query: str) -> bool:
        normalized = " ".join(str(query or "").split()).strip().casefold()
        if not normalized:
            return False
        if any(marker in normalized for marker in cls.IDENTITY_QUERY_MARKERS):
            return True
        tokens = set(re.findall(r"[A-Za-z0-9_']+", normalized))
        if {"name", "live"} & tokens and {"my", "me", "i"} & tokens:
            return True
        return False

    @classmethod
    def _query_requests_archive_scope(cls, query: str) -> bool:
        normalized = " ".join(str(query or "").split()).strip().casefold()
        if not normalized:
            return False
        return any(marker in normalized for marker in cls.ARCHIVE_QUERY_MARKERS)

    @classmethod
    def _query_requests_archaeology_scope(cls, query: str) -> bool:
        normalized = " ".join(str(query or "").split()).strip().casefold()
        if not normalized:
            return False
        return any(marker in normalized for marker in cls.ARCHAEOLOGY_QUERY_MARKERS)

    @classmethod
    def _query_scope_intent(cls, query: str) -> str:
        if cls._query_requests_archaeology_scope(query):
            return cls.ARCHAEOLOGY_SCOPE
        if cls._query_requests_archive_scope(query):
            return cls.ARCHIVE_SCOPE
        if cls._query_prefers_interaction_session(query):
            return cls.THIS_SESSION_SCOPE
        if cls._query_prefers_recent_activity(query):
            return cls.RECENT_SCOPE
        if cls._query_prefers_identity_scope(query):
            return cls.IDENTITY_SCOPE
        if cls._query_prefers_project_scope(query):
            return cls.PROJECT_SCOPE
        return cls.TOPIC_SCOPE

    @classmethod
    def _query_prefers_recent_activity(cls, query: str) -> bool:
        normalized = " ".join(str(query or "").split()).strip().casefold()
        if not normalized:
            return False
        if any(marker in normalized for marker in cls.RECENT_QUERY_MARKERS):
            return True
        tokens = set(re.findall(r"[A-Za-z0-9_']+", normalized))
        if "recently" in tokens or "lately" in tokens:
            return True
        return bool({"recent", "recently"} & tokens and {"talk", "talked", "discuss", "discussing"} & tokens)

    @classmethod
    def _query_prefers_claim_answer(cls, query: str) -> bool:
        normalized = " ".join(str(query or "").split()).strip().casefold()
        if not normalized:
            return False
        if cls._query_prefers_interaction_session(query) or cls._query_prefers_recent_activity(query):
            return False
        if cls._query_prefers_project_scope(query):
            return False
        if any(normalized.startswith(marker) for marker in cls.CLAIM_QUERY_MARKERS):
            return True
        tokens = re.findall(r"[A-Za-z0-9_']+", normalized)
        if len(tokens) < 2:
            return False
        first_two = " ".join(tokens[:2])
        if first_two in {"what is", "what are", "who is", "who are", "where is", "where are", "where do", "which is", "which are"}:
            return True
        return "remember" in tokens and "about" in tokens

    @classmethod
    def _query_prefers_relationship_focus(cls, query: str) -> bool:
        normalized = " ".join(str(query or "").split()).strip().casefold()
        if not normalized:
            return False
        if any(marker in normalized for marker in cls.RELATIONSHIP_QUERY_MARKERS):
            return True
        tokens = set(re.findall(r"[A-Za-z0-9_']+", normalized))
        if {"how", "what"} & tokens and cls.RELATIONSHIP_VERB_TOKENS & tokens:
            return True
        if "between" in tokens and len(tokens & {"related", "relation", "relationship"}) > 0:
            return True
        return False

    @classmethod
    def _query_requests_evidence(cls, query: str) -> bool:
        normalized = " ".join(str(query or "").split()).strip().casefold()
        if not normalized:
            return False
        if any(marker in normalized for marker in cls.EVIDENCE_QUERY_MARKERS):
            return True
        tokens = set(re.findall(r"[A-Za-z0-9_']+", normalized))
        return bool({"evidence", "source", "sources", "provenance", "prove"} & tokens)

    def _preferred_session_id(self, connection, *, scope_key: str, query: str) -> str | None:
        if not self._query_prefers_interaction_session(query):
            return None
        session = self.sessions_repo.preferred_interaction(connection, scope_key=scope_key)
        if session is None:
            return None
        return str(session.session_id or "").strip() or None

    def _select_events(
        self,
        connection,
        *,
        scope_key: str,
        query: str,
        preferred_session_id: str | None,
        limit: int,
        recall_mode: str,
        session_focused: bool,
        recent_focused: bool,
        claim_focused: bool,
        identity_focused: bool,
        project_focused: bool,
    ) -> list[dict]:
        candidate_limit = max(limit * 4, limit)
        event_ids = [] if recent_focused else lexical_event_search(connection, scope_key=scope_key, query=query, limit=candidate_limit)
        fallback_events = (
            self.events_repo.get_many(connection, event_ids)
            if event_ids
            else self.events_repo.list_by_scope(connection, scope_key, limit=candidate_limit)
        )
        recent_events = self.events_repo.list_by_scope(connection, scope_key, limit=candidate_limit) if recent_focused else []
        preferred_events = (
            self.events_repo.list_by_session(connection, preferred_session_id, limit=candidate_limit)
            if preferred_session_id
            else []
        )
        if session_focused and preferred_session_id and recall_mode == "default" and preferred_events:
            candidates = list(preferred_events[:candidate_limit])
        else:
            candidates = self._merge_preferred(preferred_events + recent_events, fallback_events, key="event_id", limit=candidate_limit)
        session_kind_cache: dict[str, str] = {}
        if recent_focused and recall_mode == "default":
            live_candidates = [
                item
                for item in candidates
                if self._session_kind(connection, session_id=str(item.get("session_id") or ""), cache=session_kind_cache) != "import"
            ]
            if live_candidates:
                candidates = live_candidates
        if claim_focused and recall_mode == "default":
            matched_candidates = [
                item
                for item in candidates
                if self._event_overlap(query, item) >= 0.15
            ]
            if matched_candidates:
                candidates = matched_candidates
        if identity_focused and recall_mode == "default":
            identity_candidates = [
                item
                for item in candidates
                if self._content_overlap(query, self._event_search_text(item)) > 0.0
                or "name" in self._content_tokens(self._event_search_text(item))
                or "live" in self._content_tokens(self._event_search_text(item))
            ]
            if identity_candidates:
                candidates = identity_candidates
        if project_focused and recall_mode == "default":
            project_candidates = [
                item
                for item in candidates
                if self._event_has_project_signal(item)
            ]
            if project_candidates:
                candidates = project_candidates
        recency_ranks = self._recency_ranks(candidates, lambda item: str(item.get("timestamp") or item.get("ingested_at") or ""))
        ranked_events = []
        for item in candidates:
            session_bonus = 1.0 if preferred_session_id and item["session_id"] == preferred_session_id else 0.0
            recency_bonus = self._rank_bonus(
                recency_ranks.get(item["event_id"], len(candidates)),
                len(candidates),
                max_bonus=0.9 if recent_focused else 0.25,
            )
            session_kind = self._session_kind(connection, session_id=str(item.get("session_id") or ""), cache=session_kind_cache)
            quality_penalty = self._event_quality_penalty(
                item=item,
                recall_mode=recall_mode,
                session_kind=session_kind,
                session_focused=session_focused,
                recent_focused=recent_focused,
            )
            score = (
                score_item(
                    query=query,
                    text=self._event_search_text(item),
                    recency_bias=0.1,
                    importance=float(item.get("importance") or 0.0),
                    confidence=float(item.get("confidence") or 0.0),
                    editorial_state=None,
                    recall_mode=recall_mode,
                )
                + session_bonus
                + recency_bonus
                + quality_penalty
            )
            if project_focused:
                # Project-scoped recall should prefer explicitly project-shaped evidence.
                # This stays additive so generic topic/event recall behavior is unchanged.
                score += self._project_event_bonus(item)
            ranked_events.append(
                (
                    score,
                    item,
                )
            )
        ranked_events.sort(key=lambda item: item[0], reverse=True)
        selected = [self._event_for_display(item) for _, item in ranked_events]
        return self._dedupe_events_for_output(selected, limit=limit)

    @staticmethod
    def _merge_preferred(primary: list[dict], fallback: list[dict], *, key: str, limit: int) -> list[dict]:
        merged: list[dict] = []
        seen: set[str] = set()
        for item in list(primary or []) + list(fallback or []):
            item_key = str(item.get(key) or "").strip()
            if not item_key or item_key in seen:
                continue
            seen.add(item_key)
            merged.append(item)
            if len(merged) >= max(1, int(limit)):
                break
        return merged

    @staticmethod
    def _parse_iso(value: str) -> datetime:
        text = str(value or "").strip()
        if not text:
            return datetime.min.replace(tzinfo=timezone.utc)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _recency_ranks(self, items: list[dict], timestamp_getter) -> dict[str, int]:
        keyed: list[tuple[str, datetime]] = []
        for item in items:
            item_id = str(
                item.get("event_id")
                or item.get("claim_id")
                or item.get("episode_id")
                or item.get("entity_id")
                or item.get("relation_id")
                or ""
            ).strip()
            if not item_id:
                continue
            keyed.append((item_id, self._parse_iso(timestamp_getter(item))))
        keyed.sort(key=lambda pair: pair[1], reverse=True)
        return {item_id: index for index, (item_id, _) in enumerate(keyed)}

    @staticmethod
    def _rank_bonus(rank: int, total: int, *, max_bonus: float) -> float:
        if total <= 1:
            return float(max_bonus)
        bounded_rank = max(0, min(int(rank), total - 1))
        return float(max_bonus) * (1.0 - (bounded_rank / max(1, total - 1)))

    @classmethod
    def _strip_fillers(cls, text: str) -> str:
        normalized = " ".join((text or "").split()).strip()
        updated = normalized
        while True:
            lowered = updated.casefold()
            matched = next(
                (prefix for prefix in ("all right ", "alright ", "well ", "actually ", "so ", "but ", "like ", "okay ", "ok ") if lowered.startswith(prefix)),
                None,
            )
            if not matched:
                return updated
            updated = updated[len(matched) :].lstrip()

    @classmethod
    def _looks_question_like(cls, text: str) -> bool:
        normalized = cls._strip_fillers(text).casefold()
        if not normalized:
            return False
        if "?" in normalized:
            return True
        tokens = re.findall(r"[A-Za-z0-9_']+", normalized)
        if not tokens:
            return False
        return tokens[0] in cls.QUESTION_STARTERS

    @classmethod
    def _claim_is_low_quality(cls, item: dict) -> bool:
        canonical_claim = str(item.get("canonical_claim") or "")
        if cls._looks_question_like(canonical_claim):
            return True
        return int(item.get("evidence_count") or 0) < 2 and float(item.get("confidence") or 0.0) < 0.85 and len(canonical_claim) > 90

    @classmethod
    def _claim_quality_penalty(cls, *, item: dict, recall_mode: str) -> float:
        if recall_mode == "archive":
            return 0.0
        penalty = 0.0
        if int(item.get("evidence_count") or 0) < 2 and not bool(item.get("pinned")):
            penalty -= 0.35
        if cls._looks_question_like(str(item.get("canonical_claim") or "")):
            penalty -= 0.9
        return penalty

    @staticmethod
    def _identity_claim_bonus(*, item: dict) -> float:
        canonical = str(item.get("canonical_claim") or "").strip().casefold()
        predicate = str(item.get("predicate") or "").strip().casefold()
        object_text = str(item.get("object_text") or "").strip()
        if predicate in {"has name", "asserts"} and object_text:
            if "name" in canonical or "live" in canonical:
                return 0.45
        if canonical.startswith("operator has "):
            return 0.35
        return 0.0

    @staticmethod
    def _claim_query_bonus(*, item: dict, editorial: dict | None, claim_focused: bool, recent_focused: bool, topical_match: float) -> float:
        if not claim_focused:
            return 0.0
        bonus = 0.0
        remember_state = str((editorial or {}).get("remember_state") or "candidate")
        activation_state = str((editorial or {}).get("activation_state") or "suppressed")
        if remember_state == "remembered":
            bonus += 0.75
        elif remember_state == "candidate":
            bonus -= 0.1
        if activation_state == "active":
            bonus += 0.15
        if bool(item.get("pinned")):
            bonus += 0.15
        bonus += min(0.35, max(0.0, float(topical_match)) * 0.7)
        if recent_focused:
            bonus -= 0.2
        return bonus

    @classmethod
    def _content_tokens(cls, text: str) -> set[str]:
        tokens = {
            token
            for token in re.findall(r"[A-Za-z0-9_']+", str(text or "").casefold())
            if len(token) >= 3 and token not in cls.QUERY_CONTENT_STOPWORDS
        }
        return tokens

    @classmethod
    def _content_overlap(cls, query: str, text: str) -> float:
        query_tokens = cls._content_tokens(query)
        if not query_tokens:
            return 0.0
        text_tokens = cls._content_tokens(text)
        if not text_tokens:
            return 0.0
        return len(query_tokens & text_tokens) / len(query_tokens)

    @staticmethod
    def _topical_match(*, lexical_match: float, content_match: float, content_required: bool) -> float:
        if content_required and content_match <= 0.0:
            return lexical_match * 0.1
        if content_match > 0.0:
            return max(content_match, lexical_match * 0.5)
        return lexical_match

    @staticmethod
    def _event_search_text(item: dict) -> str:
        payload = item.get("structured_payload") or {}
        payload_raw_text = str(payload.get("raw_text") or "").strip() if isinstance(payload, dict) else ""
        return " ".join(
            part
            for part in (
                payload_raw_text,
                str(item.get("raw_text") or ""),
                str(item.get("normalized_text") or ""),
            )
            if part
        )

    @staticmethod
    def _entity_search_text(item: dict) -> str:
        aliases = item.get("aliases") or []
        alias_text = " ".join(str(alias).strip() for alias in aliases if str(alias).strip())
        return " ".join(
            part
            for part in (
                str(item.get("canonical_name") or "").strip(),
                alias_text,
            )
            if part
        )

    @staticmethod
    def _display_relation(*, item: dict, entity_map: dict[str, dict | None]) -> dict:
        src_entity = entity_map.get(str(item.get("src_entity_id") or "").strip())
        dst_entity = entity_map.get(str(item.get("dst_entity_id") or "").strip())
        editorial = item.get("editorial_state") or {}
        supporting_event_count = item.get("supporting_event_count")
        if supporting_event_count in {None, ""}:
            supporting_event_count = item.get("evidence_count")
        display = dict(item)
        display["relation"] = dict(item)
        display["src_entity"] = src_entity
        display["dst_entity"] = dst_entity
        display["counterparty_entity"] = None
        display["editorial_state"] = editorial
        display["supporting_event_count"] = int(supporting_event_count or 0)
        display["temporal"] = {
            "valid_from": item.get("valid_from"),
            "valid_until": item.get("valid_until"),
            "superseded_at": item.get("superseded_at"),
            "disputed_at": item.get("disputed_at"),
            "last_reinforced_at": item.get("last_reinforced_at"),
        }
        return display

    @staticmethod
    def _relation_search_text(item: dict) -> str:
        src_name = str(((item.get("src_entity") or {}) or {}).get("canonical_name") or "").strip()
        dst_name = str(((item.get("dst_entity") or {}) or {}).get("canonical_name") or "").strip()
        relation_type = str(item.get("relation_type") or "").strip().replace("_", " ")
        return " ".join(part for part in (src_name, relation_type, dst_name) if part)

    @classmethod
    def _relation_quality_penalty(
        cls,
        *,
        relation: dict,
        editorial: dict | None,
        recall_mode: str,
    ) -> float:
        if recall_mode == "archive":
            return 0.0
        relation_type = str(relation.get("relation_type") or "").strip().casefold()
        supporting_event_count = int(relation.get("supporting_event_count") or relation.get("evidence_count") or 0)
        remember_state = str((editorial or {}).get("remember_state") or "candidate").strip().casefold()
        penalty = 0.0
        if relation_type == "related_to":
            penalty -= 1.25
        if supporting_event_count <= 1 and remember_state != "remembered":
            penalty -= 0.25
        if float(relation.get("confidence") or 0.0) < 0.7:
            penalty -= 0.1
        return penalty

    @classmethod
    def _event_overlap(cls, query: str, item: dict) -> float:
        lexical_match = lexical_overlap(query, cls._event_search_text(item))
        content_match = cls._content_overlap(query, cls._event_search_text(item))
        return cls._topical_match(
            lexical_match=lexical_match,
            content_match=content_match,
            content_required=bool(cls._content_tokens(query)),
        )

    @classmethod
    def _event_has_project_signal(cls, item: dict) -> bool:
        search_text = cls._event_search_text(item).casefold()
        if not search_text:
            return False
        return any(marker in search_text for marker in cls.PROJECT_EVENT_MARKERS)

    @classmethod
    def _project_event_bonus(cls, item: dict) -> float:
        search_text = cls._event_search_text(item).casefold()
        if not search_text:
            return 0.0
        if any(marker in search_text for marker in cls.PROJECT_EVENT_MARKERS):
            return 0.7
        return 0.0

    @classmethod
    def _episode_quality_penalty(
        cls,
        *,
        episode: dict,
        event_count: int,
        recall_mode: str,
        session_bonus: float,
        recent_focused: bool,
    ) -> float:
        if recall_mode == "archive":
            return 0.0
        title = str(episode.get("title") or "").strip().casefold()
        penalty = 0.0
        if event_count < 2:
            penalty -= 0.25
        if title in cls.GENERIC_EPISODE_TITLES and event_count < 2 and session_bonus <= 0:
            penalty -= 0.45
        if recent_focused and title in cls.GENERIC_EPISODE_TITLES and session_bonus <= 0:
            penalty -= 0.35
        return penalty

    @classmethod
    def _entity_quality_penalty(
        cls,
        *,
        entity: dict,
        recall_mode: str,
        claim_focused: bool,
        recent_focused: bool,
    ) -> float:
        if recall_mode == "archive":
            return 0.0
        name = str(entity.get("canonical_name") or "").strip().casefold()
        mention_count = int(entity.get("mention_count") or 0)
        penalty = 0.0
        if name in cls.LOW_SIGNAL_ENTITY_NAMES:
            penalty -= 1.0
        if mention_count <= 1 and claim_focused:
            penalty -= 0.25
        if mention_count <= 1 and recent_focused:
            penalty -= 0.15
        return penalty

    @classmethod
    def _event_quality_penalty(
        cls,
        *,
        item: dict,
        recall_mode: str,
        session_kind: str,
        session_focused: bool,
        recent_focused: bool,
    ) -> float:
        if recall_mode == "archive":
            return 0.0
        payload = item.get("structured_payload") or {}
        route_domain = str(payload.get("route_domain") or "").strip().casefold()
        route_action = str(payload.get("route_action") or "").strip().casefold()
        text = " ".join((str(item.get("raw_text") or "")).split()).strip()
        lowered_text = text.casefold()
        penalty = 0.0
        if route_domain == "mcp" and route_action == "observe":
            penalty -= 1.1
        elif route_domain == "session_mode":
            penalty -= 0.5
        if lowered_text in cls.LOW_SIGNAL_EVENT_TEXTS:
            penalty -= 0.6
        payload_raw_text = " ".join((str(payload.get("raw_text") or "")).split()).strip()
        if payload_raw_text and payload_raw_text != text and lowered_text.startswith(cls.INTERPRETIVE_EVENT_PREFIXES):
            penalty -= 0.55
        token_count = len(re.findall(r"[A-Za-z0-9_']+", lowered_text))
        if token_count <= 2:
            penalty -= 0.35
        if session_kind == "import":
            penalty -= 0.35
            if recent_focused:
                penalty -= 0.8
            if session_focused:
                penalty -= 1.25
        return penalty

    @classmethod
    def _event_for_display(cls, item: dict) -> dict:
        payload = item.get("structured_payload") or {}
        if not isinstance(payload, dict):
            return item
        payload_raw_text = " ".join((str(payload.get("raw_text") or "")).split()).strip()
        payload_normalized_text = " ".join((str(payload.get("normalized_text") or "")).split()).strip()
        current_raw_text = " ".join((str(item.get("raw_text") or "")).split()).strip()
        if not payload_raw_text or payload_raw_text == current_raw_text:
            return item
        lowered_current = current_raw_text.casefold()
        if not lowered_current.startswith(cls.INTERPRETIVE_EVENT_PREFIXES):
            return item
        updated = dict(item)
        updated["raw_text"] = payload_raw_text
        if payload_normalized_text:
            updated["normalized_text"] = payload_normalized_text
        return updated

    @staticmethod
    def _dedupe_events_for_output(events: list[dict], *, limit: int) -> list[dict]:
        selected: list[dict] = []
        seen_raw: set[str] = set()
        for item in events:
            raw_key = " ".join((str(item.get("raw_text") or "")).split()).strip().casefold()
            if raw_key and raw_key in seen_raw:
                continue
            if raw_key:
                seen_raw.add(raw_key)
            selected.append(item)
            if len(selected) >= max(1, int(limit)):
                break
        return selected

    def _session_kind(self, connection, *, session_id: str, cache: dict[str, str]) -> str:
        clean_session_id = str(session_id or "").strip()
        if not clean_session_id:
            return ""
        if clean_session_id in cache:
            return cache[clean_session_id]
        session = self.sessions_repo.get(connection, clean_session_id)
        kind = str((session.kind if session else "") or "").strip().casefold()
        cache[clean_session_id] = kind
        return kind
