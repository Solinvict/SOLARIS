# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.session import OpenSessionRequest

from conftest import ingest, make_event


def test_editorial_review(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="review-1",
            raw_text="Solaris is a memory substrate.",
            hints={"entities": ["Solaris"]},
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:01:00+00:00",
            idempotency_key="review-2",
            raw_text="Solaris is a memory substrate.",
            hints={"entities": ["Solaris"]},
        ),
    )
    queue = services["review"].get_review_queue(scope, None, 50)
    assert queue["items"]
    result = services["review"].run_review(scope, None, "default_v1", 50, "boundary")
    assert result["decisions_created"] >= 1


def test_run_review_respects_session_scope(services, scope):
    session_one = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    session_two = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session_one.session_id,
            timestamp="2026-04-10T08:00:00+00:00",
            idempotency_key="review-session-scope-1a",
            raw_text="Solaris keeps archive and belief separate.",
            hints={"entities": ["Solaris"]},
        ),
        make_event(
            scope=scope,
            session_id=session_one.session_id,
            timestamp="2026-04-10T08:01:00+00:00",
            idempotency_key="review-session-scope-1b",
            raw_text="Solaris keeps archive and belief separate.",
            hints={"entities": ["Solaris"]},
        ),
        make_event(
            scope=scope,
            session_id=session_two.session_id,
            timestamp="2026-04-10T08:02:00+00:00",
            idempotency_key="review-session-scope-2a",
            raw_text="The host runtime prefers natural language framing.",
            hints={"entities": ["host runtime"]},
        ),
        make_event(
            scope=scope,
            session_id=session_two.session_id,
            timestamp="2026-04-10T08:03:00+00:00",
            idempotency_key="review-session-scope-2b",
            raw_text="The host runtime prefers natural language framing.",
            hints={"entities": ["host runtime"]},
        ),
    )

    result = services["review"].run_review(scope, session_one.session_id, "default_v1", 50, "boundary")
    assert result["decisions_created"] >= 1

    with services["db"].transaction() as connection:
        decision_sessions = {
            row["session_id"]
            for row in connection.execute(
                """
                SELECT DISTINCT ev.session_id
                FROM editorial_decisions d
                JOIN json_each(d.supporting_event_ids_json) je
                  ON 1 = 1
                JOIN events ev
                  ON ev.event_id = je.value
                """
            ).fetchall()
        }

    assert decision_sessions == {session_one.session_id}


def test_single_turn_episode_stays_candidate(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="review-episode-single",
            raw_text="Ready.",
            normalized_text="ready",
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")
    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=10)
        state = services["editorial_repo"].get_state(connection, artifact_type="episode", artifact_id=episodes[0]["episode_id"])
    assert state["remember_state"] == "candidate"
    assert state["activation_state"] == "suppressed"


def test_reconsider_review_retires_repeated_question_episode(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:00:00+00:00",
            idempotency_key="review-episode-question-1",
            raw_text="how much control do you have over trading",
            normalized_text="how much control do you have over trading",
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:01:00+00:00",
            idempotency_key="review-episode-question-2",
            raw_text="how much control do you have",
            normalized_text="how much control do you have",
        ),
    )
    with services["db"].transaction() as connection:
        episode = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=10)[0]
        services["editorial_repo"].upsert_state(
            connection,
            artifact_type="episode",
            artifact_id=episode["episode_id"],
            scope=scope,
            remember_state="remembered",
            activation_state="active",
            review_status="reviewed",
            remember_score=0.82,
            influence_score=0.82,
            policy_profile="default_v1",
        )

    result = services["review"].run_review(scope, None, "default_v1", 20, "reconsider")
    assert result["retired"] >= 1

    with services["db"].transaction() as connection:
        state = services["editorial_repo"].get_state(connection, artifact_type="episode", artifact_id=episode["episode_id"])

    assert state["remember_state"] == "retired"
    assert state["activation_state"] == "suppressed"


def test_reconsider_review_retires_repeated_low_signal_command_episode(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:02:00+00:00",
            idempotency_key="review-episode-command-1",
            raw_text="read your own file on messiah_trading",
            normalized_text="read your own file on messiah_trading",
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:03:00+00:00",
            idempotency_key="review-episode-command-2",
            raw_text="read your own file config",
            normalized_text="read your own file config",
        ),
    )
    with services["db"].transaction() as connection:
        episode = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=10)[0]
        services["editorial_repo"].upsert_state(
            connection,
            artifact_type="episode",
            artifact_id=episode["episode_id"],
            scope=scope,
            remember_state="remembered",
            activation_state="active",
            review_status="reviewed",
            remember_score=0.82,
            influence_score=0.82,
            policy_profile="default_v1",
        )

    result = services["review"].run_review(scope, None, "default_v1", 20, "reconsider")
    assert result["retired"] >= 1

    with services["db"].transaction() as connection:
        state = services["editorial_repo"].get_state(connection, artifact_type="episode", artifact_id=episode["episode_id"])

    assert state["remember_state"] == "retired"
    assert state["activation_state"] == "suppressed"


