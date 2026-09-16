# The smriti memory format — v1

> A memory store is a **directory of markdown files**. Nothing else is required.
> This document is the artifact; any library that reads/writes it is replaceable.

It is plain UTF-8 text: readable by a human with no software, and parseable by
any program in about twenty lines. In a git repo it is versioned, diffable, and
forkable.

---

## 1. A memory is one file

`<id>.md`:

```markdown
---
id: user-prefers-dark-mode
hook: User prefers dark mode in all UIs
type: preference
created: 2026-06-18
updated: 2026-06-18
links: [theme-tokens-decision]
---

The body: the seed. One fact, compressed. For `decision` and `pattern`,
follow with **Why:** and **How to apply:** lines. Link related memories
inline with their id.
```

**Frontmatter fields**

| field | required | meaning |
|---|---|---|
| `id` | yes | filename stem; stable slug |
| `hook` | yes | one line (≤120 chars) — what this memory *is*. Used for recall and the index. |
| `type` | yes | one of: `fact` · `preference` · `decision` · `pattern` · `reference` |
| `created` | yes | ISO date |
| `updated` | yes | ISO date |
| `links` | no | ids of related memories: `[id-a, id-b]` |

**Body**: the seed — compressed (≤~1500 chars). If it's longer, it's a document;
store the seed and link the document.

## 2. The index is one file

`INDEX.md` — one line per memory, grouped by type. This is the file you inject
into your agent's context every turn. It is cheap (hooks only), so the agent
always sees *what it knows* and fetches a full body only when a hook is relevant.

```markdown
## preference
- [User prefers dark mode in all UIs](user-prefers-dark-mode.md) — preference
## decision
- [Use Postgres, not Mongo, for the ledger](use-postgres-for-ledger.md) — decision
```

## 3. The four rules

1. **Write filter** — store only what is durable and non-obvious: a decision,
   a pattern, a preference, a fact, or a pointer. If it's derivable, transient,
   or obvious, let it pass.
2. **Compress on store** — a one-line hook + a short body. Lead with the spine.
3. **Recall by hook** — read the index first; descend to a body only on a match.
4. **Prune** — periodically surface stale, duplicate, and broken memories and
   remove them.

## 4. Conformance

A conforming implementation MUST:
- read/write the file shape in §1 and the index in §2;
- reject a write with an empty hook, a hook >120 chars, an invalid `type`, or a
  body that exceeds the compression limit;
- provide recall over hooks without requiring a network service or embeddings.

It MUST NOT require a database, a server, or any non-text storage. The store is
the markdown; everything else is convenience.

**Hosted implementations.** A networked or hosted implementation MUST keep the
markdown files the source of truth: every memory exists as a conforming file
(§1); recall runs over hooks (§3), never SQL or vector search; and a user can
export the complete store to a directory readable with `cat`, zero services
running, losing nothing. Such a backend MAY hold identity, a per-memory
permission ledger, and a synced copy for transport — it MUST NOT be the sole home
of any memory, MUST NOT be required to read one's own memory, and MUST NOT turn
recall into a network call. The backend is to the store what GitHub is to git: a
broker over the files, never their home.
