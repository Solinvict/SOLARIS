# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.editorial import RunEditorialReviewRequest
from solaris.models.session import OpenSessionRequest

from conftest import explain, ingest, make_event


def test_claim_promotion(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    pinned = make_event(
        scope=scope,
        session_id=session.session_id,
        timestamp="2026-04-10T09:00:00+00:00",
        idempotency_key="claim-pin",
        raw_text="This system is for personal use, not a marketable tool.",
        kind="fact_assertion",
        hints={"pin": True, "entities": ["personal use"]},
        structured_payload={"pin": True},
    )
    repeated_a = make_event(
        scope=scope,
        session_id=session.session_id,
        timestamp="2026-04-10T09:01:00+00:00",
        idempotency_key="claim-repeat-a",
        raw_text="Solaris is a memory substrate.",
        hints={"entities": ["Solaris"]},
    )
    repeated_b = make_event(
        scope=scope,
        session_id=session.session_id,
        timestamp="2026-04-10T09:02:00+00:00",
        idempotency_key="claim-repeat-b",
        raw_text="Solaris is a memory substrate.",
        hints={"entities": ["Solaris"]},
    )
    result = ingest(services, pinned, repeated_a, repeated_b)
    with services["db"].transaction() as connection:
        claims = services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
        pinned_claim = next(item for item in claims if "personal use" in item["canonical_claim"])
        solaris_claim = next(item for item in claims if "Solaris" in item["canonical_claim"])
        pinned_state = services["editorial_repo"].get_state(connection, artifact_type="claim", artifact_id=pinned_claim["claim_id"])
    assert pinned_state["remember_state"] == "remembered"
    assert pinned_state["pinned"] is True
    services["review"].run_review(scope, None, "default_v1", 100, "boundary")
    solaris_explain = explain(services, scope=scope, artifact_type="claim", artifact_id=solaris_claim["claim_id"])
    assert solaris_explain["editorial_state"]["remember_state"] == "remembered"


def test_fact_assertion_memory_name_normalizes_to_operator_identity_claim(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="claim-remember-name",
            raw_text="remember my name is Jonas",
            normalized_text="remember my name is jonas",
            kind="fact_assertion",
            hints={"pin": True, "entities": ["Jonas"]},
            structured_payload={
                "route_domain": "memory",
                "route_action": "remember_fact",
                "pin": True,
            },
            importance=0.95,
            confidence=0.95,
        ),
    )
    with services["db"].transaction() as connection:
        claims = services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
        claim = next(item for item in claims if "Jonas" in item["canonical_claim"])
        state = services["editorial_repo"].get_state(connection, artifact_type="claim", artifact_id=claim["claim_id"])
    assert claim["canonical_claim"] == "operator has name Jonas"
    assert claim["predicate"] == "has name"
    assert claim["object_text"] == "Jonas"
    assert state["remember_state"] == "remembered"
    assert state["pinned"] is True


def test_explicit_claim_payload_normalizes_personal_operator_claims(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:01:00+00:00",
            idempotency_key="claim-explicit-personal-context",
            raw_text="remember my name is Jonas and I live in Example City",
            normalized_text="remember my name is jonas and i live in example city",
            kind="fact_assertion",
            hints={"pin": True, "entities": ["Jonas", "Example City"]},
            structured_payload={
                "route_domain": "memory",
                "route_action": "remember_fact",
                "pin": True,
                "claims": [
                    {
                        "subject_name": "Jonas",
                        "predicate": "has name",
                        "object_text": "Jonas",
                        "canonical_claim": "Jonas has name Jonas",
                        "confidence": 0.9,
                    },
                    {
                        "subject_name": "Jonas",
                        "predicate": "lives in",
                        "object_text": "Example City",
                        "canonical_claim": "Jonas lives in Example City",
                        "confidence": 0.9,
                    },
                ],
            },
            importance=0.95,
            confidence=0.95,
        ),
    )

    with services["db"].transaction() as connection:
        claims = services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
        canonical_claims = {item["canonical_claim"] for item in claims}

    assert "operator has name Jonas" in canonical_claims
    assert "operator lives in Example City" in canonical_claims
    assert "Jonas has name Jonas" not in canonical_claims
    assert "Jonas lives in Example City" not in canonical_claims


def test_question_like_message_does_not_create_claim(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="claim-question",
            raw_text="What are your capabilities",
            normalized_text="what are your capabilities",
        ),
    )
    with services["db"].transaction() as connection:
        claims = services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
    assert claims == []


def test_explicit_memory_message_can_promote_single_claim(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="claim-explicit-memory",
            raw_text="Remember this I live in Example City",
            normalized_text="remember this i live in example city",
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
            confidence=0.9,
        ),
    )

    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    with services["db"].transaction() as connection:
        claims = services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
        location_claim = next(item for item in claims if item["canonical_claim"] == "I live in Example City")
        state = services["editorial_repo"].get_state(connection, artifact_type="claim", artifact_id=location_claim["claim_id"])

    assert state["remember_state"] == "remembered"
    assert state["activation_state"] == "active"


def test_speech_act_interpretation_does_not_create_fallback_claim(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:03:00+00:00",
            idempotency_key="claim-speech-act-fallback",
            raw_text="You are reminding the assistant to treat the interaction as voice-first and to expect possible speech-recognition errors.",
            normalized_text="you are reminding the assistant to treat the interaction as voice-first and to expect possible speech-recognition errors",
            structured_payload={
                "interpreted_text": "You are reminding the assistant to treat the interaction as voice-first and to expect possible speech-recognition errors.",
                "needs_clarification": False,
            },
            importance=0.8,
            confidence=0.95,
        ),
    )
    with services["db"].transaction() as connection:
        claims = services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
    assert claims == []


def test_tool_result_can_create_claim_from_tool_observation_text(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:04:00+00:00",
            idempotency_key="claim-tool-observation",
            kind="tool_result",
            raw_text="inspect runtime architecture",
            structured_payload={
                "tool_observation_text": "Solaris is a standalone memory substrate.",
            },
            importance=0.8,
            confidence=0.9,
        ),
    )
    with services["db"].transaction() as connection:
        claims = services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
    assert any(item["canonical_claim"] == "Solaris is a standalone memory substrate" for item in claims)


def test_interpretive_operator_subject_does_not_create_claim(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:05:00+00:00",
            idempotency_key="claim-operator-interpretation-subject",
            raw_text="very funny",
            structured_payload={
                "interpreted_text": "The operator is reacting with amusement to something in the recent exchange.",
            },
            importance=0.8,
            confidence=0.95,
        ),
    )
    with services["db"].transaction() as connection:
        claims = services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
        entities = services["entities_repo"].list_by_scope(connection, scope.key(), limit=20)
    assert claims == []
    assert all(item["canonical_name"] != "The operator" for item in entities)
