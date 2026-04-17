# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations


def score_artifact(*, policy: dict, factors: dict, kind: str) -> tuple[float, float]:
    weights = dict(policy.get("factor_weights") or {})
    kind_bias = float((policy.get("kind_biases") or {}).get(kind, 0.0))
    remember_score = kind_bias
    for factor_name, value in factors.items():
        remember_score += float(weights.get(factor_name, 0.0)) * float(value)
    remember_score = max(0.0, min(1.0, remember_score))
    influence_score = remember_score
    if factors.get("recurrence", 0.0) > 0.5:
        influence_score = min(1.0, influence_score + 0.1)
    return remember_score, influence_score
