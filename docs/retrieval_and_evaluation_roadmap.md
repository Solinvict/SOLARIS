# Solaris Retrieval And Evaluation Roadmap

Status: in active implementation

Purpose: capture the operational disciplines Solaris should borrow from strong retrieval systems without abandoning Solaris's own doctrine of archive, derivation, editorial judgment, and activation.

This roadmap is explicitly inspired by the kinds of strengths seen in retrieval-first systems such as MemPalace:
- benchmark discipline
- clearer retrieval evals
- stronger scoped recall ergonomics
- temporal graph thinking
- productized MCP packaging

What Solaris should borrow is the rigor.
What Solaris should not borrow is the verbatim-only memory philosophy.

## Guardrail

Solaris remains committed to:
- absolute truth in the event archive
- relative truth in editorial state
- provenance-backed abstraction
- storage, remembrance, and activation as separate concerns

Any borrowing from retrieval-first systems must strengthen Solaris as a memory substrate, not collapse it into a semantic search layer.

## Current State

Implemented now:
- repo-runnable eval harness at [run_retrieval_evals.py](../run_retrieval_evals.py)
- committed eval corpus at [retrieval_eval_cases.json](../evals/retrieval_eval_cases.json)
- internal scope-intent retrieval metadata in [query.py](../src/solaris/services/query.py)
- temporal fields for claims and relations
- additive MCP aliases:
  - `solaris.recall`
  - `solaris.explain_memory`
  - `solaris.reconsider`

Current committed eval coverage:
- fact recall: `2` cases
- session recall: `2` cases
- topic recall: `5` cases

Representative covered behaviors:
- identity facts prefer remembered claims
- latest-session and recent-live recall beat imported history
- reaction queries prefer event evidence and reject weak topic entities
- default topic recall hides retired claims
- archaeology recall can surface retired claims
- project-scoped recall prefers project-shaped live evidence
- topic recall prefers matching topical claims over unrelated remembered text

Run the eval suite with:

```powershell
& '.\backend\python312-embed\python.exe' '.\solaris\run_retrieval_evals.py'
```

Usage and corpus-extension guidance lives in:

- [retrieval_eval_guide.md](./retrieval_eval_guide.md)

## Track 1: Benchmark Discipline

### Goal

Make Solaris measurable in a repeatable, falsifiable way.

### Why

Right now we improve Solaris through live inspection and targeted cleanup. That has been effective, but it is not yet enough to tell us whether quality is really improving across retrieval and editorial behavior.

### Deliverables

- A Solaris eval harness runnable from the repo.
- A versioned eval corpus committed in the workspace.
- Metrics captured over time so retrieval and editorial regressions become visible.

### Eval families

- Fact recall
  - Examples:
    - `what is my name`
    - `where do I live`
  - Expected behavior:
    - remembered claims should beat raw events by default

- Session recall
  - Examples:
    - `what did we talk about in this session`
    - `what have we discussed recently`
  - Expected behavior:
    - current or latest interaction should dominate
    - import history should not overpower recent live turns

- Topic recall
  - Examples:
    - `what is Solaris`
    - `what do you remember about trading`
  - Expected behavior:
    - results should reflect repeated or editorially meaningful topic structure
    - junk entities and low-signal events should not dominate

- Editorial behavior
  - Examples:
    - explicit identity facts should promote
    - question-shaped paraphrase claims should remain candidate or retire
    - repeated command buckets should not become remembered episodes

### Done when

- Solaris can be evaluated with a single repeatable command.
- We can compare scorecards before and after retrieval or editorial changes.
- We stop relying on memory of past behavior to judge improvements.

Current status:
- implemented
- current committed scorecard: `9/9` passing

## Track 2: Clearer Retrieval Evals

### Goal

Test not only whether Solaris returns something relevant, but whether it returns the right kind of memory object.

### Why

Solaris is not just a search engine. A correct result is not only about lexical match. It is also about whether the answer should come from:
- a claim
- an event
- an episode
- a state lease

### Deliverables

