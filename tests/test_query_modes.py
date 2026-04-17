# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.session import CloseSessionRequest, OpenSessionRequest

from conftest import ingest, make_event, query


def test_query_modes(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="mode-1",
            raw_text="Solaris is a memory substrate.",
            hints={"entities": ["Solaris"]},
        ),
    )
    default_bundle = query(services, scope=scope, text="Solaris", recall_mode="default")
    deep_bundle = query(services, scope=scope, text="Solaris", recall_mode="deep")
    archive_bundle = query(services, scope=scope, text="Solaris", recall_mode="archive")
    assert default_bundle["claims"] == []
    assert deep_bundle["claims"]
    assert archive_bundle["events"]


def test_query_prefers_latest_interaction_for_this_session(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    first = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=first.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="session-old",
            raw_text="We talked about older architecture notes.",
        ),
    )
    services["sessions"].close_session(CloseSessionRequest(session_id=first.session_id))

    latest = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=latest.session_id,
            timestamp="2026-04-10T09:05:00+00:00",
            idempotency_key="session-new",
            raw_text="We talked about the current session behavior.",
        ),
    )
    services["sessions"].close_session(CloseSessionRequest(session_id=latest.session_id))
    services["review"].run_review(scope, latest.session_id, "default_v1")

    bundle = query(services, scope=scope, text="what did we talk about in this session", recall_mode="default")
    assert bundle["events"]
    assert bundle["meta"]["scope_intent"] == "this_session"
    assert bundle["meta"]["session_narrowing_applied"] is True
    assert bundle["events"][0]["session_id"] == latest.session_id
    assert bundle["events"][0]["raw_text"] == "We talked about the current session behavior."


def test_query_prefers_current_open_interaction_for_this_session(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    closed = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=closed.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="session-closed",
            raw_text="We talked about yesterday's session.",
        ),
    )
    services["sessions"].close_session(CloseSessionRequest(session_id=closed.session_id))

    current = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=current.session_id,
            timestamp="2026-04-10T09:10:00+00:00",
            idempotency_key="session-current",
            raw_text="We are talking about the live current session.",
        ),
    )

    bundle = query(services, scope=scope, text="what are we talking about in this session", recall_mode="default")
    assert bundle["events"]
    assert bundle["events"][0]["session_id"] == current.session_id
    assert bundle["events"][0]["raw_text"] == "We are talking about the live current session."


def test_recent_query_prefers_recent_events_over_old_lexical_match(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    old_session = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=old_session.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="recent-old",
            raw_text="Please generalize what we talked about in old conversations.",
            structured_payload={"route_domain": "mcp", "route_action": "observe"},
        ),
    )
    services["sessions"].close_session(CloseSessionRequest(session_id=old_session.session_id))

    current_session = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=current_session.session_id,
            timestamp="2026-04-10T09:10:00+00:00",
            idempotency_key="recent-new",
            raw_text="We are discussing how Solaris should remember selectively.",
        ),
    )
    services["sessions"].close_session(CloseSessionRequest(session_id=current_session.session_id))

    bundle = query(services, scope=scope, text="what have we been discussing recently", recall_mode="default")
    assert bundle["events"]
    assert bundle["events"][0]["session_id"] == current_session.session_id
    assert bundle["events"][0]["raw_text"] == "We are discussing how Solaris should remember selectively."


def test_import_sessions_do_not_override_interaction_session_queries(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    imported = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="import", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=imported.session_id,
            timestamp="2026-04-10T08:55:00+00:00",
            idempotency_key="import-history",
            raw_text="We talked about old imported history.",
        ),
    )
    services["sessions"].close_session(CloseSessionRequest(session_id=imported.session_id))

    interaction = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=interaction.session_id,
            timestamp="2026-04-10T09:10:00+00:00",
            idempotency_key="interaction-live",
            raw_text="We are talking about the current live interaction.",
        ),
    )

    bundle = query(services, scope=scope, text="what did we talk about in this session", recall_mode="default")
    assert bundle["events"]
    assert bundle["events"][0]["session_id"] == interaction.session_id
    assert bundle["events"][0]["raw_text"] == "We are talking about the current live interaction."


