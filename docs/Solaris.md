Solaris v1, revised
1. Definition

Solaris is a standalone, project-agnostic MCP memory server that:

captures canonical events from any client
preserves the raw record as source truth
derives entities, relations, claims, episodes, and temporary state
applies editorial judgment to decide what should become enduring memory, what should remain candidate material, and what should fade into dormancy
returns scoped retrieval bundles with provenance and editorial rationale

A host runtime can be the first adapter, but it should not define the core.

Related notes:
- [Archive-State Memory Model](./archive_state_memory_model.md)
- [Fractal Memory Philosophy](./fractal_memory_philosophy.md)
- [Proof](./Proof.md)
- [Post-V1 Roadmap](./post_v1_roadmap.md)
- [Graph And Fractal Closeout](./graph_and_fractal_closeout.md)

2. The new design premise

Before, Solaris was:

archive → derive → retrieve

Now it is:

archive → derive → review → retrieve

That added step is the real revision.

Solaris should not passively accumulate memory and then merely rank it by relevance. It should maintain a record of what it has chosen to keep alive in its continuing history.

That choice must be explicit, inspectable, and reversible.

3. Core principles
Events are primary

The canonical event log is the source of truth. Everything else is derived.

Raw truth is preserved

Editorial decisions never overwrite or rewrite source events.

Remembering is separate from storing

A thing can be archived without becoming enduring memory.

Activation is separate from remembrance

A thing can be enduringly remembered but currently dormant.

Scope is explicit

No cross-project or cross-client memory leakage by default.

Provenance is mandatory

Every claim, relation, episode, and editorial decision must point back to supporting events.

Dormancy beats deletion

What fades should usually lose influence before it disappears from reach.

Editorial judgment is policy-driven

The Solaris core does not hardcode what matters. Clients provide policy profiles and hints.

4. The memory lifecycle

This is the revised lifecycle Solaris should enforce:

observed → archived → candidate → remembered → active/dormant → disputed/superseded/retired

What each means:

observed: an event entered the system
archived: it was safely persisted in raw form
candidate: derived memory exists, but Solaris has not committed to keeping it as enduring memory
remembered: Solaris judged it worth retaining as part of ongoing memory
active: currently allowed to influence retrieval strongly
dormant: remembered, but low present influence
disputed: conflicting evidence exists
superseded: replaced by newer memory
retired: intentionally deprioritized from normal recall, but still available in deep/archive mode

That is the critical improvement over a flat memory store.

5. What Solaris is and is not

Solaris v1 is:

a reusable memory engine
local-first
event-centered
graph-capable
editorially aware
scoped
explainable

Solaris v1 is not:

a live chat buffer replacement
a global “everything everywhere” soup
a fully autonomous self-reflective mind
an LLM-only summarization system
a graph database product
a deletion-heavy forgetting engine

It is a substrate with a deliberate notion of remembrance.

6. The architectural layers

Solaris v1 has five layers.

6.1 Archive layer

Stores the raw, immutable-enough event history.

Its question is:

What actually happened?

6.2 Derivation layer

Builds entities, relations, claims, episode candidates, and temporary state from events.

Its question is:

What structure can be extracted from what happened?

6.3 Editorial layer

Reviews derived artifacts and assigns memory status.

Its question is:

What deserves to persist as part of continuing memory?

6.4 Activation layer

Controls influence decay and default recall behavior.

Its question is:

What should matter now?

6.5 Retrieval layer

Builds scope-aware bundles for clients.

Its question is:

What is worth surfacing for this query, under this policy, in this scope?

7. Core domain model

The revised v1 has nine first-class objects.

7.1 ScopeRef

The isolation boundary.

{
  "tenant": "personal",
  "namespace": "host",
  "workspace": "default",
  "project": "core"
}

Rules:

tenant and namespace are required
workspace and project are optional
retrieval defaults to exact scope
broader recall must be requested explicitly
7.2 SessionRecord

A generic boundary object.

{
  "session_id": "sess_001",
  "parent_session_id": null,
  "kind": "runtime",
  "scope": { "...": "..." },
  "policy_profile": "operator_personal_v1",
  "policy_context": {},
  "opened_at": "2026-04-10T09:00:00Z",
  "closed_at": null
}

The core does not interpret kind; adapters do.

7.3 MemoryEvent

The canonical unit of experience.

{
  "event_id": "evt_001",
  "schema_version": 1,
  "timestamp": "2026-04-10T09:03:11Z",
  "scope": { "...": "..." },
  "session_id": "sess_001",
  "source_app": "host_runtime",
  "source_module": "host_runtime_core",
  "actor": "user",
  "kind": "message",
  "raw_text": "We paused this because agent coordination was brittle.",
  "normalized_text": "paused because agent coordination was brittle",
  "structured_payload": {},
  "hints": {
    "entities": ["agent coordination"],
    "relations": [],
    "episode_hint": "coordination-debugging"
  },
  "scores": {
    "importance": 0.81,
    "confidence": 0.93
  },
  "idempotency_key": "host-turn-441"
}

