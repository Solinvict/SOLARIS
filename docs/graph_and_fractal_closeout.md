# Graph And Fractal Closeout

Status: implementation-backed closeout artifact

## Purpose

This document records the point at which Solaris's post-V1 graph and fractal phase stopped being roadmap work and became live system behavior.

It closes out three linked efforts:

- graph maturation
- graph-aware retrieval
- fractal / meta-pattern projection

## What Was Finished

### 1. Graph Maturation

The stored graph was hardened so it now behaves as meaningful structure rather than loose adjacency.

Implemented outcomes:

- generic `related_to` fallback was removed from derivation
- legacy `related_to` residue was filtered from graph-facing reads, then removed from the stored graph through rebuild
- relation derivation now fires only from:
  - explicit hints
  - recognized lexical cues
- relation coverage was expanded with better cue handling and stronger trading-ledger relation hints
- weak relation promotion remains stricter than claim promotion

Practical result:

- the graph is now sparse-but-honest
- relation neighborhoods are readable
- old weak graph residue no longer controls live outputs

### 2. Graph-Aware Retrieval

The retrieval path now treats graph-shaped questions as first-class queries instead of forcing everything through generic artifact ranking.

Implemented outcomes:

- relationship-shaped query routing is active
- query metadata now marks relation-focused retrieval
- candidate relations can be surfaced in graph-focused queries without promoting them into remembered truth
- scoped relation search now pulls matching edges from the whole graph, not just the recent relation slice
- multi-token target matching was tightened so exact relation targets rank ahead of partial overlap

Practical result:

- `what uses OKX` can surface `trading engine uses OKX`
- `what depends on fractal memory` can surface `graph memory depends_on fractal memory`
- `what is blocked by min_trade_notional` can surface real `blocked_by` edges

### 3. Fractal / Meta-Pattern Projection

Solaris now has its first official fractal interface:

- `solaris.project_patterns`

The key doctrine was preserved:

- projected patterns are computed views
- they are not stored memory nodes
- they remain confidence-bearing and provenance-backed

Implemented outcomes:

- recurring claim clusters
- recurring episode motifs
- relation clusters
- temporal recurrence projections

The projection layer was then polished so it behaves more like structural interpretation and less like projection spam.

That polish included:

- routine operational episode motifs filtered out
- low-signal single-word episode motifs suppressed
- relation patterns grouped as neighborhoods instead of one pattern per repeated edge
- `blocked_by` and `failed_due_to` clusters anchored on the shared reason/cause side
- base patterns ranked ahead of their temporal mirror variants
- temporal variants lightly demoted so they do not crowd the primary surface

## Live Result

After the final restart and live verification, the graph and fractal surfaces both behaved as intended.

Representative live graph answers:

- `what uses OKX` -> `trading engine uses OKX`
- `what depends on fractal memory` -> `graph memory depends_on fractal memory`
- `what is blocked by min_trade_notional` -> real `blocked_by` edges

Representative live pattern surface:

- `not_worth_capital blocks cluster`
- `min_trade_notional blocks cluster`
- `momentum_rotation_equity uses cluster`
- `momentum_rotation_crypto uses cluster`
- `momentum_rotation uses cluster`
- `capital_preservation uses cluster`
- `autonomy uses cluster`
- `graph memory depends on cluster`

Then the smaller non-structural layer:

- `operator has name Jonas`
- `trading strategy review`
- `CMC Docs research`

That is the important closeout signal:

- structural patterns lead
- low-signal residue no longer dominates
- graph answers and fractal projections are both useful live

## What This Means

Solaris is no longer only:

- an honest archive
- an editorial memory substrate

It is now also:

- a live graph memory system
- a graph-aware retrieval system
- a computed pattern-projection system

without giving up its grounding rules.

The important invariant still holds:

- graph structure is stored
- fractal structure is projected
- source truth remains in the archive

## What Remains

This phase is closed, but a few things remain polish-tier rather than unfinished-foundation work.

Current residual tails:

- continued pattern ranking polish if future live memory shifts
- occasional episode-motif realism cleanup
- continued graph-surface taste improvements as the memory grows

None of those are blockers to considering graph and fractal operational.

## Bottom Line

The post-V1 graph and fractal phase is complete enough to close.

Solaris now supports:

- meaningful stored graph structure
- graph-native retrieval
- computed fractal/pattern projection

in a form that is live, grounded, and credibly usable.

Next operational phase:
- public Solaris release preparation
- private host-system cutover work outside the public Solaris docs set
