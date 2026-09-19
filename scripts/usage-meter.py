#!/usr/bin/env python3
"""Fable/LLM usage meter: tokens and generations per session, by model and by cause.

The target the toolkit is steering toward is fewer LLM generations per user
turn: deterministic programs and Jev absorb judgment, the LLM generates only.
This meter reads the engine's own transcript rows (never plugin logs) and
reports what each generation was for, so the biggest sink is visible.

Per model: generations, input/cache-write/cache-read/output tokens.
Per trigger (what preceded each generation):
  user         the user spoke -- the generation you cannot remove
  tool_result  a tool-loop step in this thread -- the main sink; move loops
               into Jev programs or a cheaper agent
  hook_context hook-injected context with no user text
  notification a system/task notification (rewake, agent completion)
Per skill attribution (`attributionSkill`) for the primary model.

Usage:
    python3 scripts/usage-meter.py                      # current/newest session
    python3 scripts/usage-meter.py <transcript.jsonl>
    python3 scripts/usage-meter.py --all --days 7       # every session, last 7 days
    python3 scripts/usage-meter.py --model fable        # substring of the model id to treat as primary
    python3 scripts/usage-meter.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
TRIGGERS = ("user", "tool_result", "hook_context", "notification")


def _projects_root() -> Path:
    return Path.home() / ".claude" / "projects"


def _find_transcripts(explicit: Path | None, all_sessions: bool, days: float) -> list[Path]:
    if explicit:
        return [explicit]
    root = _projects_root()
    files = sorted(root.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not all_sessions:
        sid = os.environ.get("CLAUDE_SESSION_ID")
        if sid:
            hits = [p for p in files if p.stem == sid]
            if hits:
                return hits[:1]
        return files[:1]
    cutoff = time.time() - days * 86400
    return [p for p in files if p.stat().st_mtime >= cutoff]


def load(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _text_of(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _has_tool_result(content: object) -> bool:
    return isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)


def classify_trigger(user_row: dict | None) -> str:
    if user_row is None:
        return "user"
    content = user_row.get("message", {}).get("content")
    if _has_tool_result(content):
        return "tool_result"
    text = _text_of(content)
    if "SYSTEM NOTIFICATION" in text or "task-notification" in text:
        return "notification"
    if user_row.get("isMeta") or "hook additional context" in text or "hook success" in text:
        if not text.strip() or text.lstrip().startswith(("[", "<", "SessionStart", "UserPromptSubmit")):
            return "hook_context"
    return "user"


def analyze(rows: list[dict]) -> dict:
    per_model: dict[str, Counter] = defaultdict(Counter)
    per_trigger: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    per_skill: dict[str, Counter] = defaultdict(Counter)
    last_user: dict | None = None
    user_turns = 0
    for r in rows:
        t = r.get("type")
        if t == "user":
            last_user = r
            if classify_trigger(r) == "user":
                user_turns += 1
            continue
        if t != "assistant":
            continue
        msg = r.get("message", {})
        model = msg.get("model") or "?"
        if model == "<synthetic>":
            continue
        u = msg.get("usage") or {}
        vals = {k: int(u.get(k) or 0) for k in USAGE_KEYS}
        if not any(vals.values()):
            continue  # not an API request
        per_model[model]["generations"] += 1
        trig = classify_trigger(last_user)
        per_trigger[model][trig]["generations"] += 1
        skill = r.get("attributionSkill") or "-"
        per_skill[model][skill] += 1
        for k, v in vals.items():
            per_model[model][k] += v
            per_trigger[model][trig][k] += v
    return {
        "user_turns": user_turns,
        "per_model": {m: dict(c) for m, c in per_model.items()},
        "per_trigger": {m: {t: dict(c) for t, c in d.items()} for m, d in per_trigger.items()},
        "per_skill": {m: dict(c.most_common(12)) for m, c in per_skill.items()},
    }


def merge(results: list[dict]) -> dict:
    out = {
        "user_turns": 0,
        "per_model": defaultdict(Counter),
        "per_trigger": defaultdict(lambda: defaultdict(Counter)),
        "per_skill": defaultdict(Counter),
    }
    for a in results:
        out["user_turns"] += a["user_turns"]
        for m, c in a["per_model"].items():
            out["per_model"][m].update(c)
        for m, d in a["per_trigger"].items():
            for t, c in d.items():
                out["per_trigger"][m][t].update(c)
        for m, c in a["per_skill"].items():
            out["per_skill"][m].update(c)
    return {
        "user_turns": out["user_turns"],
        "per_model": {m: dict(c) for m, c in out["per_model"].items()},
        "per_trigger": {m: {t: dict(c) for t, c in d.items()} for m, d in out["per_trigger"].items()},
        "per_skill": {m: dict(c.most_common(12)) for m, c in out["per_skill"].items()},
    }


def _fmt(n: int) -> str:
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}k" if n >= 1e3 else str(n)


def report(a: dict, primary: str, sessions: int) -> None:
    print(f"sessions: {sessions}   user turns: {a['user_turns']}")
    print()
    print(f"{'model':<24}{'gens':>7}{'gens/turn':>11}{'input':>9}{'cache-w':>9}{'cache-r':>9}{'output':>9}")
    for m, c in sorted(a["per_model"].items(), key=lambda kv: -kv[1].get("generations", 0)):
        g = c.get("generations", 0)
        per = g / a["user_turns"] if a["user_turns"] else 0
        print(
            f"{m:<24}{g:>7}{per:>11.1f}{_fmt(c.get('input_tokens', 0)):>9}"
            f"{_fmt(c.get('cache_creation_input_tokens', 0)):>9}{_fmt(c.get('cache_read_input_tokens', 0)):>9}"
            f"{_fmt(c.get('output_tokens', 0)):>9}"
        )
    prim = [m for m in a["per_model"] if primary.lower() in m.lower()]
    if not prim:
        return
    m = prim[0]
    total_g = a["per_model"][m].get("generations", 0)
    print()
    print(f"{m}: what triggered each generation")
    print(f"{'trigger':<16}{'gens':>7}{'share':>7}{'output':>9}{'cache-r':>9}")
    for t in TRIGGERS:
        c = a["per_trigger"].get(m, {}).get(t)
        if not c:
            continue
        g = c.get("generations", 0)
        print(
            f"{t:<16}{g:>7}{g / total_g if total_g else 0:>7.0%}{_fmt(c.get('output_tokens', 0)):>9}{_fmt(c.get('cache_read_input_tokens', 0)):>9}"
        )
    print()
    print(f"{m}: generations by skill attribution")
    for s, n in a["per_skill"].get(m, {}).items():
        print(f"  {n:>6}  {s}")
    tr = a["per_trigger"].get(m, {}).get("tool_result", {}).get("generations", 0)
    if total_g:
        print()
        print(
            f"target: tool-loop generations on {m} are {tr}/{total_g} ({tr / total_g:.0%}). "
            "Each is a full-context read. Move loops into Jev programs or a cheaper agent; "
            "the main thread should orchestrate in 1-2 tool calls per user turn."
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("transcript", nargs="?", type=Path)
    ap.add_argument("--all", action="store_true", help="every session under ~/.claude/projects")
    ap.add_argument("--days", type=float, default=7.0)
    ap.add_argument("--model", default="fable", help="substring of the primary model id")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    paths = _find_transcripts(args.transcript, args.all, args.days)
    if not paths:
        print("no transcripts found", file=sys.stderr)
        return 1
    results = [analyze(load(p)) for p in paths]
    a = merge(results) if len(results) > 1 else results[0]
    if args.json:
        print(json.dumps({"sessions": len(paths), **a}, indent=1))
    else:
        report(a, args.model, len(paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