def test_reconsider_review_retires_legacy_low_quality_claim(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:05:00+00:00",
            idempotency_key="review-legacy-claim",
            raw_text="What is your capabilities",
            normalized_text="what is your capabilities",
            importance=0.8,
            confidence=0.95,
        ),
    )
    with services["db"].transaction() as connection:
        event = services["events_repo"].list_by_scope(connection, scope.key(), limit=1)[0]
        claim = services["claims_repo"].upsert(
            connection,
            scope=scope,
            subject_entity_id=None,
            predicate="is",
            object_text="your capabilities",
            canonical_claim="what is your capabilities",
            confidence=0.95,
            pinned=False,
            seen_at=event["timestamp"],
        )
        services["evidence_repo"].link(
            connection,
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope_key=scope.key(),
            event_ids=[event["event_id"]],
        )
        services["claims_repo"].refresh_evidence_count(connection, claim["claim_id"])
        services["editorial_repo"].upsert_state(
            connection,
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope=scope,
            remember_state="remembered",
            activation_state="active",
            review_status="reviewed",
            remember_score=0.82,
            influence_score=0.82,
            policy_profile="default_v1",
        )

    result = services["review"].run_review(scope, None, "default_v1", 20, "reconsider")
    assert result["decisions_created"] >= 1
    assert result["retired"] >= 1

    with services["db"].transaction() as connection:
        event = services["events_repo"].list_by_scope(connection, scope.key(), limit=1)[0]
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="claim", artifact_id=claim["claim_id"])
        state = services["editorial_repo"].get_state(connection, artifact_type="claim", artifact_id=claim["claim_id"])

    assert event["raw_text"] == "What is your capabilities"
    assert decisions[0]["action"] == "retire"
    assert state["remember_state"] == "retired"
    assert state["activation_state"] == "suppressed"


def test_reconsider_review_retires_remembered_question_like_memory_claim(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="import"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:06:00+00:00",
            idempotency_key="review-legacy-memory-question",
            raw_text="What do you know about market trading",
            normalized_text="what do you know about market trading",
            structured_payload={"route_domain": "memory", "route_action": "query_memory"},
            importance=0.9,
            confidence=0.9,
        ),
    )
    with services["db"].transaction() as connection:
        event = services["events_repo"].list_by_scope(connection, scope.key(), limit=1)[0]
        claim = services["claims_repo"].upsert(
            connection,
            scope=scope,
            subject_entity_id=None,
            predicate="asserts",
            object_text="what do you know about market trading",
            canonical_claim="what do you know about market trading",
            confidence=0.9,
            pinned=False,
            seen_at=event["timestamp"],
        )
        services["evidence_repo"].link(
            connection,
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope_key=scope.key(),
            event_ids=[event["event_id"]],
        )
        services["claims_repo"].refresh_evidence_count(connection, claim["claim_id"])
        services["editorial_repo"].upsert_state(
            connection,
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope=scope,
            remember_state="remembered",
            activation_state="active",
            review_status="reviewed",
            remember_score=0.82,
            influence_score=0.82,
            policy_profile="default_v1",
        )

    result = services["review"].run_review(scope, None, "default_v1", 50, "reconsider")
    assert result["retired"] >= 1

    with services["db"].transaction() as connection:
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="claim", artifact_id=claim["claim_id"])
        state = services["editorial_repo"].get_state(connection, artifact_type="claim", artifact_id=claim["claim_id"])

    assert decisions[0]["action"] == "retire"
    assert state["remember_state"] == "retired"
    assert state["activation_state"] == "suppressed"


