# Solaris

Solaris is an archive-grounded editorial memory substrate for long-lived AI systems.

It archives broadly, derives structure cautiously, remembers selectively through editorial judgment, and retrieves with provenance. It is designed for builders who want memory that stays inspectable and honest instead of collapsing everything into fuzzy recall.

Status: `alpha` / `research preview`

License: `MPL-2.0`

## Why Solaris Exists

Most memory systems pick one of two bad tradeoffs:

- store everything and pretend it is all equally important
- compress aggressively and lose the record that would let you explain or correct yourself later

Solaris takes a different path:

- raw events remain the source of truth
- derived memory is editorial, not automatic
- current belief is separate from recorded history
- graph structure is stored
- higher-order patterns are projected as computed views, not stored as synthetic truth

## Core Ideas

- `archive != remembered != activated`
- remembering is a policy decision, not just a storage side effect
- every surfaced artifact should be explainable through provenance
- graph memory should be grounded in stored structure
- fractal or pattern memory should stay computed and confidence-marked
- divergence between archive and belief should be inspectable instead of hidden

## What Solaris Can Do

- ingest canonical `MemoryEvent` records
- derive claims, episodes, entities, relations, and scoped state
- run editorial review over derived memory
- query current belief and grounded archive together
- expose graph-aware retrieval through entities, relations, and timelines
- project recurring patterns without storing them as durable artifacts

## What Solaris Is Not

- not a generic vector-memory wrapper
- not an autonomous reasoning agent
- not a polished end-user product
- not a claim that "the model will figure memory out for you"

## Quickstart

Requirements:

- Python `3.12+`
- optional: Node.js for the standalone frontend

From the `solaris/` directory:

```powershell
python -m pip install -e .[dev]
```

Run the MCP server over stdio:

```powershell
python .\run_server.py --stdio
```

If console scripts are on your path, this works too:

```powershell
solaris-server --stdio
```

Run the standalone Solaris web API:

```powershell
python .\run_web.py
```

Run the detached frontend in development:

```powershell
cd .\frontend
npm install
npm run dev
```

Run the standalone backend and frontend together:

```powershell
.\run_standalone.ps1
```

## Docs

Start here:

- [Getting Started](./docs/getting_started.md)
- [Usage Guide](./docs/usage_guide.md)
- [Host Shadow Mode](./docs/host_shadow_mode.md)
- [Maturity And Limitations](./docs/maturity_and_limitations.md)
- [Open Source Release Checklist](./docs/open_source_release_checklist.md)
- [Architecture](./docs/architecture.md)
- [Event Schema](./docs/event_schema.md)
- [Query Contract](./docs/query_contract.md)

Deep design and proof docs:

- [Solaris](./docs/Solaris.md)
- [Archive-State Memory Model](./docs/archive_state_memory_model.md)
- [Fractal Memory Philosophy](./docs/fractal_memory_philosophy.md)
- [Proof](./docs/Proof.md)
- [Graph And Fractal Closeout](./docs/graph_and_fractal_closeout.md)

Evaluation and examples:

- [Retrieval Eval Guide](./docs/retrieval_eval_guide.md)
- [Host Runtime Mapping Example](./examples/host_runtime_mapping.md)
- [Host Shadow Adapter Example](./examples/host_shadow_adapter.py)
- [Host Backfill Export Example](./examples/host_backfill_export.json)
- [Sample Events](./examples/sample_events.jsonl)

## Validation

Run the core Solaris test suite:

```powershell
pytest
```

Run the retrieval eval harness:

```powershell
python .\run_retrieval_evals.py --json
```

Run the archive-state proof checks:

```powershell
python .\run_archive_state_model_checks.py --json
```

Compare host memory with Solaris in sidecar shadow mode:

```powershell
python .\tools\shadow_memory_compare.py `
  --host-json .\examples\shadow_compare_host.json `
  --solaris-json .\examples\shadow_compare_solaris.json `
  --json
```

Backfill a generic host export into a local Solaris database:

```powershell
python .\tools\backfill_host_export.py `
  --export .\examples\host_backfill_export.json `
  --json
```

CI is intentionally deferred for the first public `alpha` release while Solaris is still being extracted and stabilized as a standalone repository. For now, the expected validation path is local: `pytest` plus the committed eval and proof runners.

If you want a repeatable extraction and local release validation flow from the current workspace, use:

```powershell
python .\tools\extract_standalone_repo.py --dest <path-to-standalone-repo> --force
python .\tools\validate_public_repo.py --repo <path-to-standalone-repo>
```

## Repository Layout

- `src/solaris/` contains the server, services, retrieval, derivation, editorial, and storage layers
- `mcp_tools/` exposes the MCP tool surface
- `frontend/` contains the standalone Solaris browser app
- `migrations/` contains inspectable SQLite schema migrations
- `policies/` contains editable editorial policy profiles
- `evals/` contains committed evaluation corpora
- `tests/` contains Solaris-focused tests
- `tools/` contains extraction, validation, backfill, and shadow-comparison helpers
- `docs/` contains design, proof, roadmap, and usage documentation

## Host Integration Note

Solaris is intentionally host-runtime agnostic. It does not import host application modules; integrations are done through MCP and the standalone web surface.

Hosts that are not ready to hand authority to Solaris can still adopt it in **sidecar shadow mode** first: ingest in parallel, compare recall outputs, inspect divergence, and promote authority later.

The standalone frontend ships in `v0.1` as an optional alpha surface. The primary interface remains the MCP server and related local validation tools.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## Project Policies

- [Code Of Conduct](./CODE_OF_CONDUCT.md)
- [Security Policy](./SECURITY.md)
- [License](./LICENSE)
