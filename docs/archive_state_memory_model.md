# Archive-State Memory Model

Status: explanatory note, intended as a verification target

## Purpose

This note gives a precise version of a useful analogy:

Solaris is not a State Space Model.

Solaris does, however, have an **archive + filtered state** architecture that resembles the memory shape formalized by state-space models:
- a preserved historical sequence
- a compressed active state
- different persistence dynamics for different memory classes
- a retrieval path that can read current belief cheaply and fall back to grounded history when needed

The point of this note is not to rename Solaris.
The point is to make the architecture easier to reason about and easier to verify.

Implementation proof:
- [Proof](./Proof.md)

## The Safe Claim

The safe claim is:

Solaris has an **SSM-like editorial state layer** over an **append-only archive**.

That is intentionally different from a pure sequence model:
- a pure state-space model keeps only the compressed state
- Solaris keeps both the compressed state and the full archive

That difference is not incidental. It is the grounding invariant.

## The Mapping

### 1. Archive = Absolute Truth

The canonical event log is the preserved sequence:

`E_t = E_{t-1} U {u_t}`

In Solaris terms:
- every ingested event is preserved in the archive
- editorial review never rewrites source events
- derived artifacts can be retired, disputed, or superseded without changing what happened

This is the absolute-truth layer.

### 2. Editorial State = Relative Truth

The editorial layer behaves like a filtered active state:

`x_t = A x_{t-1} + B phi(u_t)`

In Solaris terms:
- new events update current belief
- remembered artifacts remain influential longer than ordinary conversational material
- dormant items lose influence rather than disappearing
- different kinds of material decay at different rates

This is the relative-truth layer.

The analogy is strongest here:
- messages decay quickly
- decisions decay slowly
- failures and recurring operational patterns can re-enter relevance when similar conditions recur

Solaris implements this as policy and editorial state rather than linear algebra, but the memory shape is the same.

### 3. Retrieval = State Read + Grounded Archaeology

A pure compressed-state system reads only from current state.

Solaris reads from both current state and archive:

`y_t = f(C x_t, G(E_t, q))`

Where:
- `C x_t` is the currently active editorial view
- `G(E_t, q)` is grounded archival lookup for query `q`
- `f(...)` is the retrieval bundle that reconciles or juxtaposes them

In Solaris terms:
- surface retrieval reads from current editorial state
- archaeology retrieval reads from the preserved archive
- unified retrieval can return both together

### 4. Divergence = Recorded But Not Currently Active

Solaris has an explicit place for disagreement between archive and current belief:

`delta_t = G(E_t, q) \\ C x_t`

In Solaris terms:
- items present in the recorded history but absent, retired, or low-weight in current belief
- forgotten but once-supported facts
- superseded or disputed artifacts
- historical material that matters to the query even though it is not currently active

This is the divergence field in the unified retrieval model.

In the current implementation, divergence is surfaced as a first-class query bundle field for archive-supported claims and episodes.

## Why Solaris Is Not Just An SSM

The decisive difference is simple:

- SSMs compress because they must
- Solaris compresses because it is useful, while refusing to discard the archive

That gives Solaris a different trade profile:

- belief retrieval can stay cheap because editorial state is compact
- archaeology remains possible because the historical record is preserved
- provenance is not reconstructed from summary state; it is walked back to source events

Solaris pays `O(N)` storage to preserve honesty.

That is the intended trade.

## Practical Reading Of The Analogy

This framing is useful if it helps us reason better about Solaris.

It is not useful if it encourages overclaiming.

So the practical interpretation should stay narrow:
- Solaris has a full-sequence archive
- Solaris has a filtered active-state layer
- Solaris has kind-aware persistence dynamics
- Solaris has a retrieval path that can read active state and grounded history separately or together

That is enough.

## What Must Be True In Implementation

If this note is more than a nice analogy, three things must be true in the real system.

### 1. Archive Immutability

The archive must behave like:

`E_t = E_{t-1} U {u_t}`

That means:
- events are append-only in practice
- editorial actions never remove the source event from history
- derivation failure does not erase the event
- idempotency prevents duplicates without suppressing legitimate history

### 2. Editorial Filtering

The editorial layer must behave like filtered active memory:

`x_t = A x_{t-1} + B phi(u_t)`

That means:
- current belief changes because new events land
- different event kinds have different persistence profiles
- remembered material and dormant material differ in influence rather than historical existence
- policy acts as the effective decay spectrum

### 3. Unified Retrieval

Retrieval must really combine active belief and grounded history:

`y_t = f(C x_t, G(E_t, q))`

That means:
- surface mode prefers current editorial state
- archaeology mode can recover grounded history regardless of current weight
- unified retrieval can surface divergence between the two
- provenance chains from surfaced artifacts back to events remain intact

## The Verification Path

The best way to treat this note is as a testable contract, not a philosophical flourish.

The verification path is:

1. prove archive immutability in code and behavior
2. prove kind-aware editorial filtering in code and behavior
3. prove unified retrieval and divergence behavior in code and behavior

If those hold, then the analogy is not just elegant.
It is descriptively useful.

Current verification entrypoint:
- [run_archive_state_model_checks.py](../run_archive_state_model_checks.py)
