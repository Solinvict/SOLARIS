# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import re


def lexical_overlap(query: str, text: str) -> float:
    q = set(re.findall(r"[A-Za-z0-9_']+", query.casefold()))
    t = set(re.findall(r"[A-Za-z0-9_']+", (text or "").casefold()))
    if not q or not t:
        return 0.0
    return len(q & t) / len(q)


def editorial_modifier(editorial_state: dict | None, recall_mode: str) -> float:
    if editorial_state is None:
        return 0.2 if recall_mode == "deep" else 0.0
    modifier = float(editorial_state.get("remember_score") or 0.0) + float(editorial_state.get("influence_score") or 0.0)
    remember_state = str(editorial_state.get("remember_state") or "candidate")
    activation_state = str(editorial_state.get("activation_state") or "suppressed")
    if remember_state == "remembered":
        modifier += 0.6
    elif remember_state == "candidate":
        modifier += 0.15 if recall_mode == "deep" else -0.05
    elif remember_state in {"retired", "superseded"}:
        modifier -= 0.5 if recall_mode != "archive" else 0.0
    if activation_state == "active":
        modifier += 0.25
    elif activation_state == "dormant":
        modifier += 0.05 if recall_mode == "deep" else -0.05
    else:
        modifier -= 0.1
    if editorial_state.get("pinned"):
        modifier += 0.5
    return modifier


def score_item(*, query: str, text: str, recency_bias: float, importance: float, confidence: float, editorial_state: dict | None, recall_mode: str) -> float:
    base = lexical_overlap(query, text)
    base += (float(importance) * 0.3) + (float(confidence) * 0.2) + float(recency_bias)
    return base + editorial_modifier(editorial_state, recall_mode)
