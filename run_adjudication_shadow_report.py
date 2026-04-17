# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
BACKEND = ROOT.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

try:  # Load backend .env when running inside a larger monorepo.
    import config as _backend_config  # noqa: F401
except Exception:
    _backend_config = None

from solaris.config import Settings  # noqa: E402
from solaris.editorial.adjudication import AdjudicationContext, assess_adjudication_candidate  # noqa: E402
from solaris.server import build_services  # noqa: E402


def _artifact_label(artifact_type: str, artifact: dict) -> str:
    return str(
        artifact.get("canonical_claim")
        or artifact.get("title")
        or artifact.get("relation_type")
        or artifact.get("canonical_name")
        or artifact.get("artifact_id")
        or ""
    ).strip()


def _load_recent_decisions(connection, *, limit: int) -> list[dict]:
    rows = connection.execute(
        """
        SELECT decision_id, artifact_type, artifact_id, action, previous_state, new_state, policy_profile, decided_by, decided_at
        FROM editorial_decisions
        WHERE artifact_type IN ('claim', 'episode')
        ORDER BY decided_at DESC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    ).fetchall()
    return [dict(row) for row in rows]


def _artifact_for(services: dict, connection, *, artifact_type: str, artifact_id: str) -> dict | None:
    if artifact_type == "claim":
        return services["claims_repo"].get(connection, artifact_id)
    if artifact_type == "episode":
        return services["episodes_repo"].get(connection, artifact_id)
    return None


def _build_context(*, services: dict, connection, decision: dict, probe_model: bool) -> dict:
    engine = services["review"].engine
    artifact_type = str(decision["artifact_type"])
    artifact_id = str(decision["artifact_id"])
    artifact = _artifact_for(services, connection, artifact_type=artifact_type, artifact_id=artifact_id)
    if artifact is None:
        return {
            "decision_id": decision["decision_id"],
            "artifact_type": artifact_type,
            "artifact_id": artifact_id,
            "missing_artifact": True,
        }
    current = services["editorial_repo"].get_state(connection, artifact_type=artifact_type, artifact_id=artifact_id)
    event_ids = services["evidence_repo"].event_ids_for_artifact(connection, artifact_type=artifact_type, artifact_id=artifact_id)
    supporting_events = services["events_repo"].get_many(connection, event_ids)
    policy_profile = str(current.get("policy_profile") if current else decision.get("policy_profile") or "default_v1")
    policy = engine.policy_registry.get(policy_profile)
    from solaris.editorial.factors import compute_factors
    from solaris.editorial.scoring import score_artifact

    factor_values = compute_factors(artifact_type=artifact_type, artifact=artifact, supporting_events=supporting_events)
    remember_score, influence_score = score_artifact(
        policy=policy,
        factors=factor_values,
        kind=str((supporting_events[0] if supporting_events else {}).get("kind") or artifact_type),
    )
    action, hard_locked, hard_lock_reason = engine._determine_action(
        artifact_type=artifact_type,
        artifact=artifact,
        supporting_events=supporting_events,
        current=current,
        policy=policy,
        remember_score=remember_score,
    )
    assessment = assess_adjudication_candidate(
        policy=policy,
        artifact_type=artifact_type,
        remember_score=remember_score,
        current_action=action,
        hard_locked=hard_locked,
    )
    model_suggestion = None
    adjudicator = getattr(engine, "adjudicator", None)
    if probe_model and assessment.eligible and adjudicator is not None and not adjudicator.__class__.__name__.startswith("Null"):
        canonical_text = _artifact_label(artifact_type, artifact)
        result = adjudicator.adjudicate(
            AdjudicationContext(
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                policy_profile=policy_profile,
                policy_version=int(policy.get("version", 1)),
                kind=str((supporting_events[0] if supporting_events else {}).get("kind") or artifact_type),
                canonical_text=canonical_text,
                supporting_event_ids=event_ids,
                remember_score=remember_score,
                influence_score=influence_score,
                current_action=action,
                current_state=current,
                factors=dict(factor_values),
                allowed_actions=assessment.allowed_actions,
            )
        )
        if result is not None:
            model_suggestion = {
                "action": result.action,
                "confidence": result.confidence,
                "rationale": result.rationale,
                "source": result.source,
                "model": result.model,
                "prompt_version": result.prompt_version,
            }

    return {
        "decision_id": decision["decision_id"],
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "label": _artifact_label(artifact_type, artifact),
        "decided_at": decision["decided_at"],
        "stored_action": decision["action"],
        "recomputed_action": action,
        "hard_locked": hard_locked,
        "hard_lock_reason": hard_lock_reason,
        "remember_score": round(float(remember_score), 4),
        "influence_score": round(float(influence_score), 4),
        "supporting_event_count": len(event_ids),
        "assessment": {
            "eligible": assessment.eligible,
            "mode": assessment.mode,
            "reasons": list(assessment.reasons),
            "candidate_floor": assessment.candidate_floor,
            "candidate_ceiling": assessment.candidate_ceiling,
            "promotion_threshold": assessment.promotion_threshold,
            "retire_threshold": assessment.retire_threshold,
            "allowed_actions": list(assessment.allowed_actions),
        },
        "current_state": {
            "remember_state": current.get("remember_state") if current else None,
            "activation_state": current.get("activation_state") if current else None,
            "policy_profile": policy_profile,
        },
        "supporting_events": [
            {
                "event_id": event.get("event_id"),
                "timestamp": event.get("timestamp"),
                "kind": event.get("kind"),
                "raw_text": event.get("raw_text"),
            }
            for event in supporting_events[:3]
        ],
        "model_suggestion": model_suggestion,
    }


def run(*, limit: int, probe_model: bool) -> dict:
    settings = Settings.from_env()
    services = build_services(settings)
    with services["db"].transaction() as connection:
        decisions = _load_recent_decisions(connection, limit=limit)
        rows = [_build_context(services=services, connection=connection, decision=decision, probe_model=probe_model) for decision in decisions]

    eligible = [row for row in rows if row.get("assessment", {}).get("eligible")]
    hard_locked = [row for row in rows if row.get("hard_locked")]
    reason_counts = Counter()
    hard_lock_counts = Counter()
    for row in rows:
        for reason in list(row.get("assessment", {}).get("reasons") or []):
            reason_counts[reason] += 1
        if row.get("hard_lock_reason"):
            hard_lock_counts[str(row["hard_lock_reason"])] += 1

    return {
        "ok": True,
        "db_path": str(settings.db_path),
        "adjudication_provider": settings.adjudication_provider,
        "adjudication_model": settings.adjudication_model,
        "limit": limit,
        "total_analyzed": len(rows),
        "eligible_count": len(eligible),
        "hard_locked_count": len(hard_locked),
        "reason_counts": dict(reason_counts),
        "hard_lock_reason_counts": dict(hard_lock_counts),
        "eligible_items": eligible[:10],
        "recent_items": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report Solaris shadow adjudication candidates and near-misses.")
    parser.add_argument("--limit", type=int, default=25, help="Number of recent claim/episode decisions to inspect.")
    parser.add_argument("--probe-model", action="store_true", help="Call the configured adjudicator for eligible items without writing decisions.")
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    args = parser.parse_args(argv)

    result = run(limit=max(1, int(args.limit)), probe_model=bool(args.probe_model))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Solaris adjudication shadow report: {result['eligible_count']} eligible out of {result['total_analyzed']} analyzed")
        print(f"Hard-locked: {result['hard_locked_count']}")
        if result["reason_counts"]:
            print("Rule-out reasons:")
            for key, value in sorted(result["reason_counts"].items()):
                print(f"- {key}: {value}")
        if result["hard_lock_reason_counts"]:
            print("Hard-lock reasons:")
            for key, value in sorted(result["hard_lock_reason_counts"].items()):
                print(f"- {key}: {value}")
        if result["eligible_items"]:
            print("Eligible items:")
            for item in result["eligible_items"]:
                print(f"- {item['artifact_type']} {item['label']} :: action={item['recomputed_action']} score={item['remember_score']}")
                if item.get("model_suggestion"):
                    suggestion = item["model_suggestion"]
                    print(
                        "  "
                        + f"model={suggestion.get('model')} action={suggestion.get('action')} "
                        + f"confidence={suggestion.get('confidence')}"
                    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
