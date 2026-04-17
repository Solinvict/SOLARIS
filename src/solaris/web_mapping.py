# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from solaris.web_models import (
    ArchiveDensitySummary,
    GraphSummary,
    InspectorCard,
    LayerDefinition,
    SceneEdge,
    SceneNode,
    SceneSnapshot,
)

LAYER_ARCHIVE = "archive"
LAYER_EDITORIAL = "editorial_memory"
LAYER_GRAPH = "graph_structure"
LAYER_ACTIVE = "active_recall"
LAYER_FRACTAL = "fractal_projection"

LAYER_DEFINITIONS = [
    LayerDefinition(
        key=LAYER_ARCHIVE,
        label="Archive",
        description="Canonical historical record rendered as event strata and archival particles.",
    ),
    LayerDefinition(
        key=LAYER_EDITORIAL,
        label="Editorial Memory",
        description="Remembered and candidate memory artifacts stabilized by Solaris editorial state.",
    ),
    LayerDefinition(
        key=LAYER_GRAPH,
        label="Graph Structure",
        description="Meaningful entities and relations surfaced as sparse structural neighborhoods.",
    ),
    LayerDefinition(
        key=LAYER_ACTIVE,
        label="Active Recall",
        description="Foreground recall surface showing what Solaris is surfacing right now.",
    ),
    LayerDefinition(
        key=LAYER_FRACTAL,
        label="Fractal Projection",
        description="Computed recurring motifs and pattern projections, never stored as memory truth.",
    ),
]


def _timestamp(value: str | None) -> str | None:
    return str(value).strip() if value else None


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _label(item: dict, *, artifact_type: str) -> str:
    return (
        str(item.get("canonical_claim") or "").strip()
        or str(item.get("canonical_name") or "").strip()
        or str(item.get("title") or "").strip()
        or str(item.get("label") or "").strip()
        or str(item.get("relation_type") or "").strip()
        or artifact_type
    )


def _subtitle(item: dict, *, artifact_type: str) -> str:
    if artifact_type == "entity":
        return str(item.get("entity_type") or "").strip()
    if artifact_type == "relation":
        return str(item.get("relation_type") or "").strip()
    if artifact_type == "event":
        return str(item.get("kind") or "").strip()
    if artifact_type == "pattern":
        return str(item.get("pattern_kind") or "").strip()
    return ""


def _editorial_weight(editorial_state: dict | None) -> float:
    editorial = editorial_state or {}
    influence = _float(editorial.get("influence_score"), 0.0)
    remember = _float(editorial.get("remember_score"), 0.0)
    return max(influence, remember)


def _artifact_editorial(item: dict) -> dict:
    editorial = item.get("editorial_state")
    return editorial if isinstance(editorial, dict) else {}


def _node_id(prefix: str, artifact_type: str, artifact_id: str) -> str:
    return f"{prefix}:{artifact_type}:{artifact_id}"


def _inspector_summary(item: dict, *, artifact_type: str, artifact_id: str, layer: str) -> InspectorCard:
    editorial = _artifact_editorial(item)
    summary = (
        str(item.get("summary_text") or "").strip()
        or str(item.get("object_text") or "").strip()
        or str(item.get("relation_type") or "").strip()
        or _subtitle(item, artifact_type=artifact_type)
    )
    return InspectorCard(
        title=_label(item, artifact_type=artifact_type),
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        summary=summary or f"{artifact_type} artifact",
        layer=layer,
        confidence=_float(item.get("confidence") or editorial.get("remember_score"), 0.0),
        timestamp=_timestamp(item.get("last_seen") or item.get("updated_at") or item.get("timestamp")),
    )


def _scene_node(
    *,
    prefix: str,
    layer: str,
    artifact_type: str,
    artifact_id: str,
    item: dict,
    divergence: bool = False,
    projected: bool = False,
    stored: bool = True,
    emphasis: float | None = None,
) -> SceneNode:
    editorial = _artifact_editorial(item)
    weight = _editorial_weight(editorial) or _float(item.get("weight"), 0.0)
    return SceneNode(
        id=_node_id(prefix, artifact_type, artifact_id),
        layer=layer,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        label=_label(item, artifact_type=artifact_type),
        subtitle=_subtitle(item, artifact_type=artifact_type),
        timestamp=_timestamp(
            item.get("timestamp")
            or item.get("last_seen")
            or item.get("updated_at")
            or item.get("start_at")
            or item.get("decided_at")
        ),
        confidence=max(_float(item.get("confidence"), 0.0), _float(editorial.get("remember_score"), 0.0)),
        weight=weight,
        emphasis=weight if emphasis is None else emphasis,
        remember_state=str(editorial.get("remember_state") or item.get("remember_state") or "").strip() or None,
        activation_state=str(editorial.get("activation_state") or item.get("activation_state") or "").strip() or None,
        divergence=divergence,
        projected=projected,
        stored=stored,
        metadata={
            "entity_type": item.get("entity_type"),
            "relation_type": item.get("relation_type"),
            "pattern_kind": item.get("pattern_kind"),
            "supporting_event_count": item.get("supporting_event_count"),
            "scope": item.get("scope"),
        },
    )


