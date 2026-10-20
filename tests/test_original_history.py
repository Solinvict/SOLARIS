from __future__ import annotations

import hashlib

import pytest

from solaris.models.scope import ScopeRef
from solaris.services.history import canonical, digest


def envelope(
    scope: ScopeRef,
    *,
    event_id: str,
    sequence: int,
    previous_id: str | None,
    artifacts: list[dict] | None = None,
) -> dict:
    value = {
        "schema": "aeon-original-history/v1",
        "event_id": event_id,
        "investigation_id": "investigation-1",
        "scope_key": scope.key(),
        "sequence": sequence,
        "previous_id": previous_id,
        "parent_id": None,
        "run_id": None,
        "actor": "T6/native",
        "kind": "investigation.started",
        "occurred_at": "2026-10-21T00:00:00+00:00",
        "payload": {"question": "preserve the exact source"},
        "sanitization": [],
        "artifacts": artifacts or [],
    }
    value["event_sha256"] = digest(value)
    return value


def test_original_history_round_trip_is_scoped_and_idempotent(services, scope, other_scope) -> None:
    history = services["history"]
    raw = b"source evidence\r\n"
    sha256 = hashlib.sha256(raw).hexdigest()
    event = envelope(
        scope,
        event_id="hist-1",
        sequence=1,
        previous_id=None,
        artifacts=[{"path": "source.csv", "sha256": sha256, "size": len(raw), "sanitization": []}],
    )

    assert history.ingest(scope, event, {sha256: raw}) == {"event_id": "hist-1", "duplicate": False}
    assert history.ingest(scope, event, {}) == {"event_id": "hist-1", "duplicate": True}
    assert history.read(scope, "hist-1") == event
    assert history.read(other_scope, "hist-1") is None
    assert history.artifact(scope, sha256) == raw
    assert history.artifact(other_scope, sha256) is None
    assert history.page(scope, "investigation-1") == [event]
    assert history.export(scope, "investigation-1") == {
        "investigation_id": "investigation-1",
        "scope_key": scope.key(),
        "events": [event],
        "unresolved_parents": [],
        "retention_is_scientific_eligibility": False,
    }


def test_original_history_rejects_tampered_envelope_and_artifact(services, scope) -> None:
    history = services["history"]
    raw = b"source evidence"
    sha256 = hashlib.sha256(raw).hexdigest()
    event = envelope(
        scope,
        event_id="hist-tampered",
        sequence=1,
        previous_id=None,
        artifacts=[{"path": "source.csv", "sha256": sha256, "size": len(raw), "sanitization": []}],
    )

    changed = dict(event, payload={"question": "rewritten"})
    with pytest.raises(ValueError, match="binding"):
        history.ingest(scope, changed, {sha256: raw})
    with pytest.raises(ValueError, match="artifact"):
        history.ingest(scope, event, {sha256: b"different"})


def test_original_history_rejects_sequence_gaps_and_broken_chain(services, scope) -> None:
    history = services["history"]

    with pytest.raises(ValueError, match="sequence continuity"):
        history.ingest(
            scope,
            envelope(scope, event_id="hist-2", sequence=2, previous_id="hist-1"),
            {},
        )

    first = envelope(scope, event_id="hist-1", sequence=1, previous_id=None)
    history.ingest(scope, first, {})
    with pytest.raises(ValueError, match="previous event"):
        history.ingest(
            scope,
            envelope(scope, event_id="hist-2", sequence=2, previous_id="wrong"),
            {},
        )


def test_original_history_database_uses_full_synchronous_durability(services) -> None:
    with services["db"].transaction() as connection:
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2
