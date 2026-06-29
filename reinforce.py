"""reinforce — the counterpart to forgetting. Use keeps a memory alive.

forgetting lets confidence decay with time. But decay measures *staleness*, not
worth — left alone it forgets a true-but-unused fact as fast as a trivium. This
is the other half: when a memory is USED (recalled and acted on), mark it
relevant-as-of-now by refreshing its `updated` stamp. Then decay measures
time-since-last-USED, and the pair becomes selective — the trivia nobody touches
fades, the facts you keep using stay. The spacing effect, in plain text.

A reusable piece (see GROWTH.md): it speaks the format directly — it only
rewrites the `updated:` line — and stands alone. `updated` means "last known to
be relevant," which a write *or* a use both establish.

    from smriti import Memory
    from reinforce import reinforce

    hits = mem.recall("which region is production in?")
    reinforce(mem, *[m.id for m in hits])   # using them keeps them alive
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from smriti import Memory


def reinforce(mem: Memory, *ids: str, when: str | None = None) -> list[str]:
    """Refresh `updated` to today (or `when`, ISO date) for each id that exists.
    Returns the ids actually touched. A no-op for unknown ids — reinforcing what
    isn't there shouldn't create or error."""
    stamp = when or date.today().isoformat()
    touched: list[str] = []
    for id in ids:
        path = Path(mem.dir) / f"{id}.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        new = re.sub(r"(?m)^updated:.*$", f"updated: {stamp}", text, count=1)
        if new != text:
            path.write_text(new, encoding="utf-8")
            touched.append(id)
    return touched
