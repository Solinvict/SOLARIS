# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pydantic import BaseModel, Field

from .scope import ScopeRef


class Entity(BaseModel):
    entity_id: str
    scope: ScopeRef
    canonical_name: str
    entity_type: str = "concept"
    aliases: list[str] = Field(default_factory=list)
    first_seen: str
    last_seen: str


class Relation(BaseModel):
    relation_id: str
    scope: ScopeRef
    src_entity_id: str
    relation_type: str
    dst_entity_id: str
    confidence: float = 0.5
    first_seen: str
    last_seen: str
    derivation_version: int = 1

