#!/usr/bin/env python3
"""Blind pairwise judge for planning-unknowns-v1.

For each scenario, presents the two arms' artifacts as X/Y in a random,
recorded order (uid-map.json, written before judging, not shown to judge).
Judge model (opus) scores both on a generic planning-quality rubric and
picks a winner. Writes judgments.jsonl and prints the tally.
"""

import json
import os
import random
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent
MODEL = "opus"
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


def main():
    random.seed(20260703)
    answers = RUN / "answers"
    sids = sorted(p.stem for p in (answers / "full").glob("*.md"))
    uid_map = {}
    results = []
    out = RUN / "judgments.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for sid in sids:
            full = (answers / "full" / f"{sid}.md").read_text(encoding="utf-8")
            edited = (answers / "edited" / f"{sid}.md").read_text(encoding="utf-8")
            if random.random() < 0.5:
                x, y, uid_map[sid] = full, edited, {"X": "full", "Y": "edited"}
            else:
                x, y, uid_map[sid] = edited, full, {"X": "edited", "Y": "full"}
            prompt = f"{RUBRIC}\n\nScenario id: {sid}\n\n=== ARTIFACT X ===\n{x}\n\n=== ARTIFACT Y ===\n{y}\n"
            j = call_judge(prompt)
            winner_label = j.get("winner", "tie")
            winner_arm = uid_map[sid].get(winner_label, "tie")
            rec = {"id": sid, **j, "winner_arm": winner_arm, "map": uid_map[sid]}
            results.append(rec)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(json.dumps(rec, ensure_ascii=False))
    (RUN / "uid-map.json").write_text(json.dumps(uid_map, indent=2), encoding="utf-8")
    tally = {
        "edited": sum(r["winner_arm"] == "edited" for r in results),
        "full": sum(r["winner_arm"] == "full" for r in results),
        "tie": sum(r["winner_arm"] == "tie" for r in results),
    }
    print(json.dumps({"tally": tally}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
