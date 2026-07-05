#!/usr/bin/env python3
"""Blind pairwise judge for planning-unknowns-v2.

One judgment per (scenario, sample) pair id (e.g. s01a): full vs edited
artifacts, presented as X/Y in random recorded order (uid-map.json withheld
from judge). Writes judgments.jsonl, prints tally and two-sided sign test.
"""

import json
import math
import os
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RUN = Path(__file__).resolve().parent
MODEL = "opus"
WORKERS = 4
ENV = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

RUBRIC = """You are judging two anonymous planning artifacts (X and Y) produced
for the same scenario by two different process documents. You do not know which
process produced which. Judge ONLY the artifacts.

Rubric (weigh equally):
1. Decision coverage — does it surface the decisions the requester will actually
   hit during the build, including ones they did not think to ask about?
2. Execution resilience — if reality diverges mid-task, does the artifact give a
   clear, low-risk way to absorb the surprise and keep going?
3. Grounding — does it anchor plans/questions in concrete evidence, existing
   code, or verifiable criteria rather than abstractions?
4. Sequencing — is riskier/more-volatile work positioned to get feedback early?
5. Density — no filler; every section earns its place.

Output STRICT JSON only: {"winner": "X"|"Y"|"tie", "x_score": <0-10>,
"y_score": <0-10>, "reason": "<one sentence>"}"""


def call_judge(prompt: str) -> dict:
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
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


def sign_test_p(wins_a: int, wins_b: int) -> float:
    """Two-sided exact binomial sign test on discordant pairs."""
    n = wins_a + wins_b
    if n == 0:
        return 1.0
    k = max(wins_a, wins_b)
    tail = sum(math.comb(n, i) for i in range(k, n + 1)) / 2**n
    return min(1.0, 2 * tail)


def one(args):
    pid, x, y, mapping = args
    prompt = f"{RUBRIC}\n\nPair id: {pid}\n\n=== ARTIFACT X ===\n{x}\n\n=== ARTIFACT Y ===\n{y}\n"
    try:
        j = call_judge(prompt)
    except Exception as exc:
        return {"id": pid, "error": str(exc)[:200], "winner_arm": "error", "map": mapping}
    winner_arm = mapping.get(j.get("winner", "tie"), "tie")
    return {"id": pid, **j, "winner_arm": winner_arm, "map": mapping}


def main():
    random.seed(20260703 + 2)
    answers = RUN / "answers"
    pids = sorted(p.stem for p in (answers / "full").glob("*.md"))
    tasks, uid_map = [], {}
    for pid in pids:
        full = (answers / "full" / f"{pid}.md").read_text(encoding="utf-8")
        edited = (answers / "edited" / f"{pid}.md").read_text(encoding="utf-8")
        if random.random() < 0.5:
            x, y, uid_map[pid] = full, edited, {"X": "full", "Y": "edited"}
        else:
            x, y, uid_map[pid] = edited, full, {"X": "edited", "Y": "full"}
        tasks.append((pid, x, y, uid_map[pid]))
    (RUN / "uid-map.json").write_text(json.dumps(uid_map, indent=2), encoding="utf-8")
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(one, tasks))
    with (RUN / "judgments.jsonl").open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(json.dumps(r, ensure_ascii=False))
    tally = {arm: sum(r["winner_arm"] == arm for r in results) for arm in ("edited", "full", "tie", "error")}
    p = sign_test_p(tally["edited"], tally["full"])
    print(json.dumps({"tally": tally, "sign_test_p": round(p, 5)}))
    return 1 if tally["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
