# Hybrid Editorial Review

Status: design and scaffolding artifact

Purpose: define how Solaris can add a small-model adjudication layer without giving up deterministic editorial authority.

## Core Idea

Solaris should not become an LLM memory judge.

Solaris should remain:
- archive-first
- provenance-grounded
- editorially explicit
- policy-driven

The small model belongs only in the ambiguous middle of review.

The shape is:

1. rules layer handles obvious cases
2. small model sees only borderline cases
3. editorial engine remains the authority that writes final state

## Why This Fits Solaris

Solaris already separates:
- storage
- derivation
- review
- retrieval

That means ambiguity handling has a natural home: review-time arbitration.

The model is not creating memory directly.
It is advising the editorial layer on cases where the deterministic rules are not confident enough to deserve sole authority.

## The Three Layers

### 1. Hard Rules

Deterministic review handles:
- obvious promote cases
- obvious leave-candidate cases
- obvious retire cases
- pinned artifacts
- question-like claims
- speech-act claims
- low-quality remembered episodes on reconsider

These cases are:
- cheap
- stable
- explainable
- easy to audit

They should never go through a model.

### 2. Ambiguity Band

Only the ambiguous middle is eligible for adjudication.

Current scaffold shape:
- policy-controlled
- disabled by default
- limited to selected artifact types
- limited to a small action vocabulary
- supports both `shadow` and `assist` modes

Default policy surface:

```json
"adjudication": {
  "mode": "off",
  "enabled": false,
  "artifact_types": ["claim", "episode"],
  "allowed_actions": ["promote", "leave_candidate", "retire"],
  "ambiguity_band": {
    "candidate_floor": 0.35,
    "candidate_ceiling": 0.82,
    "promotion_margin": 0.10,
    "retire_margin": 0.08
  }
}
```

This means the model is asked only when:
- rules did not hard-lock the decision
- the artifact type is eligible
- the current action is in the allowed adjudication vocabulary
- the remember score falls inside the ambiguity band

Mode meanings:
- `off` -> no model call
- `shadow` -> model suggestion is recorded but never applied
- `assist` -> model suggestion can influence final action inside the allowed vocabulary

### 3. Final Editorial Authority

Even when a model returns a suggestion, Solaris still writes the final editorial state.

The final contract remains:
- `artifact_editorial_state`
- `editorial_decisions`

The model is an input into the decision, not the owner of the memory.

## Allowed Model Output

The small model should return:
- `action`
- `confidence`
- `rationale`

Allowed action vocabulary should stay narrow:
- `promote`
- `leave_candidate`
- `retire`

That narrowness is important.

The model should not directly choose:
- `pin`
- `mark_disputed`
- `mark_superseded`
- `reinforce`
- `fade`

Those remain deterministic or manual-authority paths.

## Auditability

The rationale is not stored because the model is truth.
It is stored because Solaris needs to remain inspectable.

The right audit fields are:
- `adjudication_source`
- `adjudication_confidence`
- `adjudication_rationale`
- `adjudication_model`
- `adjudication_prompt_version`
- `adjudication_suggested_action`
- `adjudication_rule_action`
- `adjudication_final_action`
- `adjudication_applied`

Current scaffold stores these inside `rationale_json` on:
- editorial state
- editorial decision

That keeps the first implementation additive and low-risk.

`adjudication_prompt_version` matters because model behavior can drift even when the model name stays the same.
That field preserves decision lineage when prompts evolve.

## Good Uses

This layer is for cases like:
- is this a real topic entity or conversational fluff?
- is this episode title meaningful or STT residue?
- is this claim a durable personal fact or only a turn-local paraphrase?
- does this artifact deserve promotion now or more evidence first?

## What It Must Not Do

The model must not:
- overwrite provenance
- invent source events
- create memory outside the archive/derive/review flow
- become the sole authority over editorial state
- turn rationale text into first-class memory artifacts

## Current Scaffold In Code

The current repo scaffold includes:
- [adjudication.py](../src/solaris/editorial/adjudication.py)
- ambiguity-band policy fields in:
  - [default_v1.json](../policies/default_v1.json)
  - [operator_personal_v1.json](../policies/operator_personal_v1.json)
- editorial-engine hook in [engine.py](../src/solaris/editorial/engine.py)

Current behavior:
- deterministic review remains unchanged by default
- adjudication defaults to `mode: off`
- a real OpenAI-compatible adjudicator can now be wired by environment
- shadow mode records model suggestions without changing live editorial outcomes
- rationale storage shape now captures rule action, suggested action, final action, and prompt version
- [run_adjudication_shadow_report.py](../run_adjudication_shadow_report.py) can now report eligible cases, hard-lock reasons, and near-misses from the live DB

## Recommended Next Step

The next implementation step should be:

1. add a concrete small-model adjudicator implementation behind an interface
2. restrict it to claims and episodes first
3. run it in shadow mode
4. compare:
   - rule action
   - model suggestion
   - final action
5. study where the model helps and where it drifts

That preserves Solaris's doctrine:
- rules for the edges
- small model for ambiguity
- rationale for audit
- editorial state as the final memory contract
