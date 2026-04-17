# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from solaris.config import Settings
from solaris.models.scope import ScopeRef
from solaris.web_app import build_web_app

from conftest import ROOT, ingest, make_event


def _settings(tmp_path: Path, scope: ScopeRef) -> Settings:
    return Settings(
        project_root=ROOT,
        db_path=tmp_path / "solaris_web.db",
        policies_dir=ROOT / "policies",
        default_policy_profile="default_v1",
        fts_enabled=True,
        embeddings_enabled=False,
        log_level="INFO",
        adjudication_provider="off",
        adjudication_base_url="https://api.openai.com/v1",
        adjudication_api_key="",
        adjudication_model="",
        adjudication_timeout_seconds=20.0,
        adjudication_prompt_version="solaris_editorial_adjudication_v1",
        divergence_weight_threshold=0.2,
        web_ws_poll_seconds=0.05,
        default_scope_tenant=scope.tenant,
        default_scope_namespace=scope.namespace,
        default_scope_workspace=scope.workspace,
        default_scope_project=scope.project,
    )


def _seed_memory(services: dict, scope: ScopeRef) -> None:
    first = make_event(
        scope=scope,
        session_id="sess-web-1",
        timestamp="2026-04-16T10:00:00+00:00",
        idempotency_key="evt-web-1",
        raw_text="My name is Jordan and Solaris maps memory into graph structure.",
    )
    second = make_event(
        scope=scope,
        session_id="sess-web-1",
        timestamp="2026-04-16T10:01:00+00:00",
        idempotency_key="evt-web-2",
        raw_text="Graph memory depends on fractal memory and uses archival evidence.",
    )
    ingest(services, first, second)
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")


def test_web_bootstrap_landing_recall_and_artifact_inspect(tmp_path: Path, scope: ScopeRef):
    settings = _settings(tmp_path, scope)
    app = build_web_app(settings)
    services = app.state.services
    _seed_memory(services, scope)

    client = TestClient(app)

    bootstrap = client.get("/api/bootstrap")
    assert bootstrap.status_code == 200
    bootstrap_payload = bootstrap.json()
    assert bootstrap_payload["read_only"] is True
    assert [layer["label"] for layer in bootstrap_payload["layers"]] == [
        "Archive",
        "Editorial Memory",
        "Graph Structure",
        "Active Recall",
        "Fractal Projection",
    ]

    landing = client.get("/api/landing")
    assert landing.status_code == 200
    landing_payload = landing.json()
    assert landing_payload["scene"]["nodes"]
    assert landing_payload["top_recall"]

    recall = client.post(
        "/api/recall",
        json={
            "query": "what do we know about graph memory",
            "scope": scope.model_dump(mode="json"),
            "scope_mode": "local",
            "recall_mode": "default",
            "include_explanations": True,
        },
    )
    assert recall.status_code == 200
    recall_payload = recall.json()
    assert recall_payload["scene"]["nodes"]
    assert recall_payload["scene"]["focus_node_ids"]

    claim = next(
        item
        for item in recall_payload["scene"]["nodes"]
        if item["artifact_type"] == "claim" and item["layer"] in {"editorial_memory", "active_recall"}
    )
    inspect = client.get(f"/api/artifacts/claim/{claim['artifact_id']}")
    assert inspect.status_code == 200
    inspect_payload = inspect.json()
    assert inspect_payload["explain"]["artifact"]["canonical_claim"]
    assert inspect_payload["artifact_timeline"]


def test_patterns_timeline_and_scope_isolation(tmp_path: Path, scope: ScopeRef, other_scope: ScopeRef):
    settings = _settings(tmp_path, scope)
    app = build_web_app(settings)
    services = app.state.services
    _seed_memory(services, scope)
    ingest(
        services,
        make_event(
            scope=other_scope,
            session_id="sess-other",
            timestamp="2026-04-16T11:00:00+00:00",
            idempotency_key="evt-other-1",
            raw_text="This should stay isolated in a different project scope.",
        ),
    )
    services["review"].run_review(other_scope, None, "default_v1", 50, "boundary")

    client = TestClient(app)

    patterns = client.post("/api/patterns", json={"scope": scope.model_dump(mode="json"), "limit": 10})
    assert patterns.status_code == 200
    assert "patterns" in patterns.json()

    timeline = client.get("/api/timeline")
    assert timeline.status_code == 200
    timeline_payload = timeline.json()
    assert timeline_payload["scope"]["project"] == scope.project
    assert all(item["scope"]["project"] == scope.project for item in timeline_payload["timeline"]["events"])


def test_websocket_emits_invalidation_after_db_change(tmp_path: Path, scope: ScopeRef):
    settings = _settings(tmp_path, scope)
    app = build_web_app(settings)
    services = app.state.services
    client = TestClient(app)

    with client.websocket_connect("/ws") as websocket:
        hello = websocket.receive_json()
        assert hello["type"] == "hello"
        scope_state = websocket.receive_json()
        assert scope_state["type"] == "scope_state"

        ingest(
            services,
            make_event(
                scope=scope,
                session_id="sess-ws",
                timestamp="2026-04-16T12:00:00+00:00",
                idempotency_key="evt-ws-1",
                raw_text="A websocket invalidation should fire after this archive write.",
            ),
        )

        seen_invalidate = False
        for _ in range(12):
            payload = websocket.receive_json()
            if payload["type"] == "invalidate":
                seen_invalidate = True
                break
        assert seen_invalidate is True