Allowed base kinds in v1:
message, tool_call, tool_result, decision, failure, fact_assertion, state_update, summary, note, system, checkpoint

7.4 Entity

A canonical semantic node.

{
  "entity_id": "ent_coordination",
  "scope": { "...": "..." },
  "canonical_name": "agent coordination",
  "entity_type": "concept",
  "aliases": ["coordination", "agent harmony"],
  "first_seen": "...",
  "last_seen": "..."
}
7.5 Relation

A graph edge grounded in event evidence.

{
  "relation_id": "rel_001",
  "scope": { "...": "..." },
  "src_entity_id": "ent_project_x",
  "relation_type": "blocked_by",
  "dst_entity_id": "ent_coordination_brittleness",
  "confidence": 0.87,
  "first_seen": "...",
  "last_seen": "...",
  "derivation_version": 1
}

Small relation vocabulary in v1:
mentions, belongs_to, uses, depends_on, causes, blocked_by, prefers, decides, failed_due_to, related_to, contradicts, supersedes

7.6 Claim

This replaces the old fact object.

That change matters. Editorial memory needs room for uncertainty.

A claim is a memory-worthy proposition that may be candidate, remembered, disputed, or superseded.

{
  "claim_id": "clm_001",
  "scope": { "...": "..." },
  "subject_entity_id": "ent_host_runtime",
  "predicate": "is_for",
  "object_text": "personal use, not a marketable tool",
  "canonical_claim": "This system is for personal use, not a marketable tool.",
  "confidence": 1.0,
  "evidence_count": 1,
  "pinned": true,
  "first_seen": "...",
  "last_seen": "...",
  "derivation_version": 1
}

A remembered fact is just a claim whose editorial state is remembered.

7.7 Episode

A temporal arc.

{
  "episode_id": "ep_001",
  "scope": { "...": "..." },
  "title": "coordination-debugging",
  "status": "open",
  "start_at": "...",
  "end_at": null,
  "summary_text": "",
  "dominant_entities": ["agent coordination", "runtime stability"],
  "confidence": 0.72
}

Episodes represent:

debugging runs
design arcs
planning threads
failure loops
research sequences
decision chains
7.8 StateLease

Temporary operational state with expiry.

{
  "lease_id": "lease_001",
  "scope": { "...": "..." },
  "lease_key": "planner_context",
  "value_json": { "goal": "design Solaris", "phase": "revised v1" },
  "issued_at": "...",
  "refreshed_at": "...",
  "expires_at": "...",
  "status": "active"
}

State is not enduring memory. It is temporary continuity.

7.9 EditorialDecision

This is the major addition.

It records why Solaris chose to remember, reinforce, fade, or retire something.

{
  "decision_id": "ed_001",
  "artifact_type": "claim",
  "artifact_id": "clm_001",
  "action": "promote",
  "policy_profile": "operator_personal_v1",
  "scores": {
    "consequence": 0.9,
    "future_utility": 0.9,
    "identity_relevance": 0.8,
    "recurrence": 0.3
  },
  "rationale": {
    "summary": "Core identity-level project definition; explicit user statement."
  },
  "supporting_event_ids": ["evt_001"],
  "decided_by": "rule_engine",
  "decided_at": "..."
}

Allowed actions in v1:
promote, reinforce, leave_candidate, fade, pin, retire, mark_disputed, mark_superseded

8. Editorial state model

Instead of baking editorial fields into every artifact table, Solaris v1 uses a generic per-artifact editorial state.

8.1 ArtifactEditorialState
{
  "artifact_type": "claim",
  "artifact_id": "clm_001",
  "scope": { "...": "..." },
  "remember_state": "remembered",
  "activation_state": "active",
  "review_status": "reviewed",
  "remember_score": 0.88,
  "influence_score": 0.79,
  "pinned": true,
  "protected": false,
  "last_reviewed_at": "...",
  "next_review_at": null,
  "policy_profile": "operator_personal_v1",
  "policy_version": 1,
  "rationale_json": {}
}

remember_state:
candidate, remembered, disputed, superseded, retired

activation_state:
active, dormant, suppressed

review_status:
pending, reviewed

This separation is essential:

a claim may be remembered + dormant
a relation may be candidate + suppressed
an event may be archived only and never promoted
9. Storage schema

Here is the revised v1 schema shape.

sessions
events
entities
relations
claims
episodes
episode_events
state_leases
artifact_evidence
event_entities
event_embeddings
artifact_editorial_state
editorial_decisions
review_queue
sessions

Generic session boundaries with scope and policy profile.

