# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import solaris.editorial.engine as engine_module
from solaris.editorial.adjudication import AdjudicationContext, adjudication_rationale_payload, should_consider_adjudication
from solaris.config import Settings
from solaris.editorial.model_adjudicator import OpenAICompatibleAdjudicator
from solaris.models.session import OpenSessionRequest
from solaris.server import build_services

from conftest import ingest, make_event


def test_adjudication_disabled_by_default_policy_shape():
    policy = {
        "promotion_threshold": 0.7,
        "retire_threshold": 0.2,
    }
    assert not should_consider_adjudication(
        policy=policy,
        artifact_type="claim",
        remember_score=0.65,
        current_action="leave_candidate",
        hard_locked=False,
    )


def test_adjudication_enabled_for_ambiguous_claim_band():
    policy = {
        "promotion_threshold": 0.7,
        "retire_threshold": 0.2,
        "adjudication": {
            "mode": "shadow",
            "artifact_types": ["claim", "episode"],
            "allowed_actions": ["promote", "leave_candidate", "retire"],
            "ambiguity_band": {
                "candidate_floor": 0.35,
                "candidate_ceiling": 0.82,
                "promotion_margin": 0.10,
                "retire_margin": 0.08,
            },
        },
    }
    assert should_consider_adjudication(
        policy=policy,
        artifact_type="claim",
        remember_score=0.66,
        current_action="leave_candidate",
        hard_locked=False,
    )


def test_adjudication_skips_hard_locked_case():
    policy = {
        "promotion_threshold": 0.7,
        "retire_threshold": 0.2,
        "adjudication": {
            "mode": "shadow",
            "artifact_types": ["claim", "episode"],
            "allowed_actions": ["promote", "leave_candidate", "retire"],
        },
    }
    assert not should_consider_adjudication(
        policy=policy,
        artifact_type="claim",
        remember_score=0.66,
        current_action="leave_candidate",
        hard_locked=True,
    )


def test_adjudication_rationale_payload_tracks_shadow_comparison():
    result = type(
        "Result",
        (),
        {
            "source": "model",
            "confidence": 0.61,
            "rationale": "Borderline personal fact; hold until reinforced.",
            "model": "gpt-5.4-mini",
            "prompt_version": "solaris_editorial_adjudication_v1",
            "action": "leave_candidate",
        },
    )()
    payload = adjudication_rationale_payload(
        result,
        mode="shadow",
        rule_action="promote",
        final_action="promote",
        applied=False,
    )
    assert payload["adjudication_mode"] == "shadow"
    assert payload["adjudication_rule_action"] == "promote"
    assert payload["adjudication_suggested_action"] == "leave_candidate"
    assert payload["adjudication_final_action"] == "promote"
    assert payload["adjudication_applied"] is False
    assert payload["adjudication_prompt_version"] == "solaris_editorial_adjudication_v1"


def test_openai_compatible_adjudicator_parses_json_response():
    captured: dict[str, object] = {}

    def _transport(*, url, headers, payload, timeout_seconds):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        captured["timeout_seconds"] = timeout_seconds
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"action":"retire","confidence":0.72,"rationale":"Looks like conversational fluff, not durable memory."}'
                    }
                }
            ]
        }

    adjudicator = OpenAICompatibleAdjudicator(
        model="gpt-5.4-mini",
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        timeout_seconds=12.0,
        prompt_version="solaris_editorial_adjudication_v1",
        transport=_transport,
    )
    result = adjudicator.adjudicate(
        AdjudicationContext(
            artifact_type="episode",
            artifact_id="ep_1",
            policy_profile="default_v1",
            policy_version=1,
            kind="message",
            canonical_text="very funny",
            supporting_event_ids=["evt_1"],
            remember_score=0.64,
            influence_score=0.64,
            current_action="leave_candidate",
            current_state=None,
            factors={"identity_relevance": 0.1},
            allowed_actions=("promote", "leave_candidate", "retire"),
        )
    )

    assert result is not None
    assert result.action == "retire"
    assert result.confidence == 0.72
    assert "conversational fluff" in result.rationale
    assert result.model == "gpt-5.4-mini"
    assert result.prompt_version == "solaris_editorial_adjudication_v1"
    assert str(captured["url"]).endswith("/chat/completions")