def test_reconsider_review_retires_speech_act_like_claim(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:07:00+00:00",
            idempotency_key="review-speech-act-claim",
            raw_text="You are reminding the assistant to treat the interaction as voice-first.",
            normalized_text="you are reminding the assistant to treat the interaction as voice-first",
            importance=0.8,
            confidence=0.95,
        ),
    )
    with services["db"].transaction() as connection:
        event = services["events_repo"].list_by_scope(connection, scope.key(), limit=1)[0]
        claim = services["claims_repo"].upsert(
            connection,
            scope=scope,
            subject_entity_id=None,
            predicate="are",
            object_text="reminding the assistant to treat the interaction as voice-first",
            canonical_claim="You are reminding the assistant to treat the interaction as voice-first",
            confidence=0.95,
            pinned=False,
            seen_at=event["timestamp"],
        )
        services["evidence_repo"].link(
            connection,
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope_key=scope.key(),
            event_ids=[event["event_id"]],
        )
        services["claims_repo"].refresh_evidence_count(connection, claim["claim_id"])
        services["editorial_repo"].upsert_state(
            connection,
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope=scope,
            remember_state="candidate",
            activation_state="suppressed",
            review_status="reviewed",
            remember_score=0.15,
            influence_score=0.1,
            policy_profile="default_v1",
        )

    result = services["review"].run_review(scope, None, "default_v1", 50, "reconsider")
    assert result["retired"] >= 1

    with services["db"].transaction() as connection:
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="claim", artifact_id=claim["claim_id"])
        state = services["editorial_repo"].get_state(connection, artifact_type="claim", artifact_id=claim["claim_id"])

    assert decisions[0]["action"] == "retire"
    assert state["remember_state"] == "retired"
    assert state["activation_state"] == "suppressed"


def test_reconsider_review_retires_interpretation_claim_promoted_from_conversation_turn(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:08:00+00:00",
            idempotency_key="review-interpretation-claim",
            raw_text="I didn't ask people",
            normalized_text="i didn't ask people",
            structured_payload={
                "route_domain": "conversation",
                "route_action": "respond",
                "claim_signal": "interpretation",
                "claim": {
                    "subject_name": "speaker",
                    "predicate": "did_not_ask",
                    "object_text": "people",
                    "canonical_claim": "speaker did_not_ask people",
                    "confidence": 0.9,
                    "pinned": False,
                },
            },
            importance=0.65,
            confidence=0.95,
        ),
    )
    with services["db"].transaction() as connection:
        claim = services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)[0]
        services["editorial_repo"].upsert_state(
            connection,
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope=scope,
            remember_state="remembered",
            activation_state="active",
            review_status="reviewed",
            remember_score=0.82,
            influence_score=0.82,
            policy_profile="default_v1",
        )

    result = services["review"].run_review(scope, None, "default_v1", 50, "reconsider")
    assert result["retired"] >= 1

    with services["db"].transaction() as connection:
        claim = services["claims_repo"].list_by_scope(connection, scope.key(), limit=10)[0]
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="claim", artifact_id=claim["claim_id"])
        state = services["editorial_repo"].get_state(connection, artifact_type="claim", artifact_id=claim["claim_id"])

    assert decisions[0]["action"] == "retire"
    assert state["remember_state"] == "retired"
    assert state["activation_state"] == "suppressed"


def test_trading_claim_without_ledger_evidence_stays_candidate(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:00:00+00:00",
            idempotency_key="review-trading-thought-1",
            raw_text="BTC trade closed with profit after the order filled.",
            normalized_text="btc trade closed with profit after the order filled",
            importance=0.95,
            confidence=0.95,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:01:00+00:00",
            idempotency_key="review-trading-thought-2",
            raw_text="Yes, the BTC position was profitable after execution.",
            normalized_text="yes the btc position was profitable after execution",
            importance=0.95,
            confidence=0.95,
        ),
    )
    with services["db"].transaction() as connection:
        events = services["events_repo"].list_by_scope(connection, scope.key(), limit=10)
        claim = services["claims_repo"].upsert(
            connection,
            scope=scope,
            subject_entity_id=None,
            predicate="closed_profitable",
            object_text="BTC trade",
            canonical_claim="BTC trade closed profitable",
            confidence=0.95,
            pinned=False,
            seen_at=events[0]["timestamp"],
        )
        services["evidence_repo"].link(
            connection,
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope_key=scope.key(),
            event_ids=[event["event_id"] for event in events[:2]],
        )
        services["claims_repo"].refresh_evidence_count(connection, claim["claim_id"])
        services["editorial_repo"].enqueue_review(
            connection,
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope=scope,
            trigger="evidence_update",
            priority=0.95,
        )

    result = services["review"].run_review(scope, None, "default_v1", 50, "boundary")
    assert result["left_candidate"] >= 1

    with services["db"].transaction() as connection:
        state = services["editorial_repo"].get_state(connection, artifact_type="claim", artifact_id=claim["claim_id"])
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="claim", artifact_id=claim["claim_id"])

    assert state["remember_state"] == "candidate"
    assert state["activation_state"] == "suppressed"
    assert decisions[0]["action"] == "leave_candidate"
    assert decisions[0]["rationale"]["reason_code"] == "trading_claim_requires_ledger_evidence"


