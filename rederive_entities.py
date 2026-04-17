# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solaris.config import Settings  # noqa: E402
from solaris.derive.entities import derive_entities  # noqa: E402
from solaris.models.event import MemoryEvent  # noqa: E402
from solaris.storage.db import Database  # noqa: E402
from solaris.storage.db import json_loads  # noqa: E402
from solaris.storage.migrate import apply_migrations  # noqa: E402
from solaris.storage.repos.entities import EntitiesRepo  # noqa: E402


def _event_from_row(row) -> MemoryEvent:
    return MemoryEvent.model_validate(
        {
            "event_id": row["event_id"],
            "schema_version": row["schema_version"],
            "timestamp": row["timestamp"],
            "scope": {
                "tenant": row["tenant"],
                "namespace": row["namespace"],
                "workspace": row["workspace"],
                "project": row["project"],
            },
            "session_id": row["session_id"],
            "source_app": row["source_app"],
            "source_module": row["source_module"],
            "actor": row["actor"],
            "kind": row["kind"],
            "raw_text": row["raw_text"],
            "normalized_text": row["normalized_text"],
            "structured_payload": json_loads(row["structured_payload_json"], {}),
            "hints": json_loads(row["hints_json"], {}),
            "scores": json_loads(row["scores_json"], {}),
            "idempotency_key": row["idempotency_key"],
        }
    )


def run(limit: int | None = None) -> dict:
    settings = Settings.from_env()
    db = Database(settings.db_path)
    apply_migrations(db, settings.project_root / "migrations")
    entities_repo = EntitiesRepo()

    with db.transaction() as connection:
        query = "SELECT * FROM events ORDER BY timestamp ASC"
        params: tuple[object, ...] = ()
        if limit is not None and limit > 0:
            query += " LIMIT ?"
            params = (int(limit),)
        rows = connection.execute(query, params).fetchall()

        processed = 0
        entity_links = 0
        unique_entities: set[str] = set()
        for row in rows:
            event = _event_from_row(row)
            derived = derive_entities(event)
            for entity in derived:
                record = entities_repo.upsert(
                    connection,
                    scope=event.scope,
                    canonical_name=entity["name"],
                    entity_type=entity.get("type") or "concept",
                    aliases=entity.get("aliases") or [],
                    seen_at=event.timestamp,
                )
                entities_repo.link_event(connection, event_id=event.event_id or row["event_id"], entity_id=record["entity_id"])
                unique_entities.add(str(record["entity_id"]))
                entity_links += 1
            processed += 1

    return {
        "ok": True,
        "processed_events": processed,
        "entity_links_attempted": entity_links,
        "unique_entities_touched": len(unique_entities),
        "db_path": str(settings.db_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay entity derivation over archived Solaris events.")
    parser.add_argument("--limit", type=int, default=0, help="Optional maximum number of events to process.")
    args = parser.parse_args(argv)
    result = run(limit=args.limit or None)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
