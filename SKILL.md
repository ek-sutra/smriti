---
name: smriti
description: "Give your AI agent persistent plain-text memory across sessions. Write durable memories (decisions, patterns, facts, preferences), recall by query, prune stale entries — all stored as human-readable markdown files. No database, no embeddings, no dependencies, no setup."
---

# smriti — Plain-Text Memory for AI Agents

You now have persistent memory. Use it to remember things that matter across sessions: decisions made, patterns discovered, facts learned, preferences stated.

Memory is a **directory of markdown files** — you read and write them directly with your file tools. No server, no database, no setup.

## Memory Directory

The memory store lives at `~/.smriti/` (create it if it doesn't exist). Each memory is one `.md` file. The index is `INDEX.md`.

## The Format

Each memory file looks like this:

```markdown
---
id: user-prefers-postgres
hook: User prefers Postgres over Mongo for transactional data
type: decision
created: 2026-08-30
updated: 2026-08-30
links: [ledger-architecture]
---

Decided during ledger architecture review. Reason: ACID guarantees matter more than schema flexibility for financial data.
```

**Frontmatter fields:**

| Field | Required | Rules |
|---|---|---|
| `id` | yes | Filename stem. Lowercase slug, hyphens. |
| `hook` | yes | One line, ≤120 chars — what this memory IS |
| `type` | yes | One of: `fact`, `preference`, `decision`, `pattern`, `reference` |
| `created` | yes | ISO date (YYYY-MM-DD) |
| `updated` | yes | ISO date — update on every touch |
| `links` | no | IDs of related memories: `[id-a, id-b]` |

**Body:** The seed — compressed, ≤1500 chars. If longer, it's a document; store the seed and link the document.

## How to Use Memory

### At session start — load context

Read `~/.smriti/INDEX.md` to see everything you know. If it doesn't exist, the store is empty.

The index looks like:
```markdown
# Memory Index

3 memories. One line each — load this into context.

## decision
- [User prefers Postgres over Mongo](user-prefers-postgres.md) — decision

## pattern
- [Tests fail on CI but pass locally — timezone issue](tests-fail-ci-timezone.md) — pattern

## fact
- [Project uses Python 3.11 with FastAPI](project-python-fastapi.md) — fact
```

### Writing a memory

When the user states a decision, reveals a preference, or you discover a pattern:

1. Create a slug from the hook: `"User prefers dark mode"` → `user-prefers-dark-mode`
2. Write the file at `~/.smriti/<slug>.md` with the frontmatter + body
3. **Rebuild the index:** Read all `.md` files (except INDEX.md), group by type, write INDEX.md with one `- [hook](filename) — type` line per memory, sorted by updated date (newest first)

**The write filter — only store what's durable:**
- Is this a **decision** (something committed to)?
- Is this a **pattern** (something observed multiple times)?
- Is this a **fact** (something stable and non-obvious)?
- Is this a **preference** (a stated choice)?
- Is this a **reference** (a pointer to external knowledge)?

If none of these — if it's transient, derivable, or obvious — let it pass.

### Recalling memories

To find relevant memories for a topic: read INDEX.md, scan the hooks for relevance, then read the full body of matching files. Follow `links` one hop — a decision brings the pattern it rests on.

### Updating a memory

Read the existing file, update the body and `updated` date, write it back. Rebuild the index.

### Pruning

Periodically scan for:
- **Stale:** memories with `updated` older than 180 days
- **Duplicates:** two memories with nearly identical hooks
- **Broken links:** `links` pointing to IDs that don't exist as files

Report these to the user. Never auto-delete — let the user decide.

## What NOT to Store

- Transient state ("currently working on file X")
- Obvious facts ("Python uses indentation")
- Derivable information (things you can figure out from code)
- Entire documents (store the seed, link the document)
- Secrets, API keys, or credentials

## Example Session

**Start:**
```
→ Read ~/.smriti/INDEX.md
  "3 memories. User prefers dark mode. Project uses FastAPI. Tests fail on CI timezone."
  Hook "FastAPI" is relevant to current task → read ~/.smriti/project-python-fastapi.md
```

**During work:**
```
User says: "Let's use Redis for caching, not Memcached"
→ Write ~/.smriti/use-redis-for-caching-not-memcached.md
→ Rebuild INDEX.md
```

**End:**
```
→ Check: did we learn anything durable this session? If yes, write it. If no, done.
```
