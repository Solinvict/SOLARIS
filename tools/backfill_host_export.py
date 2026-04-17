# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solaris.config import Settings  # noqa: E402
from solaris.models.editorial import ApplyEditorialDecisionRequest  # noqa: E402
from solaris.models.event import EventHintSet, EventScores, IngestEventsRequest, MemoryEvent  # noqa: E402
from solaris.models.scope import ScopeRef  # noqa: E402
from solaris.models.session import CloseSessionRequest, OpenSessionRequest  # noqa: E402
from solaris.server import build_services  # noqa: E402


DEFAULT_SCOPE = {
    "tenant": "personal",
    "namespace": "host",
    "workspace": "default",
    "project": "core",
}


def _result_dict(value: object) -> dict:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return dict(model_dump())
    return {}


def _scope_from_data(data: dict | None) -> ScopeRef:
    merged = dict(DEFAULT_SCOPE)
    merged.update(data or {})
    return ScopeRef(**merged)


def _make_event(*, scope: ScopeRef, session_id: str, data: dict) -> MemoryEvent:
    return MemoryEvent(
        timestamp=str(data["timestamp"]),
        scope=scope,
        session_id=session_id,
        source_app=str(data.get("source_app") or "host_runtime"),
        source_module=str(data.get("source_module") or "host_adapter"),
        actor=str(data.get("actor") or "user"),
        kind=str(data.get("kind") or "message"),
        raw_text=str(data.get("raw_text") or ""),
        normalized_text=str(data.get("normalized_text") or str(data.get("raw_text") or "").casefold()),
        structured_payload=dict(data.get("structured_payload") or {}),
        hints=EventHintSet(**dict(data.get("hints") or {})),
        scores=EventScores(
            importance=float((data.get("scores") or {}).get("importance") or data.get("importance") or 0.8),
            confidence=float((data.get("scores") or {}).get("confidence") or data.get("confidence") or 0.9),
        ),
        idempotency_key=str(data["idempotency_key"]),
    )


def _find_artifact_record(
    services: dict,
    *,
    scope: ScopeRef,
    artifact_type: str,
    match_field: str,
    match_value: str,
) -> dict | None:
    with services["db"].transaction() as connection:
        if artifact_type == "claim":
            rows = services["claims_repo"].list_by_scope(connection, scope.key(), limit=500)
        elif artifact_type == "episode":
            rows = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=500)
        elif artifact_type == "entity":
            rows = services["entities_repo"].list_by_scope(connection, scope.key(), limit=500)
        elif artifact_type == "relation":
            rows = services["relations_repo"].list_by_scope(connection, scope.key(), limit=500)
        else:
            return None
        for row in rows:
            if str(row.get(match_field) or "").strip() == match_value:
                return row
    return None


def run_backfill(export_path: Path, *, db_path: Path | None = None, policy_profile: str = "default_v1") -> dict:
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    settings = Settings(
        project_root=ROOT,
        db_path=db_path or (ROOT / ".runtime" / "solaris.db"),
        policies_dir=ROOT / "policies",
        default_policy_profile=policy_profile,
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
    services = build_services(settings)
    scope = _scope_from_data(payload.get("scope"))

    session_aliases: dict[str, str] = {}
    for session_data in list(payload.get("sessions") or []):
        parent_session_id = None
        parent_alias = str(session_data.get("parent_alias") or "").strip()
        if parent_alias:
            parent_session_id = session_aliases[parent_alias]
        record = services["sessions"].open_session(
            OpenSessionRequest(
                scope=scope,
                kind=str(session_data.get("kind") or "runtime"),
                parent_session_id=parent_session_id,
            )
        )
        session_aliases[str(session_data["alias"])] = record.session_id

    events = [
        _make_event(
            scope=scope,
            session_id=session_aliases[str(event_data["session_alias"])],
            data=event_data,
        )
        for event_data in list(payload.get("events") or [])
    ]
    ingest_response = {"accepted": 0, "duplicates": 0}
    if events:
        ingest_response = _result_dict(services["ingest"].ingest_events(IngestEventsRequest(events=events)))

    closed_count = 0
    for alias in list(payload.get("close_sessions") or []):
        services["sessions"].close_session(CloseSessionRequest(session_id=session_aliases[str(alias)]))
        closed_count += 1

    decisions_created = 0
    for review in list(payload.get("reviews") or []):
        review_scope = _scope_from_data(review.get("scope"))
        review_session_id = None
        review_alias = str(review.get("session_alias") or "").strip()
        if review_alias:
            review_session_id = session_aliases[review_alias]
        review_response = _result_dict(services["review"].run_review(
            review_scope,
            review_session_id,
            str(review.get("policy_profile") or policy_profile),
            int(review.get("limit") or 100),
            str(review.get("mode") or "boundary"),
        ))
        decisions_created += int(review_response.get("decisions_created") or 0)

    for decision in list(payload.get("editorial_decisions") or []):
        artifact_type = str(decision["artifact_type"])
        match_field = str(decision["match_field"])
        match_value = str(decision["match_value"])
        record = _find_artifact_record(
            services,
            scope=scope,
            artifact_type=artifact_type,
            match_field=match_field,
            match_value=match_value,
        )
        if record is None:
            raise ValueError(
                f"editorial_decision target not found for {artifact_type} {match_field}={match_value}"
            )
        artifact_id = str(
            record.get(f"{artifact_type}_id")
            or record.get("claim_id")
            or record.get("episode_id")
            or record.get("entity_id")
            or record.get("relation_id")
            or ""
        ).strip()
        if not artifact_id:
            raise ValueError(
                f"editorial_decision target missing artifact id for {artifact_type} {match_field}={match_value}"
            )
        services["review"].apply_decision(
            ApplyEditorialDecisionRequest(
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                scope=scope,
                action=str(decision["action"]),
                rationale=dict(decision.get("rationale") or {}),
                policy_profile=str(decision.get("policy_profile") or policy_profile),
            )
        )

    return {
        "ok": True,
        "scope": scope.model_dump(),
        "db_path": str(settings.db_path),
        "sessions_opened": len(session_aliases),
        "sessions_closed": closed_count,
        "events_attempted": len(events),
        "accepted": int(ingest_response.get("accepted") or 0),
        "duplicates": int(ingest_response.get("duplicates") or 0),
        "decisions_created": decisions_created,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill a generic host export into a local Solaris database.")
    parser.add_argument("--export", type=Path, required=True, help="Path to the host export JSON file.")
    parser.add_argument("--db", type=Path, default=None, help="Optional SQLite database path. Defaults to .runtime/solaris.db")
    parser.add_argument("--policy-profile", default="default_v1", help="Editorial policy profile to use.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args(argv)

    result = run_backfill(args.export.resolve(), db_path=args.db.resolve() if args.db else None, policy_profile=str(args.policy_profile))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Backfill complete: {result['accepted']}/{result['events_attempted']} accepted")
        print(f"- sessions_opened: {result['sessions_opened']}")
        print(f"- sessions_closed: {result['sessions_closed']}")
        print(f"- decisions_created: {result['decisions_created']}")
        print(f"- db_path: {result['db_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
