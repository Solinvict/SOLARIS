# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pydantic import BaseModel, Field

from .scope import ScopeRef


class StateLease(BaseModel):
    lease_id: str
    scope: ScopeRef
    lease_key: str
    value_json: dict = Field(default_factory=dict)
    issued_at: str
    refreshed_at: str
    expires_at: str
    status: str = "active"


class UpsertStateRequest(BaseModel):
    scope: ScopeRef
    lease_key: str
    value_json: dict = Field(default_factory=dict)
    ttl_seconds: int = 3600

