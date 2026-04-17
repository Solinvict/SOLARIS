# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.derive.relations import derive_relations
from solaris.models.query import EntityRequest
from solaris.models.session import OpenSessionRequest

from conftest import ingest, make_event, query


def test_relation_derivation_requires_hint_or_lexical_cue(scope):
    event = make_event(
        scope=scope,
        session_id="sess_graph_plain",
        timestamp="2026-04-16T12:00:00+00:00",
        idempotency_key="graph-rel-no-cue",
        raw_text="Solaris SQLite",
        normalized_text="solaris sqlite",
    )
    relations = derive_relations(
        event,
        [{"name": "Solaris"}, {"name": "SQLite"}],
    )
    assert relations == []


def test_relation_derivation_respects_explicit_hints(scope):
    event = make_event(
        scope=scope,
        session_id="sess_graph_hint",
        timestamp="2026-04-16T12:01:00+00:00",
        idempotency_key="graph-rel-hint",
        raw_text="Solaris uses SQLite.",
        hints={"relations": [{"src": "Solaris", "dst": "SQLite", "type": "uses", "confidence": 0.93}]},
    )
    relations = derive_relations(
        event,
        [{"name": "Solaris"}, {"name": "SQLite"}],
    )
    assert relations == [{"src": "Solaris", "dst": "SQLite", "type": "uses", "confidence": 0.93}]


def test_relation_derivation_ignores_hints_without_allowed_type(scope):
    event = make_event(
        scope=scope,
        session_id="sess_graph_hint_missing_type",
        timestamp="2026-04-16T12:01:30+00:00",
        idempotency_key="graph-rel-hint-missing-type",
        raw_text="Solaris SQLite",
        hints={"relations": [{"src": "Solaris", "dst": "SQLite"}]},
    )
    relations = derive_relations(
        event,
        [{"name": "Solaris"}, {"name": "SQLite"}],
    )
    assert relations == []


def test_relation_derivation_supports_lexical_cues(scope):
    cases = [
        ("Solaris blocked by SQLite locks.", "blocked_by", "Solaris", "SQLite"),
        ("Solaris depends on SQLite.", "depends_on", "Solaris", "SQLite"),
        ("Solaris failed due to SQLite contention.", "failed_due_to", "Solaris", "SQLite"),
        ("SQLite causes Solaris errors.", "causes", "SQLite", "Solaris"),
        ("Solaris uses SQLite.", "uses", "Solaris", "SQLite"),
        ("Solaris is built on SQLite and graph memory.", "depends_on", "Solaris", "SQLite"),
        ("Solaris is powered by SQLite.", "uses", "Solaris", "SQLite"),
    ]
    for index, (raw_text, relation_type, src, dst) in enumerate(cases, start=1):
        event = make_event(
            scope=scope,
            session_id=f"sess_graph_lex_{index}",
            timestamp=f"2026-04-16T12:0{index}:00+00:00",
            idempotency_key=f"graph-rel-lex-{index}",
            raw_text=raw_text,
            normalized_text=raw_text.casefold(),
        )
        relations = derive_relations(
            event,
            [{"name": "Solaris"}, {"name": "SQLite"}] if src == "Solaris" else [{"name": "SQLite"}, {"name": "Solaris"}],
        )
        assert relations == [{"src": src, "dst": dst, "type": relation_type, "confidence": 0.65}]


def test_relation_derivation_selects_pair_around_cue(scope):
    event = make_event(
        scope=scope,
        session_id="sess_graph_pair_selection",
        timestamp="2026-04-16T12:06:00+00:00",
        idempotency_key="graph-rel-pair-selection",
        raw_text="For persistence Solaris is built on SQLite and graph memory.",
        normalized_text="for persistence solaris is built on sqlite and graph memory",
    )
    relations = derive_relations(
        event,
        [{"name": "persistence"}, {"name": "Solaris"}, {"name": "SQLite"}, {"name": "graph memory"}],
    )
    assert relations == [{"src": "Solaris", "dst": "SQLite", "type": "depends_on", "confidence": 0.65}]


