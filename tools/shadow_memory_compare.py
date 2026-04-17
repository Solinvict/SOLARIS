# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _item_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return str(value or "").strip()
    for key in (
        "canonical_claim",
        "title",
        "summary_text",
        "raw_text",
        "canonical_name",
        "label",
        "lease_key",
        "text",
    ):
        text = str(value.get(key) or "").strip()
        if text:
            return text
    return ""


def _extract_host_items(payload: dict) -> list[str]:
    texts: list[str] = []
    for key in ("artifacts", "facts", "claims", "episodes", "events", "items"):
        for item in list(payload.get(key) or []):
            text = _item_text(item)
            if text:
                texts.append(text)
    answer = str(payload.get("answer") or "").strip()
    if answer:
        texts.append(answer)
    return texts


def _relation_label(relation: dict) -> str:
    label = str(relation.get("label") or "").strip()
    if label:
        return label
    src_name = str((relation.get("src_entity") or {}).get("canonical_name") or relation.get("src") or "").strip()
    relation_type = str(
        relation.get("relation_type")
        or (relation.get("relation") or {}).get("relation_type")
        or relation.get("predicate")
        or ""
    ).strip()
    dst_name = str((relation.get("dst_entity") or {}).get("canonical_name") or relation.get("dst") or "").strip()
    return " ".join(part for part in (src_name, relation_type, dst_name) if part).strip()


def _extract_solaris_items(payload: dict) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    divergence_texts: list[str] = []
    for key in ("claims", "episodes", "events", "entities", "state_leases"):
        for item in list(payload.get(key) or []):
            text = _item_text(item)
            if text:
                texts.append(text)
    for relation in list(payload.get("relations") or []):
        label = _relation_label(relation)
        if label:
            texts.append(label)
    recorded = dict(payload.get("recorded") or {})
    for item in list(recorded.get("divergences") or []):
        text = _item_text(item)
        if not text and isinstance(item, dict):
            text = _relation_label(item)
        if text:
            divergence_texts.append(text)
    return texts, divergence_texts


def _mismatch_class(host_items: set[str], solaris_items: set[str]) -> str:
    if not host_items and not solaris_items:
        return "no_signal"
    if host_items == solaris_items:
        return "agreement"
    if host_items and solaris_items:
        host_only = host_items - solaris_items
        solaris_only = solaris_items - host_items
        if host_only and solaris_only:
            return "both_found_different_artifacts"
        if host_only:
            return "host_found_more_than_solaris"
        if solaris_only:
            return "solaris_found_more_than_host"
    if host_items:
        return "host_found_more_than_solaris"
    return "solaris_found_more_than_host"


def compare_payloads(host_payload: dict, solaris_payload: dict) -> dict:
    host_items = sorted(set(_extract_host_items(host_payload)))
    solaris_items, divergence_items = _extract_solaris_items(solaris_payload)
    solaris_items = sorted(set(solaris_items))
    divergence_items = sorted(set(divergence_items))

    host_set = set(host_items)
    solaris_set = set(solaris_items)

    return {
        "ok": True,
        "query": str(host_payload.get("query") or solaris_payload.get("query") or "").strip(),
        "mismatch_class": _mismatch_class(host_set, solaris_set),
        "overlap": sorted(host_set & solaris_set),
        "host_only": sorted(host_set - solaris_set),
        "solaris_only": sorted(solaris_set - host_set),
        "host_count": len(host_items),
        "solaris_count": len(solaris_items),
        "divergence_count": len(divergence_items),
        "divergences": divergence_items,
        "host_answer": str(host_payload.get("answer") or "").strip(),
        "solaris_meta": dict(solaris_payload.get("meta") or {}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare host-memory output with a Solaris query bundle in shadow mode.")
    parser.add_argument("--host-json", type=Path, required=True, help="Path to the host memory JSON payload.")
    parser.add_argument("--solaris-json", type=Path, required=True, help="Path to the Solaris query bundle JSON payload.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args(argv)

    host_payload = json.loads(args.host_json.read_text(encoding="utf-8"))
    solaris_payload = json.loads(args.solaris_json.read_text(encoding="utf-8"))
    result = compare_payloads(host_payload, solaris_payload)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Shadow comparison: {result['mismatch_class']}")
        print(f"- overlap: {len(result['overlap'])}")
        print(f"- host_only: {len(result['host_only'])}")
        print(f"- solaris_only: {len(result['solaris_only'])}")
        print(f"- divergences: {result['divergence_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
