# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import re

from solaris.models.event import MemoryEvent


INTERPRETIVE_EVENT_PREFIXES = (
    "the user is ",
    "the user says ",
    "the user appears ",
    "the user seems ",
    "the operator is ",
    "the operator says ",
    "the speaker is ",
    "the speaker says ",
    "you are asking ",
    "you are saying ",
    "you are reminding ",
)


def _compact(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _looks_interpretive_summary(text: str) -> bool:
    normalized = _compact(text).casefold()
    if not normalized:
        return False
    return normalized.startswith(INTERPRETIVE_EVENT_PREFIXES)


REACTION_OR_ACK_TOKENS = {
    "funny",
    "confusing",
    "crazy",
    "wild",
    "exactly",
    "nice",
    "cool",
    "great",
    "okay",
    "ok",
    "yeah",
    "yes",
    "happened",
    "long",
}
LOW_SIGNAL_REACTION_TOKENS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "do",
    "did",
    "for",
    "from",
    "get",
    "got",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "just",
    "me",
    "my",
    "not",
    "of",
    "on",
    "or",
    "so",
    "that",
    "the",
    "this",
    "to",
    "too",
    "very",
    "really",
    "quite",
    "rather",
    "pretty",
    "taking",
    "what",
    "yeah",
    "yes",
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_'-]+", _compact(text).casefold())


def _looks_explicit_fact_assertion(text: str) -> bool:
    normalized = _compact(text)
    if not normalized:
        return False
    lowered = normalized.casefold()
    if re.match(r"^my\s+[A-Za-z][A-Za-z0-9_\- ]{0,40}\s+is\s+.+$", lowered):
        return True
    if re.match(r"^i\s+(?:am|live|have|work|prefer|like|need|use)\s+.+$", lowered):
        return True
    if re.match(r"^(?:we|you|they)\s+(?:are|have)\s+.+$", lowered):
        return True
    return False


def _should_prefer_interpreted_text_for_derivation(
    *,
    raw_text: str,
    interpreted_text: str,
    event: MemoryEvent,
) -> bool:
    if event.hints.entities:
        return False
    if str(event.kind or "").strip().casefold() == "fact_assertion":
        return False
    raw_tokens = _tokens(raw_text)
    interpreted_tokens = _tokens(interpreted_text)
    if not raw_tokens or not interpreted_tokens:
        return False
    if len(raw_tokens) > 4:
        return False
    if len(interpreted_tokens) < max(8, len(raw_tokens) * 3):
        return False
    if _looks_explicit_fact_assertion(raw_text):
        return False
    return all(token in LOW_SIGNAL_REACTION_TOKENS or token in REACTION_OR_ACK_TOKENS for token in raw_tokens)


def uses_interpreted_reaction_text_for_derivation(event: MemoryEvent) -> bool:
    payload = event.structured_payload or {}
    payload_interpreted = _compact(str(payload.get("interpreted_text") or ""))
    raw_candidate = _compact(str(payload.get("raw_text") or "")) or _compact(event.raw_text or "")
    if not raw_candidate or not payload_interpreted:
        return False
    return _should_prefer_interpreted_text_for_derivation(
        raw_text=raw_candidate,
        interpreted_text=payload_interpreted,
        event=event,
    )


def best_derivation_text(event: MemoryEvent) -> str:
    payload = event.structured_payload or {}

    if str(event.kind or "").strip().casefold() == "tool_result":
        observation = _compact(str(payload.get("tool_observation_text") or ""))
        if observation:
            return observation

    payload_raw = _compact(str(payload.get("raw_text") or ""))
    payload_normalized = _compact(str(payload.get("normalized_text") or ""))
    payload_interpreted = _compact(str(payload.get("interpreted_text") or ""))
    top_raw = _compact(event.raw_text or "")
    top_normalized = _compact(event.normalized_text or "")
    raw_candidate = payload_raw or top_raw

    if payload_raw:
        if _looks_interpretive_summary(top_raw):
            return payload_raw
        if payload_interpreted and top_raw.casefold() == payload_interpreted.casefold():
            return payload_raw
    if uses_interpreted_reaction_text_for_derivation(event):
        return payload_interpreted

    return top_raw or top_normalized or payload_raw or payload_normalized or payload_interpreted


def best_normalized_derivation_text(event: MemoryEvent) -> str:
    text = best_derivation_text(event)
    payload = event.structured_payload or {}
    payload_raw = _compact(str(payload.get("raw_text") or ""))
    payload_normalized = _compact(str(payload.get("normalized_text") or ""))
    payload_interpreted = _compact(str(payload.get("interpreted_text") or ""))
    top_raw = _compact(event.raw_text or "")
    top_normalized = _compact(event.normalized_text or "")

    if payload_normalized and payload_raw and text.casefold() == payload_raw.casefold():
        return payload_normalized
    if top_normalized and top_raw and text.casefold() == top_raw.casefold():
        return top_normalized
    if payload_interpreted and text.casefold() == payload_interpreted.casefold():
        return payload_interpreted.casefold()
    return text.casefold()
