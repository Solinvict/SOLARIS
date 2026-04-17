# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from solaris.models.query import PatternProjectionRequest, QueryBudget
from solaris.models.scope import ScopeRef


class LayerDefinition(BaseModel):
    key: str
    label: str
    description: str


class SceneNode(BaseModel):
    id: str
    layer: str
    artifact_type: str
    artifact_id: str
    label: str
    subtitle: str = ""
    timestamp: str | None = None
    confidence: float = 0.0
    weight: float = 0.0
    emphasis: float = 0.0
    remember_state: str | None = None
    activation_state: str | None = None
    divergence: bool = False
    projected: bool = False
    stored: bool = True
    metadata: dict = Field(default_factory=dict)


class SceneEdge(BaseModel):
    id: str
    source: str
    target: str
    edge_type: str
    layer: str
    label: str = ""
    strength: float = 0.0
    metadata: dict = Field(default_factory=dict)


class InspectorCard(BaseModel):
    title: str
    artifact_type: str
    artifact_id: str
    summary: str
    layer: str
    confidence: float = 0.0
    timestamp: str | None = None


class ArchiveDensitySummary(BaseModel):
    total_events: int = 0
    recorded_events: int = 0
    earliest_timestamp: str | None = None
    latest_timestamp: str | None = None


class GraphSummary(BaseModel):
    relation_count: int = 0
    entity_count: int = 0
    neighborhood_count: int = 0


class SceneSnapshot(BaseModel):
    nodes: list[SceneNode] = Field(default_factory=list)
    edges: list[SceneEdge] = Field(default_factory=list)
    focus_node_ids: list[str] = Field(default_factory=list)
    inspector_cards: list[InspectorCard] = Field(default_factory=list)
    archive_density: ArchiveDensitySummary = Field(default_factory=ArchiveDensitySummary)
    graph_summary: GraphSummary = Field(default_factory=GraphSummary)
    divergence_summary: dict = Field(default_factory=dict)
    meta: dict = Field(default_factory=dict)


class BootstrapResponse(BaseModel):
    ok: bool = True
    product: dict
    default_scope: ScopeRef
    default_budget: QueryBudget
    layers: list[LayerDefinition]
    features: dict
    transport: dict
    read_only: bool = True


class LandingResponse(BaseModel):
    ok: bool = True
    generated_at: datetime
    scope: ScopeRef
    scene: SceneSnapshot
    top_patterns: list[dict] = Field(default_factory=list)
    top_recall: list[dict] = Field(default_factory=list)


class RecallSceneRequest(BaseModel):
    query: str = ""
    scope: ScopeRef
    scope_mode: str = "local"
    recall_mode: str = "default"
    budget: QueryBudget = Field(default_factory=QueryBudget)
    include_explanations: bool = True


class RecallSceneResponse(BaseModel):
    ok: bool = True
    generated_at: datetime
    query: str = ""
    scope: ScopeRef
    scene: SceneSnapshot
    top_patterns: list[dict] = Field(default_factory=list)
    bundle_meta: dict = Field(default_factory=dict)


class TimelineResponseModel(BaseModel):
    ok: bool = True
    scope: ScopeRef
    entity_id: str | None = None
    episode_id: str | None = None
    timeline: dict


class ArtifactInspectResponse(BaseModel):
    ok: bool = True
    scope: ScopeRef
    artifact_type: str
    artifact_id: str
    explain: dict = Field(default_factory=dict)
    graph: dict = Field(default_factory=dict)
    artifact_timeline: list[dict] = Field(default_factory=list)
    scene_focus: SceneSnapshot = Field(default_factory=SceneSnapshot)


class PatternsSceneRequest(BaseModel):
    scope: ScopeRef
    limit: int = 20
    min_weight: float = 0.0
    pattern_kinds: list[str] = Field(default_factory=list)

    def to_projection_request(self) -> PatternProjectionRequest:
        return PatternProjectionRequest(
            scope=self.scope,
            limit=self.limit,
            min_weight=self.min_weight,
            pattern_kinds=self.pattern_kinds,
        )


class PatternsSceneResponse(BaseModel):
    ok: bool = True
    scope: ScopeRef
    generated_at: datetime
    patterns: list[dict] = Field(default_factory=list)


class WebSocketEnvelope(BaseModel):
    type: str
    payload: dict = Field(default_factory=dict)

