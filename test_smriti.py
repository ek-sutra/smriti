"""Tests for smriti. Run with `pytest` or directly: `python3 test_smriti.py`."""

import tempfile

from smriti import Memory


def _mem() -> Memory:
    return Memory(tempfile.mkdtemp())


def test_write_and_get():
    mem = _mem()
    m = mem.write("Use Postgres for the ledger", body="ACID needed", type="decision")
    assert m.id == "use-postgres-for-the-ledger"
    assert mem.get(m.id).body == "ACID needed"


def test_filter_rejects_bad_writes():
    mem = _mem()
    for hook, type_ in [("", "fact"), ("x" * 200, "fact"), ("ok", "rumor")]:
        try:
            mem.write(hook, type=type_)
            assert False, "should have rejected"
        except ValueError:
            pass


def test_recall_ranks_by_hook():
    # Recall is lexical by design (no embeddings) — it matches words that appear.
    mem = _mem()
    mem.write("Use Postgres for the ledger", type="decision")
    mem.write("Use React for the frontend", type="fact")
    hits = mem.recall("postgres ledger")
    assert hits and hits[0].id == "use-postgres-for-the-ledger"


def test_recall_omits_body_unless_asked():
    mem = _mem()
    mem.write("Use Postgres", body="secret detail", type="decision")
    assert mem.recall("postgres")[0].body == ""
    assert mem.recall("postgres", with_body=True)[0].body == "secret detail"


def test_update_preserves_created():
    mem = _mem()
    a = mem.write("A fact", body="v1", type="fact")
    b = mem.write("A fact", body="v2", type="fact")
    assert a.id == b.id and b.body == "v2" and b.created == a.created


def test_recall_follows_links():
    # A query that matches only the decision should still pull in the pattern
    # it links to, via one hop.
    mem = _mem()
    mem.write("Exponential backoff with jitter", type="pattern")
    mem.write(
        "Use the retry helper everywhere",
        type="decision",
        links=["exponential-backoff-with-jitter"],
    )
    ids = [m.id for m in mem.recall("retry helper")]
    assert "use-the-retry-helper-everywhere" in ids  # matched
    assert "exponential-backoff-with-jitter" in ids  # pulled in via link

    no_links = [m.id for m in mem.recall("retry helper", follow_links=False)]
    assert "exponential-backoff-with-jitter" not in no_links


def test_related_forward_and_back():
    mem = _mem()
    mem.write("A pattern", type="pattern")
    mem.write("A decision", type="decision", links=["a-pattern"])
    assert "a-decision" in [m.id for m in mem.related("a-pattern")]  # backlink
    assert "a-pattern" in [m.id for m in mem.related("a-decision")]  # forward link


def test_prune_finds_broken_links():
    mem = _mem()
    mem.write("Has a dangling link", type="fact", links=["nope"])
    assert mem.prune()["broken_links"]


def test_context_lists_hooks():
    mem = _mem()
    mem.write("User prefers dark mode", type="preference")
    assert "User prefers dark mode" in mem.context()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