def test_single_evidence_lexical_relation_stays_candidate(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T12:10:00+00:00",
            idempotency_key="graph-rel-candidate",
            raw_text="Solaris uses SQLite.",
            normalized_text="solaris uses sqlite",
            hints={"entities": ["Solaris", "SQLite"]},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 20, "boundary")

    with services["db"].transaction() as connection:
        relation = services["relations_repo"].list_by_scope(connection, scope.key(), limit=10)[0]
        state = services["editorial_repo"].get_state(connection, artifact_type="relation", artifact_id=relation["relation_id"])

    assert relation["relation_type"] == "uses"
    assert state["remember_state"] == "candidate"
    assert state["activation_state"] == "suppressed"


def test_single_evidence_decision_relation_can_promote(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T12:11:00+00:00",
            idempotency_key="graph-rel-decision",
            kind="decision",
            raw_text="Decision: Solaris uses SQLite for persistence.",
            normalized_text="decision solaris uses sqlite for persistence",
            hints={"entities": ["Solaris", "SQLite"], "relations": [{"src": "Solaris", "dst": "SQLite", "type": "uses"}]},
            importance=0.95,
            confidence=0.95,
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 20, "boundary")

    with services["db"].transaction() as connection:
        relation = services["relations_repo"].list_by_scope(connection, scope.key(), limit=10)[0]
        state = services["editorial_repo"].get_state(connection, artifact_type="relation", artifact_id=relation["relation_id"])

    assert relation["relation_type"] == "uses"
    assert state["remember_state"] == "remembered"
    assert state["activation_state"] == "active"


def test_entity_service_returns_enriched_relation_neighborhood(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T12:12:00+00:00",
            idempotency_key="graph-entity-neighborhood",
            raw_text="Solaris uses SQLite.",
            hints={"entities": ["Solaris", "SQLite"], "relations": [{"src": "Solaris", "dst": "SQLite", "type": "uses"}]},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 20, "boundary")

    result = services["entity"].resolve(EntityRequest(scope=scope, canonical_name="Solaris"))
    assert result["ok"] is True
    assert result["relations"]
    relation = result["relations"][0]
    assert relation["relation_type"] == "uses"
    assert relation["counterparty_entity"]["canonical_name"] == "SQLite"
    assert relation["editorial_state"] is not None
    assert relation["supporting_event_count"] >= 1
    assert "valid_from" in relation["temporal"]


def test_entity_service_hides_suppressed_related_to_relations(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T12:12:30+00:00",
            idempotency_key="graph-entity-related-to-hidden",
            raw_text="Solaris and SQLite.",
            hints={"entities": ["Solaris", "SQLite"], "relations": [{"src": "Solaris", "dst": "SQLite", "type": "related_to"}]},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 20, "boundary")

    result = services["entity"].resolve(EntityRequest(scope=scope, canonical_name="Solaris"))
    assert result["ok"] is True
    assert result["relations"] == []


def test_entity_timeline_includes_episodes_linked_by_event_overlap(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T12:13:00+00:00",
            idempotency_key="graph-episode-link-1",
            raw_text="Solaris uses SQLite for persistence.",
            hints={"entities": ["Solaris", "SQLite"], "episode_hint": "persistence-architecture"},
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T12:14:00+00:00",
            idempotency_key="graph-episode-link-2",
            raw_text="SQLite keeps the persistence layer grounded.",
            hints={"entities": ["SQLite"], "episode_hint": "persistence-architecture"},
        ),
    )
    with services["db"].transaction() as connection:
        solaris_entity = services["entities_repo"].resolve(connection, scope_key=scope.key(), canonical_name="Solaris")
    timeline = services["timeline"].timeline(
        type("Req", (), {"scope": scope, "entity_id": solaris_entity["entity_id"], "episode_id": None, "limit": 20})()
    )
    episode_titles = {item["title"] for item in timeline["episodes"]}
    assert "persistence-architecture" in episode_titles


