# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations


def explain_artifact(*, artifact_type: str, artifact: dict | None, editorial_state: dict | None, decisions: list[dict], supporting_events: list[dict]) -> dict:
    return {
        "artifact_type": artifact_type,
        "artifact": artifact,
        "editorial_state": editorial_state,
        "decisions": decisions,
        "supporting_events": supporting_events,
    }
