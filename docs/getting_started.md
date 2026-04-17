# Getting Started

This guide gets Solaris running locally as an MCP server or standalone web surface.

## Requirements

- Python `3.12+`
- optional: Node.js for the standalone frontend

## Install

From the `solaris/` directory:

```powershell
python -m pip install -e .[dev]
```

That installs:

- the `solaris` Python package from `src/`
- development dependencies such as `pytest`
- console scripts like `solaris-server` and `solaris-web`

## Run The MCP Server

Start the stdio MCP server:

```powershell
python .\run_server.py --stdio
```

Alternative if console scripts are available:

```powershell
solaris-server --stdio
```

This is the mode you want when Solaris is being used as a memory substrate by another agent or runtime.

## Run The Standalone Web Surface

Start the Solaris web API:

```powershell
python .\run_web.py
```

Or:

```powershell
solaris-web
```

## Run The Frontend

The standalone frontend ships in `v0.1` as an optional alpha surface. The MCP server remains the primary interface.

From `solaris/frontend/`:

```powershell
npm install
npm run dev
```

If you want the standalone backend and frontend together, use:

```powershell
.\run_standalone.ps1
```

## Validate The Install

Run the test suite:

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

## First Files To Read

- [README](../README.md)
- [Usage Guide](./usage_guide.md)
- [Architecture](./architecture.md)
- [Event Schema](./event_schema.md)
- [Query Contract](./query_contract.md)

If you want to see how a host system can map its lifecycle into Solaris, read:

- [Host Runtime Mapping Example](../examples/host_runtime_mapping.md)

If you want to see the design claim Solaris is making, read:

- [Solaris](./Solaris.md)
- [Proof](./Proof.md)
