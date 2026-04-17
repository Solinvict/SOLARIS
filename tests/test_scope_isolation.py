# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.session import OpenSessionRequest

from conftest import ingest, make_event, query


def test_scope_isolation(services, scope, other_scope):
    sess_a = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    sess_b = services["sessions"].open_session(OpenSessionRequest(scope=other_scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=sess_a.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="scope-a",
            raw_text="Solaris is a memory substrate.",
            hints={"pin": True, "entities": ["Solaris"]},
            kind="fact_assertion",
            structured_payload={"pin": True},
        ),
        make_event(
            scope=other_scope,
            session_id=sess_b.session_id,
            timestamp="2026-04-10T09:01:00+00:00",
            idempotency_key="scope-b",
            raw_text="Other project should stay isolated.",
            hints={"pin": True, "entities": ["Other project"]},
            kind="fact_assertion",
            structured_payload={"pin": True},
        ),
    )
    bundle = query(services, scope=scope, text="what is Solaris", recall_mode="default")
    assert any("Solaris" in item["canonical_claim"] for item in bundle["claims"])
    assert all("Other project" not in item["canonical_claim"] for item in bundle["claims"])
