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

## Where the loop is now

The temporal test was run, and it corrected the model. The claim "trivia is swept
by decay" turned out **half true**: decay alone is *indiscriminate* — it forgets a
true-but-unused fact ("production region is eu-west-1") exactly as fast as a
trivium ("new office chairs"), because decay measures staleness, not worth. The
missing half — **reinforcement** — emerged from that failure and was built. With
it, the pair is selective: *use keeps alive, disuse fades.*

So the kept organs now form a **pair, the two halves of one metabolism:**
`reinforce` (use → recency) and `forgetting` (disuse → decay → swept,
transparently). Three pieces tried, two kept, one pruned — the discipline holds.

Honest residual the test surfaced: a trivium the curator *mistypes* as a
`decision` gets a long half-life and escapes decay. Decay can't fix a curator's
type error — recorded, not hidden. And one integration question the pair now
implies: *who calls `reinforce`?* The host, on the memories a turn actually used.
That seam — wiring use to reinforcement — is where the loop points next.

> Sow small rules; the whole raises itself. Pull the weed that won't take root;
> water the one that does.
