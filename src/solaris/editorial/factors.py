# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import re


GENERIC_EPISODE_TITLES = {"conversation", "message", "activity", "system", "note"}
QUESTION_STARTERS = {
    "what",
    "why",
    "how",
    "when",
    "where",
    "who",
    "which",
    "is",
    "are",
    "am",
    "do",
    "does",
    "did",
    "can",
    "could",
    "would",
    "should",
    "will",
    "have",
    "has",
    "tell",
    "explain",
    "summarize",
    "remind",
    "check",
}


def _looks_question_like(text: str) -> bool:
    normalized = " ".join((text or "").split()).strip().casefold()
    if not normalized:
        return False
    while True:
        matched = next(
            (prefix for prefix in ("all right ", "alright ", "well ", "actually ", "so ", "but ", "like ", "okay ", "ok ") if normalized.startswith(prefix)),
            None,
        )
        if not matched:
            break
        normalized = normalized[len(matched) :].lstrip()
    if "?" in normalized:
        return True
    tokens = re.findall(r"[A-Za-z0-9_']+", normalized)
    if not tokens:
        return False
    return tokens[0] in QUESTION_STARTERS


def compute_factors(*, artifact_type: str, artifact: dict, supporting_events: list[dict]) -> dict:
    event_count = max(1, len(supporting_events))
    primary_event = supporting_events[0] if supporting_events else {}
    primary_kind = str(primary_event.get("kind") or artifact_type).strip().casefold()
    importance = max(float(event.get("importance") or 0.0) for event in supporting_events) if supporting_events else 0.0
    question_like = artifact_type == "claim" and _looks_question_like(str(artifact.get("canonical_claim") or ""))
    primary_payload = dict(primary_event.get("structured_payload") or {}) if isinstance(primary_event.get("structured_payload"), dict) else {}
    primary_route_domain = str(primary_payload.get("route_domain") or "").strip().casefold()
    primary_route_action = str(primary_payload.get("route_action") or "").strip().casefold()
    claim_signal = str(primary_payload.get("claim_signal") or "").strip().casefold()
    source_app = str(primary_event.get("source_app") or "").strip().casefold()
    legacy_note_claim = (
        primary_kind == "note"
        and bool(primary_payload.get("claim"))
        and (source_app == "legacy_adapter" or source_app.endswith("_legacy"))
    )
    explicit_memory_signal = (
        primary_route_domain == "memory"
        or primary_route_action.startswith("remember_")
        or claim_signal == "explicit_memory"
        or legacy_note_claim
    ) and not question_like
    explicit = bool(artifact.get("pinned")) or primary_kind in {"decision", "failure", "fact_assertion"} or explicit_memory_signal
    repeated = event_count >= 2 or int(artifact.get("evidence_count") or 0) >= 2
    generic_episode = artifact_type == "episode" and str(artifact.get("title") or "").strip().casefold() in GENERIC_EPISODE_TITLES
    weak_relation = artifact_type == "relation" and str(artifact.get("relation_type") or "").strip().casefold() == "related_to"

    if explicit:
        consequence = 1.0 if artifact.get("pinned") else 0.85
    elif repeated:
        consequence = 0.65
    else:
        consequence = min(0.25, importance * 0.35)

    recurrence = 1.0 if event_count >= 3 else 0.7 if event_count == 2 else 0.0

    if artifact_type == "claim":
        if explicit:
            identity_relevance = 0.9
            future_utility = 0.95
        elif question_like:
            identity_relevance = 0.15
            future_utility = 0.1
        elif repeated:
            identity_relevance = 0.75
            future_utility = 0.75
        else:
            identity_relevance = 0.2
            future_utility = 0.15
    elif artifact_type == "episode":
        if explicit and not generic_episode:
            identity_relevance = 0.8
            future_utility = 0.8
        elif repeated and not generic_episode:
            identity_relevance = 0.7
            future_utility = 0.7
        else:
            identity_relevance = 0.1
            future_utility = 0.1
    elif artifact_type == "relation":
        if explicit and not weak_relation:
            identity_relevance = 0.75
            future_utility = 0.75
        elif repeated and not weak_relation:
            identity_relevance = 0.65
            future_utility = 0.55
        elif weak_relation:
            identity_relevance = 0.15
            future_utility = 0.1
        else:
            identity_relevance = 0.25
            future_utility = 0.2
    else:
        identity_relevance = 0.35
        future_utility = 0.25

    if artifact.get("pinned"):
        user_emphasis = 1.0
    elif explicit:
        user_emphasis = 0.85
    elif repeated:
        user_emphasis = min(0.75, importance)
    else:
        user_emphasis = min(0.2, importance * 0.2)

    return {
        "consequence": consequence,
        "recurrence": recurrence,
        "identity_relevance": identity_relevance,
        "future_utility": future_utility,
        "user_emphasis": user_emphasis,
        "unresolvedness": 0.0,
        "novelty": 0.0,
        "anti_repeat_value": 0.0,
    }
