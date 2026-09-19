"""Score a review run against hand-labeled defects.

A finding matches a label when it names the same file and either its check
matches the label's class regex or its description names the labeled function.

Usage:
    python3 score.py labels.json run.json
"""

import json
import re
import sys
from pathlib import Path


def match(lab: dict, pool: list[dict]) -> list[dict]:
    """Return the findings in ``pool`` that match one label."""
    out = []
    for f in pool:
        if not f.get("file", "").endswith(lab["file"].split("/")[-1]):
            continue
        chk = (f.get("check") or "").lower()
        desc = (f.get("description") or "").lower()
        if re.search(lab["class"], chk) or any(fn.lower() + "(" in desc for fn in lab["func"].split("|")):
            out.append(f)
    return out


def main() -> int:
    labels = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    run = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    deep = run.get("deep", run)
    found = deep.get("verified_findings") or deep.get("findings") or []
    dropped = deep.get("dropped_findings") or deep.get("dropped") or []

    hit = 0
    near = 0
    for lab in labels:
        m = match(lab, found)
        d = match(lab, dropped)
        tag = "HIT " if m else ("DROPPED" if d else "MISS")
        hit += bool(m)
        near += bool(d and not m)
        if m:
            extra = f"{m[0]['check']}:{m[0]['line']} s={m[0]['score']}"
        elif d:
            extra = f"found, then dropped by verification: {d[0]['check']} s={d[0]['score']}"
        else:
            extra = ""
        print(f"{tag:<8}{lab['id']:<4}{lab['file'].split('/')[-1]:<40}{lab['note'][:50]:<52}{extra}")
    print(f"\nRECALL {hit}/{len(labels)}  (+{near} found but dropped by verification)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
