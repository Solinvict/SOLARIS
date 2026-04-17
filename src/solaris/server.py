# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from solaris.clock import Clock
from solaris.config import Settings
from solaris.derive import DerivationPipeline
from solaris.editorial import EditorialEngine, NullEditorialAdjudicator, PolicyRegistry
from solaris.editorial.model_adjudicator import OpenAICompatibleAdjudicator
from solaris.logging import configure_logging
from solaris.mcp_tools import (
    register_editorial_tools,
    register_entity_tools,
    register_explain_tools,
    register_ingest_tools,
    register_pattern_tools,
    register_query_tools,
    register_session_tools,
    register_state_tools,
    register_timeline_tools,
)
from solaris.services import EntityService, ExplainService, IngestService, PatternProjectionService, QueryService, ReviewService, SessionService, TimelineService
from solaris.storage import Database
from solaris.storage.migrate import apply_migrations
from solaris.storage.repos import (
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


def _build_adjudicator(settings: Settings):
    provider = str(settings.adjudication_provider or "off").strip().casefold()
    model = str(settings.adjudication_model or "").strip()
    if provider in {"", "off", "none"} or not model:
        return NullEditorialAdjudicator()
    if provider == "openai_compatible":
        return OpenAICompatibleAdjudicator(
            model=model,
            base_url=settings.adjudication_base_url,
            api_key=settings.adjudication_api_key,
            timeout_seconds=settings.adjudication_timeout_seconds,
            prompt_version=settings.adjudication_prompt_version,
        )
    return NullEditorialAdjudicator()


def build_services(settings: Settings) -> dict:
    configure_logging(settings.log_level)
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
        adjudicator=_build_adjudicator(settings),
    )

    services = {
        "db": db,
        "events_repo": events_repo,
        "entities_repo": entities_repo,
        "relations_repo": relations_repo,
        "claims_repo": claims_repo,
        "episodes_repo": episodes_repo,
        "evidence_repo": evidence_repo,
        "editorial_repo": editorial_repo,
        "state_repo": state_repo,
        "sessions": SessionService(db, sessions_repo, episodes_repo),
        "ingest": IngestService(db, events_repo, pipeline),
        "review": ReviewService(db, editorial_repo, engine),
        "query": QueryService(
            db,
            sessions_repo,
            events_repo,
            entities_repo,
            relations_repo,
            claims_repo,
            episodes_repo,
            state_repo,
            editorial_repo,
            evidence_repo,
            divergence_weight_threshold=settings.divergence_weight_threshold,
        ),
        "patterns": PatternProjectionService(
            db,
            claims_repo,
            episodes_repo,
            relations_repo,
            entities_repo,
            editorial_repo,
            evidence_repo,
            events_repo,
        ),
        "entity": EntityService(db, entities_repo, relations_repo, editorial_repo, evidence_repo),
        "timeline": TimelineService(
            db,
            events_repo,
            episodes_repo,
            claims_repo,
            relations_repo,
            entities_repo,
            editorial_repo,
            evidence_repo,
        ),
        "explain": ExplainService(db, claims_repo, relations_repo, episodes_repo, editorial_repo, evidence_repo, events_repo),
    }
    return services


def build_mcp(settings: Settings) -> FastMCP:
    services = build_services(settings)
    mcp = FastMCP(
        name="Solaris",
        instructions="Standalone memory substrate MCP server with scoped archive, derivation, editorial review, and explainable retrieval.",
        log_level=settings.log_level,
    )
    register_session_tools(mcp, services)
    register_ingest_tools(mcp, services)
    register_state_tools(mcp, services)
    register_query_tools(mcp, services)
    register_pattern_tools(mcp, services)
    register_entity_tools(mcp, services)
    register_timeline_tools(mcp, services)
    register_explain_tools(mcp, services)
    register_editorial_tools(mcp, services)
    return mcp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Solaris MCP server")
    parser.add_argument("--stdio", action="store_true", help="Run using stdio transport")
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    mcp = build_mcp(settings)
    transport = "stdio" if args.stdio else "stdio"
    mcp.run(transport=transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
