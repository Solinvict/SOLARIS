# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import re

from solaris.models.event import MemoryEvent
from solaris.derive.text import best_derivation_text, uses_interpreted_reaction_text_for_derivation


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "but", "by", "for",
    "from", "how", "i", "if", "in", "is", "it", "me", "my", "of", "on", "or",
    "our", "should", "that", "the", "this", "to", "was", "we", "what", "why",
    "with", "you", "your", "so", "do", "did", "can", "will", "just", "also",
    "about", "have", "has", "had", "not", "all", "its", "it's", "they", "them",
    "there", "their", "been", "when", "which", "who", "would", "could", "want",
    "get", "got", "let", "like", "know", "think", "make", "use", "go", "going",
    "well", "right", "good", "said", "give", "more", "something", "actually",
    "yeah", "enter", "exit", "mode", "conversation", "sorry", "please",
    "currently", "working", "project", "called", "current", "previous",
    "response", "wants", "expressing", "then", "tell", "saying", "feel",
    "didn", "example", "sort", "uses", "using", "okay", "best", "love",
    "fuck", "fucking", "basically", "idea", "were", "earlier", "else",
    "around", "upward", "talking", "create", "solve", "come", "yes",
    "through", "one", "food", "understanding", "thinking", "outlining",
    "see", "anything", "different", "start", "first", "continue",
    "doing", "some", "any", "improvement", "enables", "retrieve",
    "review", "analyze", "assess", "into", "say", "session",
    "very", "really", "quite", "rather", "pretty", "too",
    "same", "other", "means", "only", "purpose", "hello", "hi", "hey",
    "user", "operator", "speaker",
}

# Minimum token length to consider as a meaningful entity
_MIN_TOKEN_LEN = 3
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
CONNECTOR_WORDS = {"and", "or", "the", "of", "to", "for", "a", "an", "by"}
GENERIC_PREFIX_TOKENS = {"mcp", "app", "project", "system", "tool"}
SINGLETON_ALLOWLIST = {"sqlite", "mcp", "python", "anthropic", "openai", "claude", "whisper"}
LOW_SIGNAL_EDGE_TOKENS = {
    "were",
    "talking",
    "earlier",
    "solve",
    "upward",
    "create",
    "else",
    "come",
    "around",
    "put",
    "consider",
    "start",
    "through",
    "first",
    "continue",
    "doing",
    "some",
    "any",
    "enables",
    "retrieve",
    "review",
    "analyze",
    "assess",
    "into",
    "say",
    "same",
    "other",
    "means",
    "only",
}


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


def _trim_phrase_edges(phrase: str) -> str:
    tokens = [token for token in str(phrase or "").split() if token]
    while tokens and (tokens[0].casefold() in CONNECTOR_WORDS or tokens[0].casefold() in LOW_SIGNAL_EDGE_TOKENS):
        tokens = tokens[1:]
    while tokens and (tokens[-1].casefold() in CONNECTOR_WORDS or tokens[-1].casefold() in LOW_SIGNAL_EDGE_TOKENS):
        tokens = tokens[:-1]
    return " ".join(tokens).strip()


def _lower_tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9\-]+", str(text or "").casefold()) if token]


def _phrase_is_low_signal(tokens: list[str], *, seen_keys: set[str]) -> bool:
    if not tokens:
        return True
    if len(tokens) == 1:
        token = tokens[0]
        return token in STOPWORDS and token not in SINGLETON_ALLOWLIST
    if tokens[0] in LOW_SIGNAL_EDGE_TOKENS or tokens[-1] in LOW_SIGNAL_EDGE_TOKENS:
        return True
    if tokens[0] in GENERIC_PREFIX_TOKENS:
        remainder = " ".join(tokens[1:]).strip()
        if remainder and remainder in seen_keys:
            return True
    non_stopwords = [token for token in tokens if token not in STOPWORDS]
    return len(non_stopwords) < 2