events

Canonical raw archive.

entities

Semantic nodes.

relations

Derived graph edges.

claims

Derived propositions; not assumed true merely because they exist.

episodes

Temporal arcs.

episode_events

Join table linking episodes to source events.

state_leases

Short-lived continuity objects.

artifact_evidence

Links any artifact back to its supporting events.

event_entities

Entity mentions per event.

event_embeddings

Optional vector storage.

artifact_editorial_state

Remember/activate/review status for each artifact.

editorial_decisions

The explicit editorial log.

review_queue

Artifacts awaiting editorial review.

9.1 Minimal field sets

The important new tables are these.

artifact_editorial_state
artifact_type
artifact_id
tenant
namespace
workspace
project
remember_state
activation_state
review_status
remember_score
influence_score
pinned
protected
last_reviewed_at
next_review_at
policy_profile
policy_version
rationale_json
updated_at
editorial_decisions
decision_id
artifact_type
artifact_id
action
policy_profile
policy_version
scores_json
rationale_json
supporting_event_ids_json
decided_by
decided_at
review_queue
review_id
artifact_type
artifact_id
scope_fields...
trigger
priority
status
not_before
created_at
reviewed_at
10. Policy model

Solaris stays project-agnostic by letting clients supply policy profiles instead of hardcoding importance.

A policy profile in v1 is a named config loaded by the server and referenced by sessions and review calls.

10.1 Policy profile shape
{
  "name": "operator_personal_v1",
  "version": 1,
  "factor_weights": {
    "consequence": 0.20,
    "recurrence": 0.15,
    "identity_relevance": 0.15,
    "future_utility": 0.15,
    "unresolvedness": 0.10,
    "novelty": 0.10,
    "user_emphasis": 0.10,
    "anti_repeat_value": 0.05
  },
  "kind_biases": {
    "decision": 0.25,
    "failure": 0.25,
    "fact_assertion": 0.20,
    "summary": 0.10,
    "message": 0.00,
    "state_update": -0.20
  },
  "promotion_threshold": 0.70,
  "reinforce_threshold": 0.55,
  "retire_threshold": 0.20,
  "protected_subjects": [],
  "default_recall_mode": "default"
}

This lets different projects use Solaris differently without changing the core.

11. Ingestion and review flow

This is the revised flow.

11.1 On ingest

Solaris does four things immediately:

validates and normalizes the event
persists the raw event
derives candidate artifacts
records evidence links

At this stage, most derived artifacts are candidates, not remembered memory.

Exceptions:

explicit pinned fact_assertion
direct manual editorial actions
state leases
11.2 Candidate creation

Derived entities, relations, claims, and episodes are created with:

remember_state = candidate
activation_state = suppressed
review_status = pending

They are retrievable in deep mode, but not treated as stable memory yet.

11.3 Review triggers

Artifacts get pushed to the review queue when one of these happens:

session close
episode close
explicit fact_assertion
decision event
failure event
contradiction detected
repeated mention across distinct events
high-importance/high-confidence event
manual review request

This is where editorial judgment happens.

11.4 Editorial review

A review pass computes factor scores using the active policy profile.

Core factors in v1:

consequence: did this alter later actions?
recurrence: does it recur?
identity relevance: does it affect the system, user, project, or role over time?
future utility: would losing it be costly?
unresolvedness: is it still live?
novelty: did it introduce a new pattern?
user emphasis: was it explicitly marked or strongly stated?
anti-repeat value: does remembering it prevent repeated mistakes?

The output is a remember_score.

11.5 Editorial actions

Based on score and policy, Solaris takes one of these actions:

promote → candidate becomes remembered
reinforce → remembered artifact gains evidence and influence
leave_candidate → retained but not yet remembered
fade → influence reduced, often leading to dormancy
retire → no longer returned in normal mode
mark_disputed
mark_superseded
pin

Each action writes an editorial_decision.

11.6 Activation and dormancy

Editorial remembrance and activation are separate.

An artifact can be remembered but dormant.

Influence is controlled by:

editorial decisions
recency
relevance
policy
resolution status
pin/protection flags

State leases do not become dormant; they simply expire.

12. Derivation rules

These stay conservative in v1.

12.1 Entities

Priority:

adapter hints
structured payload
simple extractor over normalized text

No aggressive ontology building in v1.

12.2 Relations

Priority:

adapter hints
rule patterns
fallback related_to
12.3 Claims

Rules:

pinned fact_assertion → remembered immediately
unpinned assertion → candidate claim
repeated same claim across 2+ distinct events → promote candidate
contradiction against remembered claim → mark disputed
newer pinned claim may supersede older disputed claim
12.4 Episodes

An event joins an episode if:

adapter supplies episode_hint
same session and strong entity overlap within 20 minutes
same task-like thread across 3+ events

