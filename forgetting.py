"""forgetting — the honest-forgetting organ for smriti.

One job: decide what a memory store should forget, transparently, and — only when
asked — act on it, archiving each removal to a tombstone so nothing vanishes
silently. It speaks the plain-text format and stands alone (see GROWTH.md): a
reusable piece, not part of the core.

It forgets two things, by rules you can read:
  • faded     — confidence decays with age (per-type half-life); below a floor → forget
  • duplicate — near-identical hooks; keep the most recent, forget the rest

It does NOT guess which still-fresh memories are "low value" — that is a curator's
judgment, not a forgetter's. Honest forgetting removes rot and redundancy, names
exactly what and why, and leaves the record in a tombstone (and in git).

    from smriti import Memory
    from forgetting import plan, forget

    for f in plan(Memory("./memory")):       # see the decision; nothing is removed
        print(f.id, "—", f.reason)
    forget(Memory("./memory"), apply=True)   # write FORGOTTEN.md, then remove
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from smriti import Memory

# How fast a memory's confidence halves, by type. Volatile facts fade fast;
# decisions and preferences are sticky. Tune freely — this is the only policy.
HALF_LIFE_DAYS = {"fact": 90, "reference": 180, "preference": 365, "decision": 365, "pattern": 365}
DEFAULT_HALF_LIFE = 120
FADED_FLOOR = 0.25  # confidence below this counts as faded (~two half-lives)
DUP_THRESHOLD = 0.8  # hook-token overlap to call two memories duplicates
# The tombstone lives in a subdir so the store never globs it as a memory.
TOMBSTONE = (".forgotten", "log.md")


@dataclass
class Forget:
    id: str
    hook: str
    reason: str


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


def confidence(memo, today: date | None = None) -> float:
    """0..1 — halves every half-life. 1.0 for undated or just-written memories."""
    today = today or date.today()
    try:
        age = (today - datetime.fromisoformat(memo.updated).date()).days
    except ValueError:
        return 1.0
    if age <= 0:
        return 1.0
    half_life = HALF_LIFE_DAYS.get(memo.type, DEFAULT_HALF_LIFE)
    return 0.5 ** (age / half_life)


def plan(
    mem: Memory,
    today: date | None = None,
    faded_floor: float = FADED_FLOOR,
    dup_threshold: float = DUP_THRESHOLD,
) -> list[Forget]:
    """What this store should forget, and why. Read-only — removes nothing."""
    today = today or date.today()
    memos = mem.all()
    out: list[Forget] = []
    doomed: set[str] = set()

    # faded — confidence decayed below the floor
    for m in memos:
        c = confidence(m, today)
        if c < faded_floor:
            out.append(Forget(m.id, m.hook, f"faded (confidence {c:.2f} < {faded_floor}, type {m.type})"))
            doomed.add(m.id)

    # duplicate — near-identical hooks; keep the most recently updated
    for i, a in enumerate(memos):
        if a.id in doomed:
            continue
        ta = _tokens(a.hook)
        for b in memos[i + 1 :]:
            if b.id in doomed:
                continue
            tb = _tokens(b.hook)
            union = ta | tb
            if union and len(ta & tb) / len(union) >= dup_threshold:
                older, newer = sorted((a, b), key=lambda m: m.updated)
                out.append(Forget(older.id, older.hook, f"duplicate of {newer.id!r} (kept the newer)"))
                doomed.add(older.id)

    return out


def forget(mem: Memory, apply: bool = False, **kw) -> list[Forget]:
    """Plan forgetting; when `apply`, append each removal to the tombstone
    (FORGOTTEN.md — what + why + when) and then delete it. The body stays in git
    history, so forgetting is transparent and recoverable, never silent."""
    decisions = plan(mem, **kw)
    if apply and decisions:
        tomb = Path(mem.dir).joinpath(*TOMBSTONE)
        tomb.parent.mkdir(exist_ok=True)
        new = not tomb.exists()
        with tomb.open("a", encoding="utf-8") as fh:
            if new:
                fh.write("# Forgotten\n\n> What smriti forgot, and why. The content remains in git history.\n\n")
            for f in decisions:
                fh.write(f"- {date.today().isoformat()} · `{f.id}` — {f.hook} — {f.reason}\n")
        for f in decisions:
            mem.delete(f.id)
    return decisions
