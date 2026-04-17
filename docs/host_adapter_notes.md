# Host Adapter Notes

A host runtime using Solaris should:

- open runtime and interaction sessions
- ingest one canonical event per committed turn
- start in sidecar shadow mode if immediate cutover would be risky
- map work session, planner, and codebase continuity to state leases
- run editorial review at wake and runtime boundaries

In a larger monorepo workspace, a host runtime may launch Solaris through a local Python entrypoint such as `solaris/run_server.py` so the server can add `solaris/src` to `sys.path` explicitly.

Historical backfill uses Solaris `import` sessions so legacy traffic stays distinct from live `runtime` and `interaction` sessions. The public repo now includes:

- [Host Shadow Mode](./host_shadow_mode.md)
- [Host Shadow Adapter Example](../examples/host_shadow_adapter.py)
- [shadow_memory_compare.py](../tools/shadow_memory_compare.py)
- [backfill_host_export.py](../tools/backfill_host_export.py)