Episode closure:

session closes
time gap > 20 minutes
topic shift persists across 3 events
adapter explicitly closes

Episodes are candidate memory until reviewed.

13. Retrieval model

The retrieval system now uses relevance + editorial state.

13.1 Recall modes
default

Prefer remembered, active artifacts and live state. Candidate items only appear when highly relevant.

deep

Include candidates and dormant items more liberally.

archive

Bias toward raw events and provenance, with minimal editorial filtering.

This is important because not every use case wants the same memory surface.

13.2 Query input
{
  "query": "why did we pause agent coordination work?",
  "scope": {
    "tenant": "personal",
    "namespace": "host",
    "workspace": "default",
    "project": "core"
  },
  "scope_mode": "local",
  "recall_mode": "default",
  "modes": ["state", "claims", "episodes", "events", "graph"],
  "budget": {
    "state": 3,
    "claims": 5,
    "episodes": 3,
    "events": 8,
    "entities": 6,
    "relations": 10
  },
  "include_explanations": true
}
13.3 Scoring

Solaris v1 uses two scores.

base relevance

Built from:

semantic similarity
lexical match
scope proximity
recency
importance
confidence
editorial modifier

Built from:

remember state
activation state
remember score
influence score
pin/protection bonuses
dispute/retire penalties

A remembered dormant claim should beat a weak candidate.
A pinned claim should beat both.
A retired artifact should generally stay out of default recall.

13.4 Retrieval bundle
{
  "claims": [],
  "state_leases": [],
  "episodes": [],
  "events": [],
  "entities": [],
  "relations": [],
  "explanations": []
}

Each returned artifact carries:

provenance
editorial state
scores
why it was included

That lets the client decide what to inject into prompt context.

14. MCP tools

Since the server is Solaris, the tool namespace should be solaris.*.

14.1 solaris.open_session

Open a generic session.

14.2 solaris.close_session

Close a session and finalize episode windows.

14.3 solaris.ingest_events

Persist canonical events and derive candidate artifacts.

14.4 solaris.upsert_state

Create or refresh a temporary state lease.

14.5 solaris.query

Return a structured retrieval bundle.

14.6 solaris.timeline

Return a time-ordered trace for a scope, entity, or episode.

14.7 solaris.entity

Resolve an entity and its neighborhood.

14.8 solaris.explain

Show provenance and editorial history for any artifact.

14.9 solaris.get_review_queue

Return pending review items for a scope/session.

Input:

{
  "scope": { "...": "..." },
  "session_id": "sess_001",
  "limit": 50
}
14.10 solaris.run_editorial_review

Run a review pass.

Input:

{
  "scope": { "...": "..." },
  "session_id": "sess_001",
  "policy_profile": "operator_personal_v1",
  "limit": 100,
  "mode": "boundary"
}

Output:

{
  "ok": true,
  "decisions_created": 14,
  "promoted": 4,
  "reinforced": 3,
  "left_candidate": 5,
  "faded": 2
}
14.11 solaris.apply_editorial_decision

Manual override.

Input:

{
  "artifact_type": "claim",
  "artifact_id": "clm_001",
  "action": "pin",
  "rationale": {
    "summary": "User explicitly wants this kept as enduring memory."
  }
}

This tool is important. Editorial judgment should support both automatic and manual curation.

15. Host adapter, revised

The host adapter should stay thin and policy-aware.

Session mapping
runtime start → solaris.open_session(kind="runtime")
wake start → solaris.open_session(kind="interaction", parent=runtime)
wake end → solaris.close_session(interaction) then solaris.run_editorial_review(...)
runtime shutdown → solaris.close_session(runtime) then solaris.run_editorial_review(...)
Turn ingestion

For each committed turn:

emit one canonical message event
include raw / normalized / interpreted payload in structured form
keep native IDs as idempotency keys
Explicit remember commands
emit fact_assertion
set pin hint or call solaris.apply_editorial_decision(action="pin")
Tooling
tool invocation → tool_call
tool result → tool_result
Decisions and failures

Whenever the host runtime can detect them:

architecture choices, selected routes, confirmed actions → decision
blocked attempts, repeated errors, abandoned paths → failure
Temporary continuity

Map these to state_leases:

work session
planner state
codebase investigation state
Existing summaries

Emit summary events, but summaries stay derived conveniences, not truth sources.

Most importantly: the adapter supplies a policy profile like operator_personal_v1, so Solaris remembers in a style aligned with the host runtime without hardcoding host-specific semantics into the core.

16. Build plan for v1

This revised v1 is still buildable if it is staged properly.

Phase A: archive and scope

Build:

sessions
events
scope model
idempotent ingest
FTS
optional embeddings
Phase B: derivation

Build:

entities
relations
claims
episodes
state leases
evidence links
Phase C: editorial layer

