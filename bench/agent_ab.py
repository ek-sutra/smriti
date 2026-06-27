#!/usr/bin/env python3
"""Stage 1 (v2) — the brain: agent-driven curation, real metrics, harder needs.

Plays an agent through multi-turn scenarios under three arms:

    none      sees only the current turn (the floor)
    dump      sees the entire transcript of the current session (the hoard)
    smriti    the AGENT curates its own memory, then reads the compressed index

v1 isolated *reading* (writes were a fixed policy). v2 tests the harder, more
honest thing: whether the model, guided by the four rules, *curates* well —
keeps the durable, drops the noise, compresses to a hook, overwrites on update.
After each information turn the agent is shown the rules + the current index and
replies with JSON for what to persist; we write it through `smriti` (which
enforces shape) and measure what survives.

Metrics are real: tokens and latency come from the backend (Ollama's
prompt_eval_count / eval_count / total_duration; Anthropic's usage). For smriti
we also report the final store size — the anti-hoard measure.

Grading stays deterministic (each probe's correct answer is a known string).

New needs covered:
  • cross-session persistence — a probe in a later "session" after the transcript
    is gone. none/dump can't help; smriti's files survive on disk.
  • precision under heavy noise — many distractors; does curation stay lean?
  • update / contradiction — does the agent overwrite the stale value?
  (link recall is covered deterministically in mechanics.py — Stage 0.)

Run (local, no key):
    SMRITI_BENCH_BACKEND=ollama SMRITI_BENCH_MODEL=mistral:latest python bench/agent_ab.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from smriti import Memory  # noqa: E402


@dataclass
class Result:
    text: str
    in_tokens: int = 0
    out_tokens: int = 0
    ms: float = 0.0


Model = Callable[[str, list[dict]], Result]


@dataclass
class Turn:
    user: str
    session: int = 1
    expect: list[str] | None = None  # probe if set


@dataclass
class Scenario:
    name: str
    turns: list[Turn] = field(default_factory=list)


@dataclass
class Stats:
    passed: int = 0
    total: int = 0
    in_tokens: int = 0
    out_tokens: int = 0
    ms: float = 0.0
    store: int = 0  # final memory count (smriti only)

    def add(self, r: Result) -> None:
        self.in_tokens += r.in_tokens
        self.out_tokens += r.out_tokens
        self.ms += r.ms


ANSWER_SYSTEM = (
    "You are a helpful assistant with memory of this user across sessions. "
    "Answer the user's latest message directly and concretely, using anything you "
    "remember. If you genuinely don't know, say so in a few words."
)

CURATE_SYSTEM = (
    "You maintain an assistant's long-term memory. After an exchange, decide what — "
    "if anything — is worth remembering. Follow these rules:\n"
    "1. Keep only durable, non-obvious things: a fact, preference, decision, or pattern. "
    "Skip small talk and anything easily re-derived.\n"
    "2. Compress each to a one-line hook (<=120 chars) that itself states the key fact "
    "literally — the name, the value, the choice — not buried in the body. Add a short body for detail.\n"
    "3. If a new statement updates an existing memory, REUSE that memory's id to overwrite it.\n"
    'Reply with JSON ONLY: {"remember":[{"hook":"...","type":"fact|preference|decision|pattern|reference","body":"...","id":"optional-to-overwrite"}]} '
    'or {"remember":[]} if nothing is worth keeping.'
)


# ── models ────────────────────────────────────────────────────────────────────
def echo_model(system: str, messages: list[dict]) -> Result:
    """Wiring self-test only (zero tokens). 'Knows' its context; cannot curate —
    so the smriti arm will underperform under echo. Use a real backend for results."""
    text = system + "\n" + "\n".join(m["content"] for m in messages)
    approx = (len(system) + sum(len(m["content"]) for m in messages)) // 4
    return Result(text=text, in_tokens=approx, out_tokens=len(text) // 4)


def ollama_model(model_id: str, host: str) -> Model:
    import urllib.request

    url = host.rstrip("/") + "/api/chat"

    def call(system: str, messages: list[dict]) -> Result:
        body = json.dumps(
            {
                "model": model_id,
                "messages": [{"role": "system", "content": system}, *messages],
                "stream": False,
                "options": {"temperature": 0, "num_predict": 256},
            }
        ).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.loads(r.read())
        return Result(
            text=d.get("message", {}).get("content", ""),
            in_tokens=d.get("prompt_eval_count", 0),
            out_tokens=d.get("eval_count", 0),
            ms=d.get("total_duration", 0) / 1e6,
        )

    return call


def anthropic_model(model_id: str) -> Model:
    import anthropic

    client = anthropic.Anthropic()

    def call(system: str, messages: list[dict]) -> Result:
        t0 = time.perf_counter()
        resp = client.messages.create(model=model_id, max_tokens=512, system=system, messages=messages)
        ms = (time.perf_counter() - t0) * 1000
        text = "".join(b.text for b in resp.content if b.type == "text")
        return Result(text, resp.usage.input_tokens, resp.usage.output_tokens, ms)

    return call


# ── agent-driven curation ─────────────────────────────────────────────────────
def _parse_remember(text: str) -> list[dict]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return []
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    items = obj.get("remember") or []
    return [it for it in items if isinstance(it, dict) and it.get("hook") and it.get("type")]


def curate(model: Model, mem: Memory, user_text: str, stats: Stats) -> None:
    existing = "\n".join(f"{m.id} — {m.hook}" for m in mem.all()) or "(none yet)"
    prompt = (
        f"Existing memories (id — hook):\n{existing}\n\n"
        f"Latest message from the user:\n{user_text}\n\n"
        "What, if anything, should be remembered? JSON only."
    )
    r = model(CURATE_SYSTEM, [{"role": "user", "content": prompt}])
    stats.add(r)
    for it in _parse_remember(r.text):
        try:
            mem.write(
                str(it["hook"])[:120],
                body=str(it.get("body", ""))[:1500],
                type=str(it["type"]),
                id=it.get("id"),
            )
        except (ValueError, KeyError, TypeError):
            pass  # the model proposed something malformed — the filter rejects it


# ── one arm over one scenario ─────────────────────────────────────────────────
def run_arm(scenario: Scenario, arm: str, model: Model) -> Stats:
    stats = Stats()
    mem = Memory(tempfile.mkdtemp()) if arm == "smriti" else None
    transcript: list[dict] = []
    session = 1

    for turn in scenario.turns:
        if turn.session != session:  # new session: the transcript is gone (files survive)
            transcript.clear()
            session = turn.session

        transcript.append({"role": "user", "content": turn.user})
        is_probe = turn.expect is not None

        if arm == "none":
            system, msgs = ANSWER_SYSTEM, [{"role": "user", "content": turn.user}]
        elif arm == "dump":
            system, msgs = ANSWER_SYSTEM, list(transcript)
        else:  # smriti — inject the index (all hooks) plus the bodies of what recall surfaces
            block = mem.context()
            detail = "\n".join(
                f"- {m.hook}: {m.body}" for m in mem.recall(turn.user, k=3, with_body=True) if m.body
            )
            if detail:
                block += "\n\n# Relevant detail\n" + detail
            system = ANSWER_SYSTEM + "\n\n# What you remember\n" + block
            msgs = [{"role": "user", "content": turn.user}]

        r = model(system, msgs)
        stats.add(r)
        transcript.append({"role": "assistant", "content": r.text})

        if is_probe:
            stats.total += 1
            low = r.text.lower()
            if all(s.lower() in low for s in turn.expect):
                stats.passed += 1
        elif mem is not None:  # the agent curates after an information turn
            curate(model, mem, turn.user, stats)

    if mem is not None:
        stats.store = len(mem.all())
    return stats


# ── scenarios ──────────────────────────────────────────────────────────────────
def _noise(*texts: str) -> list[Turn]:
    return [Turn(t) for t in texts]


SCENARIOS = [
    Scenario(
        "cross-session persistence",
        [
            Turn("My name is Gurprit, and I lead TV platform architecture."),
            Turn("I prefer Postgres over Mongo for data stores."),
            # New session — the transcript resets; only files survive.
            Turn("Remind me — what's my name?", session=2, expect=["gurprit"]),
        ],
    ),
    Scenario(
        "precision under heavy noise",
        [
            Turn("Production runs in region eu-west-1."),
            *_noise(
                "Nice weather today.",
                "The coffee machine is finally fixed.",
                "Standup moved to 9:30.",
                "We got new chairs.",
                "The wifi password changed.",
            ),
            Turn("Which region is production in?", expect=["eu-west-1"]),
        ],
    ),
    Scenario(
        "update / contradiction",
        [
            Turn("Our API uses REST."),
            *_noise("The office is in Vancouver.", "We use Slack."),
            Turn("Update: we migrated the API from REST to gRPC."),
            Turn("What protocol does our API use now?", expect=["grpc"]),
        ],
    ),
    Scenario(
        "decision recall",
        [
            Turn("We decided to use Cedar for authorization because it's policy-as-code."),
            *_noise("Lunch is catered Wednesdays.", "The mascot is an otter."),
            Turn("What are we using for authorization?", expect=["cedar"]),
        ],
    ),
]


def main() -> int:
    backend = os.environ.get("SMRITI_BENCH_BACKEND", "echo")
    if backend == "anthropic":
        model_id = os.environ.get("SMRITI_BENCH_MODEL", "claude-haiku-4-5")
        model, label = anthropic_model(model_id), f"anthropic:{model_id}"
    elif backend == "ollama":
        model_id = os.environ.get("SMRITI_BENCH_MODEL", "mistral:latest")
        host = os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
        host = host if host.startswith("http") else "http://" + host
        model, label = ollama_model(model_id, host), f"ollama:{model_id}"
    else:
        model, label = echo_model, "echo (wiring self-test — not a real-model result)"

    arms = ["none", "dump", "smriti"]
    print(f"smriti — Stage 1 v2: agent-curated A/B   [model: {label}]\n")

    agg = {a: Stats() for a in arms}
    for sc in SCENARIOS:
        print(f"  {sc.name}")
        for arm in arms:
            s = run_arm(sc, arm, model)
            agg[arm].passed += s.passed
            agg[arm].total += s.total
            agg[arm].in_tokens += s.in_tokens
            agg[arm].out_tokens += s.out_tokens
            agg[arm].ms += s.ms
            agg[arm].store += s.store
            extra = f"  store={s.store}" if arm == "smriti" else ""
            print(f"    {arm:7} {s.passed}/{s.total} probes   in={s.in_tokens:>6} out={s.out_tokens:>5} {s.ms / 1000:>6.1f}s{extra}")
        print()

    print(f"{'arm':8} {'success':>8} {'in_tok':>8} {'out_tok':>8} {'sec':>7} {'store':>6}")
    for arm in arms:
        a = agg[arm]
        rate = f"{(100 * a.passed / a.total):.0f}%" if a.total else "—"
        store = a.store if arm == "smriti" else "—"
        print(f"{arm:8} {rate:>8} {a.in_tokens:>8} {a.out_tokens:>8} {a.ms / 1000:>7.1f} {str(store):>6}")

    print(
        "\nRead: with the AGENT curating, does smriti still match `dump` on success"
        "\nat far fewer input tokens — and win cross-session, where `dump` has no"
        "\ntranscript to fall back on? `store` shows whether curation stayed lean"
        "\nunder noise (low = good) or hoarded (high)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
