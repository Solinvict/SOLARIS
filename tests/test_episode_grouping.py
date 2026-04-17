# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.session import OpenSessionRequest

from conftest import ingest, make_event, query


def test_episode_grouping(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="ep-1",
            raw_text="We paused coordination debugging.",
            hints={"episode_hint": "coordination-debugging", "entities": ["coordination"]},
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:05:00+00:00",
            idempotency_key="ep-2",
            raw_text="Coordination debugging still blocks progress.",
            hints={"episode_hint": "coordination-debugging", "entities": ["coordination"]},
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:10:00+00:00",
            idempotency_key="ep-3",
            raw_text="Now we are discussing retrieval ranking.",
            hints={"episode_hint": "retrieval-ranking", "entities": ["retrieval ranking"]},
        ),
    )
    bundle = query(services, scope=scope, text="coordination", recall_mode="deep")
    titles = [item["title"] for item in bundle["episodes"]]
    assert "coordination-debugging" in titles
    assert any(title == "retrieval-ranking" for title in titles)


def test_episode_title_ignores_generic_hint_and_uses_payload_raw_context(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:15:00+00:00",
            idempotency_key="ep-payload-raw",
            raw_text="The user is asking what Solaris means.",
            normalized_text="the user is asking what solaris means",
            structured_payload={
                "raw_text": "what is Solaris",
                "normalized_text": "what is solaris",
                "interpreted_text": "The user is asking what Solaris means.",
            },
            hints={"episode_hint": "conversation"},
            confidence=0.95,
        ),
    )
    bundle = query(services, scope=scope, text="Solaris", recall_mode="deep")
    titles = [item["title"] for item in bundle["episodes"]]
    assert "solaris" in titles


def test_related_episode_grouping_spans_adjacent_interactions_under_runtime_continuity(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    interaction_a = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    interaction_b = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=interaction_a.session_id,
            timestamp="2026-04-10T09:20:00+00:00",
            idempotency_key="ep-runtime-related-a",
            raw_text="I think Solaris should keep archive and belief separate.",
            hints={
                "episode_hint": "Solaris memory separation design",
                "entities": ["Solaris", "archive", "belief"],
            },
        ),
        make_event(
            scope=scope,
            session_id=interaction_b.session_id,
            timestamp="2026-04-10T09:22:00+00:00",
            idempotency_key="ep-runtime-related-b",
            raw_text="That separation matters because memory should not rewrite archived records.",
            hints={
                "episode_hint": "archive belief write separation",
                "entities": ["Solaris"],
            },
        ),
    )
    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=10)
        merged = next(item for item in episodes if item["title"] == "Solaris memory separation design")
        event_ids = services["episodes_repo"].get_event_ids(connection, merged["episode_id"])
    assert merged["session_id"] == runtime.session_id
    assert len(event_ids) == 2
