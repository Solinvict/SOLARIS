"""Supported host-facing contract for exact scoped Solaris memory."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
from pathlib import Path
import uuid

from solaris.clock import Clock
from solaris.models.scope import ScopeRef
from solaris.services.history import OriginalHistoryService
from solaris.storage import Database
from solaris.storage.migrate import apply_migrations, package_migrations_path
from solaris.storage.repos import EventsRepo


_CAPABILITIES = frozenset(
    {
        "artifact_exact_readback",
        "idempotent_publication",
        "original_history_v1",
        "scope_isolation",
        "scoped_retrieval",
    }
)


@dataclass(frozen=True)
class StoreIdentity:
    store_id: str
    schema_version: int
    path_sha256: str


@dataclass(frozen=True)
class CapabilitySet:
    names: frozenset[str]


@dataclass(frozen=True)
class PublishReceipt:
    event_id: str
    event_sha256: str
    artifact_sha256: tuple[str, ...]
    duplicate: bool


class SolarisHost:
    """Narrow exact-history API for trusted host applications.

    This surface intentionally excludes Editorial, derived claims and broad
    retrieval. Retention through this API grants no scientific authority.
    """

    def __init__(self, db: Database, history: OriginalHistoryService, identity: StoreIdentity):
        self._db = db
        self._history = history
        self._identity = identity

    @classmethod
    def open(cls, path: Path) -> "SolarisHost":
        resolved = Path(path).expanduser().resolve()
        db = Database(resolved)
        apply_migrations(db, package_migrations_path())
        with db.transaction() as connection:
            row = connection.execute(
                "SELECT value FROM host_metadata WHERE key='store_id'"
            ).fetchone()
            store_id = str(row[0]) if row else str(uuid.uuid4())
            if row is None:
                connection.execute(
                    "INSERT INTO host_metadata(key, value) VALUES ('store_id', ?)",
                    (store_id,),
                )
            names = [
                str(item[0])
                for item in connection.execute(
                    "SELECT filename FROM schema_migrations ORDER BY filename"
                ).fetchall()
            ]
        schema_version = max(int(name.split("_", 1)[0]) for name in names)
        identity = StoreIdentity(
            store_id=store_id,
            schema_version=schema_version,
            path_sha256=hashlib.sha256(str(resolved).encode("utf-8")).hexdigest(),
        )
        history = OriginalHistoryService(db, EventsRepo(Clock(), fts_enabled=False), None)
        return cls(db, history, identity)

    def identity(self) -> StoreIdentity:
        return self._identity

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(names=_CAPABILITIES)

    def publish(
        self,
        scope: ScopeRef,
        envelope: dict,
        artifacts: Mapping[str, bytes],
    ) -> PublishReceipt:
        result = self._history.ingest(scope, envelope, artifacts)
        references = tuple(str(item["sha256"]) for item in envelope.get("artifacts", ()))
        return PublishReceipt(
            event_id=str(result["event_id"]),
            event_sha256=str(envelope["event_sha256"]),
            artifact_sha256=references,
            duplicate=bool(result["duplicate"]),
        )

    def read(self, scope: ScopeRef, event_id: str) -> dict | None:
        return self._history.read(scope, event_id)

    def retrieve(self, scope: ScopeRef, investigation_id: str) -> tuple[dict, ...]:
        return tuple(self._history.page(scope, investigation_id))

    def read_artifact(self, scope: ScopeRef, sha256: str) -> bytes | None:
        return self._history.artifact(scope, sha256)


__all__ = [
    "CapabilitySet",
    "PublishReceipt",
    "SolarisHost",
    "StoreIdentity",
]
