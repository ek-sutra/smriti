"""Deterministic tests for the consolidation organ — Stage-0 style, no LLM.

Plants a store with one real cluster (three memories on one subject), a memory
that shares only a single distinctive token (must NOT be pulled in), and two
unrelated singletons. Proves: plan() is read-only, it finds the one true cluster,
one shared token is not enough to merge, and a generic token clusters nothing.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smriti import Memory  # noqa: E402
import consolidate  # noqa: E402


def _store() -> Memory:
    mem = Memory(tempfile.mkdtemp())
    # one subject, three episodes over time (falcon + priya recur)
    mem.write("Falcon migration kickoff scheduled with Priya", type="fact")
    mem.write("Falcon migration blocked on Priya capacity", type="fact")
    mem.write("Falcon rollout endorsed by Priya at review", type="decision")
    # shares only "priya" (one token) with the cluster — must stay out
    mem.write("Priya joined the design guild", type="fact")
    # unrelated singletons
    mem.write("Prefers Postgres over Mongo for datastores", type="preference")
    mem.write("Production runs in region eu-west-1", type="fact")
    return mem


def test_plan_is_read_only():
    mem = _store()
    before = len(mem.all())
    consolidate.plan(mem, rare_fraction=1.0)
    assert len(mem.all()) == before  # surfaces only; fuses nothing


def test_finds_the_one_true_cluster():
    mem = _store()
    clusters = consolidate.plan(mem, rare_fraction=1.0)
    assert len(clusters) == 1
    c = clusters[0]
    ids = {m.id for m in c.members}
    assert ids == {
        "falcon-migration-kickoff-scheduled-with-priya",
        "falcon-migration-blocked-on-priya-capacity",
        "falcon-rollout-endorsed-by-priya-at-review",
    }
    assert c.fusible and "falcon" in c.core  # a real subject has a shared core


def _hub_store() -> Memory:
    """Two real subjects welded by one bridging memory — the over-merge shape."""
    mem = Memory(tempfile.mkdtemp())
    mem.write("Falcon migration kickoff Tuesday", type="fact")          # A
    mem.write("Falcon migration blocked capacity", type="fact")         # A
    mem.write("Jupiter rollout planned Friday", type="fact")            # B
    mem.write("Jupiter rollout delayed review", type="fact")            # B
    mem.write("capacity blocked, review delayed", type="fact")          # hub → welds A+B
    return mem


def test_hub_bridge_is_flagged_not_fused():
    # single-link chaining welds the two subjects into one 5-member component,
    # but it has no token shared by half — so it is flagged, never offered to fuse.
    mem = _hub_store()
    clusters = consolidate.plan(mem, rare_fraction=1.0)
    assert [c for c in clusters if c.fusible] == []      # nothing fusible
    flagged = [c for c in clusters if not c.fusible]
    assert len(flagged) == 1 and len(flagged[0].members) == 5 and flagged[0].core == []


def test_true_subjects_fuse_once_the_hub_is_gone():
    # control: without the bridging memory, the same two subjects are two clean
    # fusible clusters. So the gate withholds the blob, not the real subjects.
    mem = _hub_store()
    mem.delete("capacity-blocked-review-delayed")
    ready = [c for c in consolidate.plan(mem, rare_fraction=1.0) if c.fusible]
    assert len(ready) == 2 and all(len(c.members) == 2 for c in ready)


def test_single_shared_token_does_not_merge():
    mem = _store()
    clusters = consolidate.plan(mem, rare_fraction=1.0)
    joined = {m.id for c in clusters for m in c.members}
    assert "priya-joined-the-design-guild" not in joined  # one shared token < min_shared


def test_generic_token_clusters_nothing():
    # every memo shares "opus" but nothing else — a generic token must not fuse them
    mem = Memory(tempfile.mkdtemp())
    mem.write("Opus login flow uses discovery endpoint", type="fact")
    mem.write("Opus billing bridge is many to one", type="fact")
    mem.write("Opus client splits lo-fi and hi-fi", type="fact")
    mem.write("Opus catalogue enters at Q4 migration", type="fact")
    assert consolidate.plan(mem, rare_fraction=0.5) == []  # "opus" is too common to count


def test_small_store_is_empty():
    mem = Memory(tempfile.mkdtemp())
    mem.write("Only one memory here", type="fact")
    assert consolidate.plan(mem) == []


def test_fuse_is_read_only_until_applied():
    mem = _store()
    before = len(mem.all())
    f = consolidate.fuse(
        mem,
        ["falcon-migration-kickoff-scheduled-with-priya",
         "falcon-migration-blocked-on-priya-capacity"],
        "Falcon effort with Priya stalled",  # note: no "migration" — it becomes a cue
        "The Falcon effort began with Priya and stalled on capacity.",
    )
    assert len(mem.all()) == before  # apply=False changes nothing
    assert f.applied is False and "migration" in f.cues  # a source word not in the hook


def test_fuse_folds_writes_cues_archives_and_relinks():
    mem = Memory(tempfile.mkdtemp())
    a = mem.write("Falcon migration kickoff with Priya", type="fact")
    b = mem.write("Falcon migration blocked on capacity", type="fact")
    # a bystander memory that points at one of the sources — its link must follow
    mem.write("Priya owns the migration", type="fact", links=[a.id])

    f = consolidate.fuse(
        mem, [a.id, b.id],
        "Falcon migration: kickoff then blocked on capacity",
        "Kickoff with Priya; then stalled on capacity.",
        apply=True,
    )

    ids = {m.id for m in mem.all()}
    assert f.id in ids                      # the pattern exists
    assert a.id not in ids and b.id not in ids  # sources left the store
    # sources archived, not destroyed — the fold is reversible
    assert (Path(mem.dir) / consolidate.ARCHIVE / f"{a.id}.md").exists()
    # cues written into the body → lexical recall still finds it under a source word
    pat = mem.get(f.id)
    assert "Cues:" in pat.body and "capacity" in pat.body
    assert mem.recall("capacity")[0].id == f.id
    # the bystander's link was repointed to the pattern; no dangling links anywhere
    assert mem.get("priya-owns-the-migration").links == [f.id]
    assert mem.prune()["broken_links"] == []


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print("ok ", fn.__name__)
    print(f"\n{len(fns)} passed")
