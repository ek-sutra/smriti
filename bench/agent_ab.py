#!/usr/bin/env python3
"""Stage 1 — the brain: an A/B over a multi-turn agent.

Memory only matters across time, so this plays an agent through scripted
multi-turn scenarios where the correct answer to a later turn depends on an
earlier one, under three arms:

    none      the agent sees only the current turn (the floor)
    dump      the agent sees the entire transcript (the hoard — recall ceiling, cost ceiling)
    smriti    the agent sees smriti's compressed index, written via a fixed policy

Per the council (v1): writes are harness-managed (a fixed curation policy), so we
isolate the variable — what the agent *reads*. Whether an LLM curates well is v2.

Grading is deterministic: each scenario plants a seed turn and a later probe whose
correct answer is a known string, so there's no LLM judge.

Models are pluggable. The default `echo` model is a zero-token stand-in that lets
you verify the harness wiring without an API key (it "knows" exactly what is in
its context, so it passes when the fact is present and fails when it isn't —
proving the arms differ). For the real test, set:

    SMRITI_BENCH_BACKEND=anthropic   # uses the Anthropic SDK
    SMRITI_BENCH_MODEL=claude-haiku-4-5   # the agent under test (override freely)
    ANTHROPIC_API_KEY=...

Run:  python bench/agent_ab.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from smriti import Memory  # noqa: E402

# A model is: (system_prompt, messages) -> assistant_text
Model = Callable[[str, list[dict]], str]


@dataclass
class Turn:
    user: str
    # Fixed curation policy: what to persist to smriti at this turn (None = nothing).
    remember: dict | None = None  # {"hook":..., "type":..., "body":?, "id":?}
    # If set, this turn is a probe: the answer must contain every string (case-insensitive).
    expect: list[str] | None = None


@dataclass
class Scenario:
    name: str
    turns: list[Turn] = field(default_factory=list)


BASE_SYSTEM = (
    "You are a helpful assistant with memory of this user across the conversation. "
    "Answer the user's latest message directly and concretely, using anything you "
    "remember. If you don't know, say so."
)


# ── models ────────────────────────────────────────────────────────────────────
def echo_model(system: str, messages: list[dict]) -> str:
    """Zero-token stand-in: 'knows' exactly what is in its context. Used to verify
    the harness wiring deterministically — not a claim about real model behavior."""
    return system + "\n" + "\n".join(m["content"] for m in messages)


def anthropic_model(model_id: str) -> Model:
    import anthropic  # imported lazily so the echo path needs no dependency

    client = anthropic.Anthropic()

    def call(system: str, messages: list[dict]) -> str:
        resp = client.messages.create(
            model=model_id, max_tokens=512, system=system, messages=messages
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    return call


def ollama_model(model_id: str, host: str) -> Model:
    """Local models via Ollama's /api/chat — stdlib only, no API key. Proves the
    seam is model-agnostic and that even small local models gain from memory."""
    import json
    import urllib.request

    url = host.rstrip("/") + "/api/chat"

    def call(system: str, messages: list[dict]) -> str:
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
            return json.loads(r.read()).get("message", {}).get("content", "")

    return call


# ── one arm over one scenario ─────────────────────────────────────────────────
def run_arm(scenario: Scenario, arm: str, model: Model) -> tuple[int, int, int]:
    """Return (probes_passed, probes_total, context_chars_total)."""
    transcript: list[dict] = []
    mem = Memory(tempfile.mkdtemp()) if arm == "smriti" else None
    passed = total = chars = 0

    for turn in scenario.turns:
        transcript.append({"role": "user", "content": turn.user})

        # Build what the agent sees, per arm.
        if arm == "none":
            system, msgs = BASE_SYSTEM, [{"role": "user", "content": turn.user}]
        elif arm == "dump":
            system, msgs = BASE_SYSTEM, list(transcript)
        elif arm == "smriti":
            system = BASE_SYSTEM + "\n\n# What you remember\n" + mem.context()
            msgs = [{"role": "user", "content": turn.user}]
        else:
            raise ValueError(arm)

        chars += len(system) + sum(len(m["content"]) for m in msgs)
        answer = model(system, msgs)
        transcript.append({"role": "assistant", "content": answer})

        if turn.expect is not None:
            total += 1
            low = answer.lower()
            if all(s.lower() in low for s in turn.expect):
                passed += 1

        # Fixed curation policy: persist after the turn (smriti only).
        if mem is not None and turn.remember:
            r = turn.remember
            mem.write(r["hook"], body=r.get("body", ""), type=r["type"], id=r.get("id"))

    return passed, total, chars


# ── scenarios (each plants a seed and a later probe; distractors in between) ────
def _distractors(*texts: str) -> list[Turn]:
    return [Turn(user=t) for t in texts]


SCENARIOS = [
    Scenario(
        "preference recall",
        [
            Turn(
                "For this project I prefer Postgres over Mongo for all data stores.",
                remember={"hook": "User prefers Postgres over Mongo for data stores", "type": "preference"},
            ),
            *_distractors("Standup is at 9am.", "Our logo is teal.", "We deploy on Fridays."),
            Turn("I'm starting a new service that needs a database. Which should I use?", expect=["postgres"]),
        ],
    ),
    Scenario(
        "don't re-ask (fact)",
        [
            Turn("By the way, my name is Gurprit.", remember={"hook": "User's name is Gurprit", "type": "fact"}),
            *_distractors("The repo is private.", "CI runs on push.", "We use feature flags."),
            Turn("Address me by name in your reply — what is it?", expect=["gurprit"]),
        ],
    ),
    Scenario(
        "decision + reason",
        [
            Turn(
                "We've decided to use Cedar for authorization because it's policy-as-code.",
                remember={
                    "hook": "Use Cedar for authorization (policy-as-code)",
                    "type": "decision",
                    "body": "**Why:** policy-as-code.\n**How to apply:** new services authorize via Cedar.",
                },
            ),
            *_distractors("The mascot is an otter.", "Docs live in the wiki.", "Lunch is catered Wednesdays."),
            Turn("What are we using for authorization?", expect=["cedar"]),
        ],
    ),
    Scenario(
        "update / contradiction",
        [
            Turn("Our API uses REST.", remember={"id": "api-protocol", "hook": "API protocol is REST", "type": "decision", "body": "REST."}),
            *_distractors("The office is in Vancouver.", "We use Slack."),
            # Same id → overwrites in smriti; dump keeps both turns and must infer the latest.
            Turn("Update: we migrated the API from REST to gRPC.", remember={"id": "api-protocol", "hook": "API protocol is now gRPC (migrated from REST)", "type": "decision", "body": "gRPC, migrated from REST."}),
            *_distractors("The new hire starts Monday.", "Coffee machine is fixed."),
            Turn("What protocol does our API use now?", expect=["grpc"]),
        ],
    ),
]


def main() -> int:
    backend = os.environ.get("SMRITI_BENCH_BACKEND", "echo")
    if backend == "anthropic":
        model_id = os.environ.get("SMRITI_BENCH_MODEL", "claude-haiku-4-5")
        model = anthropic_model(model_id)
        label = f"anthropic:{model_id}"
    elif backend == "ollama":
        model_id = os.environ.get("SMRITI_BENCH_MODEL", "mistral:latest")
        host = os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
        if not host.startswith("http"):
            host = "http://" + host
        model = ollama_model(model_id, host)
        label = f"ollama:{model_id}"
    else:
        model = echo_model
        label = "echo (harness self-test — zero tokens, not a real-model result)"

    arms = ["none", "dump", "smriti"]
    print(f"smriti — Stage 1: agent A/B   [model: {label}]\n")

    totals = {a: [0, 0, 0] for a in arms}  # passed, total, chars
    for scenario in SCENARIOS:
        print(f"  {scenario.name}")
        for arm in arms:
            p, t, c = run_arm(scenario, arm, model)
            totals[arm][0] += p
            totals[arm][1] += t
            totals[arm][2] += c
            print(f"    {arm:7} {p}/{t} probes   {c:>6} ctx chars")
        print()

    print(f"{'arm':8} {'success':>9} {'ctx chars':>11}")
    for arm in arms:
        p, t, c = totals[arm]
        rate = f"{(100 * p / t):.0f}%" if t else "—"
        print(f"{arm:8} {rate:>9} {c:>11}")

    print(
        "\nRead: smriti should match `dump` on success at a fraction of `dump`'s ctx chars,"
        "\nand beat `none`. The echo model only proves the wiring — run the anthropic"
        "\nbackend for a real-model result (esp. the update scenario, where dump may pick"
        "\nthe stale value while smriti overwrote it)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
