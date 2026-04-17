# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.query import PatternProjectionRequest


def register_pattern_tools(mcp, services) -> None:
    @mcp.tool(name="solaris.project_patterns")
    def project_patterns(scope: dict, limit: int = 20, min_weight: float = 0.0, pattern_kinds: list[str] | None = None) -> dict:
        return services["patterns"].project(
            PatternProjectionRequest(
                scope=scope,
                limit=limit,
                min_weight=min_weight,
                pattern_kinds=pattern_kinds or [],
            )
        )
