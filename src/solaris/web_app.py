# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from solaris.config import Settings
from solaris.models.query import EntityRequest, ExplainRequest, PatternProjectionRequest, QueryRequest, TimelineRequest
from solaris.models.scope import ScopeRef
from solaris.retrieval.timeline import build_timeline
from solaris.server import build_services
from solaris.web_mapping import LAYER_DEFINITIONS, build_focus_scene, build_scene_snapshot, utc_now
from solaris.web_models import (
    ArtifactInspectResponse,
    BootstrapResponse,
    LandingResponse,
    PatternsSceneRequest,
    PatternsSceneResponse,
    RecallSceneRequest,
    RecallSceneResponse,
    TimelineResponseModel,
    WebSocketEnvelope,
)


def _product_version() -> str:
    try:
        return version("solaris-memory-mcp")
    except PackageNotFoundError:
        return "0.1.0"


def _default_scope(settings: Settings) -> ScopeRef:
    return ScopeRef(
        tenant=settings.default_scope_tenant,
        namespace=settings.default_scope_namespace,
        workspace=settings.default_scope_workspace,
        project=settings.default_scope_project,
    )


def _scope_has_events(services: dict, scope: ScopeRef) -> bool:
    with services["db"].transaction() as connection:
        row = connection.execute(
            """
            select 1
            from events
            where tenant = ?
              and namespace = ?
              and workspace = ?
              and project = ?
            limit 1
            """,
            (scope.tenant, scope.namespace, scope.workspace, scope.project),
        ).fetchone()
    return row is not None


def _discover_populated_scope(services: dict) -> ScopeRef | None:
    with services["db"].transaction() as connection:
        row = connection.execute(
            """
            select tenant, namespace, workspace, project
            from events
            group by tenant, namespace, workspace, project
            order by count(*) desc, tenant, namespace, workspace, project
            limit 1
            """
        ).fetchone()
    if not row:
        return None
    return ScopeRef(
        tenant=str(row[0] or "").strip() or "personal",
        namespace=str(row[1] or "").strip() or "default",
        workspace=str(row[2] or "").strip() or "default",
        project=str(row[3] or "").strip() or "default",
    )


def _preferred_scope(settings: Settings, services: dict) -> ScopeRef:
    configured = _default_scope(settings)
    if _scope_has_events(services, configured):
        return configured
    discovered = _discover_populated_scope(services)
    return discovered or configured


def _scope_from_query(request: Request, settings: Settings, services: dict) -> ScopeRef:
    params = request.query_params
    has_explicit_scope = any(params.get(key) for key in ("tenant", "namespace", "workspace", "project"))
    default_scope = _preferred_scope(settings, services) if not has_explicit_scope else _default_scope(settings)
    return ScopeRef(
        tenant=str(params.get("tenant") or default_scope.tenant),
        namespace=str(params.get("namespace") or default_scope.namespace),
        workspace=str(params.get("workspace") or default_scope.workspace),
        project=str(params.get("project") or default_scope.project),
    )


def _db_signature(settings: Settings) -> str:
    digest = hashlib.sha256()
    for path in (settings.db_path, Path(f"{settings.db_path}-wal"), Path(f"{settings.db_path}-shm")):
        digest.update(str(path).encode("utf-8"))
        if path.exists():
            stat = path.stat()
            digest.update(f"{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8"))
        else:
            digest.update(b"missing")
    return digest.hexdigest()[:20]


