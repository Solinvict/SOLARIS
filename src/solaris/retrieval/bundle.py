# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations


def build_bundle(
    *,
    claims: list[dict],
    state_leases: list[dict],
    episodes: list[dict],
    events: list[dict],
    entities: list[dict],
    relations: list[dict],
    explanations: list[dict],
    recorded: dict | None = None,
    divergence_summary: dict | None = None,
    meta: dict | None = None,
) -> dict:
    return {
        "claims": claims,
        "state_leases": state_leases,
        "episodes": episodes,
        "events": events,
        "entities": entities,
        "relations": relations,
        "explanations": explanations,
        "recorded": dict(recorded or {}),
        "divergence_summary": dict(divergence_summary or {}),
        "meta": dict(meta or {}),
    }