Build:

artifact editorial state
review queue
editorial decisions
policy profiles
review engine
manual override path
Phase D: retrieval

Build:

query modes
default/deep/archive recall
bundle output
explain tool
Phase E: host shadow mode

Plug it in without replacing current memory reads.

That keeps the project honest.

17. What ships in revised v1

Revised v1 is complete only if all of this exists:

canonical event archive
strict scope isolation
claim/episode/relation derivation
temporary state leases
evidence/provenance links
review queue
editorial decisions
remember vs activate separation
default/deep/archive query modes
explainable retrieval
Host adapter in shadow mode

That is the actual cut line.

18. What is explicitly out of scope for v1

These are later:

replacing host-runtime production memory reads
freeform LLM self-reflection on every turn
autonomous background review daemons
destructive forgetting workflows
multi-user shared memory federation
UI dashboard
advanced contradiction arbitration across long histories
graph reasoning beyond local neighborhoods
automatic prompt injection policies inside Solaris itself

v1 needs a clean editorial substrate, not a whole synthetic psyche.

19. Acceptance criteria

Revised Solaris v1 is done when:

raw events are always recoverable
duplicate ingests do not create duplicate artifacts
candidate artifacts can be reviewed into remembered, dormant, disputed, superseded, or retired states
explicit pinning works
default queries prefer remembered active artifacts
deep queries can surface candidates and dormant material
archive queries can reconstruct the underlying trail
every promoted memory can be explained through evidence and editorial decisions
expired state leases stop behaving like memory
A host runtime can run beside Solaris without replacing current behavior
20. The revised one-line definition

This is the version worth keeping:

Solaris is a project-agnostic memory substrate that archives broadly, derives structure cautiously, remembers selectively through editorial judgment, and activates memory sparingly according to scope, policy, and relevance.
---------------------------------------------------
Here is the buildable Solaris v1 repo shape and the implementation checklist in build order.

Repository skeleton
solaris/
├─ pyproject.toml
├─ README.md
├─ .env.example
├─ .gitignore
├─ policies/
│  ├─ default_v1.json
│  └─ operator_personal_v1.json
├─ migrations/
│  ├─ 001_init.sql
│  ├─ 002_fts.sql
│  └─ 003_editorial.sql
├─ docs/
│  ├─ architecture.md
│  ├─ event_schema.md
│  ├─ query_contract.md
│  ├─ editorial_model.md
│  └─ host_adapter_notes.md
├─ src/
│  └─ solaris/
│     ├─ __init__.py
│     ├─ config.py
│     ├─ server.py
│     ├─ ids.py
│     ├─ clock.py
│     ├─ errors.py
│     ├─ logging.py
│     │
│     ├─ models/
│     │  ├─ __init__.py
│     │  ├─ common.py
│     │  ├─ scope.py
│     │  ├─ session.py
│     │  ├─ event.py
│     │  ├─ graph.py
│     │  ├─ claim.py
│     │  ├─ episode.py
│     │  ├─ state.py
│     │  ├─ editorial.py
│     │  └─ query.py
│     │
│     ├─ storage/
│     │  ├─ __init__.py
│     │  ├─ db.py
│     │  ├─ migrate.py
│     │  ├─ fts.py
│     │  ├─ embeddings.py
│     │  └─ repos/
│     │     ├─ __init__.py
│     │     ├─ sessions.py
│     │     ├─ events.py
│     │     ├─ entities.py
│     │     ├─ relations.py
│     │     ├─ claims.py
│     │     ├─ episodes.py
│     │     ├─ state_leases.py
│     │     ├─ editorial.py
│     │     └─ evidence.py
│     │
│     ├─ derive/
│     │  ├─ __init__.py
│     │  ├─ entities.py
│     │  ├─ relations.py
│     │  ├─ claims.py
│     │  ├─ episodes.py
│     │  ├─ state.py
│     │  └─ pipeline.py
│     │
│     ├─ editorial/
│     │  ├─ __init__.py
│     │  ├─ policy.py
│     │  ├─ factors.py
│     │  ├─ scoring.py
│     │  ├─ queue.py
│     │  ├─ actions.py
│     │  └─ engine.py
│     │
│     ├─ retrieval/
│     │  ├─ __init__.py
│     │  ├─ search.py
│     │  ├─ graph.py
│     │  ├─ ranking.py
│     │  ├─ bundle.py
│     │  ├─ timeline.py
│     │  └─ explain.py
│     │
│     ├─ services/
│     │  ├─ __init__.py
│     │  ├─ sessions.py
│     │  ├─ ingest.py
│     │  ├─ review.py
│     │  ├─ query.py
│     │  ├─ entity.py
│     │  ├─ timeline.py
│     │  └─ explain.py
│     │
│     ├─ mcp_tools/
│     │  ├─ __init__.py
│     │  ├─ sessions.py
│     │  ├─ ingest.py
│     │  ├─ state.py
│     │  ├─ query.py
│     │  ├─ entity.py
│     │  ├─ timeline.py
│     │  ├─ explain.py
│     │  └─ editorial.py
│     │
│     └─ adapters/
│        ├─ __init__.py
│        └─ base.py
│
├─ tests/
│  ├─ conftest.py
│  ├─ test_scope_isolation.py
│  ├─ test_idempotent_ingest.py
│  ├─ test_entity_derivation.py
│  ├─ test_claim_promotion.py
│  ├─ test_episode_grouping.py
│  ├─ test_state_expiry.py
│  ├─ test_editorial_review.py
│  ├─ test_query_modes.py
│  └─ test_explainability.py
│
└─ examples/
   ├─ sample_events.jsonl
   └─ host_runtime_mapping.md
