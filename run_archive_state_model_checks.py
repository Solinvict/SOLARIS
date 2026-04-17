# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solaris.config import Settings
from solaris.models.editorial import ApplyEditorialDecisionRequest
from solaris.models.event import EventHintSet, EventScores, IngestEventsRequest, MemoryEvent
from solaris.models.query import ExplainRequest, QueryRequest
from solaris.models.scope import ScopeRef
from solaris.models.session import OpenSessionRequest
from solaris.server import build_services

TMP_DIR = ROOT.parent / ".tmp"
DB_PATH = TMP_DIR / "archive_state_model_checks.db"


def _make_event(
    *,
    scope: ScopeRef,
    session_id: str,
    timestamp: str,
    idempotency_key: str,
    raw_text: str,
    normalized_text: str | None = None,
    kind: str = "message",
    structured_payload: dict | None = None,
    importance: float = 0.8,
    confidence: float = 0.9,
) -> MemoryEvent:
    return MemoryEvent(
        timestamp=timestamp,
        scope=scope,
        session_id=session_id,
        source_app="host_runtime",
        source_module="host_runtime_core",
        actor="user",
        kind=kind,
        raw_text=raw_text,
        normalized_text=normalized_text or raw_text.casefold(),
        structured_payload=structured_payload or {},
        hints=EventHintSet(),
        scores=EventScores(importance=importance, confidence=confidence),
        idempotency_key=idempotency_key,
    )


def _build_services() -> dict:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    settings = Settings(
        project_root=ROOT,
        db_path=DB_PATH,
        policies_dir=ROOT / "policies",
        default_policy_profile="default_v1",
        fts_enabled=True,
        embeddings_enabled=False,
        log_level="INFO",
        adjudication_provider="off",
        adjudication_base_url="https://api.openai.com/v1",
        adjudication_api_key="",
        adjudication_model="",
        adjudication_timeout_seconds=20.0,
        adjudication_prompt_version="solaris_editorial_adjudication_v1",
        divergence_weight_threshold=0.2,
    )
    return build_services(settings)


