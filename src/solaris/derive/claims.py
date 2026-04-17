# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import re

from solaris.models.event import MemoryEvent
from solaris.derive.text import best_derivation_text

QUESTION_STARTERS = {
    "what",
    "why",
    "how",
    "when",
    "where",
    "who",
    "whom",
    "whose",
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
    "had",
    "tell",
    "explain",
    "summarize",
    "remind",
    "check",
}

LEADING_FILLERS = (
    "all right ",
    "alright ",
    "well ",
    "actually ",
    "so ",
    "but ",
    "like ",
    "right ",
    "okay ",
    "ok ",
)

GENERIC_SUBJECTS = QUESTION_STARTERS | {"please", "there", "here"}
GENERIC_SUBJECT_PHRASES = {
    "the user",
    "the operator",
    "the speaker",
}
PRONOUN_SUBJECTS = {"i", "you", "we", "they", "he", "she", "it"}
SPEECH_ACT_PREFIXES = (
    "asking",
    "checking",
    "explaining",
    "reminding",
    "requesting",
    "saying",
    "summarizing",
    "telling",
    "trying",
    "wondering",
)


def _entity_label(entity: dict) -> str:
    return str(entity.get("canonical_name") or entity.get("name") or "").strip()


def _strip_leading_fillers(text: str) -> str:
    normalized = " ".join((text or "").split()).strip()
    if not normalized:
        return ""
    updated = normalized
    while True:
        lowered = updated.casefold()
        matched = next((prefix for prefix in LEADING_FILLERS if lowered.startswith(prefix)), None)
        if not matched:
            return updated
        updated = updated[len(matched) :].lstrip()


def _looks_interrogative(*, raw_text: str, normalized_text: str, interpreted_text: str) -> bool:
    raw = str(raw_text or "").strip()
    normalized = _strip_leading_fillers(normalized_text)
    interpreted = _strip_leading_fillers(interpreted_text)
    candidate = interpreted or normalized or raw
    lowered = candidate.casefold()
    if "?" in raw or "?" in candidate:
        return True
    if lowered.startswith(("please ", "can you ", "could you ", "would you ", "tell me ", "explain ", "summarize ")):
        return True
    tokens = re.findall(r"[A-Za-z0-9_']+", lowered)
    if not tokens:
        return False
    if tokens[0] in QUESTION_STARTERS:
        return True
    if len(tokens) >= 2 and f"{tokens[0]} {tokens[1]}" in {
        "do you",
        "are you",
        "is this",
        "is there",
        "how does",
        "how do",
        "what is",
        "what are",
        "why is",
        "why are",
    }:
        return True
    return False


def _looks_speech_act_like_claim(*, subject_name: str, object_text: str) -> bool:
    lowered_subject = str(subject_name or "").strip().casefold()
    lowered_object = str(object_text or "").strip().casefold()
    if not lowered_subject or not lowered_object:
        return False
    if lowered_subject not in PRONOUN_SUBJECTS:
        return False
    if lowered_object.startswith(SPEECH_ACT_PREFIXES):
        return True
    return lowered_object.startswith(("likely ", "probably ", "maybe "))


def _derivation_text(event: MemoryEvent) -> str:
    return _strip_leading_fillers(best_derivation_text(event))


def _normalize_explicit_memory_fact(text: str) -> dict | None:
    normalized = " ".join((text or "").split()).strip().rstrip(".")
    if not normalized:
        return None
    lowered = normalized.casefold()
    for prefix in ("remember that ", "remember "):
        if lowered.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
            lowered = normalized.casefold()
            break
    my_attr_match = re.match(r"my\s+(?P<attr>[A-Za-z][A-Za-z0-9_\- ]{1,40}?)\s+is\s+(?P<value>.+)$", normalized, flags=re.IGNORECASE)
    if my_attr_match is not None:
        attr = " ".join(my_attr_match.group("attr").split()).strip()
        value = " ".join(my_attr_match.group("value").split()).strip().rstrip(".")
        attr_lower = attr.casefold()
        if attr_lower == "name":
            return {
                "subject_name": "operator",
                "predicate": "has name",
                "object_text": value,
                "canonical_claim": f"operator has name {value}".strip(),
            }
        return {
            "subject_name": "operator",
            "predicate": f"has {attr}",
            "object_text": value,
            "canonical_claim": f"operator has {attr} {value}".strip(),
        }
    return None


