# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solaris.config import Settings
from solaris.models.event import EventHintSet, EventScores, IngestEventsRequest, MemoryEvent
from solaris.models.query import ExplainRequest, QueryRequest
from solaris.models.scope import ScopeRef
from solaris.server import build_mcp, build_services


@pytest.fixture()
def scope() -> ScopeRef:
    return ScopeRef(tenant="personal", namespace="host", workspace="default", project="core")


@pytest.fixture()
def other_scope() -> ScopeRef:
    return ScopeRef(tenant="personal", namespace="host", workspace="default", project="other")


@pytest.fixture()
def services(tmp_path: Path):
    settings = Settings(
        project_root=ROOT,
        db_path=tmp_path / "solaris.db",
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
    )
    return build_services(settings)


@pytest.fixture()
def mcp(tmp_path: Path):
    settings = Settings(
        project_root=ROOT,
        db_path=tmp_path / "solaris_mcp.db",
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
    )
    return build_mcp(settings)


def make_event(
    *,
    scope: ScopeRef,
    session_id: str,
    timestamp: str,
    idempotency_key: str,
    raw_text: str,
    normalized_text: str | None = None,
    kind: str = "message",
    source_app: str = "host_runtime",
    source_module: str = "host_runtime_core",
    actor: str = "user",
    hints: dict | None = None,
    structured_payload: dict | None = None,
    importance: float = 0.8,
    confidence: float = 0.9,
) -> MemoryEvent:
    return MemoryEvent(
        timestamp=timestamp,
        scope=scope,
        session_id=session_id,
        source_app=source_app,
        source_module=source_module,
        actor=actor,
        kind=kind,
        raw_text=raw_text,
        normalized_text=normalized_text or raw_text.casefold(),
        structured_payload=structured_payload or {},
        hints=EventHintSet(**(hints or {})),
        scores=EventScores(importance=importance, confidence=confidence),
        idempotency_key=idempotency_key,
    )


def ingest(services: dict, *events: MemoryEvent):
    return services["ingest"].ingest_events(IngestEventsRequest(events=list(events)))


def query(services: dict, *, scope: ScopeRef, text: str, recall_mode: str = "default") -> dict:
    return services["query"].query(QueryRequest(query=text, scope=scope, recall_mode=recall_mode))


def explain(services: dict, *, scope: ScopeRef, artifact_type: str, artifact_id: str) -> dict:
    return services["explain"].explain(ExplainRequest(scope=scope, artifact_type=artifact_type, artifact_id=artifact_id))
