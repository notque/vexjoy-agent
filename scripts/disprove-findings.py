#!/usr/bin/env python3
"""Disprove pass for review findings: build the refuter prompt, then apply its verdicts.

Usage:
    python3 scripts/disprove-findings.py prompt --findings f.json --diff d.patch --file a.py --file b.py [--lang python]
    python3 scripts/disprove-findings.py apply  --findings f.json --verdicts reply.txt --diff d.patch --file a.py

`f.json` is a list of findings: {"file", "line", "severity", "quote", "claim"} and an optional "fid" (default f1, f2, ...).
`reply.txt` is the refuter's reply (JSON, fences tolerated). `apply` prints {"kept": [...], "dropped": [...]}.

A finding is dropped only when its verdict is "refuted" and its reason quotes code (a backtick span of at least
MIN_QUOTE non-space characters) that appears in the diff or a touched file. Every other case keeps the finding:
"stands", a missing or malformed verdict, an unquoted reason, or a quote that is not in the code.

Exit codes: 0 ok; 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MIN_QUOTE = 6
FIELDS = ("file", "line", "severity", "quote", "claim")

PROMPT = """You are the disprove pass of a code review. A reviewer made the findings below about this change. Try to
refute each one, using only the diff and files in front of you.

Method (premise audit), for each finding:
1. List the premises it relies on: facts about what the code does, its inputs, its callers, types, or guards.
2. Check each premise against the diff and files. Mark it "closed" (the code shown confirms it), "false" (the code shown
   contradicts it, or the described failure cannot occur), or "open" (the code shown cannot settle it).
3. Verdict "refuted" only if a premise is false or the described problem cannot happen, and your reason quotes the code
   that shows it, in backticks. Otherwise "stands". Use "stands" when you cannot decide.
Do not refute a finding because it is minor, and do not keep one because it sounds plausible.

Reply with only JSON: {{"verdicts": {{"<fid>": {{"premises": [{{"text": ..., "status": "closed"|"false"|"open"}}],
"verdict": "refuted"|"stands", "reason": one sentence}}, ...}}}}. Include every fid.

Language: {lang}

<diff>
{diff}
</diff>

<files>
{files}
</files>

<findings>
{findings}
</findings>
"""


def norm_ws(text: str) -> str:
    """Collapse whitespace runs to one space and strip."""
    return re.sub(r"\s+", " ", text).strip()


def number_lines(text: str) -> str:
    """Return *text* with a right-aligned line number before each line."""
    return "\n".join(f"{i:5d}| {line}" for i, line in enumerate(text.split("\n"), 1))


def diff_body(diff: str) -> str:
    """Return the diff without file headers, hunk headers, or the leading +/-/space marker."""
    out = []
    for line in diff.split("\n"):
        if line.startswith(("+++", "---", "@@")):
            continue
        out.append(line[1:] if line[:1] in "+- " else line)
    return "\n".join(out)


def with_fids(findings: list[dict]) -> list[dict]:
    """Return findings with a `fid` on each (f1, f2, ... by position when absent)."""
    return [{**f, "fid": str(f.get("fid") or f"f{i}")} for i, f in enumerate(findings, 1)]


def build_prompt(findings: list[dict], diff: str, files: dict[str, str], lang: str) -> str:
    """Return the refuter prompt for all *findings* of one review."""
    body = "\n\n".join(f'<file path="{p}">\n{number_lines(t)}\n</file>' for p, t in sorted(files.items()))
    items = "\n\n".join(
        f"fid={f['fid']} file={f.get('file')} line={f.get('line')} severity={f.get('severity')}\n"
        f"quote: {f.get('quote')}\nclaim: {f.get('claim')}"
        for f in with_fids(findings)
    )
    return PROMPT.format(lang=lang, diff=diff.rstrip("\n"), files=body, findings=items)


def extract_json(text: str) -> object:
    """Parse the first JSON object in *text*; fences and prose around it are tolerated."""
    decoder = json.JSONDecoder(strict=False)
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                return decoder.raw_decode(text[i:])[0]
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON object in reply")


def quoted_spans(reason: str) -> list[str]:
    """Return backtick spans of the reason that are long enough to count as a code quote."""
    spans = re.findall(r"`([^`]+)`", reason)
    return [s for s in spans if len(s.replace(" ", "")) >= MIN_QUOTE]


def grounded(reason: str, diff: str, files: dict[str, str]) -> bool:
    """Return True when the reason quotes code found (whitespace-normalized) in the diff or a touched file."""
    hay = [norm_ws(diff_body(diff))] + [norm_ws(t) for t in files.values()]
    return any(norm_ws(s) in h for s in quoted_spans(reason) for h in hay)


def apply_verdicts(findings: list[dict], reply: str, diff: str, files: dict[str, str]) -> dict:
    """Split *findings* into kept and dropped; a drop needs a refuted verdict with a grounded reason."""
    try:
        data = extract_json(reply)
        verdicts = data.get("verdicts", data) if isinstance(data, dict) else {}
    except ValueError:
        verdicts = {}
    kept, dropped = [], []
    for f in with_fids(findings):
        v = verdicts.get(f["fid"]) if isinstance(verdicts, dict) else None
        v = v if isinstance(v, dict) else {}
        reason = str(v.get("reason", ""))
        if str(v.get("verdict", "")).lower() == "refuted" and grounded(reason, diff, files):
            dropped.append({**f, "refuted_by": reason})
        else:
            kept.append(f)
    return {"kept": kept, "dropped": dropped}


def _load_findings(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(f, dict) for f in data):
        raise ValueError("findings must be a JSON list of objects")
    return data


def _load_files(paths: list[str]) -> dict[str, str]:
    return {p: Path(p).read_text(encoding="utf-8") for p in paths}


def main(argv: list[str] | None = None) -> int:
    """Run the prompt or apply subcommand."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["prompt", "apply"])
    ap.add_argument("--findings", required=True)
    ap.add_argument("--diff", required=True)
    ap.add_argument("--file", action="append", default=[], dest="files")
    ap.add_argument("--lang", default="unknown")
    ap.add_argument("--verdicts")
    args = ap.parse_args(argv)
    try:
        findings = _load_findings(args.findings)
        diff = Path(args.diff).read_text(encoding="utf-8")
        files = _load_files(args.files)
        if args.cmd == "prompt":
            print(build_prompt(findings, diff, files, args.lang))
            return 0
        if not args.verdicts:
            raise ValueError("apply needs --verdicts")
        reply = Path(args.verdicts).read_text(encoding="utf-8")
    except (OSError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    print(json.dumps(apply_verdicts(findings, reply, diff, files), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
