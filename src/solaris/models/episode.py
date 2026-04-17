# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pydantic import BaseModel, Field

from .scope import ScopeRef


class Episode(BaseModel):
    episode_id: str
    scope: ScopeRef
    title: str
    status: str = "open"
    start_at: str
    end_at: str | None = None
    summary_text: str = ""
    dominant_entities: list[str] = Field(default_factory=list)
    confidence: float = 0.5

