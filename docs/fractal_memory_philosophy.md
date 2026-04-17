# Fractal Memory Philosophy

*Design session, 2026-04-12. Tempered by five questions.*

Related note:
- [Archive-State Memory Model](./archive_state_memory_model.md)
- [Proof](./Proof.md)

---

## The Five Questions

These are the questions that forced the redesign of this document. They are worth preserving explicitly because the final shape of the philosophy is easier to understand if the pressure that produced it remains visible.

**1. Does the fractal self-similarity claim actually hold?**

Meta-patterns do not have the same structure as events, entities, claims, and episodes. They are a weight distribution, not a stored node. The navigation logic that works at lower levels breaks at the top level. The self-similarity claim was an overclaim.

**2. Does exposure as the update mechanism assume exposure is representative?**

If the event stream is biased — some topics over-represented, some sessions never ingested — editorial weights reflect ingestion patterns rather than ground truth. Frequency and importance get conflated. A decision made once and never repeated gets buried under conversational churn.

**3. Does archaeology mode have a cold-start problem?**

The mode is philosophically correct but practically thin until data density builds. In the early months with a few hundred events, archaeology returns a sparse graph with obvious gaps. The elegance depends on data density that does not exist yet.

**4. What happens if meta-patterns emerge from a noisy graph?**

If entity extraction is wrong early on — and it will be — meta-patterns emerge from extraction errors rather than genuine signal. There is no automatic validation layer. The grounding chain exists, but auditing it requires human effort.

**5. Does the two-truths separation create a UX problem?**

When querying memory, the caller has to decide before querying whether they need belief or record. Most queries do not know that in advance. The separation puts too much burden on the caller.

These five questions did not invalidate the philosophy. They forced it to become more honest:
- the fractal claim was narrowed to the four stored levels
- meta-patterns were reclassified as computed views
- editorial weighting became explicitly kind-aware rather than frequency-naive
- archaeology was made honest about archive density
- retrieval moved toward a unified bundle that can surface belief, record, and divergence together

---

## The Two Truths

AI memory — like human memory — is twofold.

**Absolute Truth**
The immutable event record. What was said, when, by whom. This never changes because the past never changes. In Solaris this is the append-only events table in SQLite. Nothing is deleted. Nothing is rewritten.

**Relative Truth**
What is currently believed. A function of all exposure accumulated up to the present moment. This shifts as new events land that corroborate, contradict, or recontextualize what came before. In Solaris this is editorial weight — candidate, remembered, retired, faded — applied to entities, claims, relations, and episodes.

The mechanism for updating relative truth is **exposure**, not correction. Not deletion, not rewriting — new events arrive, editorial reweights in response, and belief shifts accordingly. The past is never altered; only its current significance changes.

---

## The Grounding Invariant

Every stored node at every level of abstraction carries an unbroken provenance chain back to the source events that created it. This is non-negotiable.

You can abstract without drifting because you can always verify. That is what separates a memory substrate from a retrieval index.

---

## The Four Stored Levels

Solaris has four stored levels of abstraction. The fractal property holds across these four levels and nowhere else — every node has the same structure: provenance, timestamp, editorial state, traversable links. The traversal interface is uniform. The same navigation logic, the same provenance walk, the same editorial state model applies at every level.

```
   episodes            ← stored, provenance-linked, editorial state
      ↑↓
entities / claims      ← stored, provenance-linked, editorial state
      ↑↓
    events             ← stored, immutable, absolute truth anchor
```

This is where the self-similarity claim is true and architecturally meaningful. It is also where the claim stops.

---

## Meta-Patterns Are Computed Views, Not Stored Nodes

Above the four stored levels, patterns emerge from the graph. These are not nodes. They have no provenance record, no timestamp, no editorial state. They are computed projections over the weight distribution of the stored graph — what you see when you look at the graph from sufficient distance.

Calling meta-patterns part of the fractal hierarchy was an overclaim. The fractal property requires uniform structure across levels. Meta-patterns do not share that structure. They are categorically different.

The corrected picture:

```
meta-patterns     ← computed view; projected on demand from graph weights; not stored
      ↑
   episodes        ← stored, provenance-linked, editorial state
      ↑↓
entities / claims  ← stored, provenance-linked, editorial state
      ↑↓
    events         ← stored, immutable, absolute truth anchor
```

Meta-patterns get a separate projection interface — `solaris.project_patterns(scope, min_weight)` — that computes over the graph rather than traversing stored nodes. No navigation logic breaks because the boundary is explicit.