What each part owns
Root

pyproject.toml
Use a small stack. Python, Pydantic, MCP SDK, numpy, pytest. Avoid ORM in v1.

policies/*.json
This is where Solaris stays project-agnostic while still letting clients have different memory styles.

migrations/*.sql
Keep schema plain and inspectable.

docs/
Write the contracts down once so the adapter and server do not drift.

src/solaris/config.py

One settings object:

DB path
embedding provider toggle
default policy profile
FTS enabled
max query budgets
log level
src/solaris/ids.py

Use sortable IDs, preferably ULIDs.
Events, sessions, claims, episodes, decisions all benefit from stable sortable IDs.

src/solaris/clock.py

Injectable clock for tests.
This matters because state expiry and dormancy are time-driven.

src/solaris/models/

These are Pydantic models, not DB models.

common.py

enums: artifact types, remember states, activation states, session kinds, recall modes

scope.py

ScopeRef
ScopeMode

session.py

SessionRecord
OpenSessionRequest
CloseSessionRequest

event.py

MemoryEvent
EventHintSet
IngestEventsRequest
IngestEventsResult

graph.py

Entity
Relation

claim.py

Claim

episode.py

Episode

state.py

StateLease
UpsertStateRequest

editorial.py

ArtifactEditorialState
EditorialDecision
ReviewQueueItem
RunEditorialReviewRequest
ApplyEditorialDecisionRequest

query.py

QueryRequest
QueryBudget
QueryBundle
TimelineRequest
EntityRequest
ExplainRequest
src/solaris/storage/

No ORM. Use sqlite3 with thin repositories.

db.py

connection factory
WAL mode
transaction context manager

migrate.py

applies SQL migrations in order

fts.py

FTS5 insert/update helpers
lexical search

embeddings.py

provider interface
embed(texts) stub
storage/read helpers
safe no-op mode when embeddings are disabled

repos/sessions.py

create, close, get

repos/events.py

insert events
find by scope/time
idempotency check

repos/entities.py

upsert entity
resolve by canonical name/alias

repos/relations.py

upsert relation
fetch neighborhood

repos/claims.py

create/update claims
fetch by canonical claim or subject/predicate

repos/episodes.py

create/update episodes
add event membership
close episode

repos/state_leases.py

upsert lease
expire leases
list active leases

repos/editorial.py

read/write editorial state
enqueue review item
insert editorial decision

repos/evidence.py

link any artifact back to event ids
src/solaris/derive/

This is rule-based in v1.

entities.py

prefer adapter hints
fallback to simple extractor
merge by normalized name + scope

relations.py

prefer adapter relation hints
fallback patterns like blocked_by, depends_on, failed_due_to
otherwise related_to

claims.py

convert fact_assertion, repeated propositions, and strong statements into candidate claims

episodes.py

group events into arcs by session, overlap, time gap, and optional episode_hint

state.py

normalize state_update events into StateLease

pipeline.py

orchestrates derivation after raw event persistence
src/solaris/editorial/

This is the new heart of Solaris.

policy.py

load policy profiles from JSON
expose weight maps and thresholds

factors.py

compute:
consequence
recurrence
identity relevance
future utility
unresolvedness
novelty
user emphasis
anti-repeat value

scoring.py

turn factors + policy into remember_score and influence_score

queue.py

enqueue review items from triggers
pop pending items for scope/session

actions.py

apply promote, reinforce, fade, retire, pin, mark_disputed, mark_superseded

engine.py

run the review pass
write editorial decisions
update artifact editorial state
src/solaris/retrieval/

search.py

FTS search
embedding similarity if available
time-window event search

graph.py

entity neighborhood lookup
relation traversal depth 1 only in v1

ranking.py

combine base relevance with editorial modifiers

bundle.py

assemble final response bundle:
claims
state leases
episodes
events
entities
relations
explanations

timeline.py

return time-ordered slices for scope/entity/episode

explain.py

provenance trace
editorial decision history
supporting events
src/solaris/services/

These orchestrate the repos and domain logic.

sessions.py

open/close session
session boundary hooks

ingest.py

validate event
persist raw event
run derivation pipeline
enqueue review triggers

review.py

run editorial engine for a scope/session

query.py

gather candidates
rank them
build bundle

entity.py

resolve one entity with neighborhood + support

timeline.py

scope/entity/episode timeline retrieval

explain.py

artifact explanation service
src/solaris/mcp_tools/

Thin wrappers only.
No business logic here.

Map directly to:

solaris.open_session
solaris.close_session
solaris.ingest_events
solaris.upsert_state
solaris.query
solaris.entity
solaris.timeline
solaris.explain
solaris.get_review_queue
solaris.run_editorial_review
solaris.apply_editorial_decision
src/solaris/server.py

Boot sequence:

load config
migrate DB
initialize services
register MCP tools
expose server
src/solaris/adapters/base.py

Only the contract lives here.

class ClientAdapter(Protocol):
    def open_session_events(self, native_obj) -> list[dict]: ...
    def close_session_events(self, native_obj) -> list[dict]: ...
    def map_turn(self, native_turn) -> dict: ...
    def map_state_update(self, native_state) -> dict: ...

The actual host hook code belongs in the host runtime repo, not Solaris core.

Core service interfaces

These are the concrete interfaces I would code first.

class SessionService:
    def open_session(self, req: OpenSessionRequest) -> SessionRecord: ...
    def close_session(self, req: CloseSessionRequest) -> dict: ...

class IngestService:
    def ingest_events(self, req: IngestEventsRequest) -> IngestEventsResult: ...

class ReviewService:
    def run_review(
        self,
        scope: ScopeRef,
        session_id: str | None,
        policy_profile: str,
        limit: int = 100,
        mode: str = "boundary",
    ) -> dict: ...

class QueryService:
    def query(self, req: QueryRequest) -> QueryBundle: ...

class ExplainService:
    def explain(self, req: ExplainRequest) -> dict: ...

That gives the whole repo a stable center.

End-to-end runtime flow

This is the exact Solaris v1 path.

1. A client opens a session

solaris.open_session

2. The client sends events

solaris.ingest_events

For each event:

validate
enforce scope
idempotency check
persist raw event
index into FTS
optionally embed
derive entities / relations / claims / episodes / state
link evidence
enqueue review items when triggered
3. A boundary occurs

Wake end, runtime shutdown, task boundary, or explicit checkpoint.

solaris.run_editorial_review

This:

pulls pending review items
scores them using the active policy
updates editorial states
logs EditorialDecisions
4. The client queries memory

solaris.query

This:

pulls candidates by scope and recall mode
ranks using relevance + editorial state
returns a structured bundle
5. The client can inspect why something exists

solaris.explain

This:

shows supporting event ids
shows editorial decision history
shows current remember/activation state
Implementation order

This order matters. Build it in this order and do not skip ahead.

Phase 1 — bootstrap and raw archive
Files to create first
config.py
ids.py
clock.py
models/scope.py
models/session.py
models/event.py
storage/db.py
storage/migrate.py
migrations/001_init.sql
repos/sessions.py
repos/events.py
services/sessions.py
services/ingest.py
mcp_tools/sessions.py
mcp_tools/ingest.py
server.py
Done when
session open/close works
raw event ingest works
idempotency works
scope is stored correctly
event retrieval from DB works
Hard rule

At the end of Phase 1, Solaris must already be useful as an event archive.

Phase 2 — lexical retrieval and state leases
Files
migrations/002_fts.sql
storage/fts.py
models/state.py
repos/state_leases.py
derive/state.py
services/query.py
mcp_tools/state.py
mcp_tools/query.py
Done when
FTS search works
active state leases can be upserted
expired state leases stop showing as active
solaris.query can return raw event slices + state

At this stage, the system is primitive but already testable.

Phase 3 — entities, relations, evidence
Files
models/graph.py
repos/entities.py
repos/relations.py
repos/evidence.py
derive/entities.py
derive/relations.py
derive/pipeline.py
Done when
event ingest creates entities
relation derivation works conservatively
every entity/relation can be traced back to supporting events

This is where Solaris stops being just a searchable log.

Phase 4 — claims and episodes
Files
models/claim.py
models/episode.py
repos/claims.py
repos/episodes.py
derive/claims.py
derive/episodes.py
Done when
fact_assertion creates claims
repeated claim evidence reinforces claims
episodes can open, grow, and close
episode membership is explainable

Do not promote everything into remembered memory yet. Just get candidates right.

Phase 5 — editorial layer
Files
migrations/003_editorial.sql
models/editorial.py
repos/editorial.py
editorial/policy.py
editorial/factors.py
editorial/scoring.py
editorial/queue.py
editorial/actions.py
editorial/engine.py
services/review.py
mcp_tools/editorial.py
Done when
artifacts can be candidate, remembered, dormant, disputed, superseded, retired
review queue gets populated by triggers
review run creates editorial decisions
pinning and manual overrides work

This is the point where Solaris becomes Solaris.

Phase 6 — ranked retrieval and explanation
Files
retrieval/search.py
retrieval/graph.py
retrieval/ranking.py
retrieval/bundle.py
retrieval/timeline.py
retrieval/explain.py
services/entity.py
services/timeline.py
services/explain.py
mcp_tools/entity.py
mcp_tools/timeline.py
mcp_tools/explain.py
Done when
default, deep, and archive recall modes work
editorial state affects ranking
solaris.explain shows both provenance and editorial history
solaris.timeline works for scope or entity
Phase 7 — host adapter in shadow mode

This stays outside Solaris core.

Host-side mapping
runtime start → solaris.open_session(kind="runtime")
wake start → solaris.open_session(kind="interaction", parent=runtime)
wake end → solaris.close_session(interaction) then solaris.run_editorial_review(...)
runtime shutdown → solaris.close_session(runtime) then solaris.run_editorial_review(...)
Turn mapping

Each committed turn becomes one canonical message event with:

raw_text
normalized_text
structured_payload.interpreted
native ids as idempotency_key

Do not create three separate canonical events for raw, normalized, and interpreted versions.

Explicit remember

Emit fact_assertion, then either:

set a pin hint, or
call solaris.apply_editorial_decision(action="pin")
Temporary continuity

Map these to StateLease:

work session
planner state
codebase investigation state
Important note

Do not import the host runtime’s current graph as truth into Solaris.
At most, pass it as hints. Solaris should derive its own graph from canonical events.

Host hook points

From the architecture you described, these are the clean insertion points.

host_runtime_core.py

Use for:

session open/close calls
committed turn ingest
wake-session end review trigger
runtime shutdown review trigger
host_runtime_training_log.py

Use for:

packing raw, normalized, and interpreted material into the structured payload of one event
host_runtime_domains/memory.py and host_runtime_memory.py

Use for:

explicit remember flows
auto-promotion events becoming claim candidates rather than immediate truths
host_runtime_episodes.py

Use for:

episode hints
summary events
not as authoritative truth
host_runtime_work_session.py
host_runtime_planner.py
host_runtime_codebase.py

Use for:

solaris.upsert_state
host_runtime_interpreted_turns.py

Use as:

a legacy reference during comparison
not the canonical Solaris archive
First test run

This is the first realistic end-to-end test I would run.

Scenario
Open runtime session
Open interaction session
Ingest:
user message: “Solaris is a memory substrate”
user message: “Memory without forgetting well is just accumulation”
assistant message: “Solaris should separate keep, remember, activate”
user message: “This system is for me, not a marketable tool”
state update: planner context
decision event: “Build Solaris as a sidecar MCP”
Close interaction session
Run editorial review
Query:
“what are we building?”
“what should Solaris remember?”
“why is this system personal-use?”
Explain returned claim or decision
Expected bundle

For “what are we building?”:

remembered claim about Solaris being a memory substrate
remembered decision about sidecar MCP
active planner state lease
current episode about Solaris architecture
supporting raw events

That is the first real acceptance gate.

Tests that matter most

Start with these and do not skip them.

test_scope_isolation.py
A query in one project must not surface another project’s artifacts in local mode.

test_idempotent_ingest.py
Same source app + same idempotency key = no duplicate event/artifact explosion.

test_claim_promotion.py
Pinned assertions become remembered immediately. Repeated unpinned claims get promoted later.

test_episode_grouping.py
Close temporal/topic clusters form an episode. Topic shift breaks them.

test_state_expiry.py
Expired state lease disappears from active recall.

test_editorial_review.py
Review creates a decision and updates remember/activation states.

test_query_modes.py
Default mode prefers remembered active artifacts. Deep mode surfaces candidates and dormant artifacts. Archive mode is raw-heavy.

test_explainability.py
Every returned claim/relation/episode can be traced back to event evidence.

What not to build in the first pass

Do not burn time on these early:

UI dashboard
graph database
autonomous review daemon
complex contradiction resolver
multi-user federation
heavy LLM extraction on every turn
replacing host-runtime production reads

The first win is a credible shadow memory engine, not a total memory takeover.

Minimal v1 cut line

Solaris v1 is real when all of this is true:

canonical events are persisted reliably
scope boundaries are enforced
entities, relations, claims, episodes, and state leases are derived
editorial review exists
remembered vs candidate vs dormant is real
query modes work
explanations work
A host runtime can write to Solaris in shadow mode without changing its current memory behavior
