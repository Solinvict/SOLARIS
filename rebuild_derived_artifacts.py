# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solaris.clock import Clock  # noqa: E402
from solaris.config import Settings  # noqa: E402
from solaris.derive import DerivationPipeline  # noqa: E402
from solaris.editorial import EditorialEngine, PolicyRegistry  # noqa: E402
from solaris.models.event import MemoryEvent  # noqa: E402
from solaris.models.scope import ScopeRef  # noqa: E402
from solaris.services.review import ReviewService  # noqa: E402
from solaris.storage import Database  # noqa: E402
from solaris.storage.db import json_loads  # noqa: E402
from solaris.storage.migrate import apply_migrations  # noqa: E402
from solaris.storage.repos import (  # noqa: E402
    ClaimsRepo,
    EditorialRepo,
    EntitiesRepo,
    EpisodesRepo,
    EventsRepo,
    EvidenceRepo,
    RelationsRepo,
    SessionsRepo,
    StateLeasesRepo,
)


DERIVED_TABLES = (
    "event_entities",
    "artifact_evidence",
    "episode_events",
    "review_queue",
    "editorial_decisions",
    "artifact_editorial_state",
    "relations",
    "claims",
    "episodes",
    "entities",
)


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


def _build_components(settings: Settings):
    db = Database(settings.db_path)
    apply_migrations(db, settings.project_root / "migrations")
    clock = Clock()

    sessions_repo = SessionsRepo(clock)
    events_repo = EventsRepo(clock, fts_enabled=settings.fts_enabled)
    entities_repo = EntitiesRepo()
    relations_repo = RelationsRepo()
    claims_repo = ClaimsRepo()
    episodes_repo = EpisodesRepo()
    state_repo = StateLeasesRepo(clock)
    evidence_repo = EvidenceRepo()
    editorial_repo = EditorialRepo(clock)

    pipeline = DerivationPipeline(
        sessions_repo=sessions_repo,
        entities_repo=entities_repo,
        relations_repo=relations_repo,
        claims_repo=claims_repo,
        episodes_repo=episodes_repo,
        events_repo=events_repo,
        state_repo=state_repo,
        evidence_repo=evidence_repo,
        editorial_repo=editorial_repo,
    )
    policy_registry = PolicyRegistry(settings.policies_dir)
    engine = EditorialEngine(
        policy_registry=policy_registry,
        editorial_repo=editorial_repo,
        evidence_repo=evidence_repo,
        events_repo=events_repo,
        claims_repo=claims_repo,
        relations_repo=relations_repo,
        episodes_repo=episodes_repo,
    )
    review = ReviewService(db, editorial_repo, engine)
    return {
        "db": db,
        "sessions_repo": sessions_repo,
        "events_repo": events_repo,
        "entities_repo": entities_repo,
        "relations_repo": relations_repo,
        "claims_repo": claims_repo,
        "episodes_repo": episodes_repo,
        "state_repo": state_repo,
        "evidence_repo": evidence_repo,
        "editorial_repo": editorial_repo,
        "pipeline": pipeline,
        "review": review,
    }


def _clear_derived_tables(connection) -> dict[str, int]:
    deleted: dict[str, int] = {}
    for table in DERIVED_TABLES:
        rowcount = connection.execute(f"DELETE FROM {table}").rowcount
        deleted[table] = int(rowcount or 0)
    return deleted


def run(*, review_limit: int = 5000) -> dict:
    settings = Settings.from_env()
    components = _build_components(settings)
    db = components["db"]
    pipeline = components["pipeline"]
    episodes_repo = components["episodes_repo"]
    review = components["review"]

    with db.transaction() as connection:
        deleted = _clear_derived_tables(connection)
        rows = connection.execute("SELECT * FROM events ORDER BY timestamp ASC, event_id ASC").fetchall()
        processed = 0
        for row in rows:
            event = _event_from_row(row)
            pipeline.run(connection, event=event, event_id=row["event_id"])
            processed += 1

        session_rows = connection.execute(
            "SELECT session_id, closed_at FROM sessions WHERE closed_at IS NOT NULL ORDER BY closed_at ASC"
        ).fetchall()
        episodes_closed = 0
        for row in session_rows:
            episodes_closed += episodes_repo.close_by_session(
                connection,
                session_id=str(row["session_id"]),
                closed_at=str(row["closed_at"]),
            )

    scope_rows = []
    with db.transaction() as connection:
        scope_rows = connection.execute(
            "SELECT DISTINCT tenant, namespace, workspace, project FROM events ORDER BY tenant, namespace, workspace, project"
        ).fetchall()

    review_runs = []
    for row in scope_rows:
        scope = ScopeRef(
            tenant=str(row["tenant"]),
            namespace=str(row["namespace"]),
            workspace=str(row["workspace"] or ""),
            project=str(row["project"] or ""),
        )
        result = review.run_review(scope, None, settings.default_policy_profile, review_limit, "boundary")
        review_runs.append({"scope": scope.key(), **result})

    with db.transaction() as connection:
        summary = {
            "events": int(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]),
            "entities": int(connection.execute("SELECT COUNT(*) FROM entities").fetchone()[0]),
            "relations": int(connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]),
            "claims": int(connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0]),
            "episodes": int(connection.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]),
            "editorial_states": int(connection.execute("SELECT COUNT(*) FROM artifact_editorial_state").fetchone()[0]),
            "editorial_decisions": int(connection.execute("SELECT COUNT(*) FROM editorial_decisions").fetchone()[0]),
            "review_queue_pending": int(connection.execute("SELECT COUNT(*) FROM review_queue WHERE status = 'pending'").fetchone()[0]),
        }

    return {
        "ok": True,
        "db_path": str(settings.db_path),
        "deleted": deleted,
        "processed_events": processed,
        "episodes_closed": episodes_closed,
        "review_runs": review_runs,
        "summary": summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild Solaris derived artifacts from the immutable events archive.")
    parser.add_argument("--review-limit", type=int, default=5000, help="Maximum number of review items to process per scope.")
    args = parser.parse_args(argv)
    result = run(review_limit=max(1, int(args.review_limit)))
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
