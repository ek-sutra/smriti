#!/usr/bin/env python3
"""smriti ↔ Claude Code — automatic memory via hooks.

Wire this into Claude Code's hooks so an agent recalls its own memory without
being told to. It runs three ways:

  context   print the whole index (for a SessionStart hook — the agent starts
            every session knowing what it knows)
  recall    read the user's prompt from stdin JSON and print the relevant
            memories (for a UserPromptSubmit hook — surfaced every turn); using
            them = recalling them, so they're reinforced (organ #2)
  write     capture a durable memory from the command line (the curator's job —
            the agent calls this when something worth keeping emerges)

The store is $SMRITI_STORE (a directory of .md files). This helper never breaks a
session: any error exits 0 silently.

Hook config (project .claude/settings.json):

  {"hooks": {
    "SessionStart":     [{"hooks": [{"type": "command",
       "command": "SMRITI_STORE=/abs/store python3.12 /abs/integrations/claude_code.py context"}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command",
       "command": "SMRITI_STORE=/abs/store python3.12 /abs/integrations/claude_code.py recall"}]}]
  }}
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# import smriti from the repo this script lives in — no install required
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

STORE = os.path.expanduser(os.environ.get("SMRITI_STORE", "~/.smriti"))


def _prompt_from_stdin() -> str:
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    if not raw:
        return ""
    try:  # Claude Code passes a JSON event with a `prompt` field
        return str(json.loads(raw).get("prompt", "")).strip()
    except (json.JSONDecodeError, AttributeError):
        return raw.strip()


def main(argv: list[str]) -> int:
    from smriti import Memory
    import reinforce

    mode = argv[1] if len(argv) > 1 else "context"
    mem = Memory(STORE)

    if mode == "context":
        idx = mem.context().strip()
        if idx:
            print("<!-- smriti: what I remember about this work -->")
            print(idx)

    elif mode == "recall":
        prompt = _prompt_from_stdin()
        if not prompt:
            return 0
        hits = mem.recall(prompt, k=5, with_body=True)
        if hits:
            reinforce.reinforce(mem, *[h.id for h in hits])  # using = recalling keeps them alive
            print("<!-- smriti recall: memories relevant to this message -->")
            for h in hits:
                line = f"- [{h.type}] {h.hook}"
                if h.body:
                    line += f" — {h.body}"
                print(line)

    elif mode == "write":
        # write [--type T] [--body B] <hook words...>
        args = argv[2:]
        type_, body = "fact", ""
        out: list[str] = []
        i = 0
        while i < len(args):
            if args[i] == "--type" and i + 1 < len(args):
                type_, i = args[i + 1], i + 2
            elif args[i] == "--body" and i + 1 < len(args):
                body, i = args[i + 1], i + 2
            else:
                out.append(args[i]); i += 1
        hook = " ".join(out).strip()
        if hook:
            m = mem.write(hook, body=body, type=type_)
            print(f"wrote {m.id} [{m.type}]")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except SystemExit:
        raise
    except BaseException:
        sys.exit(0)  # a memory helper must never break the session
