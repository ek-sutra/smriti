# smriti + Claude Code

Give a Claude Code agent automatic memory: it recalls what it knows on every
session and every prompt, without being told to.

`claude_code.py` runs three ways — `context` (print the index), `recall` (read a
prompt from stdin, print relevant memories, reinforce them), `write` (capture a
durable memory). The store is `$SMRITI_STORE`, a directory of `.md` files.

## Wire it

In `.claude/settings.json` (project) or `~/.claude/settings.json` (all projects):

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command",
        "command": "SMRITI_STORE=/abs/path/to/store python3 /abs/path/smriti/integrations/claude_code.py context" } ] }
    ],
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command",
        "command": "SMRITI_STORE=/abs/path/to/store python3 /abs/path/smriti/integrations/claude_code.py recall" } ] }
    ]
  }
}
```

Use a Python ≥ 3.10. The helper imports smriti from the repo it lives in — no
install needed. Any error exits 0, so a memory hook can never break a session.

## The split that matters

- **Recall is automatic** — mechanical, so hooks own it.
- **Write is curated** — worth is a judgment, so the agent owns it: it calls
  `claude_code.py write --type decision "<the durable thing>"` when something
  worth keeping months from now actually emerges. (This is the triage lesson:
  a gate can't tell trivia from substance; the curator can.)