def test_recent_query_prefers_live_events_over_import_history(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    imported = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="import", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=imported.session_id,
            timestamp="2026-04-10T09:05:00+00:00",
            idempotency_key="import-recent-memory",
            raw_text="Remember this I live in Example City.",
            structured_payload={"route_domain": "memory", "route_action": "remember_note"},
        ),
    )
    services["sessions"].close_session(CloseSessionRequest(session_id=imported.session_id))

    live_interaction = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=live_interaction.session_id,
            timestamp="2026-04-10T09:10:00+00:00",
            idempotency_key="live-recent-memory",
            raw_text="We are discussing Solaris shadow-mode validation right now.",
        ),
    )
    services["sessions"].close_session(CloseSessionRequest(session_id=live_interaction.session_id))

    bundle = query(services, scope=scope, text="what have we discussed recently", recall_mode="default")
    assert bundle["events"]
    assert bundle["events"][0]["session_id"] == live_interaction.session_id
    assert all(event["session_id"] != imported.session_id for event in bundle["events"])


def test_fact_query_prefers_remembered_claim_over_raw_event_trace(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="fact-query-memory",
            raw_text="Remember this I live in Example City",
            normalized_text="remember this i live in example city",
            kind="note",
            structured_payload={
                "route_domain": "memory",
                "route_action": "remember_note",
                "claim": {
                    "predicate": "asserts",
                    "object_text": "I live in Example City",
                    "canonical_claim": "I live in Example City",
                    "confidence": 0.9,
                    "pinned": False,
                },
            },
            importance=0.9,
            confidence=0.95,
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    bundle = query(services, scope=scope, text="where do I live", recall_mode="default")
    assert bundle["claims"]
    assert bundle["meta"]["scope_intent"] == "identity"
    assert bundle["meta"]["identity_focus_applied"] is True
    assert bundle["claims"][0]["canonical_claim"] == "I live in Example City"
    assert bundle["events"] == []
    assert bundle["entities"] == []
    assert bundle["episodes"] == []

    unrelated = query(services, scope=scope, text="what is Solaris", recall_mode="default")
    assert unrelated["claims"] == []


def test_query_detects_archaeology_scope_and_relaxes_archive_penalties(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:21:00+00:00",
            idempotency_key="archive-trail",
            raw_text="We discussed the early Solaris archive trail.",
        ),
    )

    bundle = query(
        services,
        scope=scope,
        text="show me everything including retired about Solaris",
        recall_mode="default",
    )
    assert bundle["meta"]["scope_intent"] == "archaeology"
    assert bundle["meta"]["archive_relaxation_applied"] is True


def test_session_query_prefers_displaying_original_raw_text_when_event_is_interpretive(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    interaction = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=interaction.session_id,
            timestamp="2026-04-10T09:20:00+00:00",
            idempotency_key="display-original-raw",
            raw_text='The user is asking whether you know what "Solaris" refers to.',
            normalized_text='the user is asking whether you know what solaris refers to',
            structured_payload={
                "raw_text": "what is Solaris",
                "normalized_text": "what is solaris",
                "route_domain": "conversation",
                "route_action": "respond",
            },
        ),
    )

    bundle = query(services, scope=scope, text="what did we talk about in this session", recall_mode="default")
    assert bundle["events"]
    assert bundle["events"][0]["raw_text"] == "what is Solaris"


def test_event_archive_preserves_raw_and_normalized_text_separately_from_interpretation(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:25:00+00:00",
            idempotency_key="preserve-provenance",
            raw_text="what is Solaris",
            normalized_text="what is solaris",
            structured_payload={
                "raw_text": "what is Solaris",
                "normalized_text": "what is solaris",
                "interpreted_text": 'The user is asking whether you know what "Solaris" refers to.',
                "route_domain": "conversation",
                "route_action": "respond",
            },
        ),
    )

    archive_bundle = query(services, scope=scope, text="what is Solaris", recall_mode="archive")
    assert archive_bundle["events"]
    assert archive_bundle["events"][0]["raw_text"] == "what is Solaris"
    assert archive_bundle["events"][0]["normalized_text"] == "what is solaris"
    assert archive_bundle["events"][0]["structured_payload"]["interpreted_text"] == (
        'The user is asking whether you know what "Solaris" refers to.'
    )


