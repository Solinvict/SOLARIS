# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from dataclasses import dataclass
import re

from solaris.editorial.adjudication import (
    AdjudicationContext,
    NullEditorialAdjudicator,
    adjudication_allowed_actions,
    adjudication_mode,
    adjudication_rationale_payload,
    should_consider_adjudication,
)
from solaris.editorial.actions import states_for_action
from solaris.editorial.factors import compute_factors
from solaris.editorial.scoring import score_artifact


QUESTION_STARTERS = {
    "what",
    "why",
    "how",
    "when",
    "where",
    "who",
    "which",
    "is",
    "are",
    "am",
    "do",
    "does",
    "did",
    "can",
    "could",
    "would",
    "should",
    "will",
    "have",
    "has",
    "remind",
    "check",
}

GENERIC_EPISODE_TITLES = {"conversation", "message", "activity", "system", "note"}
PRONOUN_SUBJECTS = {"i", "you", "we", "they", "he", "she", "it"}
SPEECH_ACT_PREFIXES = (
    "asking",
    "checking",
    "explaining",
    "reminding",
    "requesting",
    "saying",
    "summarizing",
    "telling",
    "trying",
    "wondering",
)
LOW_SIGNAL_EPISODE_TOKENS = {
    "the",
    "be",
    "user",
    "operator",
    "may",
    "memory",
    "training",
    "grounding",
    "codebase",
    "session_mode",
    "open",
    "look",
    "file",
    "mcp",
    "research",
    "continue",
    "bounded",
    "investigate",
    "asking",
    "remember",
    "else",
    "sounds",
    "everything",
    "opportunities",
    "love",
}
LOW_SIGNAL_IMPORT_COMMAND_PREFIXES = {
    "enter",
    "exit",
    "open",
    "close",
    "read",
    "show",
    "look",
    "start",
    "stop",
    "resume",
    "continue",
    "switch",
    "set",
}
TRADING_OPERATIONAL_KEYWORDS = {
    "trade",
    "trading",
    "order",
    "orders",
    "position",
    "positions",
    "entry",
    "entries",
    "exit",
    "exits",
    "broker",
    "exchange",
    "execution",
    "executed",
    "portfolio",
    "capital",
    "equity",
    "drawdown",
    "pnl",
    "profit",
    "loss",
    "risk",
    "thesis",
    "theses",
    "regime",
    "market",
    "buy",
    "sell",
    "long",
    "short",
}
TRADING_SYMBOL_TOKENS = {
    "btc",
    "eth",
    "sol",
    "ada",
    "doge",
    "bnb",
    "aapl",
    "nvda",
    "tsla",
    "msft",
    "googl",
    "amzn",
    "okx",
    "alpaca",
}
TRADING_SUMMARY_ONLY_KINDS = {
    "trading_scorecard",
    "trading_cycle_summary",
    "trading_journal_event",
    "trading_theses",
}
TRADING_ROUTINE_EPISODE_TITLES = {
    "crypto-regime-cycle",
    "risk-envelope",
    "execution-cycle",
    "trade-outcome-review",
    "learner-state-update",
}
TRADING_SIGNIFICANT_EPISODE_KINDS = {
    "trading_outcome",
    "trading_learner_intervention",
}
PERSONAL_PROFILE_EPISODE_TITLES = {
    "operator personal context update",
    "operator personal context review",
    "operator memory profile query",
    "operator memory self-inquiry",
}
OPERATIONAL_ROUTINE_EPISODE_TITLES = {
    "access-internet",
    "screen-capture",
    "current session context",
    "active session context",
    "switch to trading mode",
    "codebase investigation request",
    "audio pipeline trace request",
    "solaris",
}