- A retrieval-eval spec with:
  - query
  - scope
  - preferred artifact types
  - acceptable top-k results
  - forbidden results
  - expected recall mode

### Example assertions

- `where do I live`
  - preferred: remembered claim
  - forbidden: unrelated topic entities

- `what did we talk about in this session`
  - preferred: latest live events
  - forbidden: imported archival conversation dominating the answer

- `what was very funny`
  - preferred: event evidence
  - forbidden: weak reaction phrases as topic entities

### Done when

- We can explain not just whether retrieval worked, but what kind of memory Solaris chose to answer from.

Current status:
- implemented for the current eval corpus
- the harness now supports:
  - preferred artifact type checks
  - top-text expectations
  - required and forbidden surfaced texts
  - query-meta assertions
  - artifact-state assertions
  - optional editorial overrides for test setup

## Track 3: Stronger Scoped Recall Ergonomics

### Goal

Make scope visible and first-class in retrieval rather than leaving it mostly implicit inside ranking heuristics.

### Why

Scoped recall is one of the strongest ideas in retrieval-first memory products. Solaris already has the ingredients, but the ergonomics should become more explicit and operator-shapeable.

### Scope classes to formalize

- `this_session`
- `recent`
- `project`
- `identity`
- `topic`
- `archive`
- `archaeology`

### Implementation direction

- Tighten scope handling in [query.py](../src/solaris/services/query.py).
- Make scope intent more visible in explainability output.
- Prefer explicit scope narrowing before relevance boosting when the query clearly signals a scope.

### Done when

- Scope feels like a retrieval affordance, not just hidden query behavior.
- Session and recent queries become more predictable and easier to reason about.

Current status:
- implemented for `this_session`, `recent`, `project`, `identity`, `topic`, `archive`, and `archaeology`
- bundle metadata exposes which scope path was applied

## Track 4: Temporal Graph Thinking

### Goal

Make Solaris better at representing not just what is connected, but when a memory or relation was valid, active, disputed, or superseded.

### Why

This fits Solaris especially well because Solaris already distinguishes:
- what happened
- what is currently believed

Temporal semantics make that distinction operational.

### Candidate additions

- `valid_from`
- `valid_until`
- `superseded_at`
- `disputed_at`
- `last_reinforced_at`
- recurrence windows or rolling support periods

### Queries this unlocks

- `what changed`
- `what was true then vs now`
- `when did this become believed`
- `what pattern keeps recurring`

### Done when

- Solaris can answer temporal memory questions without pretending the present editorial state existed forever.

Current status:
- initial temporal fields implemented for claims and relations
- explain and timeline now surface temporal metadata when present

## Track 5: MCP Packaging And Product Surface

### Goal

Expose Solaris through a cleaner operator and agent surface.

### Why

Solaris already has strong internal machinery. The remaining gap is making that power easier to use consistently.

### Packaging direction

Keep the internal engine sophisticated, but provide a clearer outer surface such as:
- `solaris.remember`
- `solaris.recall`
- `solaris.explain_memory`
- `solaris.timeline`
- `solaris.reconsider`

This should be treated as packaging, not as a simplification of the underlying model.

### Done when

- Common memory tasks can be expressed through a smaller, clearer tool vocabulary.
- Explainability and reconsideration are easier to invoke intentionally.

Current status:
- additive aliases implemented without breaking the original MCP surface

## Recommended Order

1. Build the Solaris eval harness.
2. Add retrieval-eval fixtures covering fact, session, topic, and editorial cases.
3. Formalize scoped recall ergonomics in [query.py](../src/solaris/services/query.py).
4. Design temporal validity semantics for claims and relations.
5. Refine the MCP tool surface.

## Non-Goals

This roadmap does not imply:
- abandoning editorial memory in favor of verbatim-only search
- replacing provenance-backed derivation with raw vector retrieval
- turning Solaris into a flat context loader

Solaris should borrow retrieval discipline from systems like MemPalace while remaining a grounded memory substrate in its own right.
