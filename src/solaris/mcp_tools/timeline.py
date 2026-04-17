# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.query import TimelineRequest


def register_timeline_tools(mcp, services) -> None:
    @mcp.tool(name="solaris.timeline")
    def timeline(scope: dict, entity_id: str | None = None, episode_id: str | None = None, limit: int = 50) -> dict:
        return services["timeline"].timeline(
            TimelineRequest(scope=scope, entity_id=entity_id, episode_id=episode_id, limit=limit)
        )
