# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.query import ExplainRequest


def register_explain_tools(mcp, services) -> None:
    @mcp.tool(name="solaris.explain")
    def explain(scope: dict, artifact_type: str, artifact_id: str) -> dict:
        return services["explain"].explain(
            ExplainRequest(scope=scope, artifact_type=artifact_type, artifact_id=artifact_id)
        )

    @mcp.tool(name="solaris.explain_memory")
    def explain_memory(scope: dict, artifact_type: str, artifact_id: str) -> dict:
        return services["explain"].explain(
            ExplainRequest(scope=scope, artifact_type=artifact_type, artifact_id=artifact_id)
        )
