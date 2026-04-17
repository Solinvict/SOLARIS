# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.query import EntityRequest


def register_entity_tools(mcp, services) -> None:
    @mcp.tool(name="solaris.entity")
    def entity(scope: dict, entity_id: str | None = None, canonical_name: str | None = None, include_relations: bool = True) -> dict:
        return services["entity"].resolve(
            EntityRequest(
                scope=scope,
                entity_id=entity_id,
                canonical_name=canonical_name,
                include_relations=include_relations,
            )
        )
