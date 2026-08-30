#!/usr/bin/env python3
"""smriti MCP server — plain-text memory for AI agents over MCP.

Five tools:
  memory_context  — inject the full index into your prompt
  memory_write    — store a durable memory (decision, pattern, fact, preference, reference)
  memory_recall   — search memories by query, ranked by relevance
  memory_get      — read the full body of a specific memory by id
  memory_prune    — surface stale, duplicate, and broken-link memories

Usage:
  python mcp_server.py <memory-directory>
  # or via stdio for Claude Code / Copilot:
  python mcp_server.py ~/.smriti
"""

from __future__ import annotations

import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

# smriti lives alongside this file
sys.path.insert(0, str(Path(__file__).resolve().parent))
from smriti import Memory, VALID_TYPES

DEFAULT_DIR = str(Path.home() / ".smriti")

server = MCPServer("smriti")


def _mem() -> Memory:
    mem_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DIR
    return Memory(mem_dir)


@server.tool()
def memory_context() -> str:
    """Return the full memory index — one line per memory, hooks only.
    Inject this into your context to see everything the agent knows."""
    return _mem().context()


@server.tool()
def memory_write(
    hook: str,
    type: str = "fact",
    body: str = "",
    links: list[str] | None = None,
) -> str:
    """Store a new memory. Only store what's durable: a decision, a pattern,
    a fact, a preference, or a reference. Compress the hook to one line (≤120 chars).
    Keep body short (≤1500 chars) — store the seed, not the document.

    Args:
        hook: One-line summary of the memory (≤120 chars)
        type: One of: fact, preference, decision, pattern, reference
        body: Short detail — the seed (≤1500 chars)
        links: Optional list of related memory ids
    """
    mem = _mem()
    m = mem.write(hook, body=body, type=type, links=links)
    return f"Stored: [{m.hook}]({m.id}.md) — {m.type}"


@server.tool()
def memory_recall(query: str, k: int = 5) -> str:
    """Search memories by query. Returns the most relevant memories ranked
    by token overlap on hooks, types, and bodies. Follows links one hop.

    Args:
        query: What to search for
        k: Max results to return (default 5)
    """
    mem = _mem()
    hits = mem.recall(query, k=k, with_body=True)
    if not hits:
        return "No matching memories."
    lines = []
    for m in hits:
        lines.append(f"**[{m.type}] {m.hook}** (id: `{m.id}`)")
        if m.body:
            lines.append(f"  {m.body[:500]}")
        lines.append("")
    return "\n".join(lines)


@server.tool()
def memory_get(id: str) -> str:
    """Read the full body of a specific memory by its id.

    Args:
        id: The memory id (filename stem)
    """
    mem = _mem()
    m = mem.get(id)
    if m is None:
        return f"Memory '{id}' not found."
    return f"**{m.hook}** ({m.type}, updated {m.updated})\n\n{m.body}"


@server.tool()
def memory_prune() -> str:
    """Surface memories that may need attention: stale (untouched >180 days),
    duplicates (near-identical hooks), and broken links."""
    mem = _mem()
    report = mem.prune()
    lines = []
    for kind, items in report.items():
        if items:
            lines.append(f"**{kind}:** {items}")
        else:
            lines.append(f"**{kind}:** clean")
    return "\n".join(lines) if lines else "All clean."


if __name__ == "__main__":
    server.run(transport="stdio")
