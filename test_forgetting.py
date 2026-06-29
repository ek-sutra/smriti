"""Deterministic tests for the forgetting organ — Stage-0 style, no LLM.

Plants a rotted store (one stale, one duplicate pair, one fresh-durable) and
proves: plan() is read-only, forget(apply) removes only rot + redundancy and
keeps the durable core, and the tombstone records what and why.
"""

import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smriti import Memory  # noqa: E402
import forgetting  # noqa: E402


def _file(d: Path, name: str, hook: str, type: str, updated: str) -> None:
    (d / f"{name}.md").write_text(
        f"---\nid: {name}\nhook: {hook}\ntype: {type}\n"
        f"created: {updated}\nupdated: {updated}\nlinks: []\n---\n\n(body)\n",
        encoding="utf-8",
    )


def _store() -> Memory:
    d = Path(tempfile.mkdtemp())
    Memory(str(d)).write("Use Postgres for the ledger", type="decision")  # fresh-durable (today)
    _file(d, "old-region", "Temp deploy region was us-east-2", "fact", "2024-01-01")  # stale → faded
    _file(d, "k1", "API uses gRPC now", "decision", "2026-01-01")  # duplicate (older)
    _file(d, "k2", "API uses gRPC now", "decision", "2026-06-01")  # duplicate (newer → kept)
    return Memory(str(d))


def test_confidence_decays():
    mem = _store()
    by = {m.id: m for m in mem.all()}
    assert forgetting.confidence(by["use-postgres-for-the-ledger"]) > 0.99  # fresh
    assert forgetting.confidence(by["old-region"]) < 0.25  # ~2.5 years, fact half-life 90d


def test_plan_is_read_only():
    mem = _store()
    before = len(mem.all())
    decisions = forgetting.plan(mem)
    assert len(mem.all()) == before  # nothing removed
    ids = {f.id for f in decisions}
    assert "old-region" in ids and "k1" in ids and "k2" not in ids


def test_forget_removes_rot_and_redundancy():
    mem = _store()
    forgetting.forget(mem, apply=True)
    remaining = {m.id for m in mem.all()}
    assert remaining == {"use-postgres-for-the-ledger", "k2"}  # durable + newer dup kept
    tomb = (Path(mem.dir) / ".forgotten" / "log.md").read_text()
    assert "old-region" in tomb and "faded" in tomb
    assert "k1" in tomb and "duplicate" in tomb


def test_undated_and_fresh_are_kept():
    mem = Memory(tempfile.mkdtemp())
    mem.write("Keep me", type="fact")
    assert forgetting.plan(mem) == []


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print("ok ", fn.__name__)
    print(f"\n{len(fns)} passed")
