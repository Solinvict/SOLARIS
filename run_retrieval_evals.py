# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solaris.config import Settings  # noqa: E402
from solaris.models.editorial import ApplyEditorialDecisionRequest  # noqa: E402
from solaris.models.event import EventHintSet, EventScores, IngestEventsRequest, MemoryEvent  # noqa: E402
from solaris.models.query import QueryRequest  # noqa: E402
from solaris.models.scope import ScopeRef  # noqa: E402
from solaris.models.session import CloseSessionRequest, OpenSessionRequest  # noqa: E402
from solaris.server import build_services  # noqa: E402


DEFAULT_SCOPE = {
    "tenant": "personal",
    "namespace": "host",
    "workspace": "default",
    "project": "core",
}


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
        source_module=str(data.get("source_module") or "host_runtime_core"),
        actor=str(data.get("actor") or "user"),
        kind=str(data.get("kind") or "message"),
        raw_text=str(data.get("raw_text") or ""),
        normalized_text=str(data.get("normalized_text") or str(data.get("raw_text") or "").casefold()),
        structured_payload=dict(data.get("structured_payload") or {}),
        hints=EventHintSet(**dict(data.get("hints") or {})),
        scores=EventScores(
            importance=float(data.get("importance") or 0.8),
            confidence=float(data.get("confidence") or 0.9),
        ),
        idempotency_key=str(data["idempotency_key"]),
    )


def _artifact_texts(bundle: dict, artifact_type: str) -> list[str]:
    items = list(bundle.get(f"{artifact_type}s") or []) if artifact_type not in {"state_lease"} else list(bundle.get("state_leases") or [])
    texts: list[str] = []
    for item in items:
        if artifact_type == "claim":
            texts.append(str(item.get("canonical_claim") or "").strip())
        elif artifact_type == "event":
            texts.append(str(item.get("raw_text") or "").strip())
        elif artifact_type == "episode":
            texts.append(str(item.get("title") or item.get("summary_text") or "").strip())
        elif artifact_type == "entity":
            texts.append(str(item.get("canonical_name") or "").strip())
        elif artifact_type == "relation":
            relation_text = str(item.get("label") or "").strip()
            if not relation_text:
                src_name = str(
                    (item.get("src_entity") or {}).get("canonical_name")
                    or item.get("src_name")
                    or item.get("src")
                    or ""
                ).strip()
                relation_type = str(
                    item.get("relation_type")
                    or (item.get("relation") or {}).get("relation_type")
                    or item.get("predicate")
                    or ""
                ).strip()
                dst_name = str(
                    (item.get("dst_entity") or {}).get("canonical_name")
                    or item.get("dst_name")
                    or item.get("dst")
                    or ""
                ).strip()
                relation_text = " ".join(part for part in (src_name, relation_type, dst_name) if part).strip()
            texts.append(relation_text)
        elif artifact_type == "state_lease":
            texts.append(str(item.get("lease_key") or "").strip())
    return [text for text in texts if text]


def _top_artifact_type(bundle: dict) -> str | None:
    explanations = sorted(
        list(bundle.get("explanations") or []),
        key=lambda item: float(item.get("score") or 0.0),
        reverse=True,
    )
    for explanation in explanations:
        artifact_type = str(explanation.get("artifact_type") or "").strip()
        if artifact_type and artifact_type != "query":
            key = "state_leases" if artifact_type == "state_lease" else f"{artifact_type}s"
            if bundle.get(key):
                return artifact_type
    for artifact_type, key in (
        ("claim", "claims"),
        ("relation", "relations"),
        ("episode", "episodes"),
        ("event", "events"),
        ("entity", "entities"),
        ("state_lease", "state_leases"),
    ):
        if bundle.get(key):
            return artifact_type
    return None


def _all_texts(bundle: dict) -> list[str]:
    texts: list[str] = []
    for artifact_type in ("claim", "episode", "event", "entity", "relation", "state_lease"):
        texts.extend(_artifact_texts(bundle, artifact_type))
    return texts


