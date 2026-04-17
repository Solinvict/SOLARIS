# Query Contract

`solaris.query` accepts a scoped query with recall mode and bundle budgets, then returns claims, state leases, episodes, events, entities, relations, and explanations.

The returned bundle now also includes:
- a `meta` block for query-level explainability
- a `recorded` block for archive-facing evidence
- a `divergence_summary` block for archive-vs-belief mismatch reporting

Current `recorded` fields:
- `events`
- `provenance`
- `divergences`

Current divergence behavior:
- divergences are computed for archive-supported `claim` and `episode` artifacts first
- an item is considered divergent when it is supported by the archive but not currently active in belief
- this includes:
  - retired
  - superseded
  - disputed
  - low-weight artifacts below `SOLARIS_DIVERGENCE_WEIGHT_THRESHOLD`

Current `meta` fields:
- `scope_intent`
- `preferred_session_id`
- `preferred_episode_session_id`
- `session_narrowing_applied`
- `archive_relaxation_applied`
- `identity_focus_applied`
- `project_focus_applied`
- `recent_focus_applied`

Current internal scope-intent values:
- `this_session`
- `recent`
- `project`
- `identity`
- `topic`
- `archive`
- `archaeology`

The committed retrieval eval suite asserts these fields directly via [run_retrieval_evals.py](../run_retrieval_evals.py) and [retrieval_eval_cases.json](../evals/retrieval_eval_cases.json), so changes to query behavior should be checked against the eval harness before they are treated as stable contract behavior.

The archive-vs-state proof runner at [run_archive_state_model_checks.py](../run_archive_state_model_checks.py) also checks the divergence path directly.
