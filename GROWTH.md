# Growing smriti

smriti is not architected toward a finished product. It is **grown** — small,
reusable pieces that all speak the same plain-text format, accumulated through
use, until a coherent whole emerges on its own. Our job is to *use it, test it,
and build the next piece that real friction names* — not to draw the final shape.

## The substrate

A growing set of small organs around one memory store — a reader/writer, a
viewer, a curator (forgetting), a recaller, adapters for other agents. Each is
independently useful. None depends on the others.

## The local rules — what lets the whole emerge

1. **The format is the only interface.** Every piece reads/writes the markdown
   store ([SPEC.md](SPEC.md)) — never a private database. Pieces compose with no
   coordination because they all speak the same files. (The narrow waist.)
2. **One piece, one job, near-zero dependencies.** Small enough to read in a
   sitting and replace in an afternoon.
3. **Independently useful; composable by accident.** A piece must stand alone.
   The whole is emergent, never required.
4. **Subtract.** A piece earns its place against real use, or it's pruned.
5. **Friction names the next piece.** We don't plan a roadmap. We build the one
   thing the latest use — or the latest test — made us wish for.

## The metabolism — the loop

```
   use smriti on real work     +     test it (bench/)
              │
              ▼
        friction surfaces
              │
              ▼
   name the smallest piece that resolves it
              │
              ▼
   build it (obey the rules) → re-test → repeat
```

The whole is not assembled — it accrues. Watch for the phase transition: the
moment the pieces start composing into something used without us assembling it.
Then tune; don't control.

## The pieces so far

- **`forgetting.py`** — honest forgetting. Removes *rot* (confidence decays with a
  per-type half-life → faded) and *redundancy* (near-identical hooks → keep the
  newest), and only when asked — archiving each removal to `.forgotten/log.md`
  (what + why), so forgetting is transparent and recoverable, never silent.
  Speaks the format, stands alone, stdlib only. (`test_forgetting.py`.)
- **`reinforce.py`** — the counterpart to forgetting. When a memory is *used*
  (recalled and acted on), refresh its `updated` stamp. Decay then measures
  time-since-last-*used*, not time-since-written — so use keeps a memory alive
  and disuse lets it fade. The spacing effect, in plain text. Rewrites only the
  `updated:` line; stands alone. (`test_temporal.py`.)

## A pruned piece — and why that's the loop working

**Organ #2, `triage`, was built and pruned.** The hypothesis: a cheap lexical
advisor at write time could skip transient, unspecific trivia ("we got new
chairs") and cut the measured hoarding. We built it, tested it on the bench, and
the result was honest and clear:

- It skipped **nothing** (`triaged_out = 0`). The hoarding didn't move.
- *Why:* the curator (even a 7B model) had already (a) declined the worst on its
  own ("Nice weather today" → remembered nothing) and (b) **laundered** the rest
  into respectable facts — "we got new chairs" → `[fact] "New office chairs"`,
  typed and shaped exactly like a real fact.
- The principle underneath: **worth is semantic, not lexical.** "Wifi password
  changed" and "Database schema changed" are the same shape — one is noise, one
  is critical. Any regex that drops the first wrongly silences the second.

So write-time worth is the **curator's** job (it already does most of it), and
the *leftover* trivia is **time's** job: "new chairs" is a fact that fades and
gets swept by `forgetting`'s decay — transparently. The system already had the
right instrument. Rule 4 (subtract): triage didn't earn its place, so it's gone.

The lesson is the artifact. A negative result that says *don't build this, and
here's the principle why* is a real turn of the loop.

## The whole begins to compose

`examples/brain.py` is the first **real application** built on the kit — a daily
companion with a long memory — and it uses all three organs in one loop without
being assembled by hand:

- **recall** the index every turn (rule 3), descend to bodies on a match;
- **reinforce** whatever was recalled (this answers the open seam — *the host
  reinforces what a turn used*);
- **write** only what's new and durable;
- **forget** on demand.

That is the phase transition GROWTH watches for: the pieces composing into
something *used*, not assembled. Now we tune through real use.

## Where the loop is now

Real use named friction on the first session — which is the point:

1. **Meta-queries didn't recall.** "What do you know about me?" shares no tokens
   with "User prefers metric units," so lexical recall returned nothing. *Fixed* —
   `brain` now injects the index (rule 3) as ambient context, not just lexical
   hits. (The app had violated smriti's own rule.)
2. **Restatement makes near-duplicates that slip the dedup threshold.** A weak
   curator re-stores a known fact slightly reworded — "Prefers metric units" vs
   "Gurprit prefers metric units" — which scores 0.75 on `forgetting`'s 0.8
   overlap test, *below* the line, so it survives as a dupe. A prompt told the
   model not to; it did anyway (the triage lesson: novelty is the curator's job
   and a small model is weak at it — so the fix must be structural, not a prompt).
   Lowering the global threshold would wrongly merge real distinctions ("postgres
   for ledger" vs "postgres for billing"). The precise fix this names:
   **containment-aware dedup** — also flag when one hook's tokens are a *subset*
   of another's (restatement-with-extra-words), which catches this case without
   the false-merge risk. That's the next piece — to be built when sustained use
   confirms it bites, not on one session's hunch.

> Sow small rules; the whole raises itself. Pull the weed that won't take root;
> water the one that does. Then live in the house, and let it tell you what it needs.
