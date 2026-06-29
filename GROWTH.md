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

## Where the loop is now

The Stage-1 benchmark already measured the first real friction: **curation
hoards** — a model kept 5 of 5 distractors. So the first organ that wants to
exist is **honest forgetting**: making `prune` usable and trustworthy. Not
chosen from a roadmap — surfaced by a test.

> Sow small rules; the whole raises itself.
