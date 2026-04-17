# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.event import MemoryEvent


def derive_state_lease(event: MemoryEvent) -> dict | None:
    if event.kind != "state_update":
        return None
    payload = event.structured_payload or {}
    lease_key = str(payload.get("lease_key") or payload.get("key") or "").strip()
    if not lease_key:
        return None
    ttl_seconds = int(payload.get("ttl_seconds") or payload.get("ttl") or 3600)
    value_json = payload.get("value_json") or payload.get("value") or {}
    if not isinstance(value_json, dict):
        value_json = {"value": value_json}
    return {"lease_key": lease_key, "value_json": value_json, "ttl_seconds": ttl_seconds}