@dataclass(slots=True)
class EditorialEngine:
    policy_registry: object
    editorial_repo: object
    evidence_repo: object
    events_repo: object
    claims_repo: object
    relations_repo: object
    episodes_repo: object
    adjudicator: object = NullEditorialAdjudicator()

    def _artifact_for(self, connection, *, artifact_type: str, artifact_id: str) -> dict | None:
        if artifact_type == "claim":
            return self.claims_repo.get(connection, artifact_id)
        if artifact_type == "relation":
            return self.relations_repo.get(connection, artifact_id)
        if artifact_type == "episode":
            return self.episodes_repo.get(connection, artifact_id)
        return None

    @staticmethod
    def _looks_question_like(text: str) -> bool:
        normalized = " ".join((text or "").split()).strip().casefold()
        if not normalized:
            return False
        while True:
            matched = next(
                (prefix for prefix in ("all right ", "alright ", "well ", "actually ", "so ", "but ", "like ", "okay ", "ok ") if normalized.startswith(prefix)),
                None,
            )
            if not matched:
                break
            normalized = normalized[len(matched) :].lstrip()
        tokens = re.findall(r"[A-Za-z0-9_']+", normalized)
        if not tokens:
            return False
        return tokens[0] in QUESTION_STARTERS

    @staticmethod
    def _looks_speech_act_like_claim(text: str) -> bool:
        normalized = " ".join((text or "").split()).strip()
        if not normalized:
            return False
        match = re.match(
            r"(?P<subject>[\w \-_]{1,60}?)\s+(?P<copula>is|are|should be|means)\s+(?P<object>.+)$",
            normalized,
            flags=re.IGNORECASE,
        )
        if match is None:
            return False
        subject_name = match.group("subject").strip().casefold()
        object_text = match.group("object").strip().casefold()
        if subject_name not in PRONOUN_SUBJECTS:
            return False
        if object_text.startswith(SPEECH_ACT_PREFIXES):
            return True
        return object_text.startswith(("likely ", "probably ", "maybe "))

    @staticmethod
    def _has_explicit_memory_signal(supporting_events: list[dict]) -> bool:
        primary_event = supporting_events[0] if supporting_events else {}
        payload = primary_event.get("structured_payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        route_domain = str(payload.get("route_domain") or "").strip().casefold()
        route_action = str(payload.get("route_action") or "").strip().casefold()
        claim_signal = str(payload.get("claim_signal") or "").strip().casefold()
        source_app = str(primary_event.get("source_app") or "").strip().casefold()
        primary_kind = str(primary_event.get("kind") or "").strip().casefold()
        legacy_note_claim = (
            primary_kind == "note"
            and bool(payload.get("claim"))
            and (source_app == "legacy_adapter" or source_app.endswith("_legacy"))
        )
        return (
            route_domain == "memory"
            or route_action.startswith("remember_")
            or claim_signal == "explicit_memory"
            or legacy_note_claim
        )

    @classmethod
    def _claim_has_trading_semantics(cls, claim_text: str, supporting_events: list[dict]) -> bool:
        for event in supporting_events:
            kind = str(event.get("kind") or "").strip().casefold()
            if kind.startswith("trading_"):
                return True
            payload = event.get("structured_payload") or {}
            if not isinstance(payload, dict):
                payload = {}
            route_domain = str(payload.get("route_domain") or "").strip().casefold()
            route_action = str(payload.get("route_action") or "").strip().casefold()
            source_app = str(event.get("source_app") or "").strip().casefold()
            if route_domain == "trading" or route_action.startswith("trading_") or source_app == "trading_adapter" or source_app.endswith("_trading"):
                return True

        combined = " ".join(
            part
            for part in [claim_text, *[str(event.get("raw_text") or "") for event in supporting_events]]
            if str(part or "").strip()
        ).casefold()
        tokens = set(re.findall(r"[A-Za-z0-9_']+", combined))
        operational_hits = tokens & TRADING_OPERATIONAL_KEYWORDS
        if len(operational_hits) >= 2:
            return True
        if operational_hits and tokens & TRADING_SYMBOL_TOKENS:
            return True
        return False

    @staticmethod
    def _has_trading_fact_evidence(supporting_events: list[dict]) -> bool:
        for event in supporting_events:
            kind = str(event.get("kind") or "").strip().casefold()
            if not kind.startswith("trading_"):
                continue
            payload = event.get("structured_payload") or {}
            if not isinstance(payload, dict):
                payload = {}
            if bool(payload.get("fact_eligible")):
                return True
            if kind not in TRADING_SUMMARY_ONLY_KINDS:
                return True
        return False

    @staticmethod
    def _journal_payload(event: dict) -> dict:
        payload = event.get("structured_payload") or {}
        if not isinstance(payload, dict):
            return {}
        journal_payload = payload.get("journal_payload") or {}
        return journal_payload if isinstance(journal_payload, dict) else {}

    @staticmethod
    def _relation_has_explicit_hint(supporting_events: list[dict]) -> bool:
        for event in supporting_events:
            hints = event.get("hints") or {}
            if not isinstance(hints, dict):
                continue
            relations = hints.get("relations") or []
            if isinstance(relations, list) and any(isinstance(item, dict) for item in relations):
                return True
        return False

    @classmethod
    def _episode_has_trading_semantics(cls, title: str, supporting_events: list[dict]) -> bool:
        normalized_title = " ".join((title or "").split()).strip().casefold()
        if normalized_title in TRADING_ROUTINE_EPISODE_TITLES:
            return True
        for event in supporting_events:
            kind = str(event.get("kind") or "").strip().casefold()
            if kind.startswith("trading_"):
                return True
            payload = event.get("structured_payload") or {}
            if not isinstance(payload, dict):
                payload = {}
            route_domain = str(payload.get("route_domain") or "").strip().casefold()
            route_action = str(payload.get("route_action") or "").strip().casefold()
            source_app = str(event.get("source_app") or "").strip().casefold()
            if route_domain == "trading" or route_action.startswith("trading_") or source_app == "trading_adapter" or source_app.endswith("_trading"):
                return True
        return False

    @classmethod
    def _trading_episode_has_significant_anchor(cls, *, title: str, supporting_events: list[dict]) -> bool:
        normalized_title = " ".join((title or "").split()).strip().casefold()
        has_outcome = False
        has_intervention = False
        has_execution_failure = False
        has_execution_submission = False
        has_risk_veto = False
        has_regime_shift = False
        for event in supporting_events:
            kind = str(event.get("kind") or "").strip().casefold()
            payload = cls._journal_payload(event)
            if kind == "trading_outcome":
                has_outcome = True
            if kind == "trading_learner_intervention":
                has_intervention = True
            if kind == "trading_execution_result":
                submitted = len(list(payload.get("submitted_orders") or payload.get("broker_actions") or []))
                failed = len(list(payload.get("failed_orders") or []))
                has_execution_submission = has_execution_submission or submitted > 0
                has_execution_failure = has_execution_failure or failed > 0
            if kind == "trading_risk_envelope":
                vetoes = payload.get("vetoes")
                try:
                    veto_count = len(vetoes) if isinstance(vetoes, list) else int(vetoes or 0)
                except (TypeError, ValueError):
                    veto_count = 0
                approved = payload.get("approved")
                has_risk_veto = has_risk_veto or veto_count > 0 or approved is False
            if kind == "trading_market_state" and bool(payload.get("regime_shift")):
                has_regime_shift = True
        if normalized_title == "trade-outcome-review":
            return has_outcome
        if normalized_title == "learner-state-update":
            return has_intervention
        if normalized_title == "risk-envelope":
            return has_risk_veto
        if normalized_title == "crypto-regime-cycle":
            return has_regime_shift
        if normalized_title == "execution-cycle":
            return has_execution_failure or has_outcome or has_intervention
        return has_outcome or has_intervention or has_execution_failure or has_risk_veto or has_regime_shift

    @classmethod
    def _trading_episode_requires_consolidation(cls, *, title: str, supporting_events: list[dict]) -> bool:
        if not cls._episode_has_trading_semantics(title, supporting_events):
            return False
        normalized_title = " ".join((title or "").split()).strip().casefold()
        if normalized_title not in TRADING_ROUTINE_EPISODE_TITLES:
            return False
        return not cls._trading_episode_has_significant_anchor(title=title, supporting_events=supporting_events)

    @staticmethod
    def _personal_profile_episode_requires_consolidation(*, title: str) -> bool:
        normalized_title = " ".join((title or "").split()).strip().casefold()
        if not normalized_title:
            return False
        return normalized_title in PERSONAL_PROFILE_EPISODE_TITLES

    @staticmethod
    def _operational_routine_episode_requires_consolidation(*, title: str) -> bool:
        normalized_title = " ".join((title or "").split()).strip().casefold()
        if not normalized_title:
            return False
        return normalized_title in OPERATIONAL_ROUTINE_EPISODE_TITLES

    @staticmethod
    def _is_legacy_import(supporting_events: list[dict]) -> bool:
        if not supporting_events:
            return False
        return all(
            (
                lambda source_app: source_app == "legacy_adapter" or source_app.endswith("_legacy")
            )(str(event.get("source_app") or "").strip().casefold())
            for event in supporting_events
        )

    @classmethod
    def _episode_texts(cls, supporting_events: list[dict]) -> list[str]:
        texts: list[str] = []
        for event in supporting_events:
            payload = event.get("structured_payload") or {}
            if not isinstance(payload, dict):
                payload = {}
            raw_text = str(payload.get("raw_text") or event.get("raw_text") or "").strip()
            if raw_text:
                texts.append(" ".join(raw_text.split()))
        return texts

    @classmethod
    def _episode_has_only_low_signal_tokens(cls, tokens: list[str]) -> bool:
        return bool(tokens) and all(token in LOW_SIGNAL_EPISODE_TOKENS for token in tokens)

    @classmethod
    def _episode_is_repeated_import_command(cls, supporting_events: list[dict]) -> bool:
        texts = cls._episode_texts(supporting_events)
        if len(texts) < 2:
            return False
        normalized = [text.casefold() for text in texts]
        if len(set(normalized)) != 1:
            return False
        first_tokens = re.findall(r"[A-Za-z0-9_']+", normalized[0])
        if not first_tokens:
            return False
        return first_tokens[0] in LOW_SIGNAL_IMPORT_COMMAND_PREFIXES

    @classmethod
    def _episode_is_repeated_low_signal_command(cls, *, title: str, supporting_events: list[dict]) -> bool:
        texts = cls._episode_texts(supporting_events)
        if len(texts) < 2:
            return False
        title_tokens = [token for token in re.findall(r"[A-Za-z0-9_']+", str(title or "").casefold()) if token]
        if not title_tokens or len(title_tokens) > 3:
            return False
        normalized = [" ".join(text.casefold().split()) for text in texts]
        first_tokens = [
            re.findall(r"[A-Za-z0-9_']+", text)[0]
            for text in normalized
            if re.findall(r"[A-Za-z0-9_']+", text)
        ]
        if len(first_tokens) != len(normalized):
            return False
        if any(token not in LOW_SIGNAL_IMPORT_COMMAND_PREFIXES for token in first_tokens):
            return False
        return all(all(token in text for token in title_tokens) for text in normalized)

    @classmethod
    def _episode_is_repeated_low_signal_question(cls, *, title: str, supporting_events: list[dict]) -> bool:
        texts = cls._episode_texts(supporting_events)
        if len(texts) < 2:
            return False
        title_tokens = [token for token in re.findall(r"[A-Za-z0-9_']+", str(title or "").casefold()) if token]
        if not title_tokens or len(title_tokens) > 2:
            return False
        normalized = [" ".join(text.casefold().split()) for text in texts]
        if not all(cls._looks_question_like(text) for text in normalized):
            return False
        return all(all(token in text for token in title_tokens) for text in normalized)

    @classmethod
    def _episode_is_low_quality(cls, *, title: str, supporting_events: list[dict], event_count: int) -> bool:
        normalized = " ".join((title or "").split()).strip().casefold()
        if not normalized:
            return True
        tokens = re.findall(r"[A-Za-z0-9_']+", normalized)
        if not tokens:
            return True
        if normalized in GENERIC_EPISODE_TITLES:
            return True
        legacy_import = cls._is_legacy_import(supporting_events)
        if len(tokens) <= 2 and cls._episode_has_only_low_signal_tokens(tokens):
            return True
        if legacy_import and len(tokens) == 1:
            return True
        if legacy_import and cls._episode_has_only_low_signal_tokens(tokens):
            return True
        if legacy_import and cls._episode_is_repeated_import_command(supporting_events):
            return True
        if cls._episode_is_repeated_low_signal_command(title=normalized, supporting_events=supporting_events):
            return True
        if cls._episode_is_repeated_low_signal_question(title=normalized, supporting_events=supporting_events):
            return True
        if len(tokens) == 1 and tokens[0] in LOW_SIGNAL_EPISODE_TOKENS:
            return True
        if legacy_import and len(tokens) <= 2 and event_count < 3:
            return True
        return False

    def _hold_as_candidate(self, *, artifact_type: str, artifact: dict, supporting_events: list[dict], current: dict | None) -> bool:
        event_count = len(supporting_events)
        primary_kind = str((supporting_events[0] if supporting_events else {}).get("kind") or "").strip().casefold()
        explicit_memory_signal = self._has_explicit_memory_signal(supporting_events)
        if artifact_type == "claim":
            if self._looks_question_like(str(artifact.get("canonical_claim") or "")):
                return True
            if current and current.get("remember_state") == "remembered":
                return False
            if artifact.get("pinned") or primary_kind in {"fact_assertion", "decision", "failure"} or explicit_memory_signal:
                return False
            return int(artifact.get("evidence_count") or 0) < 2 and event_count < 2
        if artifact_type == "episode":
            title = str(artifact.get("title") or "").strip()
            if self._episode_is_low_quality(title=title, supporting_events=supporting_events, event_count=event_count):
                return True
            if self._personal_profile_episode_requires_consolidation(title=title):
                return True
            if self._operational_routine_episode_requires_consolidation(title=title):
                return True
            if self._trading_episode_requires_consolidation(title=title, supporting_events=supporting_events):
                return True
        if current and current.get("remember_state") == "remembered":
            return False
        if artifact_type == "episode":
            if primary_kind in {"decision", "failure"}:
                return False
            if event_count < 2:
                return True
            title = str(artifact.get("title") or "").strip().casefold()
            return title in GENERIC_EPISODE_TITLES and event_count < 3
        if artifact_type == "relation":
            relation_type = str(artifact.get("relation_type") or "").strip().casefold()
            explicit_relation = self._relation_has_explicit_hint(supporting_events)
            if relation_type == "related_to":
                return True
            if explicit_relation or primary_kind in {"decision", "failure"}:
                return False
            return event_count < 2
        return False

    def _determine_action(
        self,
        *,
        artifact_type: str,
        artifact: dict,
        supporting_events: list[dict],
        current: dict | None,
        policy: dict,
        remember_score: float,
    ) -> tuple[str, bool, str | None]:
        claim_text = str(artifact.get("canonical_claim") or "")
        claim_question_like = artifact_type == "claim" and self._looks_question_like(claim_text)
        claim_speech_act_like = artifact_type == "claim" and self._looks_speech_act_like_claim(claim_text)

        if current and current.get("pinned"):
            return "pin", True, "current_pinned"
        if artifact_type == "claim" and artifact.get("pinned"):
            return "pin", True, "artifact_pinned"
        if claim_speech_act_like:
            return "retire", True, "speech_act_claim"
        if artifact_type == "claim" and self._claim_has_trading_semantics(claim_text, supporting_events):
            if not self._has_trading_fact_evidence(supporting_events):
                if (current or {}).get("remember_state") == "remembered":
                    return "retire", True, "trading_claim_missing_ledger_evidence"
                return "leave_candidate", True, "trading_claim_requires_ledger_evidence"
        if claim_question_like and (current or {}).get("remember_state") == "remembered":
            return "retire", True, "remembered_question_claim"
        if artifact_type == "relation":
            relation_type = str(artifact.get("relation_type") or "").strip().casefold()
            if relation_type == "related_to":
                if (current or {}).get("remember_state") == "remembered":
                    return "retire", True, "weak_related_to_relation"
                return "leave_candidate", True, "weak_related_to_relation"
        if (
            artifact_type == "episode"
            and (current or {}).get("remember_state") == "remembered"
            and self._episode_is_low_quality(
                title=str(artifact.get("title") or ""),
                supporting_events=supporting_events,
                event_count=len(supporting_events),
            )
        ):
            return "retire", True, "low_quality_remembered_episode"
        if artifact_type == "episode" and self._trading_episode_requires_consolidation(
            title=str(artifact.get("title") or ""),
            supporting_events=supporting_events,
        ):
            if (current or {}).get("remember_state") == "remembered":
                return "retire", True, "trading_routine_episode_requires_consolidation"
            return "leave_candidate", True, "trading_routine_episode_requires_consolidation"
        if artifact_type == "episode" and self._personal_profile_episode_requires_consolidation(
            title=str(artifact.get("title") or ""),
        ):
            if (current or {}).get("remember_state") == "remembered":
                return "retire", True, "personal_profile_episode_requires_consolidation"
            return "leave_candidate", True, "personal_profile_episode_requires_consolidation"
        if artifact_type == "episode" and self._operational_routine_episode_requires_consolidation(
            title=str(artifact.get("title") or ""),
        ):
            if (current or {}).get("remember_state") == "remembered":
                return "retire", True, "operational_routine_episode_requires_consolidation"
            return "leave_candidate", True, "operational_routine_episode_requires_consolidation"
        if self._hold_as_candidate(
            artifact_type=artifact_type,
            artifact=artifact,
            supporting_events=supporting_events,
            current=current,
        ):
            return "leave_candidate", True, "hold_as_candidate"
        if (current or {}).get("remember_state") == "remembered":
            if remember_score >= float(policy.get("reinforce_threshold", 0.55)):
                return "reinforce", False, "remembered_reinforce"
            if remember_score <= float(policy.get("retire_threshold", 0.2)):
                return "retire", False, "remembered_retire"
            return "fade", False, "remembered_fade"
        if remember_score >= float(policy.get("promotion_threshold", 0.7)):
            return "promote", False, "promotion_threshold"
        return "leave_candidate", False, "below_promotion_threshold"

    def review(self, connection, *, scope, items: list[dict], policy_profile: str) -> dict:
        policy = self.policy_registry.get(policy_profile)
        decisions_created = 0
        promoted = 0
        reinforced = 0
        left_candidate = 0
        faded = 0
        retired = 0

        for item in items:
            artifact = self._artifact_for(connection, artifact_type=item["artifact_type"], artifact_id=item["artifact_id"])
            if artifact is None:
                if item.get("review_id"):
                    self.editorial_repo.mark_reviewed(connection, item["review_id"])
                continue
            current = self.editorial_repo.get_state(connection, artifact_type=item["artifact_type"], artifact_id=item["artifact_id"])
            event_ids = self.evidence_repo.event_ids_for_artifact(
                connection,
                artifact_type=item["artifact_type"],
                artifact_id=item["artifact_id"],
            )
            supporting_events = self.events_repo.get_many(connection, event_ids)
            factors = compute_factors(artifact_type=item["artifact_type"], artifact=artifact, supporting_events=supporting_events)
            remember_score, influence_score = score_artifact(
                policy=policy,
                factors=factors,
                kind=str((supporting_events[0] if supporting_events else {}).get("kind") or item["artifact_type"]),
            )
            action, hard_locked, reason_code = self._determine_action(
                artifact_type=item["artifact_type"],
                artifact=artifact,
                supporting_events=supporting_events,
                current=current,
                policy=policy,
                remember_score=remember_score,
            )

            rule_action = action
            adjudication = None
            adjudication_applied = False
            mode = adjudication_mode(policy)
            if should_consider_adjudication(
                policy=policy,
                artifact_type=item["artifact_type"],
                remember_score=remember_score,
                current_action=action,
                hard_locked=hard_locked,
            ):
                canonical_text = str(
                    artifact.get("canonical_claim")
                    or artifact.get("title")
                    or artifact.get("relation_type")
                    or artifact.get("canonical_name")
                    or ""
                ).strip()
                adjudication = self.adjudicator.adjudicate(
                    AdjudicationContext(
                        artifact_type=item["artifact_type"],
                        artifact_id=item["artifact_id"],
                        policy_profile=policy_profile,
                        policy_version=int(policy.get("version", 1)),
                        kind=str((supporting_events[0] if supporting_events else {}).get("kind") or item["artifact_type"]),
                        canonical_text=canonical_text,
                        supporting_event_ids=event_ids,
                        remember_score=remember_score,
                        influence_score=influence_score,
                        current_action=action,
                        current_state=current,
                        factors=dict(factors),
                        allowed_actions=adjudication_allowed_actions(policy) or ("promote", "leave_candidate", "retire"),
                    )
                )
                if (
                    adjudication is not None
                    and mode == "assist"
                    and adjudication.action in {"promote", "leave_candidate", "retire"}
                ):
                    action = adjudication.action
                    adjudication_applied = True

            new_remember_state, new_activation_state = states_for_action(
                action,
                current_remember_state=(current or {}).get("remember_state"),
            )
            state_rationale = {"summary": f"Action {action} chosen from editorial review.", "reason_code": reason_code}
            state_rationale.update(
                adjudication_rationale_payload(
                    adjudication,
                    mode=mode,
                    rule_action=rule_action,
                    final_action=action,
                    applied=adjudication_applied,
                )
            )
            self.editorial_repo.upsert_state(
                connection,
                artifact_type=item["artifact_type"],
                artifact_id=item["artifact_id"],
                scope=scope,
                remember_state=new_remember_state,
                activation_state=new_activation_state,
                review_status="reviewed",
                remember_score=remember_score,
                influence_score=influence_score,
                pinned=bool((current or {}).get("pinned") or artifact.get("pinned")),
                last_reviewed_at=(supporting_events[0] if supporting_events else {}).get("timestamp"),
                policy_profile=policy_profile,
                policy_version=int(policy.get("version", 1)),
                rationale_json=state_rationale,
            )
            decision_rationale = {"summary": f"Policy {policy_profile} applied.", "reason_code": reason_code}
            decision_rationale.update(
                adjudication_rationale_payload(
                    adjudication,
                    mode=mode,
                    rule_action=rule_action,
                    final_action=action,
                    applied=adjudication_applied,
                )
            )
            decision = self.editorial_repo.insert_decision(
                connection,
                artifact_type=item["artifact_type"],
                artifact_id=item["artifact_id"],
                action=action,
                previous_state=(current or {}).get("remember_state"),
                new_state=new_remember_state,
                policy_profile=policy_profile,
                policy_version=int(policy.get("version", 1)),
                scores={"remember_score": remember_score, "influence_score": influence_score, **factors},
                rationale=decision_rationale,
                supporting_event_ids=event_ids,
                decided_by="rule_engine_hybrid" if adjudication_applied else "rule_engine",
            )
            decided_at = str(decision.get("decided_at") or "")
            if decided_at:
                if item["artifact_type"] == "claim":
                    self.claims_repo.apply_temporal_action(
                        connection,
                        claim_id=item["artifact_id"],
                        action=action,
                        decided_at=decided_at,
                    )
                elif item["artifact_type"] == "relation":
                    self.relations_repo.apply_temporal_action(
                        connection,
                        relation_id=item["artifact_id"],
                        action=action,
                        decided_at=decided_at,
                    )
            if item.get("review_id"):
                self.editorial_repo.mark_reviewed(connection, item["review_id"])
            decisions_created += 1
            if action == "promote":
                promoted += 1
            elif action == "reinforce":
                reinforced += 1
            elif action == "leave_candidate":
                left_candidate += 1
            elif action == "fade":
                faded += 1
            elif action == "retire":
                retired += 1

        return {
            "ok": True,
            "decisions_created": decisions_created,
            "promoted": promoted,
            "reinforced": reinforced,
            "left_candidate": left_candidate,
            "faded": faded,
            "retired": retired,
        }
