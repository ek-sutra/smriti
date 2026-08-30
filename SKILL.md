---
name: smriti
description: "Give your AI agent persistent plain-text memory across sessions. Write durable memories (decisions, patterns, facts, preferences), recall by query, prune stale entries — all stored as human-readable markdown files. No database, no embeddings, no dependencies."
---

# smriti — Plain-Text Memory for AI Agents

You now have persistent memory. Use it to remember things that matter across sessions: decisions made, patterns discovered, facts learned, preferences stated. Everything is stored as markdown files — human-readable, git-versioned, yours.

## How to Use Memory

### Starting a session
At the start of every conversation, load context to see what you already know:

```
memory_context
```

This returns the full index — one line per memory. Scan it. If a hook is relevant to the current task, fetch the full body with `memory_get`.

### Remembering something durable
When the user states a decision, reveals a preference, or you discover a pattern worth keeping:

```
memory_write(hook="User prefers Postgres over Mongo for transactional data", type="decision", body="Decided during ledger architecture review. Reason: ACID guarantees matter more than schema flexibility for financial data.")
```

**Only store what's durable.** Apply the filter:
- Is this a **decision** (something committed to)?
- Is this a **pattern** (something observed multiple times)?
- Is this a **fact** (something stable and non-obvious)?
- Is this a **preference** (a stated choice)?
- Is this a **reference** (a pointer to external knowledge)?

If it's none of these — if it's transient, derivable, or obvious — let it pass.

**Compress.** The hook must be one line (≤120 chars). The body must be short (≤1500 chars). Store the seed, not the document.

### Recalling relevant memories
When you need context on a topic:

```
memory_recall(query="database choice", k=5)
```

Returns the most relevant memories, ranked. Follows links one hop — a decision brings the pattern it rests on.

### Reading a specific memory
When a hook from the index looks relevant and you need the full body:

```
memory_get(id="user-prefers-postgres-over-mongo-for-transactional-data")
```

### Pruning
Periodically surface memories that may need attention:

```
memory_prune
```

Reports stale entries (untouched >180 days), near-duplicate hooks, and broken links.

## The Four Rules

1. **Write filter** — store only what's durable and non-obvious
2. **Compress** — one-line hook + short body. Lead with the spine.
3. **Recall by hook** — read the index first; descend to a body only on match
4. **Prune** — surface stale, duplicate, and broken memories

## Memory Types

| Type | When to use | Example |
|---|---|---|
| `fact` | Stable, non-obvious information | "Project uses Python 3.11 with FastAPI" |
| `preference` | A stated user choice | "User prefers dark mode in all UIs" |
| `decision` | Something committed to | "Use Postgres, not Mongo, for the ledger" |
| `pattern` | Something observed multiple times | "Tests fail on CI but pass locally — Docker timezone issue" |
| `reference` | A pointer to external knowledge | "API docs at docs.example.com/v3" |

## Setup

The MCP server must be configured. Add to your MCP config:

```json
{
  "mcpServers": {
    "smriti": {
      "command": "python3",
      "args": ["{{SKILL_PATH}}/mcp_server.py", "~/.smriti"]
    }
  }
}
```

Requires: `pip install mcp` (Python 3.10+). smriti itself has zero dependencies.

## What NOT to Store

- Transient state ("currently working on file X")
- Obvious facts ("Python uses indentation")
- Derivable information (things you can figure out from code)
- Entire documents (store the seed, link the document)
- Secrets, API keys, or credentials
