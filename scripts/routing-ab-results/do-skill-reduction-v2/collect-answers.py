#!/usr/bin/env python3
"""Idempotent answer bridge for do-skill-reduction-v2.

For each prompts/<arm>/<id>.txt, calls `claude -p --model sonnet` with the
prompt verbatim, extracts the model's JSON route object, writes
answers/<arm>/<id>.json. Skips existing answers. Appends call-log.jsonl.
"""

import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

RUN = Path(__file__).resolve().parent
MODEL = "sonnet"
WORKERS = 6
LOG_LOCK = Lock()
LOG = RUN / "call-log.jsonl"

ENV = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}


def extract_json(text: str) -> dict | None:
    """First balanced {...} block that parses and has agent+skill keys."""
    for m in re.finditer(r"\{", text):
        depth = 0
        for i in range(m.start(), len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[m.start() : i + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict) and "agent" in obj and "skill" in obj:
                        return obj
                    break
    return None


def one(task):
    arm, pid, prompt_path = task
    out_path = RUN / "answers" / arm / f"{pid}.json"
    if out_path.exists():
        return "skip"
    prompt = prompt_path.read_text(encoding="utf-8")
    try:
        proc = subprocess.run(
            ["claude", "-p", "--model", MODEL, "--output-format", "json"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=300,
            env=ENV,
        )
        wrapper = json.loads(proc.stdout)
        result_text = wrapper.get("result", "")
        obj = extract_json(result_text)
        entry = {
            "arm": arm,
            "id": pid,
            "cost_usd": wrapper.get("total_cost_usd"),
            "usage": {
                k: wrapper.get("usage", {}).get(k)
                for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
            },
            "ok": obj is not None,
        }
    except Exception as exc:  # timeout, non-JSON stdout, etc.
        obj, entry = None, {"arm": arm, "id": pid, "ok": False, "error": str(exc)[:200]}
    with LOG_LOCK, LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    if obj is None:
        return "fail"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
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
