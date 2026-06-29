"""Recall-quality bench — measure, don't guess. (No LLM.)

Plants a realistic store and runs query→expected pairs grouped by failure mode,
reporting hit-rate@k by category so the worst mode is visible. Recall stays
lexical + deterministic by design (the bet); this is the regression gate —
every change to recall is judged against this number.

Failure modes, seeded from real use:
  exact       query shares a salient token with the hook        (should pass)
  paraphrase  different words, but a proper noun still overlaps  (often passes)
  synonym     no shared token at all (db→database, auth→author)  (the lexical wall)
  meta        query has no content tokens ("what do you know")   (app-layer's job)
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from smriti import Memory  # noqa: E402

STORE = [
    ("User's name is Gurprit", "fact"),
    ("Prefers Postgres over Mongo for datastores", "preference"),
    ("Use Cedar for authorization, policy-as-code", "decision"),
    ("Production runs in region eu-west-1", "fact"),
    ("API migrated from REST to gRPC", "decision"),
    ("Rate limit is 500 requests per minute", "fact"),
    ("Show the pain, not the design", "pattern"),
    ("Runbook for local setup at docs/local.md", "reference"),
    ("Prefers metric units and async updates", "preference"),
    ("Corporate CA Zscaler breaks pip, use the public registry", "fact"),
]

# (query, category, [acceptable substrings of the target hook — any-of])
QUERIES = [
    ("which region is production in", "exact", ["eu-west-1"]),
    ("rate limit per minute", "exact", ["Rate limit"]),
    ("Cedar authorization", "exact", ["Cedar"]),
    ("local setup runbook", "exact", ["Runbook"]),
    ("which protocol does the API speak", "paraphrase", ["gRPC"]),
    ("is the API still on REST", "paraphrase", ["gRPC"]),
    ("pip install is failing at work", "paraphrase", ["Zscaler"]),
    ("which database do we use", "synonym", ["Postgres"]),
    ("auth setup", "synonym", ["Cedar"]),
    ("how many calls can I make", "synonym", ["Rate limit"]),
    ("what do you know about me", "meta", ["Gurprit", "metric units", "Postgres"]),
    ("tell me about the user", "meta", ["Gurprit", "metric units"]),
]

K = 5


def _hit(memos, expected) -> int:
    hooks = " || ".join(m.hook.lower() for m in memos)
    return int(any(s.lower() in hooks for s in expected))


def main() -> int:
    mem = Memory(tempfile.mkdtemp())
    for hook, typ in STORE:
        mem.write(hook, type=typ)

    by_cat: dict[str, list[int]] = {}
    print(f"{'cat':11} {'hit':3}  query → top recall")
    print("-" * 78)
    for query, cat, expected in QUERIES:
        hits = mem.recall(query, k=K)
        h = _hit(hits, expected)
        by_cat.setdefault(cat, []).append(h)
        top = ", ".join(m.hook for m in hits[:3]) or "(nothing)"
        print(f"{cat:11} {'✓' if h else '✗':3}  {query!r}\n{'':16}→ {top[:80]}")

    print("\n=== hit-rate@%d by category ===" % K)
    total = []
    for cat, hs in by_cat.items():
        total += hs
        print(f"  {cat:11} {sum(hs)}/{len(hs)}")
    print(f"  {'OVERALL':11} {sum(total)}/{len(total)}  ({100*sum(total)//len(total)}%)")
    worst = min(by_cat, key=lambda c: sum(by_cat[c]) / len(by_cat[c]))
    print(f"\nworst mode: {worst!r} — that's where the next fix is judged (if the bet allows one).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
