# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.derive.entities import derive_entities
from solaris.derive.text import best_derivation_text
from solaris.models.scope import ScopeRef
from solaris.models.session import OpenSessionRequest

from conftest import ingest, make_event, query


def test_entity_derivation(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="ent-1",
            raw_text="We paused agent coordination because runtime stability was brittle.",
            hints={"entities": ["agent coordination", "runtime stability"]},
        ),
    )
    bundle = query(services, scope=scope, text="coordination", recall_mode="deep")
    names = {item["canonical_name"] for item in bundle["entities"]}
    assert "agent coordination" in names
    assert "runtime stability" in names


def test_entity_derivation_captures_sentence_start_proper_noun(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:05:00+00:00",
            idempotency_key="ent-solaris-start",
            raw_text="Solaris should remember selectively.",
        ),
    )
    bundle = query(services, scope=scope, text="Solaris", recall_mode="deep")
    names = {item["canonical_name"] for item in bundle["entities"]}
    assert "Solaris" in names


def test_tool_result_derives_entities_from_tool_observation_text(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:07:00+00:00",
            idempotency_key="ent-tool-observation",
            kind="tool_result",
            raw_text="show me the runtime architecture",
            structured_payload={
                "tool_observation_text": "Solaris architecture uses SQLite and graph memory.",
            },
            confidence=0.9,
        ),
    )
    bundle = query(services, scope=scope, text="Solaris", recall_mode="deep")
    names = {item["canonical_name"] for item in bundle["entities"]}
    assert "Solaris" in names


def test_entity_derivation_prefers_payload_raw_text_over_interpretive_top_level(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:08:00+00:00",
            idempotency_key="ent-payload-raw-preferred",
            raw_text="The user is asking what Solaris means.",
            normalized_text="the user is asking what solaris means",
            structured_payload={
                "raw_text": "what is Solaris",
                "normalized_text": "what is solaris",
                "interpreted_text": "The user is asking what Solaris means.",
            },
            confidence=0.95,
        ),
    )
    bundle = query(services, scope=scope, text="Solaris", recall_mode="deep")
    names = {item["canonical_name"] for item in bundle["entities"]}
    assert "Solaris" in names
    assert "The user" not in names


def test_entity_derivation_prefers_multiword_concepts_over_noisy_singletons(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:09:00+00:00",
            idempotency_key="ent-noisy-project-description",
            raw_text=(
                "So currently I'm working on a project an mCP called the Solaris and the idea "
                "is that uses that sort of an adapter for for example for you and then I'm "
                "basically using sqlite and what is what is it called graph memory so my idea "
                "is to add to this fractal memory what do you think"
            ),
        ),
    )
    bundle = query(services, scope=scope, text="memory", recall_mode="deep")
    names = {item["canonical_name"] for item in bundle["entities"]}
    assert "Solaris" in names
    assert "graph memory" in names
    assert "fractal memory" in names
    assert "mcp solaris" not in names
    assert "basically sqlite" not in names
    assert "sort" not in names
    assert "example" not in names
    assert "adapter" not in names


def test_entity_derivation_filters_low_signal_hint_entities(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:10:00+00:00",
            idempotency_key="ent-hint-sanitized",
            raw_text="Solaris should remember selectively.",
            hints={"entities": ["best", "Solaris", "graph memory"]},
        ),
    )
    bundle = query(services, scope=scope, text="Solaris", recall_mode="deep")
    names = {item["canonical_name"] for item in bundle["entities"]}
    assert "Solaris" in names
    assert "graph memory" in names
    assert "best" not in names


def test_entity_derivation_filters_conversational_scaffolding_phrases(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:11:00+00:00",
            idempotency_key="ent-scaffolding-filter",
            raw_text="we were talking about the greatest guitarist earlier",
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:12:00+00:00",
            idempotency_key="ent-solve-upward-filter",
            raw_text="I've been done how do we solve upward",
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:13:00+00:00",
            idempotency_key="ent-truth-keep",
            raw_text="what do you consider absolute truth",
            hints={"entities": ["absolute truth"]},
        ),
    )
    truth_bundle = query(services, scope=scope, text="truth", recall_mode="deep")
    truth_names = {item["canonical_name"] for item in truth_bundle["entities"]}
    guitarist_bundle = query(services, scope=scope, text="guitarist", recall_mode="deep")
    guitarist_names = {item["canonical_name"] for item in guitarist_bundle["entities"]}
    assert "absolute truth" in truth_names
    assert "were talking" not in truth_names
    assert "greatest guitarist earlier" not in guitarist_names
    assert "greatest guitarist" in guitarist_names
    assert "solve upward" not in guitarist_names


