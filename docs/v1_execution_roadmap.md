# Solaris V1 Execution Roadmap

## Status

Solaris V1 is structurally implemented and operating as a real shadow memory substrate for a host runtime.

The major loop is now closed:

```text
archive -> derive -> review -> retrieve
```

The remaining work is finish-quality work:
- validating live usefulness
- continuing topical retrieval quality hardening
- documenting the now-real retrieval/eval surface

## Principles

- Do not replace host-runtime memory reads in one jump.
- Add Solaris read paths as shadow-context first, then compare, then promote.
- Preserve raw provenance when improving canonical text handling.
- Avoid broad rewrites when a narrow seam can unlock the next stage.

## Phase 1: Close The Read Loop

### 1.1 Wire `solaris.query` into live turn handling

Goal:
- Let a host runtime read Solaris during normal conversation turns without replacing the current memory stack.

Implementation:
- Add a conversation-only Solaris prompt-context provider.
- Query Solaris with small budgets and default recall mode.
- Inject the result as an additional memory section beside the existing host-runtime memory and episodic sections.
- Keep this additive and reversible.

Done when:
- `solaris.query` is called during live conversation handling.
- Solaris claims/events/state can influence LLM responses through prompt context.
- Existing host-runtime memory behavior still remains present.

Status:
- done

### 1.2 Make Solaris shadow-read inspectable

Goal:
- Make it obvious when Solaris contributed context.

Implementation:
- Include compact Solaris contribution metadata in turn/result metadata.
- Keep operator-visible logging optional and quiet by default.

Done when:
- We can inspect whether a turn used Solaris context without digging through the DB manually.

Status:
- done

## Phase 2: Preserve Better Source Truth

### 2.1 Fix canonical text provenance

Goal:
- Preserve raw utterance, normalized utterance, and interpreted text as distinct layers.

Implementation:
- Stop overwriting top-level event `raw_text` and `normalized_text` with interpreted text.
- Keep interpreted text in `structured_payload` or a dedicated field while preserving actual raw operator text at the event top level.
- Adjust query/display logic to prefer interpreted text only when explicitly useful, not as source truth.

Done when:
- Solaris events preserve actual raw utterance provenance.
- Editorial confidence can distinguish raw STT from interpreted meaning.

Status:
- done

## Phase 3: Learn From Tool Execution

### 3.1 Stop orphaning `tool_result`

Goal:
- Let Solaris derive useful memory from tool execution outcomes.

Implementation:
- Either expand claim derivation to include selected `tool_result` events, or emit a second learnable event kind when tool execution establishes a durable fact.
- Prioritize file reads, code inspection, and web-fetch outcomes that clearly establish knowledge.

Done when:
- Tool-derived knowledge can become candidate or remembered Solaris memory.

Status:
- done

## Phase 4: Improve Topic Formation

### 4.1 Strengthen topic-level memory without fake claims

Goal:
- Make broad queries like `what is Solaris` or `what do you remember about trading` return cleaner structured memory.

Implementation:
- Continue improving entity quality and topical retrieval.
- Promote repeated high-signal topic structures cautiously.
- Prefer topic entities/episodes when no trustworthy claim exists.

Done when:
- Topic queries are no longer mostly event-led noise.
- Solaris can surface stable topic structure without reintroducing junk remembered claims.

Status:
- in progress
- materially improved, but still the main quality frontier

## Phase 5: Editorial Maturity

### 5.1 Add contradiction handling

Goal:
- Automatically dispute or supersede incompatible claims.

Implementation:
- Detect obvious contradictions during review.
- Write `mark_disputed` / `mark_superseded` decisions automatically when evidence justifies it.

Status:
- partially implemented through temporal and manual editorial plumbing
- not yet mature as full automatic contradiction handling

### 5.2 Add runtime editorial steering

Goal:
- Make policy adjustable without code edits.

Implementation:
- Expose manual overrides and runtime threshold/profile changes more directly in host-runtime tooling.

Status:
- partial
- manual override path exists
- richer runtime steering remains future work

## Order Of Execution

1. Continue topic-formation and retrieval-quality improvements.
2. Expand and maintain the committed retrieval eval corpus.
3. Harden temporal and contradiction behavior.
4. Improve runtime editorial steering where operator control is useful.

## Current Focus

Now executing:
- retrieval and evaluation hardening
- topic-quality improvements
- final documentation of the retrieval surface and eval discipline
