# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from solaris.models.event import IngestEventsResult


class IngestService:
    def __init__(self, db, events_repo, pipeline):
        self.db = db
        self.events_repo = events_repo
        self.pipeline = pipeline

    def ingest_events(self, req):
        accepted = 0
        duplicates = 0
        event_ids: list[str] = []
        derived_summary = {"entities": 0, "relations": 0, "claims": 0, "episodes": 0, "state_leases": 0}
        with self.db.transaction() as connection:
            for event in req.events:
                event_id, inserted = self.events_repo.insert(connection, event)
                event_ids.append(event_id)
                if not inserted:
                    duplicates += 1
                    continue
                accepted += 1
                derived = self.pipeline.run(connection, event=event, event_id=event_id)
                for key in derived_summary:
                    derived_summary[key] += len(derived.get(key, []))
        return IngestEventsResult(
            ok=True,
            accepted=accepted,
            duplicates=duplicates,
            event_ids=event_ids,
            derived=derived_summary,
        )