def test_entity_derivation_filters_conversational_fillers_from_recent_turns(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:14:00+00:00",
            idempotency_key="ent-yes-continue",
            raw_text="yes continue",
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:15:00+00:00",
            idempotency_key="ent-start-overview",
            raw_text="start with alcohol overview",
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:16:00+00:00",
            idempotency_key="ent-thinking-outlining",
            raw_text="I'm thinking I'm outlining",
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:17:00+00:00",
            idempotency_key="ent-any-improvement",
            raw_text="if you see any improvement we can do in the trading",
        ),
    )
    overview_bundle = query(services, scope=scope, text="overview", recall_mode="deep")
    overview_names = {item["canonical_name"] for item in overview_bundle["entities"]}
    continue_bundle = query(services, scope=scope, text="continue", recall_mode="deep")
    continue_names = {item["canonical_name"] for item in continue_bundle["entities"]}
    trading_bundle = query(services, scope=scope, text="trading", recall_mode="deep")
    trading_names = {item["canonical_name"] for item in trading_bundle["entities"]}
    assert "alcohol overview" in overview_names
    assert "start alcohol overview" not in overview_names
    assert "yes continue" not in continue_names
    assert "continue" not in continue_names
    assert "thinking" not in overview_names
    assert "outlining" not in overview_names
    assert "any improvement" not in trading_names


def test_entity_derivation_trims_action_phrases_to_underlying_topic(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:18:00+00:00",
            idempotency_key="ent-retrieve-live-logs",
            raw_text="retrieve the live logs and then we can talk about it",
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:19:00+00:00",
            idempotency_key="ent-analyze-breach-conditions",
            raw_text="do you want to analyze the breach conditions first",
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:20:00+00:00",
            idempotency_key="ent-trading-session",
            raw_text="let's go into trading session",
        ),
    )
    logs_bundle = query(services, scope=scope, text="logs", recall_mode="deep")
    logs_names = {item["canonical_name"] for item in logs_bundle["entities"]}
    breach_bundle = query(services, scope=scope, text="breach", recall_mode="deep")
    breach_names = {item["canonical_name"] for item in breach_bundle["entities"]}
    session_bundle = query(services, scope=scope, text="trading", recall_mode="deep")
    session_names = {item["canonical_name"] for item in session_bundle["entities"]}
    assert "live logs" in logs_names
    assert "retrieve live logs" not in logs_names
    assert "breach conditions" in breach_names
    assert "analyze breach conditions" not in breach_names


def test_entity_derivation_filters_short_reaction_phrase_entities(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:21:00+00:00",
            idempotency_key="ent-very-funny",
            raw_text="very funny",
            structured_payload={
                "interpreted_text": "The operator is reacting with amusement to something in the recent exchange.",
            },
        ),
    )
    bundle = query(services, scope=scope, text="funny", recall_mode="deep")
    names = {item["canonical_name"] for item in bundle["entities"]}
    assert "very funny" not in names
    assert not names


def test_entity_derivation_filters_modifier_heavy_constraint_phrases(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:23:00+00:00",
            idempotency_key="ent-constraint-phrases",
            raw_text=(
                "the same day by card is broker site so there's nothing I can do about it "
                "and the other National threshold means that is for my control purpose only"
            ),
        ),
    )
    bundle = query(services, scope=scope, text="control", recall_mode="deep")
    names = {item["canonical_name"] for item in bundle["entities"]}
    assert "broker site" in names
    assert "same day" not in names
    assert "other national" not in names
    assert "threshold means" not in names
    assert "control purpose only" not in names


def test_best_derivation_text_prefers_interpretation_for_short_reaction_turn():
    event = make_event(
        scope=ScopeRef(
            tenant="personal",
            namespace="host",
            workspace="default",
            project="core",
        ),
        session_id="sess_test",
        timestamp="2026-04-10T09:22:00+00:00",
        idempotency_key="ent-short-reaction-interpretation",
        raw_text="very funny",
        structured_payload={
            "interpreted_text": "The operator is reacting with amusement to something in the recent exchange.",
        },
    )
    assert (
        best_derivation_text(event)
        == "The operator is reacting with amusement to something in the recent exchange."
    )
    names = {item["name"] for item in derive_entities(event)}
    assert "very funny" not in names
    assert not names


def test_entity_derivation_filters_greeting_singletons(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:24:00+00:00",
            idempotency_key="ent-hello",
            raw_text="hello",
        ),
    )
    bundle = query(services, scope=scope, text="hello", recall_mode="deep")
    names = {item["canonical_name"] for item in bundle["entities"]}
    assert "hello" not in names
