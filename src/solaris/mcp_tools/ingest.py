# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.event import IngestEventsRequest, MemoryEvent


def register_ingest_tools(mcp, services) -> None:
    @mcp.tool(name="solaris.ingest_events")
    def ingest_events(events: list[dict]) -> dict:
        req = IngestEventsRequest(events=[MemoryEvent(**event) for event in events])
        return services["ingest"].ingest_events(req).model_dump(mode="json")
