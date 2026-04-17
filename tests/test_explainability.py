# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.session import OpenSessionRequest

from conftest import explain, ingest, make_event


def test_explainability(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="exp-1",
            raw_text="Solaris is a memory substrate.",
            hints={"entities": ["Solaris"]},
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:01:00+00:00",
            idempotency_key="exp-2",
            raw_text="Solaris is a memory substrate.",
            hints={"entities": ["Solaris"]},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")
    with services["db"].transaction() as connection:
        claims = services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
    explanation = explain(services, scope=scope, artifact_type="claim", artifact_id=claims[0]["claim_id"])
    assert explanation["supporting_events"]
    assert explanation["decisions"]
    assert explanation["temporal"]["valid_from"]


def test_relation_explainability_surfaces_temporal_fields_after_supersede(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:10:00+00:00",
            idempotency_key="exp-rel-1",
            raw_text="Solaris uses SQLite.",
            hints={"entities": ["Solaris", "SQLite"], "relations": [{"src": "Solaris", "dst": "SQLite", "type": "uses"}]},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")
    with services["db"].transaction() as connection:
        relation = services["relations_repo"].list_by_scope(connection, scope.key(), limit=10)[0]
        services["relations_repo"].apply_temporal_action(
            connection,
            relation_id=relation["relation_id"],
            action="mark_superseded",
            decided_at="2026-04-10T09:11:00+00:00",
        )
    explanation = explain(services, scope=scope, artifact_type="relation", artifact_id=relation["relation_id"])
    assert explanation["temporal"]["superseded_at"] == "2026-04-10T09:11:00+00:00"
    assert explanation["temporal"]["valid_until"] == "2026-04-10T09:11:00+00:00"
