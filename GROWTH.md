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
- **`consolidate.py`** — the generative organ. Where the others subtract or
  maintain, this one raises memory a level: it folds many episodes into one
  `pattern` (episodic → semantic — the *compress* organ this file long wanted).
  `plan()` surfaces candidate clusters and gates them on a shared *core*, so a
  hub-bridged blob (distinct subjects welded by a shared date or name) is flagged,
  not fused. The curator authors the one hook+seed — *worth is semantic* (the
  triage lesson), so a machine never writes the gist — and `fuse()` does the
  mechanical, reversible rest: it writes the sources' vocabulary into the body as
  a `Cues:` line so lexical recall still finds the pattern (no embeddings),
  repoints inbound links, and archives the folded sources to `.consolidated/log.md`.
  Stands alone, stdlib. (`test_consolidate.py`.)

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

## The loop closed — now run it, and sit

With `consolidate`, the five-organ metabolism is whole, and in the Claude Code
adapter it is self-firing:

    write → recall → reinforce → forget → consolidate (plan → fuse)

`integrations/claude_code.py` fires a `consolidate` beat on SessionStart, so a
session opens with the clusters ready to fold; the curator folds a clean one in
the course of real work. Proven on a live store: five OPUS-2.0 facts folded into
one `pattern`, and the planner then reported *"nothing to fold"* — a living
system does its work and rests; only a dead one manufactures work to look busy.

Asked how to grow it "more like human memory," the council's disciplined answer
was **build nothing** — recorded here so it is not relitigated:

- Human memory's famous mechanisms — rewrite-on-recall, similarity-by-vector,
  meaning-guessed-at-encoding, hidden salience — are its *constraints*, not its
  virtues. Each makes the store less faithful to what was recorded, and faithful
  plain text you can `cat` is the whole moat. Adopt the principles that make
  memory wiser — **fold, fade, associate** — and refuse the mechanisms that make
  it human. Copying those is cosplay, not growth.
- The "human" candidates are already present or are traps: associative recall is
  already `follow_links` + the `Cues:` written into a fold; salience is already
  type half-life + reinforce; schema-driven encoding and reconsolidation are
  traps — the first is the triage lesson again, the second a fidelity bug — and
  the honest slice of each is the curator weaving the existing `links` field, a
  *habit*, not an organ.

So the state is **leave it running.** Build the next piece only when one of these
tripwires actually bites in real use — never from the wish to be more human:

1. **containment-aware dedup** — a restated duplicate slips the 0.8 line again
   (the piece named above).
2. **`identity` half-life** — a true self-fact (a return date, a long-held aim)
   *wrongly fades* and must be re-taught; the fix is an effectively-infinite
   half-life for that memory, not a new subsystem.
3. **recall's synonym wall** — the standing, deliberately-unpaid lexical limit
   (`db` ≠ `database`); embeddings stay refused. A fold's `Cues:` line already
   buys back part of it from the write side.

The wish to be "more human" is not a tripwire. The wisest piece at this sitting
is the one not built.

## A deferred piece — the shared / hosted backend

A public SDK with a hosted backend (the idea: Supabase — Postgres, auth,
permissions) was considered, to make one memory that many agents plug into and
share. It is **deferred**, and writing down why is the turn of the loop.

The format is the source of truth. A server is legitimate only as a *broker over
the files* — the way GitHub is a broker over git: it holds identity, a permission
ledger, and a synced copy, and you can still `git clone` and read everything
offline with nothing running. The moment a memory's truth lives only in a
database row that `cat` cannot reconstruct, smriti has stopped being smriti — and
stopped for nothing, because at that point it is one more memory-service with its
only differentiator (no vendor between you and your memory) traded away.

The honest trigger has not bitten. The shared case has been used zero times; the
one real application (`examples/brain.py`) is single-user. For *same-org*
sharing, a git remote is already a working broker today. The one thing files
genuinely cannot do — and the only thing that would name an external broker — is
**per-memory, cross-stranger, revocable** sharing (a git clone is forever). Build
the broker the day that need is exercised, not on the hunch that "public" implies
"database." (This is the `triage` lesson at product scale — the negative result
is the artifact.)

The next piece, when shared use bites, stays in the waist: an optional
`visibility: private | shared` and `shared_with: [id, …]` in the frontmatter — so
the permission is *also* plain text — plus a shared-subset export (write the
`visibility: shared` memories to a directory a peer pulls and recalls with the
existing lexical recall). Revocation-by-omission first; an external ACL broker
only when cross-stranger revocation is a proven, recurring need. The conformance
line for any such backend is written into [SPEC §4](SPEC.md).

> Sow small rules; the whole raises itself. Pull the weed that won't take root;
> water the one that does. Then live in the house, and let it tell you what it needs.