This preserves the philosophical claim honestly. The fractal property holds where it is true. The emergent property is kept distinct where it is different.

Meta-patterns are never explicitly assigned. They emerge from current editorial weights in the entity graph — computed fresh when needed, shifting automatically as exposure shifts. This means meta-patterns are by definition relative truth. A pattern exists when the weights support it and fades when they don't. No assignment to go stale because there is no assignment.

**Meta-patterns carry explicit confidence provenance.** Because the graph they emerge from may contain extraction noise — especially early — every projected pattern carries three confidence components:

- **Source confidence.** The average extraction confidence of the entities and relations that produced this pattern. A pattern built from high-confidence entities is more trustworthy than one built from borderline extractions, and it inherits that uncertainty explicitly.

- **Consistency score.** How consistently does this pattern appear across independent event clusters? A genuine pattern appears across events from different sessions, different times, different contexts. An extraction artifact tends to cluster — it appears in events processed by the same extraction pass, often close in time. Consistency across independent clusters is the primary signal that a pattern is real rather than artifactual.

- **Grounding ratio.** What fraction of the supporting events can be walked to source text that genuinely supports the pattern? The system samples rather than auditing every chain. A pattern with a high grounding ratio is more trustworthy than one where chains lead to ambiguous or unrelated source events.

These three components combine into a pattern confidence score. Low-confidence patterns are surfaced with explicit uncertainty markers. They are not suppressed — suppression hides noise rather than exposing it. They are surfaced with honest uncertainty, which allows the querying system or operator to decide how much weight to give them.

An uncertain pattern honestly labeled is more useful than a certain-looking pattern whose uncertainty is hidden.

---

## Editorial Churn Is Not a Problem

Because nothing is discarded:
- Episodes, entities, and claims never leave their level — they only change weight
- The grounding chain is always intact — you can walk down to the source event regardless of editorial state
- Retired today does not mean irrelevant forever — a claim that scored low in November may be the most important context in March when the same pattern repeats

An episode whose entities are all retired is not a broken structure. It is a low-weight structure. The navigator traverses it, reads the weights, surfaces accordingly.

---

## Editorial Weight as Epistemological Honesty

The exposure bias problem is real and worth naming precisely. Solaris accumulates events from a stream that is not uniformly important. Conversational turns outnumber decisions by orders of magnitude. Trading cycles generate hundreds of events per day. A single architectural choice that took thirty seconds to make and never needed repeating produces one event. The editorial layer, if it treats all events equally and promotes by frequency, will reflect the shape of the stream rather than the shape of what matters. That is not memory. That is logging with extra steps.

The fix lives in the editorial layer because that is where the bridge between absolute truth and relative truth is built. The events layer never changes — that is its job. The retrieval layer returns what the editorial layer has decided. The editorial layer is the place where Solaris makes judgments about significance, and it is the right place to make those judgments correctly.

---

## The Three Dimensions of Significance

Editorial weight is a function of three independent dimensions, not one.

**Frequency** — how often does this claim, entity, or pattern appear across events? This is the naive measure most systems use exclusively. It is useful but insufficient. High frequency is evidence of salience but not proof of importance.

**Kind** — what type of event produced this? A decision event is categorically different from a message event. A failure event is categorically different from a summary. The event schema carries kind as a first-class field. Editorial policy treats kind as a prior on importance — decisions and failures are presumed significant regardless of frequency, conversational turns are presumed ordinary unless other signals elevate them.

**Explicit signal** — was this pinned? Was it marked as high importance at ingest time? Did the adapter flag it as a decision candidate? Explicit signals from the ingestion path override frequency-based inference. A pinned fact that appeared once outweighs an unpinned claim that appeared a hundred times.

These three dimensions combine into a promotion rule that is frequency-aware but not frequency-dominated.

---

## The Promotion Rule

**Path A — Explicit promotion.** `kind=fact_assertion` with `pinned=true`, or `kind=decision` with `importance >= threshold`, or an explicit `apply_editorial_decision(action=pin)` call. These bypass frequency entirely. One event is sufficient. This is how architectural decisions, trading policy changes, and failure records get protected regardless of how rarely they are discussed again.

**Path B — Frequency promotion.** `kind=message` or `kind=summary` with the same canonical claim appearing across two or more distinct events. Frequency is the signal here because repetition in conversation genuinely indicates salience for ordinary content.

**Path C — Kind-weighted promotion.** `kind=failure` or `kind=decision` without explicit pinning but with importance above a lower threshold. These get promoted after a single corroborating event rather than requiring the standard frequency threshold. Decisions and failures are structurally important regardless of whether they get discussed again. A failure that is never mentioned again is not unimportant. It may be unresolved.

