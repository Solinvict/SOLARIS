# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.state import UpsertStateRequest


def register_state_tools(mcp, services) -> None:
    @mcp.tool(name="solaris.upsert_state")
    def upsert_state(scope: dict, lease_key: str, value_json: dict | None = None, ttl_seconds: int = 3600) -> dict:
        req = UpsertStateRequest(scope=scope, lease_key=lease_key, value_json=value_json or {}, ttl_seconds=ttl_seconds)
        with services["db"].transaction() as connection:
            return services["state_repo"].upsert(
                connection,
                scope=req.scope,
                lease_key=req.lease_key,
                value_json=req.value_json,
                ttl_seconds=req.ttl_seconds,
            )
