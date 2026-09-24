#!/usr/bin/env python3
"""Run one weak-model generation for a skill-uplift experiment.

Builds a prompt from guidance files plus a task, sends it to a weaker model
through `claude -p` with no tools, and saves the prompt, raw reply, and the
extracted artifact. Used by the toolkit skill's "Uplift for weaker models" mode
(skills/meta/toolkit/references/weak-model-uplift.md).

Usage:
    python3 scripts/weak_model_run.py --task task.txt --out runs/r1/guided-dashboard \
        --guidance skills/shared-patterns/ui-design-judgment.md --format html
    python3 scripts/weak_model_run.py --task task.txt --out runs/r0/base-pool --format files

Each run writes <out>.prompt, <out>.raw (every assistant text block), <out>.err, and <out>.cost.json
(dollar cost and token counts), so a round's cost is the sum of its .cost.json files. In files format,
prose the model adds after its last file goes to <out>.commentary instead of into that file.

Formats:
    html   keep the text from <!doctype ...> to </html>
    files  split `=== FILE: path ===` blocks into files under <out>/
    text   keep the reply as is
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_MODEL = "claude-opus-4-6"
FILE_MARKER = re.compile(r"^=== FILE: (.+?) ===\s*$", re.MULTILINE)
INSTRUCTIONS = {
    "html": "Produce ONE complete, self-contained HTML file (inline CSS and JS). "
    "Output only the HTML, starting with <!doctype html>, no commentary, no code fences.",
    "files": "Output every file as a block that starts with a line `=== FILE: relative/path ===` "
    "followed by the file's full contents. No commentary, no code fences.",
    "text": "",
}


def build_prompt(task: str, guidance: list[str], fmt: str) -> str:
    """Return the full prompt: format instruction, guidance, then the task."""
    parts = [INSTRUCTIONS[fmt]] if INSTRUCTIONS[fmt] else []
    if guidance:
        parts.append("Follow this guidance closely:\n\n" + "\n\n".join(guidance))
    parts.append("TASK:\n" + task.strip())
    return "\n\n".join(parts) + "\n"


def extract_html(reply: str) -> str:
    """Return the HTML document inside *reply*, or the reply when none is found."""
    low = reply.lower()
    start, end = low.find("<!doctype"), low.rfind("</html>")
    return reply[start : end + len("</html>")] if start >= 0 and end > start else reply


def extract_files(reply: str) -> dict[str, str]:
    """Split `=== FILE: path ===` blocks. Rejects absolute paths and `..` segments."""
    files: dict[str, str] = {}
    marks = list(FILE_MARKER.finditer(reply))
    for i, m in enumerate(marks):
        path = m.group(1).strip()
        if path.startswith("/") or ".." in Path(path).parts:
            raise ValueError(f"unsafe path in reply: {path}")
        body_end = marks[i + 1].start() if i + 1 < len(marks) else len(reply)
        body = reply[m.end() : body_end].strip("\n")
        body = re.sub(r"^```[a-zA-Z0-9]*\n|\n```$", "", body)
        files[path] = body + "\n"
    return files


def parse_reply(stdout: str) -> tuple[list[str], dict[str, object]]:
    """Split `claude -p --output-format stream-json` output into (assistant text blocks, cost record).

    The `result` field holds only the model's final text block. A model that writes its files and then a
    closing summary loses the files there, so every assistant text block is collected instead. Output
    that is not a JSON event stream passes through as a single block with no cost record.
    """
    blocks: list[str] = []
    cost: dict[str, object] = {}
    keys = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return [stdout], {}
        if not isinstance(event, dict):
            return [stdout], {}
        if event.get("type") == "assistant":
            content = event.get("message", {}).get("content", [])
            blocks += [b["text"] for b in content if b.get("type") == "text" and b.get("text")]
        elif event.get("type") == "result":
            usage = event.get("usage") or {}
            cost = {"total_cost_usd": event.get("total_cost_usd"), **{k: usage.get(k) for k in keys}}
            if not blocks and event.get("result"):
                blocks = [str(event["result"])]
    return blocks, cost


def split_commentary(blocks: list[str]) -> tuple[str, str]:
    """Return (file text, trailing commentary): blocks after the last one with a FILE marker are commentary."""
    marked = [i for i, b in enumerate(blocks) if FILE_MARKER.search(b)]
    if not marked:
        return "\n\n".join(blocks), ""
    cut = marked[-1] + 1
    return "\n\n".join(blocks[:cut]), "\n\n".join(blocks[cut:])


def run_model(prompt: str, model: str, timeout: int) -> tuple[str, str]:
    """Send *prompt* to `claude -p` with no tools. Returns (stdout, stderr); stdout is a JSON event stream."""
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING", None)  # forces the deprecated fixed budget on older models
    proc = subprocess.run(
        ["claude", "-p", "--model", model, "--tools", "", "--output-format", "stream-json", "--verbose"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        check=False,
    )
    return proc.stdout, proc.stderr


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--task", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path, help="output prefix (html/text) or directory (files)")
    ap.add_argument("--guidance", action="append", default=[], type=Path)
    ap.add_argument("--format", choices=sorted(INSTRUCTIONS), default="text")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args(argv)

    prompt = build_prompt(
        args.task.read_text(encoding="utf-8"), [g.read_text(encoding="utf-8") for g in args.guidance], args.format
    )
    out = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{out}.prompt").write_text(prompt, encoding="utf-8")
    stdout, err = run_model(prompt, args.model, args.timeout)
    blocks, cost = parse_reply(stdout)
    reply = "\n\n".join(blocks)
    Path(f"{out}.raw").write_text(reply, encoding="utf-8")
    Path(f"{out}.err").write_text(err, encoding="utf-8")
    if cost:
        Path(f"{out}.cost.json").write_text(json.dumps(cost, indent=2) + "\n", encoding="utf-8")
    if not reply.strip():
        print(f"{args.model} returned an empty reply; see {out}.err", file=sys.stderr)
        return 1
    if args.format == "html":
        Path(f"{out}.html").write_text(extract_html(reply), encoding="utf-8")
    elif args.format == "files":
        files_text, commentary = split_commentary(blocks)
        if commentary:
            Path(f"{out}.commentary").write_text(commentary, encoding="utf-8")
        files = extract_files(files_text)
        if not files:
            print(f"no === FILE: blocks in reply (rate limit or refusal?); see {out}.raw", file=sys.stderr)
            return 1
        for rel, body in files.items():
            dest = out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
