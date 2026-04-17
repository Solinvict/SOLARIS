# Usage Guide

Solaris has a simple outer loop:

1. open or choose a scope/session
2. ingest canonical events
3. run editorial review
4. query current belief and recorded history
5. inspect graph structure or project patterns when needed

## Core Flow

### 1. Ingest

Use `solaris.ingest_events` to append canonical `MemoryEvent` records to the archive.

Events are the source of truth. Derived artifacts come later.

See:

- [Event Schema](./event_schema.md)
- [Sample Events](../examples/sample_events.jsonl)

### 2. Review

Use `solaris.run_editorial_review` to let Solaris decide which derived artifacts should stay candidate, become remembered, reinforce, or retire.

This is the step that keeps Solaris from behaving like flat accumulation.

Related tools:

- `solaris.get_review_queue`
- `solaris.reconsider`
- `solaris.apply_editorial_decision`

### 3. Query

Use `solaris.query` or `solaris.recall` to retrieve a scoped bundle of:

- current belief
- supporting archive material
- provenance
- divergence between archive and current belief

See:

- [Query Contract](./query_contract.md)

### 4. Inspect Structure

Use these when the question is graph-shaped rather than just textual:

- `solaris.entity`
- `solaris.timeline`
- `solaris.explain`
- `solaris.explain_memory`

These help answer questions like:

- what depends on this
- what uses this
- what blocked this
- what is the supporting chain for this claim

### 5. Project Patterns

Use `solaris.project_patterns` when you want computed higher-order structure such as:

- recurring claim clusters
- recurring episode motifs
- relation clusters
- temporal recurrence

These are computed views, not durable stored memory.

## Main MCP Tool Surface

Session and state:

- `solaris.open_session`
- `solaris.close_session`
- `solaris.upsert_state`

Archive and review:

- `solaris.ingest_events`
- `solaris.get_review_queue`
- `solaris.run_editorial_review`
- `solaris.reconsider`
- `solaris.apply_editorial_decision`

Query and explanation:

- `solaris.query`
- `solaris.recall`
- `solaris.entity`
- `solaris.timeline`
- `solaris.explain`
- `solaris.explain_memory`
- `solaris.project_patterns`

## Mental Model

Think of Solaris as five layers:

- archive
- derivation
- editorial review
- retrieval
- projection

The important distinction is that Solaris does not treat them as the same thing.

- archived events are raw truth
- remembered artifacts are editorially active memory
- projected patterns are computed views over the stored substrate

## Where To Go Deeper

- [Architecture](./architecture.md)
- [Editorial Model](./editorial_model.md)
- [Archive-State Memory Model](./archive_state_memory_model.md)
- [Fractal Memory Philosophy](./fractal_memory_philosophy.md)
- [Retrieval Eval Guide](./retrieval_eval_guide.md)
