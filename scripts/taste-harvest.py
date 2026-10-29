#!/usr/bin/env python3
"""Harvest owner decisions from Claude Code transcripts for the taste judge.

Pairs each owner reply with the assistant text that ended the turn before it.
Keeps pairs where the assistant asked something or the owner corrected it.
Writes JSONL to ~/.claude/taste/pairs.jsonl (private, outside the repo).

Usage:
    python3 scripts/taste-harvest.py [--projects DIR] [--out PATH] [--stats]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_PROJECTS = Path.home() / ".claude" / "projects"
DEFAULT_OUT = Path.home() / ".claude" / "taste" / "pairs.jsonl"

CORRECTION = re.compile(
    r"^(no\b|nope|don'?t|do not|stop|revert|undo|wrong|not that|instead|that'?s not|why did you|never\b|"
    r"too (slow|much|complicated)|i said|i told you|this (ruined|broke))",
    re.I,
)
APPROVAL = re.compile(r"^(yes|yep|yeah|ok|okay|sure|do it|go|ship it|sounds good|lgtm|approved?)\b", re.I)
PASTE = re.compile(r"<pasted_content[^>]*>.*?</pasted_content[^>]*>", re.S)
SKIP_PREFIXES = ("<", "[Request interrupted", "Caveat:")
# Slash-command bodies arrive as user text; they are not owner decisions.
SKILL_EXPANSION = "Read and follow the full skill file"
ASSISTANT_TAIL = 1200
OWNER_MAX = 1500


def _open(path: str):
    # Windows needs the long-path prefix for deep project folder names.
    if os.name == "nt":
        path = "\\\\?\\" + os.path.abspath(path)
    return open(path, encoding="utf-8", errors="ignore")


def _owner_text(content) -> str | None:
    if isinstance(content, list):
        if any(b.get("type") == "tool_result" for b in content if isinstance(b, dict)):
            return None
        content = "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(content, str):
        return None
    text = PASTE.sub("[pasted]", content).strip()
    if not text or text.startswith(SKIP_PREFIXES) or SKILL_EXPANSION in text[:400]:
        return None
    return text[:OWNER_MAX]


def _assistant_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def classify(owner: str) -> str:
    """Rough cue only; the judge eval uses labels, not this."""
    if CORRECTION.search(owner):
        return "correction"
    if APPROVAL.search(owner):
        return "approval"
    return "other"


def harvest_file(path: str) -> list[dict]:
    pairs: list[dict] = []
    last_assistant = ""
    project = Path(path).parent.name
    with _open(path) as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("isSidechain"):
                continue
            content = (rec.get("message") or {}).get("content")
            if rec.get("type") == "assistant":
                text = _assistant_text(content).strip()
                if text:
                    last_assistant = text
                continue
            if rec.get("type") != "user":
                continue
            owner = _owner_text(content)
            if owner is None:
                continue
            tail = last_assistant[-ASSISTANT_TAIL:]
            cue = classify(owner)
            if tail and ("?" in tail[-400:] or cue == "correction"):
                pairs.append(
                    {
                        "session": rec.get("sessionId"),
                        "project": project,
                        "ts": rec.get("timestamp"),
                        "assistant": tail,
                        "owner": owner,
                        "cue": cue,
                    }
                )
            last_assistant = ""
    return pairs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--projects", type=Path, default=DEFAULT_PROJECTS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--stats", action="store_true", help="print counts only, write nothing")
    args = ap.parse_args()

    files = glob.glob(str(args.projects / "*" / "*.jsonl"))
    pairs = [p for f in files for p in harvest_file(f)]
    pairs.sort(key=lambda p: p["ts"] or "")
    cues: dict[str, int] = {}
    for p in pairs:
        cues[p["cue"]] = cues.get(p["cue"], 0) + 1
    print(f"{len(files)} sessions, {len(pairs)} pairs, cues={cues}", file=sys.stderr)
    if args.stats:
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
