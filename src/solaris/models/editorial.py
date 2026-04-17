# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import ActivationState, EditorialAction, RememberState, ReviewStatus
from .scope import ScopeRef


class ArtifactEditorialState(BaseModel):
    artifact_type: str
    artifact_id: str
    scope: ScopeRef
    remember_state: str = RememberState.candidate.value
    activation_state: str = ActivationState.suppressed.value
    review_status: str = ReviewStatus.pending.value
    remember_score: float = 0.0
    influence_score: float = 0.0
    pinned: bool = False
    protected: bool = False
    last_reviewed_at: str | None = None
    next_review_at: str | None = None
    policy_profile: str = "default_v1"
    policy_version: int = 1
    rationale_json: dict = Field(default_factory=dict)


class EditorialDecision(BaseModel):
    decision_id: str
    artifact_type: str
    artifact_id: str
    action: str = EditorialAction.leave_candidate.value
    previous_state: str | None = None
    new_state: str | None = None
    policy_profile: str
    policy_version: int = 1
    scores: dict = Field(default_factory=dict)
    rationale: dict = Field(default_factory=dict)
    supporting_event_ids: list[str] = Field(default_factory=list)
    decided_by: str = "rule_engine"
    decided_at: str


class ReviewQueueItem(BaseModel):
    review_id: str
    artifact_type: str
    artifact_id: str
    scope: ScopeRef
    trigger: str
    priority: float = 0.5
    status: str = ReviewStatus.pending.value
    not_before: str | None = None
    created_at: str
    reviewed_at: str | None = None


class RunEditorialReviewRequest(BaseModel):
    scope: ScopeRef
    session_id: str | None = None
    policy_profile: str = "default_v1"
    limit: int = 100
    mode: str = "boundary"


class ApplyEditorialDecisionRequest(BaseModel):
    artifact_type: str
    artifact_id: str
    scope: ScopeRef
    action: str
    rationale: dict = Field(default_factory=dict)
    policy_profile: str = "default_v1"

