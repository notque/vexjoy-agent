#!/usr/bin/env python3
"""Re-run the repo's SessionStart hooks after session-bootstrap.sh installs the toolkit.

Claude Code starts every SessionStart hook at once, so in a home that had no launcher the
toolkit's own SessionStart hooks fail while the bootstrap is still installing. Once the
install is done, the bootstrap runs this script: it runs those hooks again with the same
SessionStart payload, in parallel, and prints one SessionStart JSON object whose
``additionalContext`` joins what they returned. The bootstrap's own entry is skipped.

Usage: session-bootstrap-replay.py <repo settings.json> <payload file> [status line] [deadline]
The status line, when given, leads the context, and is printed alone when no hook adds any.
The deadline (epoch seconds) bounds every replayed hook so the bootstrap ends inside its
own hook timeout; a hook that cannot start before it is skipped.
Always exits 0; a hook that fails or times out contributes nothing.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vexinstall.interp import is_repo_only

PER_HOOK_TIMEOUT = 30


def commands(settings: dict, source: str) -> list[str]:
    """SessionStart commands whose matcher accepts *source*, minus the repo-only bootstrap."""
    out: list[str] = []
    for group in settings.get("hooks", {}).get("SessionStart", []):
        if not isinstance(group, dict):
            continue
        matcher = group.get("matcher") or ""
        try:
            if matcher and matcher != "*" and not re.fullmatch(matcher, source or ""):
                continue
        except re.error:
            continue
        for entry in group.get("hooks", []):
            cmd = entry.get("command") if isinstance(entry, dict) else None
            if isinstance(cmd, str) and entry.get("type", "command") == "command" and not is_repo_only(cmd):
                out.append(cmd)
    return out


def context_of(stdout: str) -> str:
    """The text a SessionStart hook adds: ``additionalContext`` from JSON, else plain stdout."""
    text = stdout.strip()
    if not text:
        return ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(data, dict):
        spec = data.get("hookSpecificOutput")
        if isinstance(spec, dict) and isinstance(spec.get("additionalContext"), str):
            return spec["additionalContext"].strip()
        return ""
    return text


def run(cmd: str, payload: bytes, deadline: float | None = None) -> str:
    budget = PER_HOOK_TIMEOUT if deadline is None else min(PER_HOOK_TIMEOUT, deadline - time.time())
    if budget <= 1:
        return ""
    try:
        proc = subprocess.run(
            ["sh", "-c", cmd], input=payload, capture_output=True, timeout=budget, env=os.environ.copy()
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return context_of(proc.stdout.decode("utf-8", "replace")) if proc.returncode == 0 else ""


def main(argv: list[str]) -> int:
    try:
        settings = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        payload = Path(argv[2]).read_bytes()
    except (IndexError, OSError, json.JSONDecodeError):
        return 0
    try:
        source = json.loads(payload or b"{}").get("source", "startup")
    except (json.JSONDecodeError, AttributeError):
        source = "startup"
    try:
        deadline = float(argv[4]) if len(argv) > 4 else None
    except ValueError:
        deadline = None
    cmds = commands(settings, source)
    parts: list[str] = []
    if cmds:
        with ThreadPoolExecutor(max_workers=len(cmds)) as pool:
            parts = [p for p in pool.map(lambda c: run(c, payload, deadline), cmds) if p]
    if len(argv) > 3 and argv[3]:
        parts.insert(0, argv[3])
    if parts:
        out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n".join(parts)}}
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
