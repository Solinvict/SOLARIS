# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.editorial import ApplyEditorialDecisionRequest
from solaris.models.session import OpenSessionRequest

from conftest import explain, ingest, make_event, query


def test_archive_remains_intact_after_editorial_retirement(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="archive-state-retire-proof",
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
                    "confidence": 0.95,
                    "pinned": False,
                },
            },
            importance=0.95,
            confidence=0.95,
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    with services["db"].transaction() as connection:
        event = services["events_repo"].list_by_scope(connection, scope.key(), limit=1)[0]
        claim = next(
            item
            for item in services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
            if item["canonical_claim"] == "I live in Example City"
        )
        initial_state = services["editorial_repo"].get_state(connection, artifact_type="claim", artifact_id=claim["claim_id"])

    assert initial_state["remember_state"] == "remembered"

    services["review"].apply_decision(
        ApplyEditorialDecisionRequest(
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope=scope,
            action="retire",
            rationale={"summary": "Verification retirement for archive-state proof."},
            policy_profile="default_v1",
        )
    )

    with services["db"].transaction() as connection:
        archived_event = services["events_repo"].get(connection, event["event_id"])
        retired_state = services["editorial_repo"].get_state(connection, artifact_type="claim", artifact_id=claim["claim_id"])
        supporting_event_ids = services["evidence_repo"].event_ids_for_artifact(
            connection,
            artifact_type="claim",
            artifact_id=claim["claim_id"],
        )

    explanation = explain(services, scope=scope, artifact_type="claim", artifact_id=claim["claim_id"])

    assert archived_event is not None
    assert archived_event["raw_text"] == "Remember this I live in Example City"
    assert archived_event["idempotency_key"] == "archive-state-retire-proof"
    assert retired_state["remember_state"] == "retired"
    assert event["event_id"] in supporting_event_ids
    assert [item["event_id"] for item in explanation["supporting_events"]] == [event["event_id"]]


def test_editorial_state_filters_kinds_differently_for_single_evidence_claims(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:00:00+00:00",
            idempotency_key="archive-state-decision-claim",
            raw_text="We decided Solaris should preserve the raw record.",
            kind="decision",
            structured_payload={
                "claim": {
                    "predicate": "asserts",
                    "object_text": "Solaris should preserve the raw record",
                    "canonical_claim": "Solaris should preserve the raw record",
                    "confidence": 0.92,
                    "pinned": False,
                }
            },
            importance=0.9,
            confidence=0.92,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:01:00+00:00",
            idempotency_key="archive-state-message-claim",
            raw_text="Solaris should favor clear explanations.",
            kind="message",
            structured_payload={
                "claim": {
                    "predicate": "asserts",
                    "object_text": "Solaris should favor clear explanations",
                    "canonical_claim": "Solaris should favor clear explanations",
                    "confidence": 0.92,
                    "pinned": False,
                }
            },
            importance=0.9,
            confidence=0.92,
        ),
    )

    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    with services["db"].transaction() as connection:
        claims = services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
        decision_claim = next(item for item in claims if item["canonical_claim"] == "Solaris should preserve the raw record")
        message_claim = next(item for item in claims if item["canonical_claim"] == "Solaris should favor clear explanations")
        decision_state = services["editorial_repo"].get_state(
            connection,
            artifact_type="claim",
            artifact_id=decision_claim["claim_id"],
        )
        message_state = services["editorial_repo"].get_state(
            connection,
            artifact_type="claim",
            artifact_id=message_claim["claim_id"],
        )

    assert decision_state["remember_state"] == "remembered"
    assert decision_state["activation_state"] == "active"
    assert message_state["remember_state"] == "candidate"
    assert message_state["activation_state"] == "suppressed"
    assert float(decision_state["remember_score"]) > float(message_state["remember_score"])
    assert float(decision_state["influence_score"]) > float(message_state["influence_score"])


def test_query_can_switch_between_current_belief_and_grounded_archive(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T11:00:00+00:00",
            idempotency_key="archive-state-query-switch",
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
                    "confidence": 0.95,
                    "pinned": False,
                },
            },
            importance=0.95,
            confidence=0.95,
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    default_before = query(services, scope=scope, text="where do I live", recall_mode="default")

    with services["db"].transaction() as connection:
        claim = next(
            item
            for item in services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
            if item["canonical_claim"] == "I live in Example City"
        )
        event = services["events_repo"].list_by_scope(connection, scope.key(), limit=1)[0]

    services["review"].apply_decision(
        ApplyEditorialDecisionRequest(
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope=scope,
            action="retire",
            rationale={"summary": "Verification retirement for state-vs-archive proof."},
            policy_profile="default_v1",
        )
    )

    default_after = query(services, scope=scope, text="where do I live", recall_mode="default")
    archive_after = query(services, scope=scope, text="where do I live", recall_mode="archive")
    explanation = explain(services, scope=scope, artifact_type="claim", artifact_id=claim["claim_id"])

    assert default_before["claims"]
    assert default_before["claims"][0]["canonical_claim"] == "I live in Example City"
    assert default_after["claims"] == []
    assert default_after["recorded"]["divergences"]
    assert default_after["recorded"]["divergences"][0]["label"] == "I live in Example City"
    assert default_after["divergence_summary"]["count"] >= 1
    assert archive_after["events"]
    assert archive_after["events"][0]["event_id"] == event["event_id"]
    assert archive_after["recorded"]["divergences"]
    assert explanation["editorial_state"]["remember_state"] == "retired"
    assert explanation["supporting_events"]
    assert explanation["supporting_events"][0]["event_id"] == event["event_id"]