def test_trading_claim_with_fact_ledger_evidence_can_promote(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:05:00+00:00",
            idempotency_key="review-trading-ledger-1",
            kind="trading_execution_result",
            raw_text="Execution result: BTC order submitted successfully.",
            normalized_text="execution result btc order submitted successfully",
            source_app="trading_adapter",
            source_module="trading_journal_adapter",
            actor="system",
            structured_payload={
                "origin_store": "trading_decision_journal.jsonl",
                "origin_event": "execution_result",
                "fact_eligible": True,
                "journal_payload": {"submitted_orders": [{"symbol": "BTC"}]},
            },
            importance=0.95,
            confidence=0.95,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:06:00+00:00",
            idempotency_key="review-trading-ledger-2",
            kind="trading_outcome",
            raw_text="Outcome: BTC closed +2.40%.",
            normalized_text="outcome btc closed +2.40%",
            source_app="trading_adapter",
            source_module="trading_journal_adapter",
            actor="system",
            structured_payload={
                "origin_store": "trading_decision_journal.jsonl",
                "origin_event": "thesis_outcome",
                "fact_eligible": True,
                "journal_payload": {"symbol": "BTC", "return_pct": 2.4},
            },
            importance=0.95,
            confidence=0.95,
        ),
    )
    with services["db"].transaction() as connection:
        events = services["events_repo"].list_by_scope(connection, scope.key(), limit=10)
        claim = services["claims_repo"].upsert(
            connection,
            scope=scope,
            subject_entity_id=None,
            predicate="closed_profitable",
            object_text="BTC trade",
            canonical_claim="BTC trade closed profitable",
            confidence=0.95,
            pinned=False,
            seen_at=events[0]["timestamp"],
        )
        services["evidence_repo"].link(
            connection,
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope_key=scope.key(),
            event_ids=[event["event_id"] for event in events[:2]],
        )
        services["claims_repo"].refresh_evidence_count(connection, claim["claim_id"])
        services["editorial_repo"].enqueue_review(
            connection,
            artifact_type="claim",
            artifact_id=claim["claim_id"],
            scope=scope,
            trigger="evidence_update",
            priority=0.95,
        )

    result = services["review"].run_review(scope, None, "default_v1", 50, "boundary")
    assert result["promoted"] + result["reinforced"] >= 1

    with services["db"].transaction() as connection:
        state = services["editorial_repo"].get_state(connection, artifact_type="claim", artifact_id=claim["claim_id"])
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="claim", artifact_id=claim["claim_id"])

    assert state["remember_state"] == "remembered"
    assert state["activation_state"] == "active"
    assert decisions[0]["action"] in {"promote", "reinforce"}
    assert decisions[0]["rationale"]["reason_code"] in {"promotion_threshold", "remembered_reinforce"}


def test_routine_trading_episode_stays_candidate_without_significant_anchor(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:10:00+00:00",
            idempotency_key="review-trading-episode-routine-1",
            kind="trading_market_state",
            raw_text="All regime: multi lane",
            normalized_text="all regime multi lane",
            source_app="trading_adapter",
            source_module="trading_journal_adapter",
            actor="system",
            hints={"episode_hint": "crypto-regime-cycle"},
            structured_payload={
                "origin_store": "trading_decision_journal.jsonl",
                "origin_event": "market_state",
                "fact_eligible": True,
                "journal_payload": {"regime_shift": False},
            },
            importance=0.9,
            confidence=0.95,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:11:00+00:00",
            idempotency_key="review-trading-episode-routine-2",
            kind="trading_execution_result",
            raw_text="Execution result: 0 submitted, 0 failed, 11 suppressed",
            normalized_text="execution result 0 submitted 0 failed 11 suppressed",
            source_app="trading_adapter",
            source_module="trading_journal_adapter",
            actor="system",
            hints={"episode_hint": "crypto-regime-cycle"},
            structured_payload={
                "origin_store": "trading_decision_journal.jsonl",
                "origin_event": "execution_result",
                "fact_eligible": True,
                "journal_payload": {"submitted_orders": [], "failed_orders": [], "suppressed_actions": ["skip"]},
            },
            importance=0.95,
            confidence=0.95,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:12:00+00:00",
            idempotency_key="review-trading-episode-routine-3",
            kind="trading_cycle_summary",
            raw_text="Cycle summary: routine cycle completed",
            normalized_text="cycle summary routine cycle completed",
            source_app="trading_adapter",
            source_module="trading_journal_adapter",
            actor="system",
            hints={"episode_hint": "crypto-regime-cycle"},
            structured_payload={
                "origin_store": "trading_decision_journal.jsonl",
                "origin_event": "cycle_summary",
                "journal_payload": {"decision": "routine cycle completed"},
            },
            importance=0.85,
            confidence=0.9,
        ),
    )

    result = services["review"].run_review(scope, None, "default_v1", 50, "boundary")
    assert result["left_candidate"] >= 1

    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=20)
        episode = next(item for item in episodes if item["title"] == "crypto-regime-cycle")
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="episode", artifact_id=episode["episode_id"])
        state = services["editorial_repo"].get_state(connection, artifact_type="episode", artifact_id=episode["episode_id"])

    assert state["remember_state"] == "candidate"
    assert state["activation_state"] == "suppressed"
    assert decisions[0]["action"] == "leave_candidate"
    assert decisions[0]["rationale"]["reason_code"] == "trading_routine_episode_requires_consolidation"


