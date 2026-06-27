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
- **dump** — the agent sees the whole transcript of the current session (the hoard)
- **smriti** — the **agent curates its own memory** (a curation step guided by the
  four rules → JSON → `smriti`), then reads the index + the bodies `recall` surfaces

Grading is deterministic: each probe's correct answer is a known string — no LLM
judge. The scorecard reports success, **real tokens + latency** (from the backend),
and the final **store size** for smriti — the anti-hoard measure.

Needs covered: **cross-session persistence** (a probe after the transcript is
gone), **precision under heavy noise**, **update / contradiction**. (Link recall
is proven deterministically in Stage 0.) The earlier fixed-policy version (which
isolated *reading* from *curation*) is in git history.

### Running it

The default `echo` model is a zero-token wiring check (it can't curate, so the
smriti arm needs a real backend). Pick one — both are stdlib-only on the harness side:

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

### Result (mistral:latest, local, agent-curated)

| arm | success | input tokens | store |
|---|---|---|---|
| none | 0% | 1,177 | — |
| dump | 75% | 3,507 | — |
| smriti | **100%** | 6,642 | 13 |

**The win is real and earned: smriti 100% vs dump 75%.** The gap is
**cross-session persistence** — in a later session the transcript is gone, so
`dump` structurally fails it; smriti's files survive on disk. That is the one
thing a transcript fundamentally cannot do.

**Honest limits (reported, not hidden):**

- **Curation hoards.** `store` ended at 13 (ideal ~7); under five distractors it
  kept five. The filter is only as good as the curator, and a small local model
  curates loosely. A better-instructed / larger model should stay leaner.
- **Cost is length-dependent.** Here smriti spent *more* input tokens (6,642 vs
  3,507): curation overhead plus a bloated index, on conversations too short for
  `dump`'s transcript to balloon. smriti's cost advantage shows up in *long*
  sessions, not short ones.

The takeaway: memory-as-files buys what a transcript can't (it outlives the
session); the value of the *filter* depends on who's curating.
