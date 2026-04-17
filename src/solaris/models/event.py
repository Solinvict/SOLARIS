# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pydantic import BaseModel, Field

from .scope import ScopeRef


class EventHintSet(BaseModel):
    entities: list[str] = Field(default_factory=list)
    relations: list[dict] = Field(default_factory=list)
    episode_hint: str | None = None
    pin: bool = False


class EventScores(BaseModel):
    importance: float = 0.5
    confidence: float = 0.5


class MemoryEvent(BaseModel):
    event_id: str | None = None
    schema_version: int = 1
    timestamp: str
    scope: ScopeRef
    session_id: str | None = None
    source_app: str
    source_module: str = ""
    actor: str = "system"
    kind: str
    raw_text: str = ""
    normalized_text: str = ""
    structured_payload: dict = Field(default_factory=dict)
    hints: EventHintSet = Field(default_factory=EventHintSet)
    scores: EventScores = Field(default_factory=EventScores)
    idempotency_key: str = Field(min_length=1)


class IngestEventsRequest(BaseModel):
    events: list[MemoryEvent] = Field(default_factory=list)


class IngestEventsResult(BaseModel):
    ok: bool = True
    accepted: int = 0
    duplicates: int = 0
    event_ids: list[str] = Field(default_factory=list)
    derived: dict = Field(default_factory=dict)

