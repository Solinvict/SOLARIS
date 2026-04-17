# Proof

Status: implementation-backed proof artifact

## Purpose

This document records the strongest claim Solaris can currently justify about its memory architecture.

That claim is:

Solaris behaves as an **archive-grounded memory substrate** with:
- an append-only historical archive
- a filtered editorial state
- a retrieval path that can surface current belief, grounded history, and divergence between them

This is not a proof that Solaris is a State Space Model.

It is a proof that Solaris implements the archive-state memory shape described in:
- [Archive-State Memory Model](./archive_state_memory_model.md)
- [Fractal Memory Philosophy](./fractal_memory_philosophy.md)

## The Claim

The implementation claim is:

`Archive:    E_t = E_{t-1} U {u_t}`

`State:      x_t = A x_{t-1} + B phi(u_t)`

`Retrieval:  y_t = f(C x_t, G(E_t, q))`

`Divergence: delta_t = G(E_t, q) \\ C x_t`

Translated into Solaris terms:
- events are preserved as absolute truth
- editorial state is a compressed relative-truth layer
- retrieval can read both active belief and grounded archive
- divergence is archive-supported material not currently active in belief

## What Was Tested

The proof was reduced to three implementation checks.

### 1. Archive Immutability

Question:
- does Solaris preserve the source event even after the derived memory is retired?

Test:
- ingest a memory-bearing event
- allow review to promote the derived claim
- manually retire the claim
- confirm:
  - the source event still exists
  - the evidence link still exists
  - explainability still walks back to the source event

### 2. Editorial Filtering

Question:
- does Solaris treat different kinds of evidence differently in the editorial layer?

Test:
- ingest a single-evidence `decision` claim
- ingest a single-evidence `message` claim
- run editorial review
- confirm:
  - the decision-backed claim becomes remembered
  - the message-backed claim stays candidate
  - the remembered decision has materially higher score

### 3. Unified Retrieval And Divergence

Question:
- can Solaris distinguish between current belief and grounded archive for the same fact?

Test:
- ingest and promote a claim
- query it in default mode and confirm the claim surfaces
- retire the claim
- query again in default mode and confirm the claim no longer surfaces as current belief
- query in archive mode and confirm the source event still surfaces
- confirm divergence is emitted as a first-class query field

## Verification Artifacts

Primary runner:
- [run_archive_state_model_checks.py](../run_archive_state_model_checks.py)

Focused regression file:
- [test_archive_state_memory_model.py](../tests/test_archive_state_memory_model.py)

Related retrieval regression harness:
- [run_retrieval_evals.py](../run_retrieval_evals.py)

## Result

Current result:

- archive immutability: passed
- editorial filtering: passed
- state vs archive retrieval: passed

The dedicated runner currently reports:

- `3 / 3` archive-state checks passed
- retrieval eval harness remains green at `10 / 10`

Those `10` retrieval evals are not smoke tests. They cover:
- fact recall
- session recall
- topic recall
- archaeology/archive recall
- cross-interaction continuity

Reference:
- [run_retrieval_evals.py](../run_retrieval_evals.py)
- [retrieval_eval_cases.json](../evals/retrieval_eval_cases.json)

The implemented divergence behavior now exists in the query contract:
- `recorded.events`
- `recorded.provenance`
- `recorded.divergences`
- `divergence_summary`

## What This Proves

This proves that Solaris is not merely described as archive plus editorial state.

It behaves that way in implementation:

- the archive is preserved independently of editorial judgment
- editorial state filters significance rather than rewriting history
- retrieval can switch between active belief and grounded record
- divergence between the two is now surfaced explicitly

That is enough to justify the architectural claim that Solaris is:

**an archive-grounded memory substrate with an SSM-like active-state layer**

## What It Does Not Prove

This proof does **not** establish:

- that Solaris is mathematically equivalent to an SSM
- that all decay dynamics are continuous or formally modeled
- that every artifact type has equally mature divergence semantics
- that retrieval realism is perfect

In particular:
- divergence is strongest today for claims and episodes
- episode divergence can still surface some low-signal tails
- entity-level divergence is intentionally not first-class yet because it is noisier

## Honest Caveat

The proof holds at the level of architecture and query behavior.

It does not mean every surfaced divergence is already aesthetically perfect.

One known softness remains:
- a retired claim can correctly surface as divergence while a related low-signal episode also appears alongside it

More precisely:
- this is an **episode divergence signal/noise issue**
- it is intentionally deferred because claim divergence semantics are already stronger than episode and entity divergence semantics

That is a realism/polish issue, not a failure of the model or of the archive-state claim itself.

## Operational Rerun

To rerun the proof:

```powershell
& '.\backend\python312-embed\python.exe' '.\solaris\run_archive_state_model_checks.py' --json
```

To rerun the retrieval eval suite:

```powershell
& '.\backend\python312-embed\python.exe' '.\solaris\run_retrieval_evals.py' --json
```

## Bottom Line

The archive-state formulation survives contact with the implementation.

Solaris now has enough evidence to claim, honestly and concretely, that:

- it preserves absolute truth in the archive
- it maintains relative truth in editorial state
- it retrieves both
- and it can explicitly show where they diverge
