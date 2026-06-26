#!/usr/bin/env python3
"""Stage 0 — deterministic memory mechanics benchmark for smriti.

No LLM, no API, no network. It replays planted seed -> probe sequences straight
against write / recall / prune and checks them against ground truth (we planted
the dependency, so the right answer is known). It proves the *retrieval and
housekeeping* claims; it does NOT test agent behavior — that is Stage 1, the LLM
A/B. If smriti fails here, stop.

Run:  python bench/mechanics.py     (exits nonzero if any claim fails)
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from smriti import Memory  # noqa: E402


@dataclass
class Probe:
    query: str
    top: str | None = None  # this id must be the #1 result
    contains: list[str] = field(default_factory=list)  # must appear in results
    absent: list[str] = field(default_factory=list)  # must NOT appear
    expect_empty: bool = False  # results must be empty (no false memory)
    via_link: bool = False  # `contains` must be reachable ONLY via a link


class Tally:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.notes: list[str] = []

    def check(self, ok: bool, label: str) -> None:
        if ok:
            self.passed += 1
        else:
            self.failed += 1
            self.notes.append("FAIL: " + label)

    def info(self, s: str) -> None:
        self.notes.append(s)


def fresh() -> Memory:
    return Memory(tempfile.mkdtemp())


def run_probes(mem: Memory, probes: list[Probe], t: Tally, name: str) -> None:
    for p in probes:
        ids = [m.id for m in mem.recall(p.query, k=5)]
        if p.expect_empty:
            t.check(ids == [], f"[{name}] '{p.query}' -> empty (got {ids})")
            continue
        if p.top is not None:
            t.check(bool(ids) and ids[0] == p.top, f"[{name}] '{p.query}' top={p.top} (got {ids[:3]})")
        for cid in p.contains:
            t.check(cid in ids, f"[{name}] '{p.query}' contains {cid} (got {ids})")
        for aid in p.absent:
            t.check(aid not in ids, f"[{name}] '{p.query}' absent {aid} (got {ids})")
        if p.via_link:
            without = [m.id for m in mem.recall(p.query, k=5, follow_links=False)]
            for cid in p.contains:
                t.check(cid not in without, f"[{name}] '{p.query}' {cid} should require the link")


# ── 1. recall ranks the right memory; nonsense recalls nothing ────────────────
def scenario_recall(t: Tally) -> None:
    mem = fresh()
    mem.write("User prefers metric units", type="preference")
    mem.write("User prefers dark mode", type="preference")
    mem.write("Deploy region is eu-west-1", type="fact")
    for d in ["Standup is at 9am", "Logo color is teal", "CI runs on push", "Mascot is an otter"]:
        mem.write(d, type="fact")
    run_probes(
        mem,
        [
            Probe("metric units", top="user-prefers-metric-units", absent=["user-prefers-dark-mode"]),
            Probe("deploy region", top="deploy-region-is-eu-west-1"),
            Probe("dark mode", top="user-prefers-dark-mode"),
            Probe("xylophone quokka nebula", expect_empty=True),  # never stored -> no false memory
        ],
        t,
        "recall",
    )


# ── 2. a query that matches only a decision still pulls in its linked pattern ──
def scenario_links(t: Tally) -> None:
    mem = fresh()
    mem.write("Exponential backoff with jitter", type="pattern")  # shares no words with the query
    mem.write(
        "Always wrap external calls in the retry helper",
        type="decision",
        links=["exponential-backoff-with-jitter"],
    )
    mem.write("Frontend uses React", type="fact")
    run_probes(
        mem,
        [
            Probe(
                "retry helper external calls",
                top="always-wrap-external-calls-in-the-retry-helper",
                contains=["exponential-backoff-with-jitter"],
                via_link=True,
            )
        ],
        t,
        "links",
    )


# ── 3. same hook updates in place; created is preserved ───────────────────────
def scenario_update(t: Tally) -> None:
    mem = fresh()
    a = mem.write("API base url", body="v1: api.old.com", type="fact")
    b = mem.write("API base url", body="v2: api.new.com", type="fact")
    t.check(a.id == b.id, "update: same hook -> same id")
    t.check(mem.get(b.id).body.endswith("api.new.com"), "update: body is the latest")
    t.check(b.created == a.created, "update: created preserved")
    t.check(len([m for m in mem.all() if m.id == b.id]) == 1, "update: no duplicate file")


# ── 4. prune surfaces stale, duplicate, and broken-link memories ──────────────
def scenario_prune(t: Tally) -> None:
    mem = fresh()
    mem.write("Recent fact", type="fact")
    mem.write("Use Postgres for the ledger", type="decision")
    mem.write("Use Postgres for ledger", type="decision")  # near-identical hook
    mem.write("Points nowhere", type="fact", links=["ghost"])
    (Path(mem.dir) / "ancient.md").write_text(
        "---\nid: ancient\nhook: Ancient fact\ntype: fact\n"
        "created: 2019-01-01\nupdated: 2019-01-01\nlinks: []\n---\n\nold\n",
        encoding="utf-8",
    )
    rep = mem.prune(stale_days=180)
    t.check(any(i == "ancient" for i, _ in rep["stale"]), "prune: flags stale")
    t.check(len(rep["duplicates"]) >= 1, "prune: flags duplicate")
    t.check(any(link == "ghost" for _, link in rep["broken_links"]), "prune: flags broken link")


# ── 5. the index injected per turn is a fraction of the full store ────────────
def scenario_compression(t: Tally) -> None:
    mem = fresh()
    body = ("This is a compressed seed body that a real memory would carry. " * 6).strip()
    for i in range(40):
        mem.write(f"Memory number {i:02d} covering subject {i:02d}", body=body, type="fact")
    ctx = mem.context()
    full = "".join((Path(mem.dir) / f"{m.id}.md").read_text(encoding="utf-8") for m in mem.all())
    ratio = len(ctx) / len(full)
    t.check(ratio < 0.30, f"compression: index is {ratio:.0%} of the full store (want <30%)")
    t.info(f"  index injected per turn = {len(ctx)} chars vs full store = {len(full)} chars  ({ratio:.0%})")


def main() -> int:
    sections = [
        ("recall + precision", scenario_recall),
        ("link synthesis", scenario_links),
        ("update / overwrite", scenario_update),
        ("prune health", scenario_prune),
        ("compression (cost)", scenario_compression),
    ]
    print("smriti — Stage 0: deterministic memory mechanics\n")
    total_p = total_f = 0
    for name, fn in sections:
        t = Tally()
        fn(t)
        total_p += t.passed
        total_f += t.failed
        print(f"[{'ok ' if t.failed == 0 else 'FAIL'}] {name}: {t.passed} passed, {t.failed} failed")
        for note in t.notes:
            print("      " + note)
    print(f"\n{total_p} passed, {total_f} failed")
    print("\nStage 0 proves retrieval + housekeeping. Behavioral usefulness is Stage 1 (LLM A/B).")
    return 1 if total_f else 0


if __name__ == "__main__":
    raise SystemExit(main())
