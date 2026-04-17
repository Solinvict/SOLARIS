# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.scope import ScopeRef
from solaris.models.query import QueryRequest
from solaris.models.session import OpenSessionRequest

from conftest import ingest, make_event


def test_state_expiry(services, scope: ScopeRef):
    with services["db"].transaction() as connection:
        lease = services["state_repo"].upsert(
            connection,
            scope=scope,
            lease_key="planner_context",
            value_json={"goal": "design Solaris"},
            ttl_seconds=60,
        )
    with services["db"].transaction() as connection:
        connection.execute(
            "UPDATE state_leases SET expires_at = '2000-01-01T00:00:00+00:00' WHERE lease_id = ?",
            (lease["lease_id"],),
        )
    bundle = services["query"].query(QueryRequest(query="planner", scope=scope))
    assert bundle["state_leases"] == []


def test_entity_timeline_surfaces_temporal_claims_and_relations(services, scope: ScopeRef):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="timeline-temporal-1",
            raw_text="Solaris is a memory substrate.",
            hints={"entities": ["Solaris"]},
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:01:00+00:00",
            idempotency_key="timeline-temporal-2",
            raw_text="Solaris uses SQLite.",
            hints={"entities": ["Solaris", "SQLite"], "relations": [{"src": "Solaris", "dst": "SQLite", "type": "uses"}]},
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")
    with services["db"].transaction() as connection:
        solaris_entity = services["entities_repo"].resolve(connection, scope_key=scope.key(), canonical_name="Solaris")
    timeline = services["timeline"].timeline(
        type("Req", (), {"scope": scope, "entity_id": solaris_entity["entity_id"], "episode_id": None, "limit": 20})()
    )
    assert timeline["claims"]
    assert timeline["relations"]
    assert "valid_from" in timeline["claims"][0]
    assert "valid_from" in timeline["relations"][0]
