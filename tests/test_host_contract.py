from __future__ import annotations

import hashlib
from pathlib import Path

from solaris.host import SolarisHost
from solaris.models.scope import ScopeRef
from solaris.services.history import digest


def _envelope(
    scope: ScopeRef,
    *,
    event_id: str = "event-1",
    investigation_id: str = "mission-1",
    artifact: bytes | None = None,
) -> tuple[dict, dict[str, bytes]]:
    artifacts: dict[str, bytes] = {}
    references: list[dict] = []
    if artifact is not None:
        sha256 = hashlib.sha256(artifact).hexdigest()
        artifacts[sha256] = artifact
        references.append(
            {"path": "result.json", "sha256": sha256, "size": len(artifact), "sanitization": []}
        )
    value = {
        "schema": "solaris-original-history/v1",
        "event_id": event_id,
        "investigation_id": investigation_id,
        "scope_key": scope.key(),
        "sequence": 1,
        "previous_id": None,
        "parent_id": None,
        "run_id": "run-1",
        "actor": "discovery-engine/T4",
        "kind": "investigation.completed",
        "occurred_at": "2026-10-30T00:00:00+00:00",
        "payload": {"claim_ceiling": "finite_observed_condition"},
        "sanitization": [],
        "artifacts": references,
    }
    value["event_sha256"] = digest(value)
    return value, artifacts


def test_host_identity_is_stable_and_capabilities_are_explicit(tmp_path: Path) -> None:
    first = SolarisHost.open(tmp_path / "solaris.db")
    reopened = SolarisHost.open(tmp_path / "solaris.db")
    other = SolarisHost.open(tmp_path / "other.db")

    assert first.identity() == reopened.identity()
    assert first.identity().store_id != other.identity().store_id
    assert first.identity().schema_version == 7
    assert first.capabilities().names == frozenset(
        {
            "artifact_exact_readback",
            "idempotent_publication",
            "original_history_v1",
            "scope_isolation",
            "scoped_retrieval",
        }
    )
    assert "editorial" not in first.capabilities().names


def test_host_publication_is_idempotent_scoped_and_exact(tmp_path: Path) -> None:
    host = SolarisHost.open(tmp_path / "solaris.db")
    scope = ScopeRef(tenant="personal", namespace="discovery", workspace="m1", project="demo")
    other = ScopeRef(tenant="personal", namespace="discovery", workspace="m1", project="other")
    raw = b'{"result":"bounded"}\n'
    envelope, artifacts = _envelope(scope, artifact=raw)

    first = host.publish(scope, envelope, artifacts)
    duplicate = host.publish(scope, envelope, {})

    assert first.event_id == "event-1"
    assert first.duplicate is False
    assert duplicate.event_id == "event-1"
    assert duplicate.duplicate is True
    assert host.read(scope, "event-1") == envelope
    assert host.read(other, "event-1") is None
    assert host.retrieve(scope, "mission-1") == (envelope,)
    assert host.retrieve(other, "mission-1") == ()
    sha256 = hashlib.sha256(raw).hexdigest()
    assert host.read_artifact(scope, sha256) == raw
    assert host.read_artifact(other, sha256) is None


def test_host_path_never_invokes_editorial(monkeypatch, tmp_path: Path) -> None:
    from solaris.editorial.engine import EditorialEngine

    def forbidden(*args, **kwargs):
        raise AssertionError("Editorial must not be invoked by SolarisHost")

    monkeypatch.setattr(EditorialEngine, "review", forbidden)
    host = SolarisHost.open(tmp_path / "solaris.db")
    scope = ScopeRef(tenant="personal", namespace="discovery", workspace="m1", project="demo")
    envelope, artifacts = _envelope(scope)

    assert host.publish(scope, envelope, artifacts).event_id == "event-1"