def _scene_edge(
    *,
    edge_type: str,
    layer: str,
    source: str,
    target: str,
    label: str = "",
    strength: float = 0.0,
    metadata: dict | None = None,
) -> SceneEdge:
    return SceneEdge(
        id=f"{edge_type}:{source}:{target}",
        source=source,
        target=target,
        edge_type=edge_type,
        layer=layer,
        label=label,
        strength=strength,
        metadata=dict(metadata or {}),
    )


def _bundle_top_items(bundle: dict, limit: int = 6) -> list[tuple[str, dict, str]]:
    ordered: list[tuple[str, dict, str]] = []
    for artifact_type, key, layer in (
        ("claim", "claims", LAYER_EDITORIAL),
        ("episode", "episodes", LAYER_EDITORIAL),
        ("entity", "entities", LAYER_GRAPH),
        ("relation", "relations", LAYER_GRAPH),
        ("event", "events", LAYER_ARCHIVE),
    ):
        for item in bundle.get(key) or []:
            artifact_id = str(
                item.get(f"{artifact_type}_id")
                or item.get("event_id")
                or item.get("entity_id")
                or item.get("relation_id")
                or item.get("claim_id")
                or item.get("episode_id")
                or ""
            ).strip()
            if artifact_id:
                ordered.append((artifact_type, item, layer))
            if len(ordered) >= limit:
                return ordered
    return ordered


def _archive_density(bundle: dict) -> ArchiveDensitySummary:
    events = list(bundle.get("events") or [])
    recorded_events = list((bundle.get("recorded") or {}).get("events") or [])
    all_events = recorded_events or events
    timestamps = [
        _timestamp(item.get("timestamp"))
        for item in all_events
        if _timestamp(item.get("timestamp"))
    ]
    return ArchiveDensitySummary(
        total_events=len(events),
        recorded_events=len(recorded_events),
        earliest_timestamp=min(timestamps) if timestamps else None,
        latest_timestamp=max(timestamps) if timestamps else None,
    )


def _graph_summary(bundle: dict) -> GraphSummary:
    relations = bundle.get("relations") or []
    entities = bundle.get("entities") or []
    neighborhood_count = len(
        {
            str(item.get("src_entity_id") or "").strip()
            for item in relations
            if str(item.get("src_entity_id") or "").strip()
        }
        | {
            str(item.get("dst_entity_id") or "").strip()
            for item in relations
            if str(item.get("dst_entity_id") or "").strip()
        }
    )
    return GraphSummary(
        relation_count=len(relations),
        entity_count=len(entities),
        neighborhood_count=neighborhood_count,
    )


