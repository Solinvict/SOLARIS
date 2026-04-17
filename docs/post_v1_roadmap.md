# Solaris Post-V1 Roadmap

Status: next-phase roadmap

Follow-up:
- [Graph And Fractal Closeout](./graph_and_fractal_closeout.md)

## Summary

Solaris V1 is complete enough to stop treating the project as unfinished substrate work.

The major loop is now real:

```text
archive -> derive -> review -> retrieve
```

The next phase is different in character.

V1 built an honest memory substrate.
Post-V1 should make that substrate structurally intelligent.

The next work naturally falls into three tracks:
- graph maturation
- fractal / meta-pattern projection
- deferred realism polish

## Track 1: Graph Maturation

### Goal

Make the stored graph more meaningful, more traversable, and more retrieval-useful.

### Why

Right now Solaris has graph-capable structure:
- entities
- relations
- claims
- episodes
- provenance links

But the graph is still more *present* than *mature*. The next step is to make graph structure a first-class retrieval and reasoning asset rather than mostly a support layer for editorial memory.

### Priorities

- improve relation quality
  - reduce weak `related_to` residue
  - prefer semantically meaningful relation types
  - strengthen relation promotion standards

- improve graph traversal
  - better neighborhood walking from claims to entities to episodes
  - better entity-centered timeline views
  - clearer provenance-preserving graph explanations

- improve graph-aware retrieval
  - allow query answers to surface structure, not just ranked artifacts
  - make relation paths and episode clusters easier to use as answer material

- improve graph confidence
  - expose more confidence cues on derived graph structure
  - distinguish stable structure from weak extraction residue

### Done when

- graph traversal produces meaning, not just adjacency
- relation quality is high enough that graph outputs feel trustworthy by default
- graph-aware retrieval gives better answers than plain artifact ranking for the right queries

## Track 2: Fractal / Meta-Pattern Projection

### Goal

Operationalize the top of the philosophy without falsely turning projected patterns into stored memory nodes.

### Why

The fractal philosophy is now honest:
- the four stored levels are real
- meta-patterns are computed views, not stored nodes

That means the next step is not “store the top level.”
It is:
- compute it
- score it
- ground it
- surface it with explicit confidence

### Priorities

- add pattern projection primitives
  - recurrence across claims
  - recurring episode motifs
  - repeated relation clusters
  - temporal reappearance under similar conditions

- add confidence-bearing pattern outputs
  - source confidence
  - cross-cluster consistency
  - grounding ratio

- add a projection interface
  - a real `project_patterns(...)` or equivalent service/tool
  - scope-aware
  - explicitly computed, not stored

- add pattern-facing retrieval
  - queries like:
    - `what keeps recurring`
    - `what pattern is emerging`
    - `what does this resemble historically`

### Guardrail

Meta-patterns must remain:
- computed
- query-time or report-time projections
- explicitly confidence-marked
- provenance-backed through the stored graph

They must not silently become stored memory artifacts unless Solaris later introduces a separate, explicitly designed pattern layer.

### Done when

- Solaris can project meaningful higher-order patterns from the stored graph
- projected patterns are honest about uncertainty
- the fractal philosophy becomes operational without overclaiming structural uniformity

## Track 3: Deferred Realism Polish

### Goal

Finish the parts we intentionally deferred because they were polish-tier, not integrity-tier.

### Why

V1 is now honest enough to ship internally.
That does not mean every output is yet aesthetically or semantically perfect.

### Current deferred items

- episode divergence signal/noise cleanup
- entity realism polish on weak residual tails
- better distinction between routine operational arcs and meaningful historical arcs
- continued refinement of graph-facing retrieval aesthetics

### Done when

- the system feels not just structurally correct, but consistently tasteful
- the remaining weak outputs are rare enough to feel exceptional rather than characteristic

## Suggested Order

1. Graph maturation
2. Fractal/meta-pattern projection
3. Deferred realism polish alongside both

That order matters because:
- fractal projection depends on graph quality
- realism polish becomes easier once the graph is carrying more of the structural burden

## Bottom Line

Post-V1 Solaris is no longer about proving the substrate exists.

It is about making the substrate capable of:
- richer graph structure
- higher-order pattern projection
- more intelligent historical interpretation

V1 built memory honestly.
Post-V1 should make that honesty structurally powerful.