def _find_artifact_state(
    services: dict,
    *,
    scope: ScopeRef,
    artifact_type: str,
    match_field: str,
    match_value: str,
) -> dict | None:
    with services["db"].transaction() as connection:
        if artifact_type == "claim":
            rows = services["claims_repo"].list_by_scope(connection, scope.key(), limit=200)
        elif artifact_type == "episode":
            rows = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=200)
        else:
            return None
        for row in rows:
            if str(row.get(match_field) or "").strip() == match_value:
                artifact_id = str(row.get(f"{artifact_type}_id") or "").strip()
                if not artifact_id:
                    return None
                return services["editorial_repo"].get_state(connection, artifact_type=artifact_type, artifact_id=artifact_id)
    return None


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


def _scope_key(scope: ScopeRef) -> str:
    return scope.key()


def run_case(case: dict) -> dict:
    eval_root = ROOT / ".runtime" / "evals"
    eval_root.mkdir(parents=True, exist_ok=True)
    case_key = str(case.get("id") or "case").strip().replace(" ", "_")
    case_dir = eval_root / case_key
    db_path = case_dir / "solaris_eval.db"
    shutil.rmtree(case_dir, ignore_errors=True)
    case_dir.mkdir(parents=True, exist_ok=True)
    try:
        settings = Settings(
            project_root=ROOT,
            db_path=db_path,
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
        services = build_services(settings)
        scope = _scope_from_data(case.get("scope"))
        session_aliases: dict[str, str] = {}

        for session_data in list(case.get("setup", {}).get("sessions") or []):
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
            for event_data in list(case.get("setup", {}).get("events") or [])
        ]
        if events:
            services["ingest"].ingest_events(IngestEventsRequest(events=events))

        for alias in list(case.get("setup", {}).get("close_sessions") or []):
            services["sessions"].close_session(CloseSessionRequest(session_id=session_aliases[str(alias)]))

        for review in list(case.get("setup", {}).get("reviews") or []):
            review_scope = _scope_from_data(review.get("scope"))
            review_session_id = None
            review_alias = str(review.get("session_alias") or "").strip()
            if review_alias:
                review_session_id = session_aliases[review_alias]
            services["review"].run_review(
                review_scope,
                review_session_id,
                str(review.get("policy_profile") or "default_v1"),
                int(review.get("limit") or 50),
                str(review.get("mode") or "boundary"),
            )

        for decision in list(case.get("setup", {}).get("editorial_decisions") or []):
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
                    policy_profile=str(decision.get("policy_profile") or "default_v1"),
                )
            )

        bundle = services["query"].query(
            QueryRequest(
                query=str(case["query"]["text"]),
                scope=scope,
                recall_mode=str(case["query"].get("recall_mode") or "default"),
            )
        )

        expect = dict(case.get("expect") or {})
        failures: list[str] = []

        preferred_type = str(expect.get("preferred_artifact_type") or "").strip()
        if preferred_type:
            top_type = _top_artifact_type(bundle)
            if top_type != preferred_type:
                failures.append(f"preferred_artifact_type expected {preferred_type} got {top_type}")

        allowed_top_texts = [str(item).strip() for item in list(expect.get("allowed_top_texts") or []) if str(item).strip()]
        if preferred_type and allowed_top_texts:
            top_texts = _artifact_texts(bundle, preferred_type)
            top_text = top_texts[0] if top_texts else ""
            if top_text not in allowed_top_texts:
                failures.append(f"top_{preferred_type}_text expected one of {allowed_top_texts} got {top_text!r}")

        forbidden_texts = [str(item).strip() for item in list(expect.get("forbidden_texts") or []) if str(item).strip()]
        all_texts = _all_texts(bundle)
        required_texts = [str(item).strip() for item in list(expect.get("required_texts") or []) if str(item).strip()]
        for required in required_texts:
            if not any(required in text for text in all_texts):
                failures.append(f"required_text missing: {required}")
        for forbidden in forbidden_texts:
            if forbidden in all_texts:
                failures.append(f"forbidden_text surfaced: {forbidden}")

        top_text_assertions = dict(expect.get("top_text_assertions") or {})
        for artifact_type, allowed_values in top_text_assertions.items():
            allowed = [str(item).strip() for item in list(allowed_values or []) if str(item).strip()]
            if not allowed:
                continue
            top_text = (_artifact_texts(bundle, str(artifact_type)) or [""])[0]
            if top_text not in allowed:
                failures.append(
                    f"top_{artifact_type}_text expected one of {allowed} got {top_text!r}"
                )

        forbidden_entities = [str(item).strip() for item in list(expect.get("forbidden_entities") or []) if str(item).strip()]
        entity_texts = _artifact_texts(bundle, "entity")
        for forbidden in forbidden_entities:
            if forbidden in entity_texts:
                failures.append(f"forbidden_entity surfaced: {forbidden}")

        meta_assertions = dict(expect.get("meta_assertions") or {})
        bundle_meta = dict(bundle.get("meta") or {})
        for key, expected_value in meta_assertions.items():
            actual_value = bundle_meta.get(key)
            if actual_value != expected_value:
                failures.append(f"meta_assertion expected {key}={expected_value!r} got {actual_value!r}")

        for assertion in list(expect.get("artifact_assertions") or []):
            state = _find_artifact_state(
                services,
                scope=scope,
                artifact_type=str(assertion["artifact_type"]),
                match_field=str(assertion["match_field"]),
                match_value=str(assertion["match_value"]),
            )
            if state is None:
                failures.append(
                    f"artifact_assertion missing artifact {assertion['artifact_type']} {assertion['match_field']}={assertion['match_value']}"
                )
                continue
            expected_state = str(assertion.get("remember_state") or "").strip()
            if expected_state and str(state.get("remember_state") or "").strip() != expected_state:
                failures.append(
                    f"artifact_assertion expected remember_state={expected_state} got {state.get('remember_state')}"
                )

        return {
            "id": case["id"],
            "family": case.get("family"),
            "ok": not failures,
            "failures": failures,
            "top_artifact_type": _top_artifact_type(bundle),
            "top_claim": (_artifact_texts(bundle, "claim") or [None])[0],
            "top_event": (_artifact_texts(bundle, "event") or [None])[0],
            "top_episode": (_artifact_texts(bundle, "episode") or [None])[0],
            "top_entity": (_artifact_texts(bundle, "entity") or [None])[0],
            "top_relation": (_artifact_texts(bundle, "relation") or [None])[0],
            "meta": dict(bundle.get("meta") or {}),
        }
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def run(corpus_path: Path) -> dict:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    cases = list(corpus.get("cases") or [])
    results = [run_case(case) for case in cases]
    family_totals: dict[str, dict[str, int]] = {}
    for result in results:
        family = str(result.get("family") or "uncategorized")
        family_totals.setdefault(family, {"total": 0, "passed": 0, "failed": 0})
        family_totals[family]["total"] += 1
        if result["ok"]:
            family_totals[family]["passed"] += 1
        else:
            family_totals[family]["failed"] += 1
    return {
        "ok": all(result["ok"] for result in results),
        "total": len(results),
        "passed": sum(1 for result in results if result["ok"]),
        "failed": sum(1 for result in results if not result["ok"]),
        "families": family_totals,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Solaris retrieval and editorial evaluation cases.")
    parser.add_argument(
        "--corpus",
        default=str(ROOT / "evals" / "retrieval_eval_cases.json"),
        help="Path to the retrieval eval corpus JSON file.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    args = parser.parse_args(argv)

    result = run(Path(args.corpus))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Solaris evals: {result['passed']}/{result['total']} passed")
        for family, totals in result["families"].items():
            print(f"- {family}: {totals['passed']}/{totals['total']} passed")
        for case in result["results"]:
            status = "PASS" if case["ok"] else "FAIL"
            print(f"{status} {case['id']} ({case['family']})")
            if case["failures"]:
                for failure in case["failures"]:
                    print(f"  - {failure}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