def build_scene_snapshot(*, bundle: dict, patterns: list[dict], query: str = "") -> SceneSnapshot:
    nodes: list[SceneNode] = []
    edges: list[SceneEdge] = []
    focus_node_ids: list[str] = []
    inspectors: list[InspectorCard] = []
    node_ids: set[str] = set()
    entity_graph_nodes: set[str] = set()

    for event in (bundle.get("recorded") or {}).get("events") or bundle.get("events") or []:
        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            continue
        node = _scene_node(prefix="archive", layer=LAYER_ARCHIVE, artifact_type="event", artifact_id=event_id, item=event)
        if node.id not in node_ids:
            nodes.append(node)
            node_ids.add(node.id)

    for claim in bundle.get("claims") or []:
        claim_id = str(claim.get("claim_id") or "").strip()
        if not claim_id:
            continue
        node = _scene_node(prefix="memory", layer=LAYER_EDITORIAL, artifact_type="claim", artifact_id=claim_id, item=claim)
        if node.id not in node_ids:
            nodes.append(node)
            node_ids.add(node.id)

    for episode in bundle.get("episodes") or []:
        episode_id = str(episode.get("episode_id") or "").strip()
        if not episode_id:
            continue
        node = _scene_node(prefix="memory", layer=LAYER_EDITORIAL, artifact_type="episode", artifact_id=episode_id, item=episode)
        if node.id not in node_ids:
            nodes.append(node)
            node_ids.add(node.id)

    for entity in bundle.get("entities") or []:
        entity_id = str(entity.get("entity_id") or "").strip()
        if not entity_id:
            continue
        node = _scene_node(prefix="graph", layer=LAYER_GRAPH, artifact_type="entity", artifact_id=entity_id, item=entity)
        if node.id not in node_ids:
            nodes.append(node)
            node_ids.add(node.id)
            entity_graph_nodes.add(node.id)

    for relation in bundle.get("relations") or []:
        relation_id = str(relation.get("relation_id") or "").strip()
        src_entity_id = str(relation.get("src_entity_id") or "").strip()
        dst_entity_id = str(relation.get("dst_entity_id") or "").strip()
        if relation_id and relation_id:
            relation_node = _scene_node(
                prefix="graph",
                layer=LAYER_GRAPH,
                artifact_type="relation",
                artifact_id=relation_id,
                item=relation,
            )
            if relation_node.id not in node_ids:
                nodes.append(relation_node)
                node_ids.add(relation_node.id)
        if src_entity_id and dst_entity_id:
            src_node = _node_id("graph", "entity", src_entity_id)
            dst_node = _node_id("graph", "entity", dst_entity_id)
            edges.append(
                _scene_edge(
                    edge_type="relation",
                    layer=LAYER_GRAPH,
                    source=src_node,
                    target=dst_node,
                    label=str(relation.get("relation_type") or "").strip(),
                    strength=_float(relation.get("confidence"), 0.0),
                    metadata={"relation_id": relation_id},
                )
            )

    for pattern in patterns:
        pattern_id = str(pattern.get("pattern_id") or pattern.get("label") or "").strip()
        if not pattern_id:
            continue
        node = _scene_node(
            prefix="pattern",
            layer=LAYER_FRACTAL,
            artifact_type="pattern",
            artifact_id=pattern_id,
            item=pattern,
            projected=True,
            stored=False,
            emphasis=max(_float(pattern.get("confidence"), 0.0), 0.18),
        )
        if node.id not in node_ids:
            nodes.append(node)
            node_ids.add(node.id)
        for claim_id in pattern.get("support_claim_ids") or []:
            edges.append(
                _scene_edge(
                    edge_type="projection",
                    layer=LAYER_FRACTAL,
                    source=node.id,
                    target=_node_id("memory", "claim", str(claim_id)),
                    label=str(pattern.get("pattern_kind") or "").strip(),
                    strength=_float(pattern.get("confidence"), 0.0),
                )
            )
        for episode_id in pattern.get("support_episode_ids") or []:
            edges.append(
                _scene_edge(
                    edge_type="projection",
                    layer=LAYER_FRACTAL,
                    source=node.id,
                    target=_node_id("memory", "episode", str(episode_id)),
                    label=str(pattern.get("pattern_kind") or "").strip(),
                    strength=_float(pattern.get("confidence"), 0.0),
                )
            )
        for relation_id in pattern.get("support_relation_ids") or []:
            edges.append(
                _scene_edge(
                    edge_type="projection",
                    layer=LAYER_FRACTAL,
                    source=node.id,
                    target=_node_id("graph", "relation", str(relation_id)),
                    label=str(pattern.get("pattern_kind") or "").strip(),
                    strength=_float(pattern.get("confidence"), 0.0),
                )
            )

    for divergence in (bundle.get("recorded") or {}).get("divergences") or []:
        artifact_type = str(divergence.get("artifact_type") or "").strip()
        artifact_id = str(divergence.get("artifact_id") or "").strip()
        if not artifact_type or not artifact_id:
            continue
        node = _scene_node(
            prefix="divergence",
            layer=LAYER_ARCHIVE,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            item=divergence,
            divergence=True,
            emphasis=max(_float(divergence.get("influence_score"), 0.0), 0.16),
        )
        if node.id not in node_ids:
            nodes.append(node)
            node_ids.add(node.id)
        base_prefix = "memory" if artifact_type in {"claim", "episode"} else "graph"
        edges.append(
            _scene_edge(
                edge_type="divergence",
                layer=LAYER_ARCHIVE,
                source=node.id,
                target=_node_id(base_prefix, artifact_type, artifact_id),
                label="divergence",
                strength=max(_float(divergence.get("remember_score"), 0.0), 0.15),
            )
        )

    for artifact_type, item, layer in _bundle_top_items(bundle):
        artifact_id = str(
            item.get(f"{artifact_type}_id")
            or item.get("event_id")
            or item.get("entity_id")
            or item.get("relation_id")
            or item.get("claim_id")
            or item.get("episode_id")
            or ""
        ).strip()
        if not artifact_id:
            continue
        recall_node = _scene_node(
            prefix="recall",
            layer=LAYER_ACTIVE,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            item=item,
            emphasis=max(_float(item.get("confidence"), 0.0), 0.5),
        )
        if recall_node.id not in node_ids:
            nodes.append(recall_node)
            node_ids.add(recall_node.id)
        base_prefix = LAYER_ARCHIVE if artifact_type == "event" else ("graph" if artifact_type in {"entity", "relation"} else "memory")
        target_prefix = {
            LAYER_ARCHIVE: "archive",
            "graph": "graph",
            "memory": "memory",
        }[base_prefix]
        edges.append(
            _scene_edge(
                edge_type="recall",
                layer=LAYER_ACTIVE,
                source=recall_node.id,
                target=_node_id(target_prefix, artifact_type, artifact_id),
                label="active recall",
                strength=recall_node.emphasis,
            )
        )
        focus_node_ids.append(recall_node.id)
        inspectors.append(_inspector_summary(item, artifact_type=artifact_type, artifact_id=artifact_id, layer=layer))

    if query.strip():
        inspectors.insert(
            0,
            InspectorCard(
                title="Query",
                artifact_type="query",
                artifact_id="active",
                summary=query.strip(),
                layer=LAYER_ACTIVE,
                confidence=1.0,
                timestamp=None,
            ),
        )

    return SceneSnapshot(
        nodes=nodes,
        edges=edges,
        focus_node_ids=focus_node_ids,
        inspector_cards=inspectors[:8],
        archive_density=_archive_density(bundle),
        graph_summary=_graph_summary(bundle),
        divergence_summary=dict(bundle.get("divergence_summary") or (bundle.get("recorded") or {}).get("divergence_summary") or {}),
        meta={
            "layer_counts": dict(_layer_counts(nodes)),
            "query": query,
            "meta": dict(bundle.get("meta") or {}),
        },
    )


