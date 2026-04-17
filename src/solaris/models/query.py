# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import RecallMode
from .scope import ScopeMode, ScopeRef


class QueryBudget(BaseModel):
    state: int = 3
    claims: int = 5
    episodes: int = 3
    events: int = 8
    entities: int = 6
    relations: int = 10


class QueryRequest(BaseModel):
    query: str
    scope: ScopeRef
    scope_mode: str = ScopeMode.local.value
    recall_mode: str = RecallMode.default.value
    modes: list[str] = Field(default_factory=lambda: ["state", "claims", "episodes", "events", "graph"])
    budget: QueryBudget = Field(default_factory=QueryBudget)
    include_explanations: bool = True


class QueryBundle(BaseModel):
    claims: list[dict] = Field(default_factory=list)
    state_leases: list[dict] = Field(default_factory=list)
    episodes: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    entities: list[dict] = Field(default_factory=list)
    relations: list[dict] = Field(default_factory=list)
    explanations: list[dict] = Field(default_factory=list)
    recorded: dict = Field(default_factory=dict)
    divergence_summary: dict = Field(default_factory=dict)
    meta: dict = Field(default_factory=dict)


class TimelineRequest(BaseModel):
    scope: ScopeRef
    entity_id: str | None = None
    episode_id: str | None = None
    limit: int = 50


class EntityRequest(BaseModel):
    scope: ScopeRef
    entity_id: str | None = None
    canonical_name: str | None = None
    include_relations: bool = True


class ExplainRequest(BaseModel):
    scope: ScopeRef
    artifact_type: str
    artifact_id: str


class PatternProjectionRequest(BaseModel):
    scope: ScopeRef
    limit: int = 20
    min_weight: float = 0.0
    pattern_kinds: list[str] = Field(default_factory=list)
