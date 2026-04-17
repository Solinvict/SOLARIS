# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.query import QueryRequest


def register_query_tools(mcp, services) -> None:
    @mcp.tool(name="solaris.query")
    def query(query: str, scope: dict, scope_mode: str = "local", recall_mode: str = "default", modes: list[str] | None = None, budget: dict | None = None, include_explanations: bool = True) -> dict:
        req = QueryRequest(
            query=query,
            scope=scope,
            scope_mode=scope_mode,
            recall_mode=recall_mode,
            modes=modes or ["state", "claims", "episodes", "events", "graph"],
            budget=budget or {},
            include_explanations=include_explanations,
        )
        return services["query"].query(req)

    @mcp.tool(name="solaris.recall")
    def recall(
        query: str,
        scope: dict,
        scope_mode: str = "local",
        recall_mode: str = "default",
        modes: list[str] | None = None,
        budget: dict | None = None,
        include_explanations: bool = True,
    ) -> dict:
        req = QueryRequest(
            query=query,
            scope=scope,
            scope_mode=scope_mode,
            recall_mode=recall_mode,
            modes=modes or ["state", "claims", "episodes", "events", "graph"],
            budget=budget or {},
            include_explanations=include_explanations,
        )
        return services["query"].query(req)
