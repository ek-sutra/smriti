"""consolidate — the consolidation organ for smriti. Many episodes → one memory.

One job: surface CLUSTERS of memories that have become a single recurring subject
over time — the ones a human mind would already hold as one *pattern* — so the
curator can fuse them (episodic → semantic). It only *surfaces*; it never fuses.
Deciding what a cluster *means*, and writing the one hook+seed that carries it, is
the curator's judgment. The triage lesson holds: worth — and sameness — is
semantic, not lexical, so a regex must never author a memory (see GROWTH.md).

Every other organ is subtractive or custodial: forgetting removes rot, reinforce
maintains, prune cleans. This is the one *generative* organ — it moves memory up a
level of abstraction. That upward fold is the most human thing a memory does.

It reads plain text and stands alone, stdlib only. It clusters on *distinctive*
shared tokens — proper nouns and rare domain words; a token in most memos is too
generic to mean "same subject" — plus the `links` graph. No embeddings: a
cluster's shared vocabulary is reported as `cues`, to be written *into* the fused
pattern's body, so ordinary lexical recall finds it later. Meaning must live in
the text, never beside it — so consolidation closes the synonym wall from the
write side, without a vector index.

    from smriti import Memory
    from consolidate import plan

    for c in plan(Memory(store)):          # read-only — fuses nothing
        print(c.reason)
        for m in c.members:
            print("   ", m.hook)

    # the curator then fuses ONE cluster it agrees is one subject, in its own
    # words — carrying every load-bearing claim, and the cues, into the seed:
    #   mem.write(gist_hook, gist_body, type="pattern",
    #             links=[m.id for m in c.members])
    # …and archives the sources it folded. Fusion is not automated here on
    # purpose: the false-merge cost (fusing "postgres for ledger" with "postgres
    # for billing") is too high to hand a machine. Surface, then let a mind fold.

Clustering is single-link (transitive), so a hub memory touching two subjects can
chain them into one component. That over-merge is caught, not avoided: a component
is only fuse-ready when a distinctive token is shared by a *core* — at least half
its members (`CORE_FRACTION`). A hub-bridged blob has no such core, so it is
withheld from the fuse-ready list and reported *flagged* for a human to split —
never swallowed silently (the tombstone rule). Read `c.fusible`; fuse only those.
`RARE_FRACTION` tunes what counts as "too generic"; it suits larger stores.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from math import ceil
from pathlib import Path

from smriti import Memory, _slug

# A token in more than this fraction of the store is too generic to mean "same
# subject" (e.g. "opus" in an OPUS-heavy store) — excluded from clustering.
RARE_FRACTION = 0.5
MIN_SHARED = 2      # memos need ≥2 shared distinctive tokens to join (or a link)
MIN_CLUSTER = 2     # a cluster is ≥2 memories — one memory is not a consolidation
CORE_FRACTION = 0.5  # a fuse-ready cluster shares a token across ≥ this fraction
# Folded sources are archived here (never deleted) — the fold is reversible, like
# forgetting's tombstone. The subdir is never globbed as a memory.
ARCHIVE = ".consolidated"
CUES_MAX = 24        # a Cues line is the salient shared vocabulary, not every token

_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on",
    "with", "it", "this", "that", "be", "by", "as", "at", "from", "was", "not",
    "but", "our", "we", "you", "they", "his", "her", "its", "into", "over",
}


@dataclass
class Cluster:
    """A set of memories that read as one subject — a candidate for one pattern.

    `core` is the distinctive tokens shared by at least half the members: the
    subject the cluster is *about*. A cluster with a core is `fusible` (hand it to
    the curator to fold). A cluster with none is a hub-bridged blob — reported, but
    withheld from fusing until a human splits it."""

    members: list          # list[Memo], most-recently-updated first
    cues: list[str] = field(default_factory=list)   # tokens shared by ≥2 members
    core: list[str] = field(default_factory=list)   # tokens shared by ≥ half
    score: int = 0         # cohesion: summed pairwise shared-distinctive tokens

    @property
    def fusible(self) -> bool:
        return bool(self.core)

    @property
    def reason(self) -> str:
        k = len(self.members)
        if self.core:
            return f"{k} memories on one subject — core: {', '.join(self.core[:6])}"
        return (
            f"{k} memories chained through hubs — no shared core "
            f"(bridged by: {', '.join(self.cues[:6]) or 'links'}) — split by hand"
        )


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in _STOP}


class _UF:
    """Tiny union-find over ids — the associative graph, resolved to components."""

    def __init__(self, ids):
        self.p = {i: i for i in ids}

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def plan(
    mem: Memory,
    min_shared: int = MIN_SHARED,
    rare_fraction: float = RARE_FRACTION,
    min_cluster: int = MIN_CLUSTER,
    core_fraction: float = CORE_FRACTION,
) -> list[Cluster]:
    """Candidate clusters, fuse-ready first. Read-only — fuses nothing.

    Two memos join a cluster when they share ≥`min_shared` *distinctive* hook
    tokens, or when the `links` graph already ties them. A distinctive token is
    one shared by at least two memos but present in at most `rare_fraction` of the
    store (generic tokens cluster everything and mean nothing). A cluster is
    `fusible` only if some token is shared by ≥`core_fraction` of its members;
    otherwise it is a hub-bridged blob, returned flagged (not fused)."""
    memos = mem.all()
    if len(memos) < 2:
        return []

    toks = {m.id: _tokens(m.hook) for m in memos}
    df: Counter = Counter()
    for ts in toks.values():
        for t in ts:
            df[t] += 1

    cap = max(3, round(rare_fraction * len(memos)))
    distinctive = {mid: {t for t in ts if 2 <= df[t] <= cap} for mid, ts in toks.items()}

    uf = _UF(m.id for m in memos)
    for i, a in enumerate(memos):
        da, la = distinctive[a.id], set(a.links)
        for b in memos[i + 1 :]:
            shared = da & distinctive[b.id]
            linked = b.id in la or a.id in set(b.links) or bool(la & set(b.links))
            if len(shared) >= min_shared or linked:
                uf.union(a.id, b.id)

    groups: dict[str, list] = defaultdict(list)
    for m in memos:
        groups[uf.find(m.id)].append(m)

    clusters: list[Cluster] = []
    for members in groups.values():
        k = len(members)
        if k < min_cluster:
            continue
        seen: Counter = Counter()
        for m in members:
            seen.update(distinctive[m.id])
        cues = [t for t, c in seen.most_common() if c >= 2]
        # the core: tokens the subject actually shares across ≥ half its members.
        # No core → the component is only hub-bridged (distinct subjects welded by
        # a shared date/name), so it is reported but not offered for fusing.
        core_min = max(2, ceil(core_fraction * k))
        core = [t for t, c in seen.most_common() if c >= core_min]
        ids = [m.id for m in members]
        score = sum(
            len(distinctive[ids[i]] & distinctive[ids[j]])
            for i in range(len(ids))
            for j in range(i + 1, len(ids))
        )
        members.sort(key=lambda m: m.updated, reverse=True)
        clusters.append(Cluster(members, cues, core, score))

    # fuse-ready first, then flagged; each group strongest-cohesion first.
    clusters.sort(key=lambda c: (c.fusible, c.score, len(c.members)), reverse=True)
    return clusters


@dataclass
class Fusion:
    """The record of a fold: many episodes → one pattern."""

    id: str                # the new pattern's id
    sources: list[str]     # the memories folded into it (now archived)
    cues: list[str]        # their vocabulary, written into the pattern's body
    relinked: list[str]    # memories whose links were repointed to the pattern
    applied: bool


def _set_links(path: Path, links: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    new = re.sub(r"(?m)^links:.*$", "links: [" + ", ".join(links) + "]", text, count=1)
    if new != text:
        path.write_text(new, encoding="utf-8")


def fuse(
    mem: Memory,
    source_ids: list[str],
    hook: str,
    body: str,
    type: str = "pattern",
    id: str | None = None,
    links: list[str] | None = None,
    apply: bool = False,
) -> Fusion:
    """Fold a cluster the curator has judged one subject into a single memory.

    The curator authors the semantic part — `hook` and `body` (carrying every
    load-bearing claim; the one-seed test is the curator's, not ours). This does
    only the mechanical, reversible part:
      • writes the sources' vocabulary into the body as a `Cues:` line, so lexical
        recall still finds the pattern under every word that found a source;
      • gives the pattern the sources' *outbound* links (not the sources), so the
        graph stays valid — no dangling links;
      • repoints every *inbound* link (memories elsewhere that pointed at a source)
        to the new pattern, so associations survive the fold;
      • archives each source to `.consolidated/` and logs it — never deletes.
    Read-only unless `apply=True`."""
    srcs = []
    for sid in source_ids:
        m = mem.get(sid)
        if m is None:
            raise ValueError(f"unknown source id: {sid!r}")
        srcs.append(m)
    if len(srcs) < 2:
        raise ValueError("fuse needs ≥2 source memories — one memory is not a fold")

    new_id = id or _slug(hook)
    # cues: the sources' salient shared vocabulary (most common first, capped) —
    # written into the body so lexical recall still finds the pattern by old words.
    cue_counts = Counter(t for m in srcs for t in _tokens(m.hook))
    for t in _tokens(hook):
        cue_counts.pop(t, None)
    cues = [t for t, _ in cue_counts.most_common(CUES_MAX)]
    inherited = {l for m in srcs for l in m.links} - set(source_ids) - {new_id}
    new_links = sorted(inherited | set(links or []))

    full = body.rstrip()
    if cues:
        full += "\n\nCues: " + ", ".join(cues)
    # provenance stays in the archive log (which holds every source id), so the
    # body stays bounded no matter how many or how long the source ids are.
    full += f"\n\nFolded from {len(srcs)} memories — see {ARCHIVE}/log.md"

    # who elsewhere points at a source? those links must follow it into the pattern
    relinked: list[str] = []
    src_set = set(source_ids)
    for m in mem.all():
        if m.id in src_set or m.id == new_id:
            continue
        if src_set & set(m.links):
            repointed, seen = [], set()
            for l in m.links:
                nl = new_id if l in src_set else l
                if nl not in seen:
                    repointed.append(nl)
                    seen.add(nl)
            if apply:
                _set_links(Path(mem.dir) / f"{m.id}.md", repointed)
            relinked.append(m.id)

    if apply:
        mem.write(hook, full, type=type, id=new_id, links=new_links)
        arch = Path(mem.dir) / ARCHIVE
        arch.mkdir(exist_ok=True)
        log = arch / "log.md"
        new_log = not log.exists()
        with log.open("a", encoding="utf-8") as fh:
            if new_log:
                fh.write("# Consolidated\n\n> Episodes folded into patterns. "
                         "The sources remain here and in git — the fold is reversible.\n\n")
            for m in srcs:
                fh.write(f"- {date.today().isoformat()} · `{m.id}` → `{new_id}` — {m.hook}\n")
        for m in srcs:
            (Path(mem.dir) / f"{m.id}.md").rename(arch / f"{m.id}.md")
        mem._write_index()  # sources are gone from the store now — refresh the index

    return Fusion(new_id, list(source_ids), cues, relinked, apply)


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python consolidate.py <store-dir>")
        return 1
    clusters = plan(Memory(argv[1]))
    ready = [c for c in clusters if c.fusible]
    flagged = [c for c in clusters if not c.fusible]
    if not clusters:
        print("no consolidation candidates — nothing has clustered into one subject yet.")
        return 0

    print(f"{len(ready)} fuse-ready cluster(s) — the curator folds each into one pattern:\n")
    for i, c in enumerate(ready, 1):
        print(f"[{i}] {c.reason}")
        for m in c.members:
            print(f"      · ({m.type}) {m.hook}")
        print()

    if flagged:
        print(f"{len(flagged)} flagged cluster(s) — hub-bridged, no shared core; split by hand:\n")
        for i, c in enumerate(flagged, 1):
            print(f"[F{i}] {c.reason}")
            for m in c.members:
                print(f"      · ({m.type}) {m.hook}")
            print()
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv))