def _cors_origins(settings: Settings) -> list[str]:
    raw = str(settings.web_dev_cors_origin or "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _landing_bundle(services: dict, scope: ScopeRef) -> dict:
    return services["query"].query(
        QueryRequest(
            query="",
            scope=scope,
            include_explanations=True,
        )
    )


def _pattern_payload(services: dict, scope: ScopeRef, *, limit: int = 12) -> dict:
    return services["patterns"].project(
        PatternProjectionRequest(
            scope=scope,
            limit=limit,
            min_weight=0.0,
            pattern_kinds=[],
        )
    )


def _top_recall(scene) -> list[dict]:
    cards = []
    for card in scene.inspector_cards:
        if card.artifact_type == "query":
            continue
        cards.append(card.model_dump(mode="json"))
    return cards[:6]


def _artifact_supporting_timeline(services: dict, *, artifact_type: str, artifact_id: str, explain_payload: dict) -> list[dict]:
    if artifact_type == "episode":
        timeline = services["timeline"].timeline(
            TimelineRequest(scope=ScopeRef(**(explain_payload.get("artifact") or {}).get("scope", {})), episode_id=artifact_id, limit=32)
        )
        return list(timeline.get("events") or [])
    supporting_events = explain_payload.get("supporting_events") or []
    return build_timeline(supporting_events)


def _artifact_graph(services: dict, *, artifact_type: str, explain_payload: dict, scope: ScopeRef) -> dict:
    artifact = explain_payload.get("artifact") or {}
    entity_ids: list[str] = []
    if artifact_type == "claim":
        claim_entity = str(artifact.get("subject_entity_id") or "").strip()
        if claim_entity:
            entity_ids.append(claim_entity)
    elif artifact_type == "episode":
        entity_ids.extend([str(item).strip() for item in artifact.get("dominant_entities") or [] if str(item).strip()])
    elif artifact_type == "relation":
        for key in ("src_entity_id", "dst_entity_id"):
            value = str(artifact.get(key) or "").strip()
            if value:
                entity_ids.append(value)
    elif artifact_type == "entity":
        entity_id = str(artifact.get("entity_id") or "").strip()
        if entity_id:
            entity_ids.append(entity_id)

    relations: list[dict] = []
    entities: list[dict] = []
    focal = None
    seen_relations: set[str] = set()
    seen_entities: set[str] = set()
    for entity_id in entity_ids[:4]:
        payload = services["entity"].resolve(EntityRequest(scope=scope, entity_id=entity_id, include_relations=True))
        entity = payload.get("entity")
        if entity and not focal:
            focal = entity
        if entity and str(entity.get("entity_id") or "").strip() not in seen_entities:
            entities.append(entity)
            seen_entities.add(str(entity.get("entity_id") or "").strip())
        for relation in payload.get("relations") or []:
            relation_id = str(relation.get("relation_id") or "").strip()
            if relation_id and relation_id not in seen_relations:
                relations.append(relation)
                seen_relations.add(relation_id)
            for entity_key in ("src_entity", "dst_entity", "counterparty_entity"):
                item = relation.get(entity_key)
                entity_ref = str((item or {}).get("entity_id") or "").strip()
                if item and entity_ref and entity_ref not in seen_entities:
                    entities.append(item)
                    seen_entities.add(entity_ref)
    return {"entity": focal, "entities": entities, "relations": relations[:24]}


def _inspect_payload(services: dict, *, scope: ScopeRef, artifact_type: str, artifact_id: str) -> ArtifactInspectResponse:
    if artifact_type in {"claim", "relation", "episode"}:
        explain_payload = services["explain"].explain(ExplainRequest(scope=scope, artifact_type=artifact_type, artifact_id=artifact_id))
    elif artifact_type == "entity":
        entity_payload = services["entity"].resolve(EntityRequest(scope=scope, entity_id=artifact_id, include_relations=True))
        if not entity_payload.get("ok"):
            raise HTTPException(status_code=404, detail="Entity not found")
        entity = entity_payload.get("entity") or {}
        with services["db"].transaction() as connection:
            editorial_state = services["editorial_repo"].get_state(connection, artifact_type="entity", artifact_id=artifact_id)
            decisions = services["editorial_repo"].list_decisions(connection, artifact_type="entity", artifact_id=artifact_id)
            event_ids = services["entities_repo"].event_ids_for_entity(connection, entity_id=artifact_id)
            supporting_events = services["events_repo"].get_many(connection, event_ids[:64])
        explain_payload = {
            "artifact_type": "entity",
            "artifact": entity,
            "editorial_state": editorial_state,
            "decisions": decisions,
            "supporting_events": supporting_events,
        }
    elif artifact_type == "event":
        with services["db"].transaction() as connection:
            event = services["events_repo"].get(connection, artifact_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        explain_payload = {
            "artifact_type": "event",
            "artifact": event,
            "editorial_state": None,
            "decisions": [],
            "supporting_events": [event],
        }
    else:
        raise HTTPException(status_code=404, detail=f"Unsupported artifact type: {artifact_type}")

    artifact = explain_payload.get("artifact")
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    graph = _artifact_graph(services, artifact_type=artifact_type, explain_payload=explain_payload, scope=scope)
    timeline = _artifact_supporting_timeline(services, artifact_type=artifact_type, artifact_id=artifact_id, explain_payload=explain_payload)
    label = (
        str(artifact.get("canonical_claim") or "").strip()
        or str(artifact.get("canonical_name") or "").strip()
        or str(artifact.get("title") or "").strip()
        or str(artifact.get("raw_text") or "").strip()
        or artifact_type
    )
    scene_focus = build_focus_scene(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        label=label,
        timeline=timeline,
        graph=graph,
    )
    return ArtifactInspectResponse(
        scope=scope,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        explain=explain_payload,
        graph=graph,
        artifact_timeline=timeline,
        scene_focus=scene_focus,
    )


def build_web_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    services = build_services(settings)

    app = FastAPI(title="Solaris Web", version=_product_version())
    app.state.settings = settings
    app.state.services = services

    origins = _cors_origins(settings)
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "product": "Solaris",
            "version": _product_version(),
            "db_path": str(settings.db_path),
            "db_signature": _db_signature(settings),
        }

    @app.get("/api/bootstrap", response_model=BootstrapResponse)
    def bootstrap() -> BootstrapResponse:
        default_scope = _preferred_scope(settings, services)
        return BootstrapResponse(
            product={"name": "Solaris", "version": _product_version()},
            default_scope=default_scope,
            default_budget=QueryRequest(query="", scope=default_scope).budget,
            layers=LAYER_DEFINITIONS,
            features={
                "read_only": True,
                "divergence_overlay": True,
                "graph_navigation": True,
                "fractal_projection": True,
            },
            transport={
                "http": True,
                "websocket": True,
                "websocket_path": "/ws",
                "invalidate_mode": "db_signature",
            },
            read_only=True,
        )

    @app.get("/api/landing", response_model=LandingResponse)
    def landing(request: Request) -> LandingResponse:
        scope = _scope_from_query(request, settings, services)
        bundle = _landing_bundle(services, scope)
        pattern_payload = _pattern_payload(services, scope, limit=12)
        scene = build_scene_snapshot(bundle=bundle, patterns=pattern_payload.get("patterns") or [], query="")
        return LandingResponse(
            generated_at=utc_now(),
            scope=scope,
            scene=scene,
            top_patterns=list(pattern_payload.get("patterns") or [])[:8],
            top_recall=_top_recall(scene),
        )

    @app.post("/api/recall", response_model=RecallSceneResponse)
    def recall(body: RecallSceneRequest) -> RecallSceneResponse:
        bundle = services["query"].query(
            QueryRequest(
                query=body.query,
                scope=body.scope,
                scope_mode=body.scope_mode,
                recall_mode=body.recall_mode,
                budget=body.budget,
                include_explanations=body.include_explanations,
            )
        )
        pattern_payload = _pattern_payload(services, body.scope, limit=12)
        scene = build_scene_snapshot(bundle=bundle, patterns=pattern_payload.get("patterns") or [], query=body.query)
        return RecallSceneResponse(
            generated_at=utc_now(),
            query=body.query,
            scope=body.scope,
            scene=scene,
            top_patterns=list(pattern_payload.get("patterns") or [])[:8],
            bundle_meta=dict(bundle.get("meta") or {}),
        )

    @app.get("/api/artifacts/{artifact_type}/{artifact_id}", response_model=ArtifactInspectResponse)
    def inspect_artifact(
        artifact_type: str,
        artifact_id: str,
        tenant: str = Query(default=None),
        namespace: str = Query(default=None),
        workspace: str = Query(default=None),
        project: str = Query(default=None),
    ) -> ArtifactInspectResponse:
        default_scope = _preferred_scope(settings, services)
        scope = ScopeRef(
            tenant=tenant or default_scope.tenant,
            namespace=namespace or default_scope.namespace,
            workspace=workspace or default_scope.workspace,
            project=project or default_scope.project,
        )
        return _inspect_payload(services, scope=scope, artifact_type=artifact_type, artifact_id=artifact_id)

    @app.get("/api/timeline", response_model=TimelineResponseModel)
    def timeline(
        request: Request,
        entity_id: str | None = Query(default=None),
        episode_id: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> TimelineResponseModel:
        scope = _scope_from_query(request, settings, services)
        payload = services["timeline"].timeline(TimelineRequest(scope=scope, entity_id=entity_id, episode_id=episode_id, limit=limit))
        return TimelineResponseModel(scope=scope, entity_id=entity_id, episode_id=episode_id, timeline=payload)

    @app.post("/api/patterns", response_model=PatternsSceneResponse)
    def patterns(body: PatternsSceneRequest) -> PatternsSceneResponse:
        payload = services["patterns"].project(body.to_projection_request())
        return PatternsSceneResponse(scope=body.scope, generated_at=utc_now(), patterns=list(payload.get("patterns") or []))

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        default_scope = _preferred_scope(settings, services)
        await websocket.accept()
        current_scope = ScopeRef(
            tenant=str(websocket.query_params.get("tenant") or default_scope.tenant),
            namespace=str(websocket.query_params.get("namespace") or default_scope.namespace),
            workspace=str(websocket.query_params.get("workspace") or default_scope.workspace),
            project=str(websocket.query_params.get("project") or default_scope.project),
        )
        last_signature = _db_signature(settings)
        await websocket.send_json(
            WebSocketEnvelope(
                type="hello",
                payload={
                    "product": "Solaris",
                    "version": _product_version(),
                    "db_signature": last_signature,
                    "read_only": True,
                },
            ).model_dump(mode="json")
        )
        await websocket.send_json(
            WebSocketEnvelope(type="scope_state", payload=current_scope.model_dump(mode="json")).model_dump(mode="json")
        )
        heartbeat_counter = 0
        try:
            while True:
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=settings.web_ws_poll_seconds)
                    payload = json.loads(raw)
                    if str(payload.get("type") or "").strip() == "scope_state":
                        next_scope = payload.get("payload") or {}
                        current_scope = ScopeRef(
                            tenant=str(next_scope.get("tenant") or current_scope.tenant),
                            namespace=str(next_scope.get("namespace") or current_scope.namespace),
                            workspace=str(next_scope.get("workspace") or current_scope.workspace),
                            project=str(next_scope.get("project") or current_scope.project),
                        )
                        await websocket.send_json(
                            WebSocketEnvelope(type="scope_state", payload=current_scope.model_dump(mode="json")).model_dump(mode="json")
                        )
                except asyncio.TimeoutError:
                    pass
                heartbeat_counter += 1
                next_signature = _db_signature(settings)
                if next_signature != last_signature:
                    last_signature = next_signature
                    await websocket.send_json(
                        WebSocketEnvelope(
                            type="invalidate",
                            payload={
                                "db_signature": next_signature,
                                "scope": current_scope.model_dump(mode="json"),
                            },
                        ).model_dump(mode="json")
                    )
                if heartbeat_counter % max(1, int(10 / settings.web_ws_poll_seconds)) == 0:
                    await websocket.send_json(
                        WebSocketEnvelope(
                            type="activity",
                            payload={
                                "db_signature": last_signature,
                                "scope": current_scope.model_dump(mode="json"),
                            },
                        ).model_dump(mode="json")
                    )
        except WebSocketDisconnect:
            return

    static_dir = settings.web_static_dir
    index_path = static_dir / "index.html" if static_dir else None

    @app.get("/", response_model=None)
    async def root():
        if index_path and index_path.exists():
            return FileResponse(index_path)
        return JSONResponse(
            {
                "ok": True,
                "product": "Solaris",
                "message": "Solaris web API is running. Build `solaris/frontend` to serve the standalone app here.",
            }
        )

    @app.get("/{full_path:path}", response_model=None)
    async def spa_fallback(full_path: str):
        if full_path.startswith("api") or full_path == "ws":
            raise HTTPException(status_code=404, detail="Not found")
        if index_path and index_path.exists():
            asset_path = static_dir / full_path if static_dir else None
            if asset_path and asset_path.exists() and asset_path.is_file():
                return FileResponse(asset_path)
            return FileResponse(index_path)
        return JSONResponse({"ok": False, "detail": "Frontend build not found"}, status_code=404)

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Solaris web API and standalone product surface")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    host = str(args.host or settings.web_host)
    port = int(args.port or settings.web_port)
    uvicorn.run(build_web_app(settings), host=host, port=port, log_level=settings.log_level.lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