def test_shadow_mode_preserves_rule_action_but_records_model_suggestion(scope, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    case_dir = root / ".runtime" / "test_shadow_adjudication" / uuid4().hex
    case_dir.mkdir(parents=True, exist_ok=True)
    try:
        services = build_services(
            Settings(
                project_root=root,
                db_path=case_dir / "solaris.db",
                policies_dir=root / "policies",
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
        )
        session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
        ingest(
            services,
            make_event(
                scope=scope,
                session_id=session.session_id,
                timestamp="2026-04-12T10:00:00+00:00",
                idempotency_key="shadow-adj-1",
                raw_text="Solaris supports shadow review.",
                normalized_text="solaris supports shadow review",
            ),
            make_event(
                scope=scope,
                session_id=session.session_id,
                timestamp="2026-04-12T10:01:00+00:00",
                idempotency_key="shadow-adj-2",
                raw_text="Solaris supports shadow review in practice.",
                normalized_text="solaris supports shadow review in practice",
            ),
        )
        with services["db"].transaction() as connection:
            events = services["events_repo"].list_by_scope(connection, scope.key(), limit=2)
            event = events[0]
            claim = services["claims_repo"].upsert(
                connection,
                scope=scope,
                subject_entity_id=None,
                predicate="supports",
                object_text="shadow review",
                canonical_claim="Solaris supports shadow review",
                confidence=0.92,
                pinned=False,
                seen_at=event["timestamp"],
            )
            services["evidence_repo"].link(
                connection,
                artifact_type="claim",
                artifact_id=claim["claim_id"],
                scope_key=scope.key(),
                event_ids=[row["event_id"] for row in events],
            )
            services["claims_repo"].refresh_evidence_count(connection, claim["claim_id"])
            services["editorial_repo"].enqueue_review(
                connection,
                artifact_type="claim",
                artifact_id=claim["claim_id"],
                scope=scope,
                trigger="derived",
                priority=0.5,
            )

        policy = {
            "version": 1,
            "promotion_threshold": 0.7,
            "retire_threshold": 0.2,
            "reinforce_threshold": 0.55,
            "adjudication": {
                "mode": "shadow",
                "artifact_types": ["claim", "episode"],
                "allowed_actions": ["promote", "leave_candidate", "retire"],
                "ambiguity_band": {
                    "candidate_floor": 0.35,
                    "candidate_ceiling": 0.82,
                    "promotion_margin": 0.10,
                    "retire_margin": 0.08,
                },
            },
        }

        class _StaticAdjudicator:
            def adjudicate(self, context):
                del context
                return type(
                    "Result",
                    (),
                    {
                        "action": "promote",
                        "confidence": 0.67,
                        "rationale": "Borderline but looks durable enough to test as remembered.",
                        "source": "model",
                        "model": "gpt-5.4-mini",
                        "prompt_version": "solaris_editorial_adjudication_v1",
                    },
                )()

        services["review"].engine.adjudicator = _StaticAdjudicator()
        monkeypatch.setattr(services["review"].engine.policy_registry, "get", lambda profile: dict(policy))
        monkeypatch.setattr(engine_module, "compute_factors", lambda **kwargs: {"identity_relevance": 0.4, "future_utility": 0.4})
        monkeypatch.setattr(engine_module, "score_artifact", lambda **kwargs: (0.66, 0.66))

        result = services["review"].run_review(scope, None, "default_v1", 20, "boundary")
        assert result["decisions_created"] >= 1

        with services["db"].transaction() as connection:
            decisions = services["editorial_repo"].list_decisions(connection, artifact_type="claim", artifact_id=claim["claim_id"])
            state = services["editorial_repo"].get_state(connection, artifact_type="claim", artifact_id=claim["claim_id"])

        assert decisions[0]["action"] == "leave_candidate"
        assert decisions[0]["decided_by"] == "rule_engine"
        assert decisions[0]["rationale"]["adjudication_mode"] == "shadow"
        assert decisions[0]["rationale"]["adjudication_rule_action"] == "leave_candidate"
        assert decisions[0]["rationale"]["adjudication_suggested_action"] == "promote"
        assert decisions[0]["rationale"]["adjudication_final_action"] == "leave_candidate"
        assert decisions[0]["rationale"]["adjudication_applied"] is False
        assert state["rationale_json"]["adjudication_prompt_version"] == "solaris_editorial_adjudication_v1"
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_cross_interaction_episode_recurrence_enters_shadow_adjudication(scope):
    root = Path(__file__).resolve().parents[1]
    case_dir = root / ".runtime" / "test_shadow_episode_adjudication" / uuid4().hex
    case_dir.mkdir(parents=True, exist_ok=True)
    try:
        services = build_services(
            Settings(
                project_root=root,
                db_path=case_dir / "solaris.db",
                policies_dir=root / "policies",
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
        )
        runtime = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
        interaction_a = services["sessions"].open_session(
            OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
        )
        interaction_b = services["sessions"].open_session(
            OpenSessionRequest(scope=scope, kind="interaction", parent_session_id=runtime.session_id)
        )
        ingest(
            services,
            make_event(
                scope=scope,
                session_id=interaction_a.session_id,
                timestamp="2026-04-12T10:00:00+00:00",
                idempotency_key="shadow-episode-a",
                raw_text="I think Solaris should keep archive and belief separate.",
                hints={
                    "episode_hint": "Solaris memory separation design",
                    "entities": ["Solaris", "archive", "belief"],
                },
            ),
            make_event(
                scope=scope,
                session_id=interaction_b.session_id,
                timestamp="2026-04-12T10:01:00+00:00",
                idempotency_key="shadow-episode-b",
                raw_text="That separation matters because memory should not rewrite archived records.",
                hints={
                    "episode_hint": "archive belief write separation",
                    "entities": ["Solaris"],
                },
            ),
        )

        class _StaticAdjudicator:
            def adjudicate(self, context):
                del context
                return type(
                    "Result",
                    (),
                    {
                        "action": "promote",
                        "confidence": 0.73,
                        "rationale": "Repeated cross-turn episode is in the ambiguous middle; promote is plausible.",
                        "source": "model",
                        "model": "gpt-5.4-mini",
                        "prompt_version": "solaris_editorial_adjudication_v1",
                    },
                )()

        services["review"].engine.adjudicator = _StaticAdjudicator()
        result = services["review"].run_review(scope, None, "default_v1", 20, "boundary")
        assert result["decisions_created"] >= 1

        with services["db"].transaction() as connection:
            episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=10)
            episode = next(item for item in episodes if item["title"] == "Solaris memory separation design")
            state = services["editorial_repo"].get_state(connection, artifact_type="episode", artifact_id=episode["episode_id"])
            decisions = services["editorial_repo"].list_decisions(connection, artifact_type="episode", artifact_id=episode["episode_id"])

        assert state["remember_score"] >= 0.65
        assert decisions[0]["rationale"]["adjudication_mode"] == "shadow"
        assert decisions[0]["rationale"]["adjudication_rule_action"] == "leave_candidate"
        assert decisions[0]["rationale"]["adjudication_suggested_action"] == "promote"
        assert decisions[0]["rationale"]["adjudication_final_action"] == "leave_candidate"
        assert decisions[0]["rationale"]["adjudication_applied"] is False
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)
