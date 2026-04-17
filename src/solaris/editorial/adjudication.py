# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


DEFAULT_ALLOWED_ACTIONS = ("promote", "leave_candidate", "retire")
DEFAULT_ARTIFACT_TYPES = ("claim", "episode")


@dataclass(slots=True)
class AdjudicationContext:
    artifact_type: str
    artifact_id: str
    policy_profile: str
    policy_version: int
    kind: str
    canonical_text: str
    supporting_event_ids: list[str]
    remember_score: float
    influence_score: float
    current_action: str
    current_state: dict | None
    factors: dict
    allowed_actions: tuple[str, ...]


@dataclass(slots=True)
class AdjudicationResult:
    action: str
    confidence: float
    rationale: str
    source: str = "model"
    model: str | None = None
    prompt_version: str | None = None


@dataclass(slots=True)
class AdjudicationAssessment:
    eligible: bool
    mode: str
    reasons: tuple[str, ...]
    candidate_floor: float
    candidate_ceiling: float
    promotion_threshold: float
    retire_threshold: float
    allowed_actions: tuple[str, ...]
    artifact_types: tuple[str, ...]


class EditorialAdjudicator(Protocol):
    def adjudicate(self, context: AdjudicationContext) -> AdjudicationResult | None: ...


class NullEditorialAdjudicator:
    def adjudicate(self, context: AdjudicationContext) -> AdjudicationResult | None:
        del context
        return None


def adjudication_policy(policy: dict) -> dict:
    payload = dict(policy.get("adjudication") or {})
    payload.setdefault("enabled", False)
    payload.setdefault("mode", "assist" if bool(payload.get("enabled")) else "off")
    payload.setdefault("artifact_types", list(DEFAULT_ARTIFACT_TYPES))
    payload.setdefault("allowed_actions", list(DEFAULT_ALLOWED_ACTIONS))
    payload.setdefault("ambiguity_band", {})
    band = dict(payload.get("ambiguity_band") or {})
    band.setdefault("candidate_floor", 0.35)
    band.setdefault("candidate_ceiling", 0.82)
    band.setdefault("promotion_margin", 0.10)
    band.setdefault("retire_margin", 0.08)
    payload["ambiguity_band"] = band
    return payload


def adjudication_mode(policy: dict) -> str:
    settings = adjudication_policy(policy)
    mode = str(settings.get("mode") or "").strip().casefold()
    if mode in {"off", "shadow", "assist"}:
        return mode
    return "assist" if bool(settings.get("enabled")) else "off"


def adjudication_allowed_actions(policy: dict) -> tuple[str, ...]:
    settings = adjudication_policy(policy)
    return tuple(
        str(item).strip()
        for item in list(settings.get("allowed_actions") or [])
        if str(item).strip()
    )


def assess_adjudication_candidate(
    *,
    policy: dict,
    artifact_type: str,
    remember_score: float,
    current_action: str,
    hard_locked: bool,
) -> AdjudicationAssessment:
    settings = adjudication_policy(policy)
    mode = adjudication_mode(policy)
    artifact_types = tuple(
        str(item).strip()
        for item in list(settings.get("artifact_types") or [])
        if str(item).strip()
    )
    allowed_actions = adjudication_allowed_actions(policy)
    band = dict(settings.get("ambiguity_band") or {})
    promotion_threshold = float(policy.get("promotion_threshold", 0.7))
    retire_threshold = float(policy.get("retire_threshold", 0.2))
    candidate_floor = max(float(band.get("candidate_floor", 0.35)), retire_threshold + float(band.get("retire_margin", 0.08)))
    candidate_ceiling = min(float(band.get("candidate_ceiling", 0.82)), 1.0)
    promotion_margin = float(band.get("promotion_margin", 0.10))
    retire_margin = float(band.get("retire_margin", 0.08))

    reasons: list[str] = []
    if mode == "off":
        reasons.append("mode_off")
    if hard_locked:
        reasons.append("hard_locked")
    if artifact_type not in artifact_types:
        reasons.append("artifact_type_ineligible")
    if current_action not in allowed_actions:
        reasons.append("action_ineligible")

    score_eligible = True
    if current_action == "promote":
        score_eligible = remember_score >= max(candidate_floor, promotion_threshold - promotion_margin)
    elif current_action == "retire":
        score_eligible = remember_score <= min(candidate_ceiling, retire_threshold + retire_margin)
    else:
        score_eligible = candidate_floor <= remember_score <= candidate_ceiling
    if not score_eligible:
        reasons.append("score_outside_ambiguity_band")

    return AdjudicationAssessment(
        eligible=not reasons,
        mode=mode,
        reasons=tuple(reasons),
        candidate_floor=candidate_floor,
        candidate_ceiling=candidate_ceiling,
        promotion_threshold=promotion_threshold,
        retire_threshold=retire_threshold,
        allowed_actions=allowed_actions,
        artifact_types=artifact_types,
    )


def should_consider_adjudication(
    *,
    policy: dict,
    artifact_type: str,
    remember_score: float,
    current_action: str,
    hard_locked: bool,
) -> bool:
    return assess_adjudication_candidate(
        policy=policy,
        artifact_type=artifact_type,
        remember_score=remember_score,
        current_action=current_action,
        hard_locked=hard_locked,
    ).eligible


def adjudication_rationale_payload(
    result: AdjudicationResult | None,
    *,
    mode: str,
    rule_action: str,
    final_action: str,
    applied: bool,
) -> dict:
    if result is None:
        return {}
    return {
        "adjudication_mode": mode,
        "adjudication_source": result.source,
        "adjudication_confidence": float(result.confidence),
        "adjudication_rationale": str(result.rationale or "").strip(),
        "adjudication_model": result.model,
        "adjudication_prompt_version": result.prompt_version,
        "adjudication_suggested_action": str(result.action or "").strip(),
        "adjudication_rule_action": str(rule_action or "").strip(),
        "adjudication_final_action": str(final_action or "").strip(),
        "adjudication_applied": bool(applied),
    }
