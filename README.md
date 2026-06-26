# smriti

Memory for AI agents, stored as markdown files. No database, no embeddings, no
dependencies — Python standard library only.

## A memory on disk

```
$ cat memory/use-postgres-for-the-ledger.md
---
id: use-postgres-for-the-ledger
hook: Use Postgres, not Mongo, for the ledger
type: decision
created: 2026-06-18
updated: 2026-06-18
---

**Why:** the ledger needs ACID transactions.
**How to apply:** new services default to Postgres.
```

That file is the whole thing. `git` versions it, a person reads it, any program
parses it in about twenty lines.

## Use

```python
from smriti import Memory
mem = Memory("./memory")

mem.write(
    "Use Postgres, not Mongo, for the ledger",
    body="**Why:** the ledger needs ACID transactions.",
    type="decision",
)

mem.context()                  # the index, one line per memory — inject into your prompt
mem.recall("postgres ledger")  # ranked matches
mem.get("use-postgres-for-the-ledger").body
mem.prune()                    # stale / duplicate / broken-link memories
```

## How it works

- **write** stores a memory if it has a one-line hook, a known type
  (`fact` · `preference` · `decision` · `pattern` · `reference`), and a body
  that fits. Same hook updates in place.
- **context** returns the index — one line per memory — small enough to put in
  the prompt every turn.
- **recall** matches words in hooks and bodies. Lexical and deterministic; no
  embeddings — the model does the semantics over `context()`.
- **prune** reports memories that have gone stale, duplicate, or point at a
  missing link.

The store is a directory of `<id>.md` files plus an `INDEX.md`. The format is
the whole specification: [SPEC.md](SPEC.md).

## Limits

- Recall is lexical: "database" will not find "Postgres".
- The write filter checks shape, not worth — deciding what deserves remembering
  is yours.
- Sized for hundreds to a few thousand memories, not millions of rows.

## Install

```bash
pip install agent-smriti        # import smriti
```

Or copy `smriti.py` into your project — Python 3.10+, standard library only.

## CLI

```bash
python smriti.py ./memory context           # print the index
python smriti.py ./memory recall postgres   # search
python smriti.py ./memory prune             # health report
```

MIT licensed. See [SPEC.md](SPEC.md) for the format.
