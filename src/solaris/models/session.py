# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import SessionKind
from .scope import ScopeRef


class SessionRecord(BaseModel):
    session_id: str
    parent_session_id: str | None = None
    kind: str = SessionKind.runtime.value
    scope: ScopeRef
    policy_profile: str
    policy_context: dict = Field(default_factory=dict)
    opened_at: str
    closed_at: str | None = None


class OpenSessionRequest(BaseModel):
    parent_session_id: str | None = None
    kind: str = SessionKind.runtime.value
    scope: ScopeRef
    policy_profile: str = "default_v1"
    policy_context: dict = Field(default_factory=dict)


class CloseSessionRequest(BaseModel):
    session_id: str