def test_significant_trading_episode_with_outcome_can_promote(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:15:00+00:00",
            idempotency_key="review-trading-episode-outcome-1",
            kind="trading_scorecard",
            raw_text="Scorecard: equity $100000.00, PnL $+1200.00, drawdown 0.20%",
            normalized_text="scorecard equity 100000 pnl +1200 drawdown 0.20",
            source_app="trading_adapter",
            source_module="trading_journal_adapter",
            actor="system",
            hints={"episode_hint": "trade-outcome-review"},
            structured_payload={
                "origin_store": "trading_decision_journal.jsonl",
                "origin_event": "scorecard",
                "journal_payload": {"current_equity": 100000.0, "total_pnl": 1200.0, "drawdown_pct": 0.2},
            },
            importance=0.85,
            confidence=0.9,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:16:00+00:00",
            idempotency_key="review-trading-episode-outcome-2",
            kind="trading_outcome",
            raw_text="Outcome: BTC closed +2.40%",
            normalized_text="outcome btc closed +2.40%",
            source_app="trading_adapter",
            source_module="trading_journal_adapter",
            actor="system",
            hints={"episode_hint": "trade-outcome-review"},
            structured_payload={
                "origin_store": "trading_decision_journal.jsonl",
                "origin_event": "thesis_outcome",
                "fact_eligible": True,
                "journal_payload": {"symbol": "BTC", "status": "closed", "return_pct": 2.4},
            },
            importance=0.95,
            confidence=0.95,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:17:00+00:00",
            idempotency_key="review-trading-episode-outcome-3",
            kind="trading_outcome",
            raw_text="Outcome: ETH closed +1.80%",
            normalized_text="outcome eth closed +1.80%",
            source_app="trading_adapter",
            source_module="trading_journal_adapter",
            actor="system",
            hints={"episode_hint": "trade-outcome-review"},
            structured_payload={
                "origin_store": "trading_decision_journal.jsonl",
                "origin_event": "thesis_outcome",
                "fact_eligible": True,
                "journal_payload": {"symbol": "ETH", "status": "closed", "return_pct": 1.8},
            },
            importance=0.95,
            confidence=0.95,
        ),
    )

    result = services["review"].run_review(scope, None, "default_v1", 50, "boundary")
    assert result["promoted"] + result["reinforced"] >= 1

    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=20)
        episode = next(item for item in episodes if item["title"] == "trade-outcome-review")
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="episode", artifact_id=episode["episode_id"])
        state = services["editorial_repo"].get_state(connection, artifact_type="episode", artifact_id=episode["episode_id"])

    assert state["remember_state"] == "remembered"
    assert state["activation_state"] == "active"
    assert decisions[0]["action"] in {"promote", "reinforce"}
    assert decisions[0]["rationale"]["reason_code"] in {"promotion_threshold", "remembered_reinforce"}


