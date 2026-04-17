# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pydantic import BaseModel

from .scope import ScopeRef


class Claim(BaseModel):
    claim_id: str
    scope: ScopeRef
    subject_entity_id: str | None = None
    predicate: str
    object_text: str
    canonical_claim: str
    confidence: float = 0.5
    evidence_count: int = 1
    pinned: bool = False
    first_seen: str
    last_seen: str
    derivation_version: int = 1