def _hint_entity_names(hints: list[str]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for item in hints:
        cleaned = _trim_phrase_edges(_strip_leading_fillers(str(item or "").strip()))
        key = cleaned.casefold().strip()
        if not key or key in seen:
            continue
        if _phrase_is_low_signal(_lower_tokens(cleaned), seen_keys=seen):
            continue
        seen.add(key)
        names.append(cleaned)
    return names


def _extract_phrases(text: str) -> list[str]:
    """Extract meaningful noun phrases and named entities from text.

    Priority order:
    1. Capitalised multi-word sequences (proper nouns / titles)
    2. Quoted strings
    3. Single meaningful capitalised words
    4. Longer lowercase words not in stopwords
    """
    phrases: list[str] = []
    seen: set[str] = set()

    def _add(phrase: str) -> None:
        cleaned = _trim_phrase_edges(phrase)
        key = cleaned.casefold().strip()
        if key and key not in seen and not _phrase_is_low_signal(_lower_tokens(cleaned), seen_keys=seen):
            seen.add(key)
            phrases.append(cleaned)

    # 1. Quoted strings (high confidence they're intentional)
    for m in re.finditer(r'["\u201c\u201d]([^""\u201c\u201d]{2,60})["\u201c\u201d]', text):
        _add(m.group(1))

    # 2. Capitalised multi-word runs (e.g. "Stairway to Heaven", "Example City")
    for m in re.finditer(r'(?:[A-Z][a-z]{1,}(?:\s+(?:[A-Z][a-z]{0,}|by|of|the|and)){1,5})', text):
        candidate = m.group(0).strip()
        # Only keep if it has at least one non-stopword token
        tokens = candidate.split()
        if any(t.casefold() not in STOPWORDS for t in tokens):
            _add(candidate)

    # 3. Single capitalised words, including sentence-start proper nouns like "Solaris"
    sentence_start = re.match(r'^\b([A-Z][A-Za-z0-9\-]{2,})\b', text)
    if sentence_start:
        word = sentence_start.group(1)
        if word.casefold() not in STOPWORDS:
            _add(word)

    for m in re.finditer(r'(?<!\.\s)(?<!\?\s)(?<!\!\s)(?<!^)\b([A-Z][a-z]{2,})\b', text):
        word = m.group(1)
        if word.casefold() not in STOPWORDS:
            _add(word)

    # 4. Lowercase multi-word phrases (e.g. "fractal memory", "graph memory")
    if len(phrases) < 4:
        for m in re.finditer(r'\b([a-z][a-z0-9\-]{2,}(?:\s+[a-z][a-z0-9\-]{2,}){1,3})\b', text.lower()):
            candidate = m.group(1).strip()
            tokens = [token for token in candidate.split() if token not in STOPWORDS]
            if len(tokens) < 2:
                continue
            _add(" ".join(tokens))
            if len(phrases) >= 6:
                break

    # 5. Single lowercase tokens only for short utterances
    word_count = len(re.findall(r'\b[a-z][a-z0-9\-]{1,}\b', text.lower()))
    if len(phrases) < 3 and word_count <= 4:
        covered_tokens = {
            token
            for phrase in phrases
            if " " in phrase
            for token in _lower_tokens(phrase)
        }
        for token in re.findall(r'\b[a-z][a-z0-9\-]{4,}\b', text.lower()):
            if token in covered_tokens:
                continue
            if token not in STOPWORDS and len(token) >= max(_MIN_TOKEN_LEN, 5):
                _add(token)
            if len(phrases) >= 6:
                break

    multiword_tokens = {
        token
        for phrase in phrases
        if " " in phrase
        for token in _lower_tokens(phrase)
    }
    filtered = [
        phrase
        for phrase in phrases
        if " " in phrase or _lower_tokens(phrase)[0] not in multiword_tokens
    ]
    return filtered[:8]


def derive_entities(event: MemoryEvent) -> list[dict]:
    # Adapter-supplied hints are highest quality — use them exclusively if present
    hints = _hint_entity_names([item.strip() for item in event.hints.entities if str(item or "").strip()])
    if hints:
        return [{"name": name, "type": "concept", "aliases": []} for name in hints]

    if uses_interpreted_reaction_text_for_derivation(event):
        return []

    text = _strip_leading_fillers(best_derivation_text(event))
    if not text:
        return []

    phrases = _extract_phrases(text)
    return [{"name": p, "type": "concept", "aliases": []} for p in phrases]
