# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.editorial import ApplyEditorialDecisionRequest, RunEditorialReviewRequest
from solaris.models.scope import ScopeRef


def register_editorial_tools(mcp, services) -> None:
    @mcp.tool(name="solaris.get_review_queue")
    def get_review_queue(scope: dict, session_id: str | None = None, limit: int = 50) -> dict:
        return services["review"].get_review_queue(scope=ScopeRef(**scope), session_id=session_id, limit=limit)

    @mcp.tool(name="solaris.run_editorial_review")
    def run_editorial_review(scope: dict, session_id: str | None = None, policy_profile: str = "default_v1", limit: int = 100, mode: str = "boundary") -> dict:
        req = RunEditorialReviewRequest(scope=scope, session_id=session_id, policy_profile=policy_profile, limit=limit, mode=mode)
        return services["review"].run_review(req.scope, req.session_id, req.policy_profile, req.limit, req.mode)

    @mcp.tool(name="solaris.reconsider")
    def reconsider(scope: dict, session_id: str | None = None, policy_profile: str = "default_v1", limit: int = 100) -> dict:
        req = RunEditorialReviewRequest(
            scope=scope,
            session_id=session_id,
            policy_profile=policy_profile,
            limit=limit,
            mode="reconsider",
        )
        return services["review"].run_review(req.scope, req.session_id, req.policy_profile, req.limit, req.mode)

    @mcp.tool(name="solaris.apply_editorial_decision")
    def apply_editorial_decision(scope: dict, artifact_type: str, artifact_id: str, action: str, rationale: dict | None = None, policy_profile: str = "default_v1") -> dict:
        req = ApplyEditorialDecisionRequest(
            scope=scope,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            action=action,
            rationale=rationale or {},
            policy_profile=policy_profile,
        )
        return services["review"].apply_decision(req)