def _layer_counts(nodes: list[SceneNode]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for node in nodes:
        counts[node.layer] += 1
    return counts


def build_focus_scene(*, artifact_type: str, artifact_id: str, label: str, timeline: list[dict], graph: dict) -> SceneSnapshot:
    focus_node = SceneNode(
        id=_node_id("focus", artifact_type, artifact_id),
        layer=LAYER_ACTIVE,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        label=label,
        confidence=1.0,
        weight=1.0,
        emphasis=1.0,
    )
    nodes = [focus_node]
    edges: list[SceneEdge] = []
    inspectors = [
        InspectorCard(
            title=label,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            summary=f"Focused {artifact_type} inspector view",
            layer=LAYER_ACTIVE,
            confidence=1.0,
        )
    ]
    for event in timeline[:16]:
        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            continue
        node = _scene_node(prefix="archive", layer=LAYER_ARCHIVE, artifact_type="event", artifact_id=event_id, item=event)
        nodes.append(node)
        edges.append(
            _scene_edge(
                edge_type="supports",
                layer=LAYER_ARCHIVE,
                source=focus_node.id,
                target=node.id,
                label="supporting event",
                strength=max(_float(event.get("confidence"), 0.0), 0.15),
            )
        )
    for relation in graph.get("relations") or []:
        relation_id = str(relation.get("relation_id") or "").strip()
        if not relation_id:
            continue
        node = _scene_node(prefix="graph", layer=LAYER_GRAPH, artifact_type="relation", artifact_id=relation_id, item=relation)
        nodes.append(node)
        edges.append(
            _scene_edge(
                edge_type="relation",
                layer=LAYER_GRAPH,
                source=focus_node.id,
                target=node.id,
                label=str(relation.get("relation_type") or "").strip(),
                strength=_float(relation.get("confidence"), 0.0),
            )
        )
    return SceneSnapshot(
        nodes=nodes,
        edges=edges,
        focus_node_ids=[focus_node.id],
        inspector_cards=inspectors,
        archive_density=ArchiveDensitySummary(total_events=len(timeline), recorded_events=len(timeline)),
        graph_summary=GraphSummary(
            relation_count=len(graph.get("relations") or []),
            entity_count=1 if graph.get("entity") else 0,
            neighborhood_count=len(graph.get("relations") or []),
        ),
        divergence_summary={},
        meta={"artifact_type": artifact_type, "artifact_id": artifact_id},
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

