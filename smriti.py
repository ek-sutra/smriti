"""
smriti — plain-text memory for AI agents.

Memory that is small, filtered, compressed, and self-pruning — stored as
human-readable markdown files in a directory you can read with `cat` and
version with `git`. No database, no embeddings, no vendor, no dependencies
(Python standard library only).

The value is not the storage — it's the discipline:

  1. WRITE FILTER   store only what's worth remembering (a decision, a pattern,
                    a fact, a preference) — not everything.
  2. COMPRESS       each memory is a one-line HOOK + a short body (the seed),
                    never a document.
  3. RECALL BY HOOK retrieve the small hooks first; descend to a full body only
                    when a hook actually matches what you need.
  4. PRUNE          surface stale, duplicate, and broken memories so the store
                    stays lean instead of accreting forever.

The format is the artifact and will outlive this file. This library is just a
small, replaceable reference reader/writer for it. See SPEC.md.

Quick start:

    from smriti import Memory
    mem = Memory("./memory")
    mem.write("User prefers dark mode", type="preference")
    mem.context()                 # -> the index to inject into your prompt
    mem.recall("dark mode")       # -> ranked matching memories
    mem.get("user-prefers-dark-mode").body
    mem.prune()                   # -> {stale, duplicates, broken_links}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

__all__ = ["Memory", "Memo", "VALID_TYPES"]

# The small, fixed set of memory kinds. Keep it small on purpose: a type you
# can't choose quickly is a type that won't be used. (Subtract, don't add.)
VALID_TYPES = ("fact", "preference", "decision", "pattern", "reference")

HOOK_MAX = 120      # a hook longer than one line isn't a hook
BODY_MAX = 1500     # a body longer than this is a document — compress it
INDEX_FILE = "INDEX.md"

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for",
    "on", "with", "it", "this", "that", "be", "by", "as", "at", "from",
}


# ── data ──────────────────────────────────────────────────────────────────────
@dataclass
class Memo:
    id: str
    hook: str
    type: str
    body: str = ""
    created: str = ""
    updated: str = ""
    links: list[str] = field(default_factory=list)

    def line(self) -> str:
        """One-line index entry — the form that gets injected into a prompt."""
        return f"- [{self.hook}]({self.id}.md) — {self.type}"


# ── tiny frontmatter (a YAML subset — no dependency) ──────────────────────────
def _split(text: str) -> tuple[str, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[3:end].strip("\n"), text[end + 4 :].lstrip("\n")
    return "", text


def _parse_meta(fm: str) -> dict:
    meta: dict = {}
    for raw in fm.splitlines():
        if not raw.strip() or ":" not in raw:
            continue
        key, val = raw.split(":", 1)
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            meta[key] = [p.strip().strip("\"'") for p in inner.split(",") if p.strip()]
        else:
            meta[key] = val.strip("\"'")
    return meta


def _dump_meta(meta: dict) -> str:
    out = ["---"]
    for key in ("id", "hook", "type", "created", "updated", "links"):
        if key not in meta:
            continue
        val = meta[key]
        if isinstance(val, list):
            val = "[" + ", ".join(val) + "]"
        out.append(f"{key}: {val}")
    out.append("---")
    return "\n".join(out)


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "memo"


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _today() -> str:
    return date.today().isoformat()


# ── store ─────────────────────────────────────────────────────────────────────
class Memory:
    """A directory of markdown memories. Cheap to construct; reads on demand."""

    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    # -- load ------------------------------------------------------------------
    def all(self) -> list[Memo]:
        memos = []
        for path in sorted(self.dir.glob("*.md")):
            if path.name == INDEX_FILE:
                continue
            memos.append(self._read(path))
        return memos

    def _read(self, path: Path) -> Memo:
        fm, body = _split(path.read_text(encoding="utf-8"))
        meta = _parse_meta(fm)
        return Memo(
            id=meta.get("id", path.stem),
            hook=meta.get("hook", path.stem),
            type=meta.get("type", "fact"),
            body=body.strip(),
            created=meta.get("created", ""),
            updated=meta.get("updated", ""),
            links=meta.get("links", []) if isinstance(meta.get("links"), list) else [],
        )

    def get(self, id: str) -> Memo | None:
        path = self.dir / f"{id}.md"
        return self._read(path) if path.exists() else None

    # -- write (rules 1 & 2: filter + compress) --------------------------------
    def write(
        self,
        hook: str,
        body: str = "",
        type: str = "fact",
        id: str | None = None,
        links: list[str] | None = None,
    ) -> Memo:
        """Store a memory. Enforces the mechanical parts of the filter:
        a valid type, a one-line hook, a compressed body, no duplicate id.
        (Whether a thing is *worth* remembering is the caller's judgment —
        this enforces that what's stored is stored *well*.)"""
        hook = hook.strip()
        if not hook:
            raise ValueError("a memory needs a hook (one line saying what it is)")
        if len(hook) > HOOK_MAX:
            raise ValueError(f"hook too long ({len(hook)}>{HOOK_MAX}) — compress it to one line")
        if type not in VALID_TYPES:
            raise ValueError(f"type must be one of {VALID_TYPES}, got {type!r}")
        if len(body) > BODY_MAX:
            raise ValueError(
                f"body too long ({len(body)}>{BODY_MAX}) — store the seed, link the document"
            )

        mid = id or _slug(hook)
        path = self.dir / f"{mid}.md"
        existing = self._read(path) if path.exists() else None  # same id = update

        meta = {
            "id": mid,
            "hook": hook,
            "type": type,
            "created": existing.created if existing and existing.created else _today(),
            "updated": _today(),
            "links": links if links is not None else (existing.links if existing else []),
        }
        path.write_text(_dump_meta(meta) + "\n\n" + body.strip() + "\n", encoding="utf-8")
        self._write_index()
        return self._read(path)

    def delete(self, id: str) -> bool:
        path = self.dir / f"{id}.md"
        if path.exists():
            path.unlink()
            self._write_index()
            return True
        return False

    # -- recall (rule 3: by hook, ranked, no embeddings) -----------------------
    @staticmethod
    def _strip(m: Memo) -> Memo:
        return Memo(m.id, m.hook, m.type, "", m.created, m.updated, m.links)

    def recall(
        self, query: str, k: int = 5, with_body: bool = False, follow_links: bool = True
    ) -> list[Memo]:
        """Return the memories most relevant to `query`, ranked. Matches on the
        hook (weighted), type, and body — plain token overlap, deterministic,
        dependency-free. When `follow_links` is set, the top hits also pull in
        the memories they link to (one hop): a decision brings the pattern it
        rests on. Bodies are omitted unless `with_body=True`."""
        q = _tokens(query)
        if not q:
            return []
        memos = self.all()
        scored = []
        for m in memos:
            score = (
                3 * len(q & _tokens(m.hook))
                + 2 * len(q & _tokens(m.type))
                + 1 * len(q & _tokens(m.body))
            )
            if score:
                scored.append((score, m))
        scored.sort(key=lambda s: s[0], reverse=True)
        hits = [m for _, m in scored[:k]]

        if follow_links:  # walk the links already written into the files (one hop)
            by_id = {m.id: m for m in memos}
            seen = {m.id for m in hits}
            for m in list(hits):
                for lid in m.links:
                    if lid not in seen and lid in by_id:
                        hits.append(by_id[lid])
                        seen.add(lid)

        return hits if with_body else [self._strip(m) for m in hits]

    def related(self, id: str, with_body: bool = False) -> list[Memo]:
        """Memories one hop from `id` — both the ones it links to (forward) and
        the ones that link to it (back). The graph the `links` field describes."""
        memos = self.all()
        here = next((m for m in memos if m.id == id), None)
        if here is None:
            return []
        want = (set(here.links) | {m.id for m in memos if id in m.links}) - {id}
        out = [m for m in memos if m.id in want]
        return out if with_body else [self._strip(m) for m in out]

    def context(self) -> str:
        """The whole index as text — cheap to inject into a system prompt every
        turn. Hooks only: the agent sees *what it knows*, and calls get(id) to
        descend only when a hook is relevant. (Deploy the seed, not the document.)"""
        return (self.dir / INDEX_FILE).read_text(encoding="utf-8") if (self.dir / INDEX_FILE).exists() else self._render_index()

    # -- prune (rule 4: keep it lean) ------------------------------------------
    def prune(self, stale_days: int = 180, dup_threshold: float = 0.8) -> dict:
        """Surface (never auto-delete) memories that have gone bad:
        stale (untouched too long), duplicates (near-identical hooks), and
        broken links (pointing at an id that no longer exists)."""
        memos = self.all()
        ids = {m.id for m in memos}
        today = date.today()

        stale = []
        for m in memos:
            if not m.updated:
                continue
            try:
                age = (today - datetime.fromisoformat(m.updated).date()).days
            except ValueError:
                continue
            if age > stale_days:
                stale.append((m.id, age))

        duplicates = []
        for i, a in enumerate(memos):
            ta = _tokens(a.hook)
            for b in memos[i + 1 :]:
                tb = _tokens(b.hook)
                union = ta | tb
                if union and len(ta & tb) / len(union) >= dup_threshold:
                    duplicates.append((a.id, b.id))

        broken = [(m.id, link) for m in memos for link in m.links if link not in ids]

        return {"stale": stale, "duplicates": duplicates, "broken_links": broken}

    # -- index -----------------------------------------------------------------
    def _render_index(self) -> str:
        memos = self.all()
        lines = ["# Memory Index", "", f"{len(memos)} memories. One line each — load this into context.", ""]
        for t in VALID_TYPES:
            group = [m for m in memos if m.type == t]
            if not group:
                continue
            lines.append(f"## {t}")
            lines += [m.line() for m in sorted(group, key=lambda m: m.updated, reverse=True)]
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _write_index(self) -> None:
        (self.dir / INDEX_FILE).write_text(self._render_index(), encoding="utf-8")


# ── tiny CLI: `python smriti.py <dir> <command> [args]` ───────────────────────
def _main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: python smriti.py <dir> <context|recall|prune|write> [args]")
        return 1
    mem = Memory(argv[1])
    cmd = argv[2]
    if cmd == "context":
        print(mem.context())
    elif cmd == "recall":
        for m in mem.recall(" ".join(argv[3:])):
            print(f"  {m.line()}")
    elif cmd == "prune":
        report = mem.prune()
        for kind, items in report.items():
            print(f"{kind}: {items or '—'}")
    elif cmd == "write":
        hook = " ".join(argv[3:])
        m = mem.write(hook)
        print(f"wrote {m.id}")
    else:
        print(f"unknown command: {cmd}")
        return 1
    return 0


def cli() -> None:
    """Console entry point (installed as the `smriti` command; see pyproject)."""
    import sys

    raise SystemExit(_main(sys.argv))


if __name__ == "__main__":
    cli()
