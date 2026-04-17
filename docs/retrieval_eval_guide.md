# Solaris Retrieval Eval Guide

Status: active

Purpose: document how to run, extend, and interpret the Solaris retrieval evaluation harness.

## What This Harness Covers

The Solaris retrieval eval suite is the repeatable check for whether retrieval behavior still matches the system we want.

It currently covers:
- fact recall
- session recall
- topic recall
- scope-intent behavior
- archaeology/archive behavior
- selected editorial-memory outcomes

This is not a synthetic benchmark in the abstract. It is a committed regression corpus for the actual Solaris behaviors we care about.

## How To Run It

From the repo root:

```powershell
& '.\backend\python312-embed\python.exe' '.\solaris\run_retrieval_evals.py'
```

JSON output:

```powershell
& '.\backend\python312-embed\python.exe' '.\solaris\run_retrieval_evals.py' --json
```

The harness creates scratch databases under:

```text
solaris/.runtime/evals/<case_id>/
```

and removes them after each case finishes.

That workspace-local behavior is intentional so the evals do not depend on the Windows temp directory, which has been unreliable in this environment for full pytest runs.

## Corpus Location

Committed eval cases live in:

- [retrieval_eval_cases.json](../evals/retrieval_eval_cases.json)

The harness entrypoint is:

- [run_retrieval_evals.py](../run_retrieval_evals.py)

## Case Shape

Each case has:
- `id`
- `family`
- `setup`
- `query`
- `expect`

### `setup`

Supports:
- `sessions`
- `events`
- `close_sessions`
- `reviews`
- `editorial_decisions`

This lets us build compact, deterministic memory situations inside a scratch Solaris store without depending on the live DB.

### `query`

Currently supports:
- `text`
- `recall_mode`

The public request schema stays simple. Scope-intent is inferred by Solaris internally and then asserted through eval metadata.

### `expect`

Currently supports:
- `preferred_artifact_type`
- `allowed_top_texts`
- `required_texts`
- `forbidden_texts`
- `forbidden_entities`
- `meta_assertions`
- `artifact_assertions`

## What The Assertions Mean

### Preferred Artifact Type

Checks what kind of memory Solaris chose to answer from first.

This matters because Solaris is not just trying to be relevant. It is trying to choose the right memory layer:
- claim
- event
- episode
- entity
- relation
- state lease

### Allowed Top Texts

Checks the first surfaced item of the preferred artifact type.

Use this when the top answer should be specific.

### Required Texts

Checks that a piece of memory surfaced somewhere in the returned bundle, even if it is not the top answer.

This is especially useful for archaeology/archive cases where we want breadth without forcing a retired artifact to outrank the current claim.

### Forbidden Texts And Forbidden Entities

Checks that known-bad outputs do not surface.

Use this for:
- junk topic entities
- irrelevant remembered material
- imported history dominating a recent query

### Meta Assertions

Checks query-bundle metadata, such as:
- `scope_intent`
- `archive_relaxation_applied`
- `session_narrowing_applied`
- `identity_focus_applied`
- `project_focus_applied`
- `recent_focus_applied`

This is important because some regressions are not about the final answer. They are about the path Solaris took to get there.

### Artifact Assertions

Checks editorial state for a specific artifact, for example:
- a claim is `remembered`
- a claim is `retired`

This lets retrieval evals also enforce memory-policy outcomes where appropriate.

## Current Coverage Philosophy

The current corpus is deliberately small but high-signal.

We are not trying to create a huge benchmark set before the behavior is stable enough to deserve it. We are building a compact suite that catches:
- wrong memory layer choice
- wrong scope behavior
- topic-recall drift
- archaeology/archive regressions
- editorial state leakage into normal recall

## When To Add A New Eval

Add a case when one of these is true:
- we fixed a real bug in retrieval behavior
- we added a new scope behavior
- we added a new editorial or temporal retrieval rule
- a live regression taught us something Solaris should never do again

Do not add evals just to increase case count.

## Current Next Layer

Good candidates for future expansion:
- temporal retrieval questions such as `what changed`
- project recall with stronger codebase-specific evidence
- state-lease-centered queries
- contradiction/disputed-memory behavior once that path is mature

## Related Docs

- [query_contract.md](./query_contract.md)
