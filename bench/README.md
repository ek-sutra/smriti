# bench — does smriti actually help an agent?

Memory only matters across time: a single call can't reveal it. So usefulness is
tested longitudinally — does an agent behave correctly on situations whose right
answer depends on earlier turns. Two stages, smallest falsifier first.

## Stage 0 — mechanics (here, deterministic, no LLM)

`python bench/mechanics.py`

Replays planted seed → probe sequences against `write` / `recall` / `prune` and
checks them against ground truth. Proves the retrieval and housekeeping claims:

- **recall + precision** — the right memory ranks first; a query for something
  never stored returns nothing (no false memory).
- **link synthesis** — a query that matches only a decision still pulls in the
  pattern it links to, and *only* because of the link.
- **update / overwrite** — the same hook updates in place; `created` is preserved.
- **prune health** — stale, duplicate, and broken-link memories are surfaced.
- **compression (cost)** — the index injected per turn is a fraction of the full
  store (measured ~17% on the planted set).

Exits nonzero on any failure, so it can gate CI. This proves the *plumbing* —
not that an agent is better off.

## Stage 1 — behavior (the brain, with an LLM)

The real test, not yet built. Run a Claude agent across multi-turn scenarios
under four arms — `none` · `window` · `dump` (full transcript) · `smriti` — and
score behavior and cost:

- **success@need** — when the past mattered, did it act right?
- **re-ask rate**, **contradiction rate**
- **context tokens per turn** — the cost claim, against `dump`
- **store size over time** — does it stay lean while `dump` grows unbounded?

The bar: **smriti ≈ `dump` on success, ≈ `none` on cost, flat where `dump`
explodes.** If smriti can't beat `none`, the idea is wrong; if it can't approach
`dump` cheaper, its selectivity is lossy. The whole loop is under test, including
the `write` step — storing the wrong things is a failure recall can't fix.
