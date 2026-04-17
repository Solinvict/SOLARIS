# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.query import PatternProjectionRequest
from solaris.models.session import CloseSessionRequest, OpenSessionRequest

from conftest import ingest, make_event


def test_project_patterns_returns_computed_views_without_storing_artifacts(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    first = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id))
    second = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=first.session_id,
            timestamp="2026-04-16T13:00:00+00:00",
            idempotency_key="pattern-claim-1",
            raw_text="Solaris keeps archive and belief separate.",
            hints={"entities": ["Solaris"]},
            structured_payload={
                "claim": {
                    "subject_name": "Solaris",
                    "predicate": "keeps",
                    "object_text": "archive and belief separate",
                    "canonical_claim": "Solaris keeps archive and belief separate",
                    "confidence": 0.9,
                }
            },
        ),
        make_event(
            scope=scope,
            session_id=second.session_id,
            timestamp="2026-04-17T13:00:00+00:00",
            idempotency_key="pattern-claim-2",
            raw_text="Solaris keeps archive and belief separate.",
            hints={"entities": ["Solaris"]},
            structured_payload={
                "claim": {
                    "subject_name": "Solaris",
                    "predicate": "keeps",
                    "object_text": "archive and belief separate",
                    "canonical_claim": "Solaris keeps archive and belief separate",
                    "confidence": 0.9,
                }
            },
        ),
    )
    services["sessions"].close_session(CloseSessionRequest(session_id=first.session_id))
    services["sessions"].close_session(CloseSessionRequest(session_id=second.session_id))
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    with services["db"].transaction() as connection:
        before_states = len(services["editorial_repo"].list_states_by_scope(connection, scope_key=scope.key(), limit=100))

    result = services["patterns"].project(PatternProjectionRequest(scope=scope, limit=10))

    with services["db"].transaction() as connection:
        after_states = len(services["editorial_repo"].list_states_by_scope(connection, scope_key=scope.key(), limit=100))

    assert result["ok"] is True
    assert result["patterns"]
    assert result["meta"]["computed_view"] is True
    assert result["meta"]["stored"] is False
    assert before_states == after_states


