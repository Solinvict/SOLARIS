# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256


class PatternProjectionService:
    ALL_PATTERN_KINDS = (
        "recurring_claim_cluster",
        "recurring_episode_motif",
        "relation_cluster",
        "temporal_recurrence",
    )
    ROUTINE_EPISODE_TITLES = {
        "conversation",
        "message",
        "activity",
        "system",
        "note",
        "execution-cycle",
        "risk-envelope",
        "crypto-regime-cycle",
        "learner-state-update",
        "trade-outcome-review",
        "casual greeting",
        "exit current mode",
        "trading status check",
        "solaris",
        "contract",
        "training",
    }
    PATTERN_KIND_SORT_PRIORITY = {
        "relation_cluster": 4,
        "recurring_claim_cluster": 3,
        "recurring_episode_motif": 2,
        "temporal_recurrence": 1,
    }
    RELATION_CLUSTER_ANCHOR_ROLE = {
        "blocked_by": "dst",
        "failed_due_to": "dst",
    }
    RELATION_CLUSTER_LABEL_PHRASE = {
        "blocked_by": "blocks",
        "failed_due_to": "failure cause",
    }

    def __init__(
        self,
        db,
        claims_repo,
        episodes_repo,
        relations_repo,
        entities_repo,
        editorial_repo,
        evidence_repo,
        events_repo,
    ):
        self.db = db
        self.claims_repo = claims_repo
        self.episodes_repo = episodes_repo
        self.relations_repo = relations_repo
        self.entities_repo = entities_repo
        self.editorial_repo = editorial_repo
        self.evidence_repo = evidence_repo
        self.events_repo = events_repo

    def project(self, req) -> dict:
        with self.db.transaction() as connection:
            scope_key = req.scope.key()
            allowed = set(req.pattern_kinds or self.ALL_PATTERN_KINDS)
            state_rows = self.editorial_repo.list_states_by_scope(connection, scope_key=scope_key, limit=max(250, req.limit * 25))
            state_map = {
                (str(item.get("artifact_type") or "").strip(), str(item.get("artifact_id") or "").strip()): item
                for item in state_rows
            }
            patterns: list[dict] = []
            if "recurring_claim_cluster" in allowed or "temporal_recurrence" in allowed:
                patterns.extend(self._claim_patterns(connection, scope_key=scope_key, state_map=state_map, min_weight=req.min_weight, include_temporal="temporal_recurrence" in allowed))
            if "recurring_episode_motif" in allowed or "temporal_recurrence" in allowed:
                patterns.extend(self._episode_patterns(connection, scope_key=scope_key, state_map=state_map, min_weight=req.min_weight, include_temporal="temporal_recurrence" in allowed))
            if "relation_cluster" in allowed or "temporal_recurrence" in allowed:
                patterns.extend(self._relation_patterns(connection, scope_key=scope_key, state_map=state_map, min_weight=req.min_weight, include_temporal="temporal_recurrence" in allowed))
            patterns.sort(
                key=lambda item: (
                    self.PATTERN_KIND_SORT_PRIORITY.get(str(item.get("pattern_kind") or ""), 0),
                    float(item.get("confidence") or 0.0),
                    float(item.get("consistency_score") or 0.0),
                    item.get("label") or "",
                ),
                reverse=True,
            )
            return {
                "ok": True,
                "patterns": patterns[: max(1, int(req.limit))],
                "meta": {
                    "computed_view": True,
                    "stored": False,
                    "scope": scope_key,
                    "pattern_kinds": sorted(allowed),
                },
            }

    def _claim_patterns(self, connection, *, scope_key: str, state_map: dict, min_weight: float, include_temporal: bool) -> list[dict]:
        patterns: list[dict] = []
        claims = self.claims_repo.list_by_scope(connection, scope_key, limit=500)
        for claim in claims:
            claim_id = str(claim.get("claim_id") or "").strip()
            if not claim_id:
                continue
            editorial = state_map.get(("claim", claim_id)) or {}
            if self._artifact_weight(editorial) < min_weight:
                continue
            event_ids = self.evidence_repo.event_ids_for_artifact(connection, artifact_type="claim", artifact_id=claim_id)
            recurrence = self._recurrence_support(connection, event_ids)
            if not self._is_recurring(recurrence):
                continue
            patterns.append(
                self._pattern(
                    scope_key=scope_key,
                    pattern_kind="recurring_claim_cluster",
                    label=str(claim.get("canonical_claim") or "").strip() or "claim cluster",
                    summary=f"Claim recurs across {recurrence['distinct_sessions']} sessions and {recurrence['distinct_windows']} time windows.",
                    support_claim_ids=[claim_id],
                    support_episode_ids=[],
                    support_relation_ids=[],
                    sample_event_ids=recurrence["sample_event_ids"],
                    source_confidence=float(claim.get("confidence") or 0.0),
                    consistency_score=recurrence["consistency_score"],
                    grounding_ratio=recurrence["grounding_ratio"],
                )
            )
            if include_temporal:
                patterns.append(
                    self._pattern(
                        scope_key=scope_key,
                        pattern_kind="temporal_recurrence",
                        label=f"Temporal recurrence: {str(claim.get('canonical_claim') or '').strip() or 'claim'}",
                        summary=f"Claim family reappears across {recurrence['distinct_windows']} time windows.",
                        support_claim_ids=[claim_id],
                        support_episode_ids=[],
                        support_relation_ids=[],
                        sample_event_ids=recurrence["sample_event_ids"],
                        source_confidence=float(claim.get("confidence") or 0.0),
                        consistency_score=recurrence["consistency_score"],
                        grounding_ratio=recurrence["grounding_ratio"],
                    )
                )
        return patterns

    def _episode_patterns(self, connection, *, scope_key: str, state_map: dict, min_weight: float, include_temporal: bool) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for episode in self.episodes_repo.list_by_scope(connection, scope_key, limit=500):
            episode_id = str(episode.get("episode_id") or "").strip()
            title = str(episode.get("title") or "").strip()
            if not episode_id or not title:
                continue
            editorial = state_map.get(("episode", episode_id)) or {}
            if self._artifact_weight(editorial) < min_weight:
                continue
            if title.casefold() in self.ROUTINE_EPISODE_TITLES:
                continue
            grouped[title.casefold()].append(episode)
        patterns: list[dict] = []
        for _, episodes in grouped.items():
            if len(episodes) < 2:
                continue
            event_ids: list[str] = []
            for episode in episodes:
                event_ids.extend(self.episodes_repo.get_event_ids(connection, episode["episode_id"]))
            recurrence = self._recurrence_support(connection, event_ids)
            if not self._is_recurring(recurrence):
                continue
            confidences = [float(item.get("confidence") or 0.0) for item in episodes]
            label = str(episodes[0].get("title") or "").strip()
            support_ids = [str(item.get("episode_id") or "").strip() for item in episodes if str(item.get("episode_id") or "").strip()]
            if self._is_low_signal_episode_motif(label=label, support_count=len(support_ids)):
                continue
            patterns.append(
                self._pattern(
                    scope_key=scope_key,
                    pattern_kind="recurring_episode_motif",
                    label=label,
                    summary=f"Episode motif recurs across {len(support_ids)} stored arcs and {recurrence['distinct_windows']} time windows.",
                    support_claim_ids=[],
                    support_episode_ids=support_ids,
                    support_relation_ids=[],
                    sample_event_ids=recurrence["sample_event_ids"],
                    source_confidence=sum(confidences) / max(1, len(confidences)),
                    consistency_score=recurrence["consistency_score"],
                    grounding_ratio=recurrence["grounding_ratio"],
                )
            )
            if include_temporal:
                patterns.append(
                    self._pattern(
                        scope_key=scope_key,
                        pattern_kind="temporal_recurrence",
                        label=f"Temporal recurrence: {label}",
                        summary=f"Episode motif reappears across {recurrence['distinct_windows']} time windows.",
                        support_claim_ids=[],
                        support_episode_ids=support_ids,
                        support_relation_ids=[],
                        sample_event_ids=recurrence["sample_event_ids"],
                        source_confidence=sum(confidences) / max(1, len(confidences)),
                        consistency_score=recurrence["consistency_score"],
                        grounding_ratio=recurrence["grounding_ratio"],
                    )
                )
        return patterns

    def _relation_patterns(self, connection, *, scope_key: str, state_map: dict, min_weight: float, include_temporal: bool) -> list[dict]:
        grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for relation in self.relations_repo.list_by_scope(connection, scope_key, limit=500):
            relation_id = str(relation.get("relation_id") or "").strip()
            relation_type = str(relation.get("relation_type") or "").strip().casefold()
            src_entity_id = str(relation.get("src_entity_id") or "").strip()
            dst_entity_id = str(relation.get("dst_entity_id") or "").strip()
            if not relation_id or not src_entity_id or not relation_type or relation_type == "related_to":
                continue
            editorial = state_map.get(("relation", relation_id)) or {}
            if self._artifact_weight(editorial) < min_weight:
                continue
            anchor_role = self.RELATION_CLUSTER_ANCHOR_ROLE.get(relation_type, "src")
            anchor_entity_id = dst_entity_id if anchor_role == "dst" else src_entity_id
            if not anchor_entity_id:
                continue
            grouped[(anchor_role, anchor_entity_id, relation_type)].append(relation)

        patterns: list[dict] = []
        for (anchor_role, anchor_entity_id, relation_type), relations in grouped.items():
            if len(relations) < 2:
                continue
            event_ids: list[str] = []
            support_relation_ids: list[str] = []
            confidence_values: list[float] = []
            neighborhood_names: list[str] = []
            for relation in relations:
                relation_id = str(relation.get("relation_id") or "").strip()
                if not relation_id:
                    continue
                support_relation_ids.append(relation_id)
                confidence_values.append(float(relation.get("confidence") or 0.0))
                event_ids.extend(self.evidence_repo.event_ids_for_artifact(connection, artifact_type="relation", artifact_id=relation_id))
                neighbor_entity_id = str(
                    relation.get("src_entity_id") if anchor_role == "dst" else relation.get("dst_entity_id") or ""
                ).strip()
                neighbor = self.entities_repo.get(connection, neighbor_entity_id) if neighbor_entity_id else None
                neighbor_name = str((neighbor or {}).get("canonical_name") or neighbor_entity_id).strip()
                if neighbor_name:
                    neighborhood_names.append(neighbor_name)
            if len(support_relation_ids) < 2:
                continue
            recurrence = self._recurrence_support(connection, event_ids)
            if not self._is_recurring(recurrence):
                continue
            anchor = self.entities_repo.get(connection, anchor_entity_id)
            anchor_name = str((anchor or {}).get("canonical_name") or anchor_entity_id).strip()
            width_score = min(1.0, len(set(neighborhood_names)) / 4.0)
            consistency_score = max(float(recurrence["consistency_score"]), width_score)
            relation_phrase = self.RELATION_CLUSTER_LABEL_PHRASE.get(relation_type, relation_type.replace("_", " "))
            label = f"{anchor_name} {relation_phrase} cluster".strip()
            dst_preview = ", ".join(sorted(set(neighborhood_names))[:3])
            summary = (
                f"Relation neighborhood spans {len(set(neighborhood_names))} targets "
                f"across {recurrence['distinct_sessions']} sessions and {recurrence['distinct_windows']} time windows."
            )
            if dst_preview:
                summary += f" Sample targets: {dst_preview}."
            patterns.append(
                self._pattern(
                    scope_key=scope_key,
                    pattern_kind="relation_cluster",
                    label=label,
                    summary=summary,
                    support_claim_ids=[],
                    support_episode_ids=[],
                    support_relation_ids=support_relation_ids,
                    sample_event_ids=recurrence["sample_event_ids"],
                    source_confidence=sum(confidence_values) / max(1, len(confidence_values)),
                    consistency_score=consistency_score,
                    grounding_ratio=recurrence["grounding_ratio"],
                )
            )
            if include_temporal:
                patterns.append(
                    self._pattern(
                        scope_key=scope_key,
                        pattern_kind="temporal_recurrence",
                        label=f"Temporal recurrence: {label}",
                        summary=f"Relation neighborhood reappears across {recurrence['distinct_windows']} time windows.",
                        support_claim_ids=[],
                        support_episode_ids=[],
                        support_relation_ids=support_relation_ids,
                        sample_event_ids=recurrence["sample_event_ids"],
                        source_confidence=sum(confidence_values) / max(1, len(confidence_values)),
                        consistency_score=consistency_score,
                        grounding_ratio=recurrence["grounding_ratio"],
                    )
                )
        return patterns

    @staticmethod
    def _artifact_weight(editorial: dict) -> float:
        return max(float(editorial.get("remember_score") or 0.0), float(editorial.get("influence_score") or 0.0))

    def _recurrence_support(self, connection, event_ids: list[str]) -> dict:
        resolved = self.events_repo.get_many(connection, list(dict.fromkeys(event_ids)))
        sample_event_ids = [str(item.get("event_id") or "").strip() for item in resolved[:5] if str(item.get("event_id") or "").strip()]
        sessions = {str(item.get("session_id") or "").strip() for item in resolved if str(item.get("session_id") or "").strip()}
        windows = {str(item.get("timestamp") or "").strip()[:10] for item in resolved if str(item.get("timestamp") or "").strip()}
        distinct_support = max(len(sessions), len(windows))
        consistency_score = min(1.0, distinct_support / 3.0)
        grounding_ratio = len(resolved) / max(1, len(list(dict.fromkeys(event_ids))))
        return {
            "distinct_sessions": len(sessions),
            "distinct_windows": len(windows),
            "consistency_score": consistency_score,
            "grounding_ratio": grounding_ratio,
            "sample_event_ids": sample_event_ids,
        }

    @staticmethod
    def _is_recurring(recurrence: dict) -> bool:
        return int(recurrence.get("distinct_sessions") or 0) >= 2 or int(recurrence.get("distinct_windows") or 0) >= 2

    @classmethod
    def _is_low_signal_episode_motif(cls, *, label: str, support_count: int) -> bool:
        normalized = " ".join(str(label or "").split()).strip().casefold()
        if not normalized:
            return True
        if normalized in cls.ROUTINE_EPISODE_TITLES:
            return True
        words = [part for part in normalized.split(" ") if part]
        if len(words) == 1 and support_count < 4:
            return True
        return False

    def _pattern(
        self,
        *,
        scope_key: str,
        pattern_kind: str,
        label: str,
        summary: str,
        support_claim_ids: list[str],
        support_episode_ids: list[str],
        support_relation_ids: list[str],
        sample_event_ids: list[str],
        source_confidence: float,
        consistency_score: float,
        grounding_ratio: float,
    ) -> dict:
        confidence = (0.4 * float(source_confidence)) + (0.35 * float(consistency_score)) + (0.25 * float(grounding_ratio))
        if pattern_kind == "temporal_recurrence":
            confidence -= 0.06
        principal_support_ids = sorted(set(support_claim_ids + support_episode_ids + support_relation_ids))
        pattern_id = "pat_" + sha256(
            "|".join([scope_key, pattern_kind, label.casefold().strip(), *principal_support_ids]).encode("utf-8")
        ).hexdigest()[:16]
        return {
            "pattern_id": pattern_id,
            "label": label,
            "pattern_kind": pattern_kind,
            "confidence": round(max(0.0, min(1.0, confidence)), 4),
            "source_confidence": round(max(0.0, min(1.0, float(source_confidence))), 4),
            "consistency_score": round(max(0.0, min(1.0, float(consistency_score))), 4),
            "grounding_ratio": round(max(0.0, min(1.0, float(grounding_ratio))), 4),
            "support_claim_ids": list(support_claim_ids),
            "support_episode_ids": list(support_episode_ids),
            "support_relation_ids": list(support_relation_ids),
            "sample_event_ids": list(sample_event_ids),
            "summary": summary,
            "scope": scope_key,
        }
