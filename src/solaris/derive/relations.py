# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import re

from solaris.models.event import MemoryEvent
from solaris.derive.text import best_normalized_derivation_text

ALLOWED_RELATION_TYPES = {
    "blocked_by",
    "depends_on",
    "failed_due_to",
    "causes",
    "uses",
}

LOW_SIGNAL_RELATION_TOKENS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "by",
    "for",
    "from",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "so",
    "that",
    "the",
    "this",
    "to",
    "was",
    "we",
    "what",
    "why",
    "with",
    "you",
    "your",
}

RELATION_CUE_RULES = (
    ("blocked by", "blocked_by", False),
    ("depends on", "depends_on", False),
    ("depends upon", "depends_on", False),
    ("requires", "depends_on", False),
    ("built on", "depends_on", False),
    ("grounded on", "depends_on", False),
    ("backed by", "depends_on", False),
    ("on top of", "depends_on", False),
    ("runs on", "depends_on", False),
    ("failed because", "failed_due_to", False),
    ("failed due to", "failed_due_to", False),
    ("failure due to", "failed_due_to", False),
    ("caused by", "causes", True),
    ("causes", "causes", False),
    ("caused ", "causes", False),
    ("uses", "uses", False),
    ("using", "uses", False),
    ("built with", "uses", False),
    ("powered by", "uses", False),
    ("connected to", "uses", False),
    ("connection to", "uses", False),
)


def _entity_label(entity: dict) -> str:
    return str(entity.get("canonical_name") or entity.get("name") or "").strip()


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9_\-]+", str(text or "").casefold()) if token]


def _entity_is_low_signal(name: str) -> bool:
    tokens = _tokens(name)
    if not tokens:
        return True
    non_stopwords = [token for token in tokens if token not in LOW_SIGNAL_RELATION_TOKENS]
    return len(non_stopwords) < 1


def _candidate_entity_names(entities: list[dict]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for entity in entities:
        name = _entity_label(entity)
        key = name.casefold().strip()
        if not key or key in seen or _entity_is_low_signal(name):
            continue
        seen.add(key)
        names.append(name)
    return names


def _entity_spans(normalized_text: str, entity_names: list[str]) -> list[dict]:
    spans: list[dict] = []
    for name in entity_names:
        for match in re.finditer(re.escape(name.casefold()), normalized_text):
            spans.append({"name": name, "start": match.start(), "end": match.end()})
    return spans


def _select_pair_for_cue(normalized_text: str, entity_names: list[str], cue: str) -> tuple[str, str] | None:
    if len(entity_names) < 2:
        return None
    cue_match = re.search(re.escape(cue), normalized_text)
    if cue_match is None:
        return None
    spans = _entity_spans(normalized_text, entity_names)
    if not spans:
        return None
    before = [item for item in spans if int(item["end"]) <= cue_match.start()]
    after = [item for item in spans if int(item["start"]) >= cue_match.end()]
    if before and after:
        src = max(before, key=lambda item: int(item["end"]))["name"]
        dst = min(after, key=lambda item: int(item["start"]))["name"]
        if src.casefold() != dst.casefold():
            return src, dst
    return entity_names[0], entity_names[1]


def derive_relations(event: MemoryEvent, entities: list[dict]) -> list[dict]:
    hinted = []
    for item in event.hints.relations:
        if not isinstance(item, dict):
            continue
        src = str(item.get("src") or item.get("source") or "").strip()
        dst = str(item.get("dst") or item.get("target") or "").strip()
        rel_type = str(item.get("type") or item.get("relation_type") or "").strip()
        if src and dst and rel_type in ALLOWED_RELATION_TYPES:
            hinted.append({"src": src, "dst": dst, "type": rel_type, "confidence": float(item.get("confidence") or 0.8)})
    if hinted:
        return hinted

    normalized = best_normalized_derivation_text(event)
    entity_names = _candidate_entity_names(entities)
    if len(entity_names) < 2:
        return []
    for cue, relation_type, swap_direction in RELATION_CUE_RULES:
        pair = _select_pair_for_cue(normalized, entity_names, cue)
        if pair is None:
            continue
        src, dst = pair
        if swap_direction:
            src, dst = dst, src
        if src and dst and src.casefold() != dst.casefold():
            return [{"src": src, "dst": dst, "type": relation_type, "confidence": 0.65}]
    return []
