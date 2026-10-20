"""Scoped original history and artifact reads, independent of memory derivation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any
import zlib

from solaris.models.event import MemoryEvent
from solaris.models.scope import ScopeRef
from solaris.storage.repos.events import EventsRepo


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def decode(value: bytes | str) -> dict:
    raw = zlib.decompress(value).decode("utf-8") if isinstance(value, bytes) else value
    event = json.loads(raw)
    unsigned = {key: item for key, item in event.items() if key != "event_sha256"}
    if digest(unsigned) != event.get("event_sha256"):
        raise ValueError("Original event digest mismatch")
    return event


class OriginalHistoryService:
    """Store exact AEON originals without granting scientific authority."""

    def __init__(self, db, events_repo: EventsRepo, pipeline):
        self.db = db
        self.events_repo = EventsRepo(events_repo.clock, fts_enabled=False)
        self.pipeline = pipeline

    def ingest(
        self,
        scope: ScopeRef,
        envelope: dict,
        artifacts: Mapping[str, bytes],
    ) -> dict:
        event = dict(envelope)
        claimed_digest = event.pop("event_sha256", None)
        if (
            event.get("schema") != "aeon-original-history/v1"
            or digest(event) != claimed_digest
            or event.get("scope_key") != scope.key()
        ):
            raise ValueError("Original history binding mismatch")
        if not isinstance(event.get("sequence"), int) or event["sequence"] < 1:
            raise ValueError("Invalid original sequence")

        with self.db.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM original_history WHERE event_id=?",
                (event["event_id"],),
            ).fetchone()
            if existing:
                if decode(existing["envelope_json"]) != envelope:
                    raise ValueError("Original history identity conflict")
                return {"event_id": event["event_id"], "duplicate": True}

            previous = connection.execute(
                """
                SELECT event_id, sequence
                FROM original_history
                WHERE scope_key=? AND investigation_id=?
                ORDER BY sequence DESC
                LIMIT 1
                """,
                (scope.key(), event["investigation_id"]),
            ).fetchone()
            self._require_contiguous(event, previous)

            for reference in event["artifacts"]:
                raw = artifacts.get(reference["sha256"])
                if (
                    raw is None
                    or hashlib.sha256(raw).hexdigest() != reference["sha256"]
                    or len(raw) != reference["size"]
                ):
                    raise ValueError("Original artifact unavailable or changed")
                connection.execute(
                    """
                    INSERT OR IGNORE INTO original_artifacts(sha256, content, codec)
                    VALUES (?, ?, ?)
                    """,
                    (reference["sha256"], zlib.compress(raw), "deflate-v1"),
                )

            original = MemoryEvent(
                event_id=event["event_id"],
                timestamp=event["occurred_at"],
                scope=scope,
                source_app="aeon-original-history",
                source_module="native",
                actor=event["actor"],
                kind="investigation_original",
                raw_text=(
                    f"Original {event['kind']} by {event['actor']} in "
                    f"{event['investigation_id']}, sequence {event['sequence']}"
                ),
                structured_payload={
                    "schema": "original-history-reference/v1",
                    "event_id": event["event_id"],
                    "event_sha256": claimed_digest,
                },
                idempotency_key=event["event_id"],
            )
            identity, inserted = self.events_repo.insert(connection, original)
            if not inserted or identity != event["event_id"]:
                raise ValueError("Original history event collision")

            connection.execute(
                "INSERT INTO original_history VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event["event_id"],
                    scope.key(),
                    event["investigation_id"],
                    event["sequence"],
                    zlib.compress(canonical(envelope).encode("utf-8")),
                    claimed_digest,
                ),
            )
            connection.executemany(
                "INSERT OR IGNORE INTO original_artifact_links VALUES (?, ?)",
                [(event["event_id"], reference["sha256"]) for reference in event["artifacts"]],
            )
        return {"event_id": event["event_id"], "duplicate": False}

    @staticmethod
    def _require_contiguous(event: dict, previous) -> None:
        if previous is None:
            if event["sequence"] != 1 or event.get("previous_id") is not None:
                raise ValueError(
                    "Original history sequence continuity requires sequence 1 with no previous event"
                )
            return
        if event["sequence"] != previous["sequence"] + 1:
            raise ValueError("Original history sequence continuity gap")
        if event.get("previous_id") != previous["event_id"]:
            raise ValueError("Original history previous event binding mismatch")

    def read(self, scope: ScopeRef, event_id: str) -> dict | None:
        with self.db.transaction() as connection:
            row = connection.execute(
                "SELECT envelope_json FROM original_history WHERE scope_key=? AND event_id=?",
                (scope.key(), event_id),
            ).fetchone()
            return decode(row[0]) if row else None

    def page(
        self,
        scope: ScopeRef,
        investigation_id: str,
        *,
        after: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        if not 1 <= limit <= 1000:
            raise ValueError("History page size out of range")
        with self.db.transaction() as connection:
            rows = connection.execute(
                """
                SELECT envelope_json
                FROM original_history
                WHERE scope_key=? AND investigation_id=? AND sequence>?
                ORDER BY sequence
                LIMIT ?
                """,
                (scope.key(), investigation_id, after, limit),
            )
            return [decode(row[0]) for row in rows]

    def artifact(self, scope: ScopeRef, sha256: str) -> bytes | None:
        with self.db.transaction() as connection:
            row = connection.execute(
                """
                SELECT a.content, a.codec
                FROM original_artifacts a
                JOIN original_artifact_links l ON l.sha256=a.sha256
                JOIN original_history h ON h.event_id=l.event_id
                WHERE h.scope_key=? AND a.sha256=?
                LIMIT 1
                """,
                (scope.key(), sha256),
            ).fetchone()
            if not row:
                return None
            raw = zlib.decompress(row[0]) if row["codec"] == "deflate-v1" else bytes(row[0])
            if hashlib.sha256(raw).hexdigest() != sha256:
                raise ValueError("Original artifact corrupted")
            return raw

    def export(self, scope: ScopeRef, investigation_id: str) -> dict:
        events: list[dict] = []
        after = 0
        while True:
            current_page = self.page(scope, investigation_id, after=after)
            if not current_page:
                break
            events.extend(current_page)
            after = current_page[-1]["sequence"]
        event_ids = {event["event_id"] for event in events}
        return {
            "investigation_id": investigation_id,
            "scope_key": scope.key(),
            "events": events,
            "unresolved_parents": [
                event["parent_id"]
                for event in events
                if event["parent_id"] and event["parent_id"] not in event_ids
            ],
            "retention_is_scientific_eligibility": False,
        }

    def derive(self, scope: ScopeRef, event_id: str) -> dict:
        """Optionally retry derivation; failure cannot roll back the original."""

        event = self.read(scope, event_id)
        if event is None:
            raise ValueError("Original not found")
        try:
            with self.db.transaction() as connection:
                original = self.events_repo.get(connection, event_id)
                material = MemoryEvent(
                    event_id=event_id,
                    timestamp=original["timestamp"],
                    scope=scope,
                    source_app=original["source_app"],
                    actor=original["actor"],
                    kind=original["kind"],
                    raw_text=canonical(event["payload"]),
                    structured_payload=event,
                    idempotency_key=event_id,
                )
                self.pipeline.run(connection, event=material, event_id=event_id)
            status, error = "succeeded", None
        except Exception as exc:
            status, error = "failed", str(exc)
        with self.db.transaction() as connection:
            connection.execute(
                "INSERT INTO original_projection_attempts(event_id, status, error) VALUES (?, ?, ?)",
                (event_id, status, error),
            )
        return {"status": status, "error": error}
