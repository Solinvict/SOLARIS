# Maturity And Limitations

Solaris is ready to publish as a serious `alpha` / `research preview`.

That means the architecture is real, the implementation is live, and the behavior is tested enough to be useful. It does not mean every surface is polished or fully generalized.

## What Feels Mature

- append-only event archive
- derivation of claims, episodes, entities, relations, and state
- editorial review and reconsider flows
- scoped query and recall
- archive-vs-belief divergence
- graph-aware retrieval
- computed pattern projection
- proof and eval harnesses

## What Is Still Alpha

- public onboarding is new and still being tightened
- pattern ranking still has taste-level tuning room
- episode semantics are less mature than claim semantics
- SQLite write contention is handled, but it is still SQLite
- standalone UI is usable, not yet product-finished

## Known Design Boundaries

- Solaris is not a replacement for application reasoning
- projected patterns are not stored truth
- Solaris is optimized for provenance and inspectability, not minimum storage cost
- query behavior is stable enough to evaluate, but still evolving

## Current Rough Edges

- some graph and episode surfaces still need realism polish over time
- first-run or cold-start paths can be slower than warm queries
- integration-specific behavior may still differ across host systems
- the broader monorepo workspace contains context that is not part of the Solaris package itself

## How To Read This Project Correctly

Good framing:

- archive-grounded memory substrate
- editorial memory system
- graph-aware memory layer
- research-grade implementation with proof and eval artifacts

## License Posture

Solaris uses `MPL-2.0`.

That is a deliberate middle ground:

- people can use Solaris, integrate it, and build on it
- modifications to Solaris-covered files stay open
- the project can spread without letting the Solaris code itself quietly disappear into a closed fork

Bad framing:

- universal AGI memory
- plug-and-play black-box memory oracle
- fully productized persistence layer for everyone

## Release Recommendation

If you publish Solaris on GitHub today, the honest label is:

- `alpha`
- `research preview`
- `for serious builders`

That framing is a strength, not a weakness. Solaris is most valuable to people who care about memory honesty, provenance, and long-lived system continuity.
