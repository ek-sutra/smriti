#!/usr/bin/env python3
"""brain — a personal companion with a long memory, built on smriti.

A real, daily-use CLI: talk to it, and it remembers durable things about you
across every session — stored as plain markdown files you can read and edit.
It composes the whole smriti kit in one loop:

  • recall      — pull what's relevant to your message (rule 3)
  • reinforce   — using a memory keeps it alive (organ #2)
  • write       — capture only what's durable, compressed (rules 1-2)
  • forget      — /forget sweeps rot + duplicates, transparently (organ #1)

No database, no embeddings, no vendor. Memory lives in $BRAIN_DIR (default
~/.brain) as <id>.md. Model is local Ollama (no API key) — set $BRAIN_MODEL.

    ollama serve &              # once
    python examples/brain.py    # then just talk

Commands:  /memories   /recall <q>   /forget   /help   /quit
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from smriti import Memory  # noqa: E402
import forgetting  # noqa: E402
import reinforce  # noqa: E402

MODEL = os.environ.get("BRAIN_MODEL", "mistral:latest")
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
BRAIN_DIR = os.environ.get("BRAIN_DIR", str(Path.home() / ".brain"))

SYSTEM = (
    "You are a personal companion with a long memory. You are shown what you already "
    "remember about the user, then their latest message. Do two things and reply with "
    "JSON ONLY:\n"
    '  {"reply": "<a short, natural reply>",\n'
    '   "remember": [{"hook": "<one line, the durable fact>", '
    '"type": "fact|preference|decision|pattern|reference", "body": "<optional detail>"}]}\n'
    "Only remember things that are DURABLE and worth keeping months from now — a stable "
    "fact about the user, a preference, a decision. Capture ONLY NEW information the user "
    "states in this message — never re-store something already shown in memory, and never "
    "store facts you are merely recalling or repeating back. Never remember small talk or "
    "passing state. If nothing new is worth keeping, use an empty list. Put the key fact "
    "in the hook."
)


def ollama_chat(messages: list[dict]) -> str:
    payload = json.dumps(
        {"model": MODEL, "messages": messages, "stream": False,
         "options": {"temperature": 0.4, "num_predict": 400}}
    ).encode()
    req = urllib.request.Request(f"{HOST}/api/chat", data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["message"]["content"]


def parse(text: str) -> tuple[str, list[dict]]:
    """Pull {reply, remember} out of the model's JSON; degrade gracefully."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return text.strip(), []
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return text.strip(), []
    reply = str(obj.get("reply") or "").strip() or "(no reply)"
    items = [it for it in (obj.get("remember") or [])
             if isinstance(it, dict) and it.get("hook") and it.get("type")]
    return reply, items


DIM, OFF, BOLD = "\033[2m", "\033[0m", "\033[1m"


def note(s: str) -> None:
    print(f"{DIM}  {s}{OFF}")


def show_memories(mem: Memory) -> None:
    rows = sorted(mem.all(), key=lambda m: m.updated, reverse=True)
    if not rows:
        note("(nothing remembered yet)")
        return
    for m in rows:
        print(f"  {DIM}[{m.type}]{OFF} {m.hook}  {DIM}· {m.updated}{OFF}")


def do_forget(mem: Memory) -> None:
    plan = forgetting.plan(mem)
    if not plan:
        note("nothing to forget — store is clean")
        return
    print(f"{BOLD}  would forget:{OFF}")
    for f in plan:
        print(f"    {f.hook}  {DIM}— {f.reason}{OFF}")
    if input("  forget these? [y/N] ").strip().lower() == "y":
        forgetting.forget(mem, apply=True)
        note(f"forgot {len(plan)} · recorded in .forgotten/log.md")


def turn(mem: Memory, user: str) -> None:
    # rule 3: inject the cheap index every turn (so meta-queries like "what do you
    # know about me?" work), then descend to bodies only for the sharp matches.
    ambient = mem.context()
    recalled = mem.recall(user, k=3, with_body=True)
    if recalled:
        reinforce.reinforce(mem, *[m.id for m in recalled])  # using them keeps them alive
    detail = "\n".join(f"- {m.hook}: {m.body}" for m in recalled if m.body)
    known = ambient + (f"\n\nRelevant detail:\n{detail}" if detail else "")
    content = f"What you remember about the user:\n{known}\n\nUser: {user}"

    try:
        raw = ollama_chat([{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": content}])
    except (urllib.error.URLError, OSError) as e:
        note(f"model unreachable ({e}). Is `ollama serve` running?")
        return

    reply, items = parse(raw)
    print(f"\n{reply}\n")
    if recalled:
        note(f"↺ recalled {len(recalled)}, reinforced")
    for it in items:
        try:
            m = mem.write(str(it["hook"])[:120], body=str(it.get("body", ""))[:1500], type=str(it["type"]))
            note(f"+ remembered [{m.type}]: {m.hook}")
        except (ValueError, KeyError, TypeError):
            pass  # malformed — the filter rejects it


def main() -> int:
    mem = Memory(BRAIN_DIR)
    print(f"{BOLD}brain{OFF} {DIM}· {MODEL} · {len(mem.all())} memories · {BRAIN_DIR}{OFF}")
    note("talk to me. /help for commands.")
    while True:
        try:
            line = input(f"{BOLD}> {OFF}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("/quit", "/exit", "/q"):
            break
        if line in ("/help", "/h"):
            note("/memories  /recall <q>  /forget  /quit")
        elif line in ("/memories", "/mem"):
            show_memories(mem)
        elif line.startswith("/recall "):
            for m in mem.recall(line[8:], k=5):
                print(f"  {DIM}[{m.type}]{OFF} {m.hook}")
        elif line == "/forget":
            do_forget(mem)
        else:
            turn(mem, line)
    note("memory saved. bye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