def _check_archive_immutability() -> dict:
    services = _build_services()
    scope = ScopeRef(tenant="personal", namespace="host", workspace="default", project="core")
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    services["ingest"].ingest_events(
        IngestEventsRequest(
            events=[
                _make_event(
                    scope=scope,
                    session_id=session.session_id,
                    timestamp="2026-04-10T09:00:00+00:00",
                    idempotency_key="archive-state-retire-proof",
                    raw_text="Remember this I live in Example City",
                    normalized_text="remember this i live in example city",
                    kind="note",
                    structured_payload={
                        "route_domain": "memory",
                        "route_action": "remember_note",
                        "claim": {
                            "predicate": "asserts",
                            "object_text": "I live in Example City",
                            "canonical_claim": "I live in Example City",
                            "confidence": 0.95,
                            "pinned": False,
                        },
                    },
                    importance=0.95,
                    confidence=0.95,
                )
            ]
        )
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    with services["db"].transaction() as connection:
        event = services["events_repo"].list_by_scope(connection, scope.key(), limit=1)[0]
        claim = next(
            item
            for item in services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
            if item["canonical_claim"] == "I live in Example City"
        )

    services["review"].apply_decision(
        ApplyEditorialDecisionRequest(
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope=scope,
            action="retire",
            rationale={"summary": "Archive immutability verification retirement."},
            policy_profile="default_v1",
        )
    )

    explanation = services["explain"].explain(
        ExplainRequest(scope=scope, artifact_type="claim", artifact_id=claim["claim_id"])
    )
    with services["db"].transaction() as connection:
        archived_event = services["events_repo"].get(connection, event["event_id"])
        retired_state = services["editorial_repo"].get_state(connection, artifact_type="claim", artifact_id=claim["claim_id"])
        supporting_event_ids = services["evidence_repo"].event_ids_for_artifact(
            connection,
            artifact_type="claim",
            artifact_id=claim["claim_id"],
        )

    passed = (
        archived_event is not None
        and archived_event["event_id"] == event["event_id"]
        and retired_state["remember_state"] == "retired"
        and event["event_id"] in supporting_event_ids
        and [item["event_id"] for item in explanation["supporting_events"]] == [event["event_id"]]
    )
    return {
        "name": "archive_immutability",
        "passed": passed,
        "event_id": event["event_id"],
        "remember_state": retired_state["remember_state"],
        "raw_text": archived_event["raw_text"] if archived_event else None,
    }


def _check_editorial_filtering() -> dict:
    services = _build_services()
    scope = ScopeRef(tenant="personal", namespace="host", workspace="default", project="core")
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    services["ingest"].ingest_events(
        IngestEventsRequest(
            events=[
                _make_event(
                    scope=scope,
                    session_id=session.session_id,
                    timestamp="2026-04-10T10:00:00+00:00",
                    idempotency_key="archive-state-decision-claim",
                    raw_text="We decided Solaris should preserve the raw record.",
                    kind="decision",
                    structured_payload={
                        "claim": {
                            "predicate": "asserts",
                            "object_text": "Solaris should preserve the raw record",
                            "canonical_claim": "Solaris should preserve the raw record",
                            "confidence": 0.92,
                            "pinned": False,
                        }
                    },
                    importance=0.9,
                    confidence=0.92,
                ),
                _make_event(
                    scope=scope,
                    session_id=session.session_id,
                    timestamp="2026-04-10T10:01:00+00:00",
                    idempotency_key="archive-state-message-claim",
                    raw_text="Solaris should favor clear explanations.",
                    kind="message",
                    structured_payload={
                        "claim": {
                            "predicate": "asserts",
                            "object_text": "Solaris should favor clear explanations",
                            "canonical_claim": "Solaris should favor clear explanations",
                            "confidence": 0.92,
                            "pinned": False,
                        }
                    },
                    importance=0.9,
                    confidence=0.92,
                ),
            ]
        )
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    with services["db"].transaction() as connection:
        claims = services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
        decision_claim = next(item for item in claims if item["canonical_claim"] == "Solaris should preserve the raw record")
        message_claim = next(item for item in claims if item["canonical_claim"] == "Solaris should favor clear explanations")
        decision_state = services["editorial_repo"].get_state(
            connection,
            artifact_type="claim",
            artifact_id=decision_claim["claim_id"],
        )
        message_state = services["editorial_repo"].get_state(
            connection,
            artifact_type="claim",
            artifact_id=message_claim["claim_id"],
        )

    passed = (
        decision_state["remember_state"] == "remembered"
        and decision_state["activation_state"] == "active"
        and message_state["remember_state"] == "candidate"
        and message_state["activation_state"] == "suppressed"
        and float(decision_state["remember_score"]) > float(message_state["remember_score"])
    )
    return {
        "name": "editorial_filtering",
        "passed": passed,
        "decision_state": decision_state["remember_state"],
        "decision_score": decision_state["remember_score"],
        "message_state": message_state["remember_state"],
        "message_score": message_state["remember_score"],
    }


def _check_state_vs_archive_retrieval() -> dict:
    services = _build_services()
    scope = ScopeRef(tenant="personal", namespace="host", workspace="default", project="core")
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    services["ingest"].ingest_events(
        IngestEventsRequest(
            events=[
                _make_event(
                    scope=scope,
                    session_id=session.session_id,
                    timestamp="2026-04-10T11:00:00+00:00",
                    idempotency_key="archive-state-query-switch",
                    raw_text="Remember this I live in Example City",
                    normalized_text="remember this i live in example city",
                    kind="note",
                    structured_payload={
                        "route_domain": "memory",
                        "route_action": "remember_note",
                        "claim": {
                            "predicate": "asserts",
                            "object_text": "I live in Example City",
                            "canonical_claim": "I live in Example City",
                            "confidence": 0.95,
                            "pinned": False,
                        },
                    },
                    importance=0.95,
                    confidence=0.95,
                )
            ]
        )
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    default_before = services["query"].query(QueryRequest(query="where do I live", scope=scope, recall_mode="default"))
    with services["db"].transaction() as connection:
        claim = next(
            item
            for item in services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)
            if item["canonical_claim"] == "I live in Example City"
        )
        event = services["events_repo"].list_by_scope(connection, scope.key(), limit=1)[0]

    services["review"].apply_decision(
        ApplyEditorialDecisionRequest(
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope=scope,
            action="retire",
            rationale={"summary": "State-vs-archive verification retirement."},
            policy_profile="default_v1",
        )
    )

    default_after = services["query"].query(QueryRequest(query="where do I live", scope=scope, recall_mode="default"))
    archive_after = services["query"].query(QueryRequest(query="where do I live", scope=scope, recall_mode="archive"))
    explanation = services["explain"].explain(ExplainRequest(scope=scope, artifact_type="claim", artifact_id=claim["claim_id"]))

    passed = (
        bool(default_before["claims"])
        and default_before["claims"][0]["canonical_claim"] == "I live in Example City"
        and default_after["claims"] == []
        and bool((default_after.get("recorded") or {}).get("divergences"))
        and str(default_after["recorded"]["divergences"][0].get("label") or "") == "I live in Example City"
        and int((default_after.get("divergence_summary") or {}).get("count") or 0) >= 1
        and bool(archive_after["events"])
        and archive_after["events"][0]["event_id"] == event["event_id"]
        and bool((archive_after.get("recorded") or {}).get("divergences"))
        and explanation["editorial_state"]["remember_state"] == "retired"
        and bool(explanation["supporting_events"])
        and explanation["supporting_events"][0]["event_id"] == event["event_id"]
    )
    return {
        "name": "state_vs_archive_retrieval",
        "passed": passed,
        "default_before_claims": [item["canonical_claim"] for item in default_before["claims"]],
        "default_after_claims": [item["canonical_claim"] for item in default_after["claims"]],
        "default_after_divergences": [
            item["label"] for item in (default_after.get("recorded") or {}).get("divergences", [])
        ],
        "archive_event_ids": [item["event_id"] for item in archive_after["events"]],
        "retired_state": explanation["editorial_state"]["remember_state"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Solaris archive-state memory model checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    args = parser.parse_args()

    checks = [
        _check_archive_immutability(),
        _check_editorial_filtering(),
        _check_state_vs_archive_retrieval(),
    ]
    passed = sum(1 for item in checks if item["passed"])
    result = {
        "ok": passed == len(checks),
        "passed": passed,
        "total": len(checks),
        "checks": checks,
        "note": "Divergence is now surfaced as a first-class query bundle field for archive-supported claims and episodes.",
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Archive-state checks: {passed}/{len(checks)} passed")
        for item in checks:
            status = "PASS" if item["passed"] else "FAIL"
            print(f"- {status}: {item['name']}")
        print(result["note"])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