A thin adapter that emits everything as `kind=message` collapses all three paths into Path B and reintroduces the frequency bias. The adapter's responsibility is not just format translation — it is semantic tagging. Getting kind right at ingest time is what makes editorial honesty possible downstream.

---

## Dormancy Is Kind-Aware

Conversational content that has not been referenced in months should decay toward dormant naturally. A decision that has not been referenced in months should not. The dormancy policy for `kind=decision` and `kind=failure` has a much longer half-life than the dormancy policy for `kind=message`. Decisions do not become less true because they are not discussed. They become more dangerous if forgotten.

Some things matter more as time passes, not less. A failure record dormant for six months is not stale — it is a risk factor waiting for the right retrieval query.

---

## Archaeology Mode and Archive Density

Archaeology mode ignores editorial weight and returns the full historical record. It is a present capability, not a future one. It is available from day one. What changes over time is not its correctness but its richness.

A sparse archive honestly returned is more epistemologically sound than a dense index that pretends to completeness. The grounding invariant applies to the retrieval response itself — the system does not pretend to completeness it does not have.

Every archaeology response includes a density report:

- Total events in scope
- Entity coverage
- Provenance chain completeness
- Current archive maturity state

Archive maturity has three natural states:

| State | Event count | Character |
|-------|-------------|-----------|
| Sparse | < 500 | Thin graph, obvious gaps, useful for recent history only |
| Developing | 500–5,000 | Meaningful traversal, some gaps, patterns beginning to emerge |
| Mature | 5,000+ | Dense graph, archaeology genuinely illuminating |

When density is below threshold, the response includes an explicit note: "Archive covers N events from X date. Gaps exist before this date. Results reflect available record, not complete history."

The capability is real from day one. It just gets more useful over time, and it is honest about that trajectory.

---

## The Unified Retrieval Bundle

The two truths are not alternatives to choose between. They are complementary lenses on the same reality.

Most queries do not know in advance which truth they need. A caller asking "what do we know about the trading architecture" does not know whether the answer should come from current belief or historical record. Forcing that choice onto the caller puts too much burden on the wrong side of the interface.

The default retrieval response returns both truths simultaneously with clear labeling:

```python
{
  "believed": {
    "facts":     [],   # currently remembered, weighted by editorial state
    "entities":  [],   # active entities with current weight
    "episodes":  [],   # active episodes
    "relations": []    # active relations
  },
  "recorded": {
    "events":      [],  # raw events supporting the query
    "provenance":  [],  # grounding chains for believed items
    "divergences": []   # items in recorded but absent or retired in believed
  },
  "divergence_summary": {
    "count":   0,
    "notable": []  # items where recorded and believed disagree significantly
  }
}
```

The `divergences` field is the most important addition. It surfaces items that exist in the historical record but are not currently believed — decisions that faded, failures that were retired, claims that lost weight. The caller does not need to run archaeology separately to find these. They arrive automatically alongside current belief.

Divergence is not a failure state. It is a signal. It may mean a decision was made and forgotten. It may mean a failure pattern was retired prematurely. It may mean the exposure stream stopped talking about something important. Surfacing divergences automatically means the caller never has to know to ask for archaeology — the system tells them when archaeology would be revealing.

Explicit mode selection remains available. `mode=surface` for pure belief, `mode=archaeology` for pure record. But the default — and the recommended path for most queries — is the unified bundle.

---

## The Full Philosophy

Solaris is fractal across four stored levels of abstraction — events, entities, claims, and episodes — where the self-similarity claim is true and traversal is uniform. Above those levels, patterns emerge as computed projections with explicit confidence provenance, honest about the quality of the graph they came from.

The editorial layer governs relative truth through kind-aware promotion, explicit signal, and kind-aware dormancy. It is frequency-aware but not frequency-dominated. The adapter contract is the boundary where kind is established — getting it right at ingest is what makes editorial honesty possible downstream.

Archaeology mode is a present capability whose utility grows with archive density, and it is honest about that density at every stage. Retrieval returns both truths simultaneously, with divergence surfaced automatically so the caller never has to know to ask.

Nothing is discarded. Everything is reweighted. The grounding invariant holds at every stored level. The past is never rewritten — only its current significance changes.

The result is a memory substrate that is honest at every level: about what it currently believes, about what it has recorded, about where those two things disagree, and about how confident it is in its own abstractions.

That is the difference between a memory system and a memory substrate.