def _normalize_operator_profile_claim(
    *,
    subject_name: str | None,
    predicate: str,
    object_text: str,
    canonical_claim: str,
) -> dict:
    normalized_subject = " ".join(str(subject_name or "").split()).strip()
    normalized_predicate = " ".join(str(predicate or "").split()).strip()
    normalized_object = " ".join(str(object_text or "").split()).strip().rstrip(".")
    normalized_canonical = " ".join(str(canonical_claim or "").split()).strip().rstrip(".")

    subject_lower = normalized_subject.casefold()
    predicate_lower = normalized_predicate.casefold()
    canonical_lower = normalized_canonical.casefold()

    if predicate_lower == "has name" and normalized_object:
        if subject_lower == "operator" or (
            normalized_subject
            and subject_lower not in PRONOUN_SUBJECTS
            and normalized_object.casefold() == subject_lower
        ):
            return {
                "subject_name": "operator",
                "predicate": "has name",
                "object_text": normalized_object,
                "canonical_claim": f"operator has name {normalized_object}".strip(),
            }

    if predicate_lower in {"lives in", "lives"} and normalized_object:
        if subject_lower == "operator" or (
            normalized_subject
            and subject_lower not in PRONOUN_SUBJECTS
            and (
                canonical_lower.startswith(f"{subject_lower} lives in ")
                or canonical_lower.startswith(f"{subject_lower} lives ")
            )
        ):
            return {
                "subject_name": "operator",
                "predicate": "lives in",
                "object_text": normalized_object,
                "canonical_claim": f"operator lives in {normalized_object}".strip(),
            }

    return {
        "subject_name": normalized_subject or None,
        "predicate": normalized_predicate,
        "object_text": normalized_object,
        "canonical_claim": normalized_canonical or f"{normalized_predicate} {normalized_object}".strip(),
    }


def derive_claims(event: MemoryEvent, entities: list[dict]) -> list[dict]:
    payload = event.structured_payload or {}
    explicit_claims = payload.get("claims") or []
    if isinstance(explicit_claims, list):
        derived_claims = []
        for explicit in explicit_claims:
            if not isinstance(explicit, dict):
                continue
            predicate = str(explicit.get("predicate") or "").strip()
            object_text = str(explicit.get("object_text") or explicit.get("object") or "").strip()
            if not predicate or not object_text:
                continue
            normalized_claim = _normalize_operator_profile_claim(
                subject_name=str(explicit.get("subject_name") or explicit.get("subject") or (_entity_label(entities[0]) if entities else "")).strip(),
                predicate=predicate,
                object_text=object_text,
                canonical_claim=str(explicit.get("canonical_claim") or f"{predicate} {object_text}").strip(),
            )
            derived_claim = {
                **normalized_claim,
                "confidence": float(explicit.get("confidence") or event.scores.confidence),
                "pinned": bool(explicit.get("pinned") or event.hints.pin),
            }
            derived_claims.append(derived_claim)
        if derived_claims:
            return derived_claims

    explicit = payload.get("claim") or payload.get("fact") or {}
    if isinstance(explicit, dict):
        predicate = str(explicit.get("predicate") or "").strip()
        object_text = str(explicit.get("object_text") or explicit.get("object") or "").strip()
        if predicate and object_text:
            normalized_claim = _normalize_operator_profile_claim(
                subject_name=str(explicit.get("subject_name") or (_entity_label(entities[0]) if entities else "")).strip(),
                predicate=predicate,
                object_text=object_text,
                canonical_claim=str(explicit.get("canonical_claim") or f"{predicate} {object_text}").strip(),
            )
            return [
                {
                    **normalized_claim,
                    "confidence": float(explicit.get("confidence") or event.scores.confidence),
                    "pinned": bool(explicit.get("pinned") or event.hints.pin),
                }
            ]

    if event.kind not in {"message", "decision", "summary", "note", "fact_assertion", "tool_result"}:
        return []

    text = _derivation_text(event)
    if not text:
        return []

    if event.kind == "fact_assertion":
        normalized_fact = _normalize_explicit_memory_fact(text)
        if normalized_fact is not None:
            return [
                {
                    **normalized_fact,
                    "confidence": max(0.7, float(event.scores.confidence)),
                    "pinned": bool(event.hints.pin or payload.get("pin")),
                }
            ]
        subject_name = _entity_label(entities[0]) if entities else None
        return [
            {
                "subject_name": subject_name,
                "predicate": "asserts",
                "object_text": text,
                "canonical_claim": text.rstrip("."),
                "confidence": max(0.7, float(event.scores.confidence)),
                "pinned": bool(event.hints.pin or payload.get("pin")),
            }
        ]

    if event.kind == "message":
        if _looks_interrogative(
            raw_text=event.raw_text,
            normalized_text=text,
            interpreted_text=str(payload.get("interpreted_text") or ""),
        ):
            return []
        if bool(payload.get("needs_clarification")):
            return []
        if float(event.scores.confidence) < 0.85:
            return []
    elif event.kind == "tool_result":
        if float(event.scores.confidence) < 0.7:
            return []

    match = re.match(
        r"(?P<subject>[\w \-_]{2,60}?)\s+(?P<copula>is|are|should be|means)\s+(?P<object>.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return []
    subject_name = match.group("subject").strip()
    predicate = match.group("copula").strip().casefold()
    object_text = match.group("object").strip().rstrip(".")
    if subject_name.casefold() in GENERIC_SUBJECTS:
        return []
    if subject_name.casefold() in GENERIC_SUBJECT_PHRASES:
        return []
    if _looks_speech_act_like_claim(subject_name=subject_name, object_text=object_text):
        return []
    if len(object_text) > 160:
        return []
    canonical_claim = f"{subject_name} {predicate} {object_text}".strip()
    return [
        {
            "subject_name": subject_name,
            "predicate": predicate,
            "object_text": object_text,
            "canonical_claim": canonical_claim,
            "confidence": float(event.scores.confidence),
            "pinned": bool(event.hints.pin),
        }
    ]