def test_claim_focused_query_filters_to_matching_events_when_no_claim_exists(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    first = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=first.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="claim-filter-solaris",
            raw_text="do you know what Solaris is",
        ),
        make_event(
            scope=scope,
            session_id=first.session_id,
            timestamp="2026-04-10T09:01:00+00:00",
            idempotency_key="claim-filter-noise",
            raw_text="my favorite song is stairway to heaven",
        ),
    )
    services["sessions"].close_session(CloseSessionRequest(session_id=first.session_id))

    bundle = query(services, scope=scope, text="what is Solaris", recall_mode="default")
    assert bundle["claims"] == []
    assert bundle["events"]
    assert bundle["events"][0]["raw_text"] == "do you know what Solaris is"
    assert all("favorite song" not in event["raw_text"] for event in bundle["events"])


def test_claim_focused_query_dedupes_duplicate_event_texts(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    live_session = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    import_session = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="import", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=live_session.session_id,
            timestamp="2026-04-10T09:10:00+00:00",
            idempotency_key="dedupe-live",
            raw_text="do you know what Solaris is",
        ),
        make_event(
            scope=scope,
            session_id=import_session.session_id,
            timestamp="2026-04-10T09:09:00+00:00",
            idempotency_key="dedupe-import",
            raw_text="do you know what Solaris is",
            source_app="legacy_adapter",
            source_module="training_log",
        ),
    )
    services["sessions"].close_session(CloseSessionRequest(session_id=import_session.session_id))

    bundle = query(services, scope=scope, text="what is Solaris", recall_mode="default")
    assert bundle["events"]
    assert [event["raw_text"] for event in bundle["events"]] == ["do you know what Solaris is"]


def test_topic_query_prefers_events_with_real_topic_tokens(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    interaction = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=interaction.session_id,
            timestamp="2026-04-10T09:30:00+00:00",
            idempotency_key="topic-query-generic",
            raw_text="Please tell me what you remember from this session.",
        ),
        make_event(
            scope=scope,
            session_id=interaction.session_id,
            timestamp="2026-04-10T09:31:00+00:00",
            idempotency_key="topic-query-trading",
            raw_text="Are you aware of your trading capabilities",
        ),
    )
    services["sessions"].close_session(CloseSessionRequest(session_id=interaction.session_id))

    bundle = query(services, scope=scope, text="what do you remember about trading", recall_mode="default")
    assert bundle["claims"] == []
    assert bundle["events"]
    assert bundle["events"][0]["raw_text"] == "Are you aware of your trading capabilities"
    assert all("remember from this session" not in event["raw_text"] for event in bundle["events"])


def test_topic_query_surfaces_relevant_entity_without_graph_junk(services, scope):
    runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    interaction = services["sessions"].open_session(
        OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
    )
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=interaction.session_id,
            timestamp="2026-04-10T09:40:00+00:00",
            idempotency_key="topic-entity-trading-1",
            raw_text="We discussed trading discipline today.",
        ),
        make_event(
            scope=scope,
            session_id=interaction.session_id,
            timestamp="2026-04-10T09:41:00+00:00",
            idempotency_key="topic-entity-trading-2",
            raw_text="Your trading capabilities need a clearer summary.",
        ),
        make_event(
            scope=scope,
            session_id=interaction.session_id,
            timestamp="2026-04-10T09:42:00+00:00",
            idempotency_key="topic-entity-noise",
            raw_text="Well right now we should keep going.",
        ),
    )
    services["sessions"].close_session(CloseSessionRequest(session_id=interaction.session_id))

    bundle = query(services, scope=scope, text="what do you remember about trading", recall_mode="default")
    entity_names = [item["canonical_name"] for item in bundle["entities"]]
    assert "trading" in entity_names
    assert "well" not in entity_names
    assert "right" not in entity_names