def test_execution_cycle_with_only_submitted_orders_stays_candidate(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:20:00+00:00",
            idempotency_key="review-trading-execution-routine-1",
            kind="trading_execution_plan",
            raw_text="Execution plan: planner merged active lanes.",
            normalized_text="execution plan planner merged active lanes",
            source_app="trading_adapter",
            source_module="trading_journal_adapter",
            actor="system",
            hints={"episode_hint": "execution-cycle"},
            structured_payload={
                "origin_store": "trading_decision_journal.jsonl",
                "origin_event": "execution_plan",
                "fact_eligible": True,
                "journal_payload": {"planner": "dual-lane"},
            },
            importance=0.9,
            confidence=0.95,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:21:00+00:00",
            idempotency_key="review-trading-execution-routine-2",
            kind="trading_execution_result",
            raw_text="Execution result: 2 submitted, 0 failed, 4 suppressed",
            normalized_text="execution result 2 submitted 0 failed 4 suppressed",
            source_app="trading_adapter",
            source_module="trading_journal_adapter",
            actor="system",
            hints={"episode_hint": "execution-cycle"},
            structured_payload={
                "origin_store": "trading_decision_journal.jsonl",
                "origin_event": "execution_result",
                "fact_eligible": True,
                "journal_payload": {"submitted_orders": [{"symbol": "BTC"}, {"symbol": "ETH"}], "failed_orders": [], "suppressed_actions": ["skip"]},
            },
            importance=0.95,
            confidence=0.95,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:22:00+00:00",
            idempotency_key="review-trading-execution-routine-3",
            kind="trading_cycle_summary",
            raw_text="Cycle summary: execution completed without notable exception",
            normalized_text="cycle summary execution completed without notable exception",
            source_app="trading_adapter",
            source_module="trading_journal_adapter",
            actor="system",
            hints={"episode_hint": "execution-cycle"},
            structured_payload={
                "origin_store": "trading_decision_journal.jsonl",
                "origin_event": "cycle_summary",
                "journal_payload": {"decision": "execution completed without notable exception"},
            },
            importance=0.85,
            confidence=0.9,
        ),
    )

    result = services["review"].run_review(scope, None, "default_v1", 50, "boundary")
    assert result["left_candidate"] >= 1

    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=20)
        episode = next(item for item in episodes if item["title"] == "execution-cycle")
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="episode", artifact_id=episode["episode_id"])
        state = services["editorial_repo"].get_state(connection, artifact_type="episode", artifact_id=episode["episode_id"])

    assert state["remember_state"] == "candidate"
    assert state["activation_state"] == "suppressed"
    assert decisions[0]["action"] == "leave_candidate"
    assert decisions[0]["rationale"]["reason_code"] == "trading_routine_episode_requires_consolidation"


def test_crypto_regime_cycle_with_regime_shift_can_promote(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="runtime"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:25:00+00:00",
            idempotency_key="review-trading-regime-shift-1",
            kind="trading_market_state",
            raw_text="Regime shift detected toward crypto momentum dominance.",
            normalized_text="regime shift detected toward crypto momentum dominance",
            source_app="trading_adapter",
            source_module="trading_journal_adapter",
            actor="system",
            hints={"episode_hint": "crypto-regime-cycle"},
            structured_payload={
                "origin_store": "trading_decision_journal.jsonl",
                "origin_event": "market_state",
                "fact_eligible": True,
                "journal_payload": {"regime_shift": True},
            },
            importance=0.95,
            confidence=0.95,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:26:00+00:00",
            idempotency_key="review-trading-regime-shift-2",
            kind="trading_theses",
            raw_text="Trade theses: 3 candidate(s) for BTC, ETH, SOL",
            normalized_text="trade theses 3 candidates for btc eth sol",
            source_app="trading_adapter",
            source_module="trading_journal_adapter",
            actor="system",
            hints={"episode_hint": "crypto-regime-cycle"},
            structured_payload={
                "origin_store": "trading_decision_journal.jsonl",
                "origin_event": "trade_theses",
                "journal_payload": {"theses": [{"symbol": "BTC"}, {"symbol": "ETH"}, {"symbol": "SOL"}]},
            },
            importance=0.9,
            confidence=0.9,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T10:27:00+00:00",
            idempotency_key="review-trading-regime-shift-3",
            kind="trading_cycle_summary",
            raw_text="Cycle summary: regime change reallocated attention to crypto.",
            normalized_text="cycle summary regime change reallocated attention to crypto",
            source_app="trading_adapter",
            source_module="trading_journal_adapter",
            actor="system",
            hints={"episode_hint": "crypto-regime-cycle"},
            structured_payload={
                "origin_store": "trading_decision_journal.jsonl",
                "origin_event": "cycle_summary",
                "journal_payload": {"decision": "regime change reallocated attention to crypto"},
            },
            importance=0.85,
            confidence=0.9,
        ),
    )

    result = services["review"].run_review(scope, None, "default_v1", 50, "boundary")
    assert result["promoted"] + result["reinforced"] >= 1

    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=20)
        episode = next(item for item in episodes if item["title"] == "crypto-regime-cycle")
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="episode", artifact_id=episode["episode_id"])
        state = services["editorial_repo"].get_state(connection, artifact_type="episode", artifact_id=episode["episode_id"])

    assert state["remember_state"] == "remembered"
    assert state["activation_state"] == "active"
    assert decisions[0]["action"] in {"promote", "reinforce"}
    assert decisions[0]["rationale"]["reason_code"] in {"promotion_threshold", "remembered_reinforce"}


