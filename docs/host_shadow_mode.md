# SPDX-License-Identifier: MPL-2.0

# Host Shadow Mode

Solaris does not need to become a host runtime's primary memory on day one.

The safest adoption pattern is **shadow mode**:

- the host keeps using its current memory stack
- Solaris ingests the same committed turns in parallel
- recall questions can be queried against Solaris side-by-side
- the host compares what it would have surfaced against what Solaris surfaces
- operators decide when Solaris is strong enough to move from sidecar to authority

This is the public, host-agnostic version of the rollout pattern Solaris was first proven under.

## Why Start In Shadow Mode

Shadow mode lowers adoption risk.

It lets a host runtime:

- build archive and editorial state without breaking the current product
- compare present-memory quality before changing authority
- inspect divergence instead of hiding it
- test graph and pattern retrieval on real traffic
- backfill historical memory into Solaris without forcing a cutover

## Recommended Rollout

### 1. Ingest-only shadow

The host continues using its current memory system.

Solaris only:

- opens runtime / interaction sessions
- ingests one canonical event per committed turn
- runs editorial review at reasonable boundaries

The goal is to accumulate real memory before trusting Solaris answers.

### 2. Side-by-side recall

For memory-shaped questions, the host queries both:

- current host memory
- Solaris query bundle

Then compare them.

Use [shadow_memory_compare.py](../tools/shadow_memory_compare.py) for a lightweight comparison report.

### 3. Selective authority

Once Solaris is reliably stronger for a category, promote it selectively.

Good early candidates:

- project continuity
- graph-shaped recall
- divergence-sensitive recall
- historical archive lookups

Common categories to leave shadow-backed longer:

- host-specific notes / tasks
- narrowly product-shaped personal profile surfaces

### 4. Primary memory

Only after side-by-side comparisons feel stable should Solaris become primary memory.

At that point, the original host memory can remain as:

- comparison instrumentation
- rollback safety
- migration residue

## Host Responsibilities

A host runtime using Solaris in shadow mode should:

- open runtime and interaction sessions
- ingest canonical `MemoryEvent` records
- preserve the host's own memory behavior while Solaris is sidecar
- query Solaris on recall-shaped turns
- compare host output with Solaris output
- run editorial review at wake / boundary moments

Historical backfill should use Solaris `import` sessions so old traffic stays distinct from live `runtime` and `interaction` sessions.

## Minimal Comparison Flow

Create one JSON payload from the host and one from Solaris, then compare them:

```powershell
python .\tools\shadow_memory_compare.py `
  --host-json .\examples\shadow_compare_host.json `
  --solaris-json .\examples\shadow_compare_solaris.json `
  --json
```

The comparison runner emits:

- overlap
- host-only items
- Solaris-only items
- a mismatch class:
  - `agreement`
  - `host_found_more_than_solaris`
  - `solaris_found_more_than_host`
  - `both_found_different_artifacts`
  - `no_signal`

## Historical Backfill

To seed Solaris from a host export without a hard cutover, use:

```powershell
python .\tools\backfill_host_export.py `
  --export .\examples\host_backfill_export.json `
  --json
```

The public backfill tool expects a generic export file with:

- `scope`
- `sessions`
- `events`
- optional `close_sessions`
- optional `reviews`

See [host_backfill_export.json](../examples/host_backfill_export.json) for a minimal example.

## Related Files

- [Host Adapter Notes](./host_adapter_notes.md)
- [Host Runtime Mapping Example](../examples/host_runtime_mapping.md)
- [Host Shadow Adapter Example](../examples/host_shadow_adapter.py)
- [shadow_memory_compare.py](../tools/shadow_memory_compare.py)
- [backfill_host_export.py](../tools/backfill_host_export.py)
