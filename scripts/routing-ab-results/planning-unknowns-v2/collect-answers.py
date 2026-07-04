#!/usr/bin/env python3
"""Idempotent answer bridge for planning-unknowns-v2.

For each prompts/<arm>/<id>.txt, calls `claude -p --model sonnet` and writes
the raw markdown artifact to answers/<arm>/<id>.md. Skips existing answers.
Appends call-log.jsonl. Adapted from do-skill-reduction-v2/collect-answers.py
(free-text artifact instead of JSON route object).
"""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

RUN = Path(__file__).resolve().parent
MODEL = "sonnet"
WORKERS = 4
LOG_LOCK = Lock()
LOG = RUN / "call-log.jsonl"

ENV = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}


def one(task):
    arm, pid, prompt_path = task
    out_path = RUN / "answers" / arm / f"{pid}.md"
    if out_path.exists():
        return "skip"
    prompt = prompt_path.read_text(encoding="utf-8")
    try:
        proc = subprocess.run(
            ["claude", "-p", "--model", MODEL, "--output-format", "json"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=600,
            env=ENV,
        )
        wrapper = json.loads(proc.stdout)
        text = wrapper.get("result", "")
        entry = {
            "arm": arm,
            "id": pid,
            "cost_usd": wrapper.get("total_cost_usd"),
            "ok": bool(text.strip()),
        }
    except Exception as exc:
        text, entry = "", {"arm": arm, "id": pid, "ok": False, "error": str(exc)[:200]}
    with LOG_LOCK, LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    if not text.strip():
        return "fail"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return "done"


def main():
    tasks = []
    for arm_dir in sorted((RUN / "prompts").iterdir()):
        for p in sorted(arm_dir.glob("*.txt")):
            tasks.append((arm_dir.name, p.stem, p))
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(one, tasks))
    counts = {s: results.count(s) for s in ("done", "skip", "fail")}
    print(json.dumps(counts))
    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
