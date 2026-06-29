"""Temporal test — does decay actually sweep the trivia? (No LLM.)

GROWTH.md claimed: trivia is removed by decay over time, not gated at the door.
This puts that claim under load. It finds the claim is only HALF true:

  • decay ALONE is indiscriminate — it forgets a true-but-unused fact ("production
    region is eu-west-1") exactly as fast as trivia ("new office chairs"). Decay
    measures staleness, not worth.
  • the missing half is REINFORCEMENT: when a memory is used (recalled and acted
    on), refresh its recency. Then decay measures time-since-last-USED — so the
    trivia nobody touches fades, and the facts you keep using stay.

That's the spacing effect, in plain text: use keeps alive, disuse lets go.
"""

import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smriti import Memory  # noqa: E402
import forgetting  # noqa: E402
import reinforce  # noqa: E402

BASE = "2026-01-01"
TODAY = date(2026, 7, 20)  # 200 days later: facts (90d half-life) fade; decisions/prefs (365d) don't

KEEPERS_USED = {  # true, and the user keeps asking about them
    "region": ("Production region is eu-west-1", "fact"),
    "name": ("User's name is Gurprit", "fact"),
    "grpc": ("API migrated to gRPC", "fact"),
}
KEEPERS_TYPED = {  # intentional records — sticky by type
    "cedar": ("Use Cedar for authorization", "decision"),
    "postgres": ("Prefers Postgres over Mongo", "preference"),
}
TRIVIA = {  # the noise the curator let through, typed as facts
    "coffee": ("Coffee machine is fixed", "fact"),
    "chairs": ("New office chairs", "fact"),
    "wifi": ("Wifi password changed", "fact"),
}
TRIVIA_TYPED = {  # a trivium the curator mistyped as a decision
    "standup": ("Standup time changed to 9:30", "decision"),
}


def _plant() -> Memory:
    d = Path(tempfile.mkdtemp())
    for id, (hook, typ) in {**KEEPERS_USED, **KEEPERS_TYPED, **TRIVIA, **TRIVIA_TYPED}.items():
        (d / f"{id}.md").write_text(
            f"---\nid: {id}\nhook: {hook}\ntype: {typ}\ncreated: {BASE}\nupdated: {BASE}\nlinks: []\n---\n\nx\n",
            encoding="utf-8",
        )
    return Memory(str(d))


def test_decay_alone_is_indiscriminate():
    faded = {f.id for f in forgetting.plan(_plant(), today=TODAY)}
    assert {"coffee", "chairs", "wifi"} <= faded            # trivia fades — good
    assert {"region", "name", "grpc"} <= faded              # but true keepers fade too — the problem
    assert not ({"cedar", "postgres"} & faded)              # sticky types survive


def test_reinforcement_makes_decay_selective():
    mem = _plant()
    reinforce.reinforce(mem, "region", "name", "grpc", when="2026-07-15")  # the user used them
    faded = {f.id for f in forgetting.plan(mem, today=TODAY)}
    assert faded == {"coffee", "chairs", "wifi"}            # only untouched trivia fades now
    assert not ({"region", "name", "grpc"} & faded)         # used keepers stay


def test_honest_residual_mistyped_trivium_survives():
    # a trivium the curator labelled a 'decision' escapes decay (365d half-life).
    # decay can't fix a curator's type error — recorded, not hidden.
    mem = _plant()
    reinforce.reinforce(mem, "region", "name", "grpc", when="2026-07-15")
    assert "standup" not in {f.id for f in forgetting.plan(mem, today=TODAY)}


if __name__ == "__main__":
    print("PHASE A — decay alone (nothing reinforced):")
    a = sorted(f.id for f in forgetting.plan(_plant(), today=TODAY))
    print(f"  faded: {a}")
    print("  → decay forgets true keepers (region/name/grpc) as fast as trivia. Indiscriminate.\n")

    print("PHASE B — with reinforcement (the user USED region/name/grpc):")
    mem = _plant()
    reinforce.reinforce(mem, "region", "name", "grpc", when="2026-07-15")
    b = sorted(f.id for f in forgetting.plan(mem, today=TODAY))
    print(f"  faded: {b}")
    print("  → only the untouched trivia fades. Used facts stay. Selective.\n")

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print("ok ", fn.__name__)
    print(f"\n{len(fns)} passed")