def test_recurring_claim_cluster_requires_independent_support(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    first = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id))
    second = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=first.session_id,
            timestamp="2026-04-16T13:05:00+00:00",
            idempotency_key="pattern-recurring-1",
            raw_text="Solaris keeps archive and belief separate.",
            hints={"entities": ["Solaris"]},
            structured_payload={
                "claim": {
                    "subject_name": "Solaris",
                    "predicate": "keeps",
                    "object_text": "archive and belief separate",
                    "canonical_claim": "Solaris keeps archive and belief separate",
                    "confidence": 0.9,
                }
            },
        ),
        make_event(
            scope=scope,
            session_id=second.session_id,
            timestamp="2026-04-17T13:05:00+00:00",
            idempotency_key="pattern-recurring-2",
            raw_text="Solaris keeps archive and belief separate.",
            hints={"entities": ["Solaris"]},
            structured_payload={
                "claim": {
                    "subject_name": "Solaris",
                    "predicate": "keeps",
                    "object_text": "archive and belief separate",
                    "canonical_claim": "Solaris keeps archive and belief separate",
                    "confidence": 0.9,
                }
            },
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    result = services["patterns"].project(
        PatternProjectionRequest(scope=scope, limit=10, pattern_kinds=["recurring_claim_cluster"])
    )
    labels = {item["label"] for item in result["patterns"]}
    assert "Solaris keeps archive and belief separate" in labels


def test_low_confidence_pattern_projection_is_surfaced_explicitly(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    first = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id))
    second = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=first.session_id,
            timestamp="2026-04-16T13:10:00+00:00",
            idempotency_key="pattern-low-confidence-1",
            raw_text="We might want a graph-first roadmap.",
            hints={"entities": ["graph-first roadmap"]},
            structured_payload={
                "claim": {
                    "subject_name": "we",
                    "predicate": "might want",
                    "object_text": "a graph-first roadmap",
                    "canonical_claim": "We might want a graph-first roadmap",
                    "confidence": 0.45,
                }
            },
            importance=0.35,
            confidence=0.45,
        ),
        make_event(
            scope=scope,
            session_id=second.session_id,
            timestamp="2026-04-17T13:10:00+00:00",
            idempotency_key="pattern-low-confidence-2",
            raw_text="We might want a graph-first roadmap.",
            hints={"entities": ["graph-first roadmap"]},
            structured_payload={
                "claim": {
                    "subject_name": "we",
                    "predicate": "might want",
                    "object_text": "a graph-first roadmap",
                    "canonical_claim": "We might want a graph-first roadmap",
                    "confidence": 0.45,
                }
            },
            importance=0.35,
            confidence=0.45,
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    result = services["patterns"].project(
        PatternProjectionRequest(scope=scope, limit=10, pattern_kinds=["recurring_claim_cluster"])
    )
    pattern = next(item for item in result["patterns"] if item["label"] == "We might want a graph-first roadmap")
    assert pattern["confidence"] < 0.75
    assert pattern["source_confidence"] <= 0.5


def test_routine_repeated_operational_episode_does_not_dominate_pattern_output(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    first = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime", parent_session_id=runtime.session_id))
    second = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime", parent_session_id=runtime.session_id))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=first.session_id,
            timestamp="2026-04-16T13:15:00+00:00",
            kind="trading_execution_plan",
            idempotency_key="pattern-routine-1",
            raw_text="Execution plan: planner merged active lanes.",
            hints={"episode_hint": "execution-cycle"},
            structured_payload={"origin_event": "execution_plan", "journal_payload": {"planner": "dual-lane"}},
        ),
        make_event(
            scope=scope,
            session_id=second.session_id,
            timestamp="2026-04-17T13:15:00+00:00",
            kind="trading_execution_plan",
            idempotency_key="pattern-routine-2",
            raw_text="Execution plan: planner merged active lanes.",
            hints={"episode_hint": "execution-cycle"},
            structured_payload={"origin_event": "execution_plan", "journal_payload": {"planner": "dual-lane"}},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    result = services["patterns"].project(
        PatternProjectionRequest(scope=scope, limit=10, pattern_kinds=["recurring_episode_motif"])
    )
    labels = {item["label"] for item in result["patterns"]}
    assert "execution-cycle" not in labels


def test_trade_outcome_review_is_treated_as_routine_episode_motif(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    first = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime", parent_session_id=runtime.session_id))
    second = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime", parent_session_id=runtime.session_id))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=first.session_id,
            timestamp="2026-04-16T13:17:00+00:00",
            kind="trading_outcome",
            idempotency_key="pattern-outcome-routine-1",
            raw_text="Outcome review: lane closed with expected result.",
            hints={"episode_hint": "trade-outcome-review"},
            structured_payload={"origin_event": "thesis_outcome", "journal_payload": {"symbol": "BTC"}},
        ),
        make_event(
            scope=scope,
            session_id=second.session_id,
            timestamp="2026-04-17T13:17:00+00:00",
            kind="trading_outcome",
            idempotency_key="pattern-outcome-routine-2",
            raw_text="Outcome review: lane closed with expected result.",
            hints={"episode_hint": "trade-outcome-review"},
            structured_payload={"origin_event": "thesis_outcome", "journal_payload": {"symbol": "ETH"}},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    result = services["patterns"].project(
        PatternProjectionRequest(scope=scope, limit=10, pattern_kinds=["recurring_episode_motif"])
    )
    labels = {item["label"] for item in result["patterns"]}
    assert "trade-outcome-review" not in labels


def test_low_signal_single_word_episode_motif_is_suppressed(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    first = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id))
    second = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=first.session_id,
            timestamp="2026-04-16T13:18:00+00:00",
            idempotency_key="pattern-low-signal-episode-1",
            raw_text="We discussed Solaris architecture.",
            hints={"episode_hint": "solaris"},
        ),
        make_event(
            scope=scope,
            session_id=second.session_id,
            timestamp="2026-04-17T13:18:00+00:00",
            idempotency_key="pattern-low-signal-episode-2",
            raw_text="We discussed Solaris architecture again.",
            hints={"episode_hint": "solaris"},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    result = services["patterns"].project(
        PatternProjectionRequest(scope=scope, limit=10, pattern_kinds=["recurring_episode_motif"])
    )
    labels = {item["label"] for item in result["patterns"]}
    assert "solaris" not in labels


def test_projected_patterns_walk_back_to_supporting_artifacts_and_events(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    first = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id))
    second = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=first.session_id,
            timestamp="2026-04-16T13:20:00+00:00",
            kind="decision",
            idempotency_key="pattern-rel-1",
            raw_text="Decision: Solaris uses SQLite for persistence.",
            hints={"entities": ["Solaris", "SQLite"], "relations": [{"src": "Solaris", "dst": "SQLite", "type": "uses"}]},
        ),
        make_event(
            scope=scope,
            session_id=first.session_id,
            timestamp="2026-04-16T13:21:00+00:00",
            kind="decision",
            idempotency_key="pattern-rel-1b",
            raw_text="Decision: Solaris uses FTS5 for lexical retrieval.",
            hints={"entities": ["Solaris", "FTS5"], "relations": [{"src": "Solaris", "dst": "FTS5", "type": "uses"}]},
        ),
        make_event(
            scope=scope,
            session_id=second.session_id,
            timestamp="2026-04-17T13:20:00+00:00",
            kind="decision",
            idempotency_key="pattern-rel-2",
            raw_text="Decision: Solaris uses SQLite for persistence.",
            hints={"entities": ["Solaris", "SQLite"], "relations": [{"src": "Solaris", "dst": "SQLite", "type": "uses"}]},
        ),
        make_event(
            scope=scope,
            session_id=second.session_id,
            timestamp="2026-04-17T13:21:00+00:00",
            kind="decision",
            idempotency_key="pattern-rel-2b",
            raw_text="Decision: Solaris uses FTS5 for lexical retrieval.",
            hints={"entities": ["Solaris", "FTS5"], "relations": [{"src": "Solaris", "dst": "FTS5", "type": "uses"}]},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    result = services["patterns"].project(
        PatternProjectionRequest(scope=scope, limit=10, pattern_kinds=["relation_cluster", "temporal_recurrence"])
    )
    assert result["patterns"]
    for pattern in result["patterns"]:
        assert pattern["sample_event_ids"]
        assert pattern["support_claim_ids"] or pattern["support_episode_ids"] or pattern["support_relation_ids"]


def test_single_repeated_relation_edge_does_not_become_relation_cluster(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    first = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id))
    second = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=first.session_id,
            timestamp="2026-04-16T13:30:00+00:00",
            kind="decision",
            idempotency_key="pattern-single-rel-1",
            raw_text="Decision: Solaris uses SQLite for persistence.",
            hints={"entities": ["Solaris", "SQLite"], "relations": [{"src": "Solaris", "dst": "SQLite", "type": "uses"}]},
        ),
        make_event(
            scope=scope,
            session_id=second.session_id,
            timestamp="2026-04-17T13:30:00+00:00",
            kind="decision",
            idempotency_key="pattern-single-rel-2",
            raw_text="Decision: Solaris uses SQLite for persistence.",
            hints={"entities": ["Solaris", "SQLite"], "relations": [{"src": "Solaris", "dst": "SQLite", "type": "uses"}]},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    result = services["patterns"].project(
        PatternProjectionRequest(scope=scope, limit=10, pattern_kinds=["relation_cluster"])
    )
    labels = {item["label"] for item in result["patterns"]}
    assert "Solaris uses cluster" not in labels


def test_base_patterns_rank_ahead_of_temporal_recurrence_variants(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    first = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id))
    second = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=first.session_id,
            timestamp="2026-04-16T13:40:00+00:00",
            kind="decision",
            idempotency_key="pattern-rank-order-1",
            raw_text="Decision: Solaris uses SQLite for persistence.",
            hints={"entities": ["Solaris", "SQLite"], "relations": [{"src": "Solaris", "dst": "SQLite", "type": "uses"}]},
        ),
        make_event(
            scope=scope,
            session_id=first.session_id,
            timestamp="2026-04-16T13:41:00+00:00",
            kind="decision",
            idempotency_key="pattern-rank-order-1b",
            raw_text="Decision: Solaris uses FTS5 for lexical retrieval.",
            hints={"entities": ["Solaris", "FTS5"], "relations": [{"src": "Solaris", "dst": "FTS5", "type": "uses"}]},
        ),
        make_event(
            scope=scope,
            session_id=second.session_id,
            timestamp="2026-04-17T13:40:00+00:00",
            kind="decision",
            idempotency_key="pattern-rank-order-2",
            raw_text="Decision: Solaris uses SQLite for persistence.",
            hints={"entities": ["Solaris", "SQLite"], "relations": [{"src": "Solaris", "dst": "SQLite", "type": "uses"}]},
        ),
        make_event(
            scope=scope,
            session_id=second.session_id,
            timestamp="2026-04-17T13:41:00+00:00",
            kind="decision",
            idempotency_key="pattern-rank-order-2b",
            raw_text="Decision: Solaris uses FTS5 for lexical retrieval.",
            hints={"entities": ["Solaris", "FTS5"], "relations": [{"src": "Solaris", "dst": "FTS5", "type": "uses"}]},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    result = services["patterns"].project(PatternProjectionRequest(scope=scope, limit=10))
    labels = [item["label"] for item in result["patterns"]]
    assert "Solaris uses cluster" in labels
    assert "Temporal recurrence: Solaris uses cluster" in labels
    assert labels.index("Solaris uses cluster") < labels.index("Temporal recurrence: Solaris uses cluster")
