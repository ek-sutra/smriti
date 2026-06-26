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

`python bench/agent_ab.py`

Plays an agent through multi-turn scenarios where a later turn's correct answer
depends on an earlier one, under three arms:

- **none** — the agent sees only the current turn (the floor)
- **dump** — the agent sees the entire transcript (the hoard)
- **smriti** — the agent sees smriti's compressed index, written via a fixed policy

Grading is deterministic: each scenario plants a seed and a later probe whose
correct answer is a known string — no LLM judge. The scorecard reports success
rate and context size per arm.

**v1 scope (council decision):** writes are harness-managed (a fixed curation
policy), so we isolate the variable — what the agent *reads*. Whether an LLM
*curates* well is v2. This tests retrieval-in-context, not curation.

### Running it

The default `echo` model is a zero-token stand-in that proves the wiring (arms
differ, scoring works) without an API key. It already shows the shape:
`none` 0% · `dump` 100% · `smriti` 100% at ~16% of `dump`'s context size.

For a real-model result, pick a backend — both are stdlib-only on the harness side:

```bash
# Local model via Ollama (no API key, runs on your hardware)
export SMRITI_BENCH_BACKEND=ollama
export SMRITI_BENCH_MODEL=mistral:latest   # any installed model
python bench/agent_ab.py

# Or the Anthropic API
pip install anthropic
export SMRITI_BENCH_BACKEND=anthropic
export SMRITI_BENCH_MODEL=claude-haiku-4-5
export ANTHROPIC_API_KEY=...
python bench/agent_ab.py
```

The bar: **smriti ≈ `dump` on success, ≈ `none` on cost, flat where `dump`
explodes.** The `update / contradiction` scenario is the sharp one — `dump` holds
both the old and new value and must infer the latest, while smriti overwrote it.

### Result (mistral:latest, local via Ollama)

| arm | success | context chars |
|---|---|---|
| `none` | 25% (1/4) | 4,899 |
| `dump` | 100% (4/4) | 22,963 |
| `smriti` | 100% (4/4) | 8,646 |

smriti matched the full-transcript hoard on success at ~38% of its context, and
beat no-memory 4×. Honest caveat: `none`'s one pass was the preference probe
(the model defaults to Postgres anyway — its prior, not memory). On the three
un-guessable facts (name, Cedar, gRPC) `none` scored 0/3 and `smriti` 3/3 —
memory doing real work. Run on a 7B local model, no vendor.

### Not yet covered (v2)

- **Agent-driven curation** — let the LLM decide what to `write` (tests the filter).
- **Real token + latency** — capture `usage` from the API, not just context chars.
- **More needs** — precision under heavy noise, cross-session persistence, link recall.