def test_reconsider_review_retires_low_quality_legacy_import_episode(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="import"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:09:00+00:00",
            idempotency_key="review-import-episode-a",
            raw_text="training update one",
            normalized_text="training update one",
            structured_payload={"origin_store": "training_events.jsonl"},
            hints={"episode_hint": "training"},
            confidence=0.9,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:10:00+00:00",
            idempotency_key="review-import-episode-b",
            raw_text="training update two",
            normalized_text="training update two",
            structured_payload={"origin_store": "training_events.jsonl"},
            hints={"episode_hint": "training"},
            confidence=0.9,
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=10)
        training_episode = next(item for item in episodes if item["title"] == "training")
        services["editorial_repo"].upsert_state(
            connection,
            artifact_type="episode",
            artifact_id=training_episode["episode_id"],
            scope=scope,
            remember_state="remembered",
            activation_state="active",
            review_status="reviewed",
            remember_score=0.8,
            influence_score=0.8,
            policy_profile="default_v1",
        )

    result = services["review"].run_review(scope, None, "default_v1", 50, "reconsider")
    assert result["retired"] >= 1

    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=10)
        training_episode = next(item for item in episodes if item["title"] == "training")
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="episode", artifact_id=training_episode["episode_id"])
        state = services["editorial_repo"].get_state(connection, artifact_type="episode", artifact_id=training_episode["episode_id"])

    assert decisions[0]["action"] == "retire"
    assert state["remember_state"] == "retired"
    assert state["activation_state"] == "suppressed"


def test_reconsider_review_retires_repeated_import_command_episode(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="import"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:11:00+00:00",
            idempotency_key="review-import-command-a",
            raw_text="enter bounded research",
            normalized_text="enter bounded research",
            structured_payload={"origin_store": "training_events.jsonl"},
            hints={"episode_hint": "bounded-research"},
            confidence=0.9,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:12:00+00:00",
            idempotency_key="review-import-command-b",
            raw_text="enter bounded research",
            normalized_text="enter bounded research",
            structured_payload={"origin_store": "training_events.jsonl"},
            hints={"episode_hint": "bounded-research"},
            confidence=0.9,
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=20)
        episode = next(item for item in episodes if item["title"] == "bounded-research")
        services["editorial_repo"].upsert_state(
            connection,
            artifact_type="episode",
            artifact_id=episode["episode_id"],
            scope=scope,
            remember_state="remembered",
            activation_state="active",
            review_status="reviewed",
            remember_score=0.8,
            influence_score=0.8,
            policy_profile="default_v1",
        )

    result = services["review"].run_review(scope, None, "default_v1", 50, "reconsider")
    assert result["retired"] >= 1

    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=20)
        episode = next(item for item in episodes if item["title"] == "bounded-research")
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="episode", artifact_id=episode["episode_id"])
        state = services["editorial_repo"].get_state(connection, artifact_type="episode", artifact_id=episode["episode_id"])

    assert decisions[0]["action"] == "retire"
    assert state["remember_state"] == "retired"
    assert state["activation_state"] == "suppressed"


def test_reconsider_review_retires_low_signal_pronoun_episode(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:13:00+00:00",
            idempotency_key="review-user-may-a",
            raw_text="the user may be confirming the current account state",
            normalized_text="the user may be confirming the current account state",
            hints={"episode_hint": "user-may"},
            confidence=0.95,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:14:00+00:00",
            idempotency_key="review-user-may-b",
            raw_text="the user may be asking for the same account state",
            normalized_text="the user may be asking for the same account state",
            hints={"episode_hint": "user-may"},
            confidence=0.95,
        ),
    )
    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=20)
        episode = next(item for item in episodes if item["title"] == "user-may")
        services["editorial_repo"].upsert_state(
            connection,
            artifact_type="episode",
            artifact_id=episode["episode_id"],
            scope=scope,
            remember_state="remembered",
            activation_state="active",
            review_status="reviewed",
            remember_score=0.8,
            influence_score=0.8,
            policy_profile="default_v1",
        )

    result = services["review"].run_review(scope, None, "default_v1", 50, "reconsider")
    assert result["retired"] >= 1

    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=20)
        episode = next(item for item in episodes if item["title"] == "user-may")
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="episode", artifact_id=episode["episode_id"])
        state = services["editorial_repo"].get_state(connection, artifact_type="episode", artifact_id=episode["episode_id"])

    assert decisions[0]["action"] == "retire"
    assert state["remember_state"] == "retired"
    assert state["activation_state"] == "suppressed"


