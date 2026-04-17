# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.session import CloseSessionRequest, OpenSessionRequest


def register_session_tools(mcp, services) -> None:
    @mcp.tool(name="solaris.open_session")
    def open_session(scope: dict, kind: str = "runtime", parent_session_id: str | None = None, policy_profile: str = "default_v1", policy_context: dict | None = None) -> dict:
        req = OpenSessionRequest(
            scope=scope,
            kind=kind,
            parent_session_id=parent_session_id,
            policy_profile=policy_profile,
            policy_context=policy_context or {},
        )
        return services["sessions"].open_session(req).model_dump(mode="json")

    @mcp.tool(name="solaris.close_session")
    def close_session(session_id: str) -> dict:
        return services["sessions"].close_session(CloseSessionRequest(session_id=session_id))