def test_entity_timeline_hides_suppressed_related_to_relations(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T12:14:30+00:00",
            idempotency_key="graph-timeline-related-to-hidden",
            raw_text="Solaris and SQLite.",
            hints={"entities": ["Solaris", "SQLite"], "relations": [{"src": "Solaris", "dst": "SQLite", "type": "related_to"}]},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 20, "boundary")

    with services["db"].transaction() as connection:
        solaris_entity = services["entities_repo"].resolve(connection, scope_key=scope.key(), canonical_name="Solaris")
    timeline = services["timeline"].timeline(
        type("Req", (), {"scope": scope, "entity_id": solaris_entity["entity_id"], "episode_id": None, "limit": 20})()
    )
    assert timeline["relations"] == []


def test_relationship_shaped_query_surfaces_relations(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T12:15:00+00:00",
            idempotency_key="graph-query-rel-1",
            kind="decision",
            raw_text="Decision: Solaris uses SQLite for persistence.",
            normalized_text="decision solaris uses sqlite for persistence",
            hints={"entities": ["Solaris", "SQLite"], "relations": [{"src": "Solaris", "dst": "SQLite", "type": "uses"}]},
            importance=0.95,
            confidence=0.95,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T12:16:00+00:00",
            idempotency_key="graph-query-rel-2",
            raw_text="Solaris persistence architecture stays grounded on SQLite.",
            hints={"entities": ["Solaris", "SQLite"], "episode_hint": "persistence-architecture"},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 20, "boundary")

    bundle = query(services, scope=scope, text="what uses SQLite", recall_mode="default")
    assert bundle["meta"]["relation_focus_applied"] is True
    assert bundle["relations"]
    assert bundle["relations"][0]["relation_type"] == "uses"
    assert bundle["episodes"]
    assert any(item["artifact_type"] == "relation" for item in bundle["explanations"])


def test_relationship_shaped_query_can_surface_candidate_relations(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T12:17:00+00:00",
            idempotency_key="graph-query-candidate-rel",
            raw_text="Solaris uses SQLite for persistence.",
            normalized_text="solaris uses sqlite for persistence",
            hints={"entities": ["Solaris", "SQLite"]},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 20, "boundary")

    bundle = query(services, scope=scope, text="what uses SQLite", recall_mode="default")
    assert bundle["meta"]["relation_focus_applied"] is True
    assert bundle["meta"]["relation_candidate_relaxation_applied"] is True
    assert bundle["relations"]
    assert bundle["relations"][0]["relation_type"] == "uses"


def test_relationship_shaped_query_prefers_matching_target_side(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T12:18:00+00:00",
            idempotency_key="graph-query-target-1",
            raw_text="Dual lane strategy uses BTC.",
            normalized_text="dual lane strategy uses btc",
            hints={"entities": ["dual lane strategy", "BTC"]},
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T12:19:00+00:00",
            idempotency_key="graph-query-target-2",
            raw_text="Trading engine uses OKX.",
            normalized_text="trading engine uses okx",
            hints={"entities": ["trading engine", "OKX"]},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 20, "boundary")

    bundle = query(services, scope=scope, text="what uses BTC", recall_mode="default")
    assert bundle["meta"]["relation_focus_applied"] is True
    assert bundle["relations"]
    top_relation = bundle["relations"][0]
    assert top_relation["relation_type"] == "uses"
    assert (top_relation.get("dst_entity") or {}).get("canonical_name") == "BTC"


