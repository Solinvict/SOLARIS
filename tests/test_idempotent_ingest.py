# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.session import OpenSessionRequest

from conftest import ingest, make_event


def test_idempotent_ingest(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    event = make_event(
        scope=scope,
        session_id=session.session_id,
        timestamp="2026-04-10T09:00:00+00:00",
        idempotency_key="dup-1",
        raw_text="Solaris is a memory substrate.",
    )
    result = ingest(services, event, event)
    assert result.accepted == 1
    assert result.duplicates == 1
    with services["db"].transaction() as connection:
        rows = services["events_repo"].list_by_scope(connection, scope.key(), limit=10)
    assert len(rows) == 1
