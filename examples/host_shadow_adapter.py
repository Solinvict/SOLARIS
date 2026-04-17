# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SolarisToolClient(Protocol):
    def call_tool(self, tool_name: str, payload: dict) -> dict: ...


@dataclass(slots=True)
class HostTurn:
    timestamp: str
    session_id: str
    text: str
    kind: str = "message"
    actor: str = "user"
    source_app: str = "host_runtime"
    source_module: str = "host_adapter"


class SolarisShadowAdapter:
    """Minimal example of running Solaris beside an existing host memory stack."""

    def __init__(self, client: SolarisToolClient, *, scope: dict[str, str], policy_profile: str = "default_v1") -> None:
        self._client = client
        self._scope = dict(scope)
        self._policy_profile = str(policy_profile)

    def open_runtime_session(self) -> str:
        response = self._client.call_tool(
            "solaris.open_session",
            {
                "scope": self._scope,
                "kind": "runtime",
                "policy_profile": self._policy_profile,
            },
        )
        return str(response["session_id"])

    def open_interaction_session(self, *, parent_session_id: str) -> str:
        response = self._client.call_tool(
            "solaris.open_session",
            {
                "scope": self._scope,
                "kind": "interaction",
                "parent_session_id": parent_session_id,
                "policy_profile": self._policy_profile,
            },
        )
        return str(response["session_id"])

    def ingest_turn(self, turn: HostTurn) -> dict:
        event = {
            "timestamp": turn.timestamp,
            "scope": self._scope,
            "session_id": turn.session_id,
            "source_app": turn.source_app,
            "source_module": turn.source_module,
            "actor": turn.actor,
            "kind": turn.kind,
            "raw_text": turn.text,
            "normalized_text": turn.text.casefold(),
            "structured_payload": {},
            "hints": {
                "entities": [],
                "relations": [],
                "episode_hint": None,
                "pin": False,
            },
            "scores": {
                "importance": 0.7,
                "confidence": 0.8,
            },
            "idempotency_key": f"{turn.session_id}:{turn.timestamp}:{turn.text}",
        }
        return self._client.call_tool("solaris.ingest_events", {"events": [event]})

    def run_review(self, *, session_id: str | None = None, mode: str = "boundary", limit: int = 200) -> dict:
        payload = {
            "scope": self._scope,
            "policy_profile": self._policy_profile,
            "mode": mode,
            "limit": limit,
        }
        if session_id:
            payload["session_id"] = session_id
        return self._client.call_tool("solaris.run_editorial_review", payload)

    def shadow_recall(self, query_text: str, *, recall_mode: str = "default") -> dict:
        return self._client.call_tool(
            "solaris.query",
            {
                "query": query_text,
                "scope": self._scope,
                "recall_mode": recall_mode,
            },
        )


def example_shadow_flow(client: SolarisToolClient) -> dict:
    """Illustrative sidecar flow: existing host memory remains authoritative."""

    adapter = SolarisShadowAdapter(
        client,
        scope={
            "tenant": "personal",
            "namespace": "host",
            "workspace": "default",
            "project": "core",
        },
    )
    runtime_session_id = adapter.open_runtime_session()
    interaction_session_id = adapter.open_interaction_session(parent_session_id=runtime_session_id)

    adapter.ingest_turn(
        HostTurn(
            timestamp="2026-04-17T18:00:00+00:00",
            session_id=interaction_session_id,
            text="We keep graph structure stored and fractal memory projected.",
        )
    )
    adapter.run_review(session_id=interaction_session_id)

    host_memory_payload = {
        "query": "what do you remember about graph and fractal memory",
        "answer": "We store graph structure and project fractal patterns.",
        "artifacts": [
            "graph memory is stored structure",
            "fractal memory is projected structure",
        ],
    }
    solaris_bundle = adapter.shadow_recall("what do you remember about graph and fractal memory")

    return {
        "host_memory_payload": host_memory_payload,
        "solaris_bundle": solaris_bundle,
    }