def test_personal_profile_episode_stays_candidate_even_with_followup_query(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:15:00+00:00",
            idempotency_key="review-personal-context-a",
            raw_text="remember my name is Jonas and I live in Example City",
            normalized_text="remember my name is jonas and i live in example city",
            kind="fact_assertion",
            hints={"episode_hint": "operator personal context update", "pin": True, "entities": ["Jonas", "Example City"]},
            structured_payload={
                "route_domain": "memory",
                "route_action": "remember_fact",
                "claims": [
                    {
                        "subject_name": "Jonas",
                        "predicate": "has name",
                        "object_text": "Jonas",
                        "canonical_claim": "Jonas has name Jonas",
                        "confidence": 0.9,
                    },
                    {
                        "subject_name": "Jonas",
                        "predicate": "lives in",
                        "object_text": "Example City",
                        "canonical_claim": "Jonas lives in Example City",
                        "confidence": 0.9,
                    },
                ],
            },
            importance=0.95,
            confidence=0.95,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:16:00+00:00",
            idempotency_key="review-personal-context-b",
            raw_text="what do you know about me",
            normalized_text="what do you know about me",
            hints={"episode_hint": "operator personal context update"},
            structured_payload={
                "route_domain": "memory",
                "route_action": "recall_profile",
            },
            importance=0.8,
            confidence=0.95,
        ),
    )

    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=20)
        episode = next(item for item in episodes if item["title"] == "operator personal context update")
        state = services["editorial_repo"].get_state(connection, artifact_type="episode", artifact_id=episode["episode_id"])
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="episode", artifact_id=episode["episode_id"])

    assert state["remember_state"] == "candidate"
    assert state["activation_state"] == "suppressed"
    assert decisions[0]["action"] == "leave_candidate"
    assert decisions[0]["rationale"]["reason_code"] == "personal_profile_episode_requires_consolidation"


def test_operational_routine_episode_stays_candidate_and_reconsider_retires_if_remembered(services, scope):
    session = services["sessions"].open_session(OpenSessionRequest(scope=scope, kind="interaction"))
    ingest(
        services,
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:17:00+00:00",
            idempotency_key="review-access-internet-a",
            raw_text="can you access internet",
            normalized_text="can you access internet",
            hints={"episode_hint": "access-internet"},
            structured_payload={
                "route_domain": "conversation",
                "route_action": "respond",
            },
            confidence=0.95,
        ),
        make_event(
            scope=scope,
            session_id=session.session_id,
            timestamp="2026-04-10T09:18:00+00:00",
            idempotency_key="review-access-internet-b",
            raw_text="how are you handling web access",
            normalized_text="how are you handling web access",
            hints={"episode_hint": "access-internet"},
            structured_payload={
                "route_domain": "conversation",
                "route_action": "respond",
            },
            confidence=0.95,
        ),
    )

    services["review"].run_review(scope, None, "default_v1", 50, "boundary")

    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=20)
        episode = next(item for item in episodes if item["title"] == "access-internet")
        state = services["editorial_repo"].get_state(connection, artifact_type="episode", artifact_id=episode["episode_id"])
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="episode", artifact_id=episode["episode_id"])
        services["editorial_repo"].upsert_state(
            connection,
            artifact_type="episode",
            artifact_id=episode["episode_id"],
            scope=scope,
            remember_state="remembered",
            activation_state="active",
            review_status="reviewed",
            remember_score=0.8,
            influence_score=0.8,
            policy_profile="default_v1",
        )

    assert state["remember_state"] == "candidate"
    assert state["activation_state"] == "suppressed"
    assert decisions[0]["action"] == "leave_candidate"
    assert decisions[0]["rationale"]["reason_code"] == "operational_routine_episode_requires_consolidation"

    result = services["review"].run_review(scope, None, "default_v1", 50, "reconsider")
    assert result["retired"] >= 1

    with services["db"].transaction() as connection:
        episodes = services["episodes_repo"].list_by_scope(connection, scope.key(), limit=20)
        episode = next(item for item in episodes if item["title"] == "access-internet")
        state = services["editorial_repo"].get_state(connection, artifact_type="episode", artifact_id=episode["episode_id"])
        decisions = services["editorial_repo"].list_decisions(connection, artifact_type="episode", artifact_id=episode["episode_id"])

    assert state["remember_state"] == "retired"
    assert state["activation_state"] == "suppressed"
    assert decisions[0]["action"] == "retire"
    assert decisions[0]["rationale"]["reason_code"] == "operational_routine_episode_requires_consolidation"
