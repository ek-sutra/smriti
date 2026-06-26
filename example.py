"""A self-contained demo that proves smriti end to end.

Run: python example.py
It writes a few memories into ./demo-memory, then shows the index, recall,
descent, and the prune report.
"""

from smriti import Memory

mem = Memory("./demo-memory")

# 1. WRITE — filtered + compressed
mem.write("User prefers dark mode in all UIs", type="preference")
ledger = mem.write(
    "Use Postgres, not Mongo, for the ledger",
    body="**Why:** the ledger needs ACID transactions.\n"
    "**How to apply:** new services default to Postgres unless proven otherwise.",
    type="decision",
    links=["theme-tokens"],  # intentionally points at a missing memo — prune() will flag it
)
mem.write("Retries should use exponential backoff with jitter", type="pattern")
mem.write("API docs live at docs.internal/api", type="reference")
mem.write("User's name is Gurprit", type="fact")

# The filter rejects what isn't stored well:
for hook, type_ in [
    ("", "fact"),  # no hook
    ("x" * 130, "fact"),  # hook too long
    ("valid hook", "rumor"),  # invalid type
]:
    try:
        mem.write(hook, type=type_)
    except ValueError as e:
        print("filter rejected:", e)

print("\n── context() — inject this whole thing into your prompt ──")
print(mem.context())

print("── recall('which database for transactions') ──")
for m in mem.recall("which database for transactions"):
    print(" ", m.hook, f"[{m.type}]")

print("\n── descend to the seed only when a hook matches ──")
print(mem.get(ledger.id).body)

print("\n── prune() — keep it lean ──")
report = mem.prune()
for kind, items in report.items():
    print(f"  {kind}: {items or '—'}")
