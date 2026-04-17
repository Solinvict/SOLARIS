# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.event import MemoryEvent
from solaris.derive.text import best_derivation_text


LOW_SIGNAL_EPISODE_HINTS = {"conversation", "message", "activity", "system", "note", "work_session", "tool", "conversation_turn"}


def episode_title_for_event(event: MemoryEvent, entities: list[dict]) -> str:
    if event.hints.episode_hint:
        hinted = str(event.hints.episode_hint).strip()
        if hinted and hinted.casefold() not in LOW_SIGNAL_EPISODE_HINTS:
            return hinted
    if entities:
        label = str(entities[0].get("canonical_name") or entities[0].get("name") or "").strip()
        if label:
            return label.casefold().replace(" ", "-")
    derivation_text = best_derivation_text(event).strip()
    if derivation_text:
        tokens = derivation_text.split()
        if tokens:
            short_title = " ".join(tokens[:4]).strip().casefold()
            if short_title and short_title not in LOW_SIGNAL_EPISODE_HINTS:
                return short_title.replace(" ", "-")
    kind = str(event.kind or "activity").strip().casefold()
    return kind or "activity"