def test_relationship_shaped_query_can_find_older_matching_relation_outside_recent_window(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T12:20:00+00:00",
            idempotency_key="graph-query-older-okx",
            kind="decision",
            raw_text="Trading engine uses OKX.",
            normalized_text="trading engine uses okx",
            hints={"entities": ["trading engine", "OKX"], "relations": [{"src": "trading engine", "dst": "OKX", "type": "uses"}]},
            importance=0.95,
            confidence=0.95,
        ),
    )
    for index in range(35):
        minute = 21 + index
        ingest(
            services,
            make_event(
                scope=scope,
                session_id=session.session_id,
                timestamp=f"2026-04-16T12:{minute:02d}:00+00:00",
                idempotency_key=f"graph-query-recent-{index}",
                kind="decision",
                raw_text=f"Strategy {index} uses asset {index}.",
                normalized_text=f"strategy {index} uses asset {index}",
                hints={
                    "entities": [f"strategy_{index}", f"asset_{index}"],
                    "relations": [{"src": f"strategy_{index}", "dst": f"asset_{index}", "type": "uses"}],
                },
                importance=0.9,
                confidence=0.9,
            ),
        )
    services["review"].run_review(scope, None, "default_v1", 200, "boundary")

    bundle = query(services, scope=scope, text="what uses OKX", recall_mode="default")
    assert bundle["meta"]["relation_focus_applied"] is True
    assert bundle["relations"]
    top_relation = bundle["relations"][0]
    assert top_relation["relation_type"] == "uses"
    assert (top_relation.get("dst_entity") or {}).get("canonical_name") == "OKX"
    assert (top_relation.get("src_entity") or {}).get("canonical_name") == "trading engine"


def test_relationship_shaped_query_supports_reason_code_targets(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T13:10:00+00:00",
            idempotency_key="graph-query-reason-code",
            kind="failure",
            raw_text="BTC blocked by crypto_liquidity_veto.",
            normalized_text="btc blocked by crypto_liquidity_veto",
            hints={
                "entities": ["BTC", "crypto_liquidity_veto"],
                "relations": [{"src": "BTC", "dst": "crypto_liquidity_veto", "type": "blocked_by"}],
            },
            importance=0.95,
            confidence=0.95,
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    bundle = query(services, scope=scope, text="what is blocked by crypto_liquidity_veto", recall_mode="default")
    assert bundle["meta"]["relation_focus_applied"] is True
    assert bundle["relations"]
    top_relation = bundle["relations"][0]
    assert top_relation["relation_type"] == "blocked_by"
    assert (top_relation.get("dst_entity") or {}).get("canonical_name") == "crypto_liquidity_veto"
    assert (top_relation.get("src_entity") or {}).get("canonical_name") == "BTC"


def test_relationship_shaped_query_prefers_exact_multi_token_target(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T13:15:00+00:00",
            kind="decision",
            idempotency_key="graph-query-multitoken-1",
            raw_text="Decision: graph memory depends on fractal memory.",
            normalized_text="decision graph memory depends on fractal memory",
            hints={
                "entities": ["graph memory", "fractal memory"],
                "relations": [{"src": "graph memory", "dst": "fractal memory", "type": "depends_on"}],
            },
            importance=0.95,
            confidence=0.95,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-16T13:16:00+00:00",
            kind="decision",
            idempotency_key="graph-query-multitoken-2",
            raw_text="Decision: fractal memory depends on graph memory.",
            normalized_text="decision fractal memory depends on graph memory",
            hints={
                "entities": ["fractal memory", "graph memory"],
                "relations": [{"src": "fractal memory", "dst": "graph memory", "type": "depends_on"}],
            },
            importance=0.95,
            confidence=0.95,
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    bundle = query(services, scope=scope, text="what depends on fractal memory", recall_mode="default")
    assert bundle["meta"]["relation_focus_applied"] is True
    assert bundle["relations"]
    top_relation = bundle["relations"][0]
    assert top_relation["relation_type"] == "depends_on"
    assert (top_relation.get("src_entity") or {}).get("canonical_name") == "graph memory"
    assert (top_relation.get("dst_entity") or {}).get("canonical_name") == "fractal memory"
