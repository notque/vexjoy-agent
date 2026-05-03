#!/usr/bin/env python3
"""Extract negatively framed instruction blocks for low-token rewriting."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_PATTERNS = [
    "AGENT_TEMPLATE_V2.md",
    "CLAUDE.md",
    "docs/*.md",
    "agents/**/*.md",
    "agents/**/references/*.md",
    "skills/**/SKILL.md",
    "skills/**/references/*.md",
]
PRIMARY_PATTERNS = [
    ("NEVER", re.compile(r"\bNEVER\b")),
    ("do NOT", re.compile(r"\b[Dd]o NOT\b")),
    ("must NOT", re.compile(r"\bmust NOT\b")),
    ("FORBIDDEN", re.compile(r"\bFORBIDDEN\b")),
    ("Don't", re.compile(r"^\s*[-*]?\s*Don't\b")),
    ("Avoid", re.compile(r"^\s*#{1,6}.*Avoid|^\s*[-*]?\s*Avoid\b", re.IGNORECASE)),
    ("Anti-Pattern", re.compile(r"^\s*#{1,6}.*[Aa]nti-[Pp]attern")),
    ("What NOT To Do", re.compile(r"What NOT To Do")),
]
HEADING_RE = re.compile(r"^#{1,6}\s+")


@dataclass
class ExtractedBlock:
    id: str
    file: str
    line_start: int
    line_end: int
    heading: str
    hit_patterns: list[str]
    block_sha256: str
    estimated_tokens: int
    rewrite_goal: str
    replacement_schema: str
    block_text: str


def collect_targets() -> list[Path]:
    seen: set[Path] = set()
    targets: list[Path] = []
    for pattern in SCAN_PATTERNS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if path.is_file() and path not in seen:
                seen.add(path)
                targets.append(path)
    return targets


def block_id(rel_path: str, line_start: int, block_text: str) -> str:
    digest = hashlib.sha256(block_text.encode("utf-8")).hexdigest()[:12]
    slug = rel_path.replace("/", "__")
    return f"{slug}:{line_start}:{digest}"


def block_sha(block_text: str) -> str:
    return hashlib.sha256(block_text.encode("utf-8")).hexdigest()


def build_rewrite_goal(hit_patterns: list[str]) -> str:
    labels = ", ".join(hit_patterns)
    return (
        "Rewrite this instruction block into positive-action guidance. "
        f"Replace negatively framed signals ({labels}) with what to do, why it matters, "
        "and how to verify it."
    )


def line_hits(line: str) -> list[str]:
    hits: list[str] = []
    for label, rx in PRIMARY_PATTERNS:
        if rx.search(line):
            hits.append(label)
    return hits


def extract_blocks(path: Path) -> list[ExtractedBlock]:
    rel = str(path.relative_to(REPO_ROOT))
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    extracted: list[ExtractedBlock] = []
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence or line.lstrip().startswith(">"):
            i += 1
            continue

        hits = line_hits(line)
        if not hits:
            i += 1
            continue

        line_start = i + 1
        block_lines = [line]
        j = i + 1
        nested_fence = False
        while j < len(lines):
            candidate = lines[j]
            if candidate.startswith("```"):
                nested_fence = not nested_fence
                block_lines.append(candidate)
                j += 1
                continue
            if nested_fence:
                block_lines.append(candidate)
                j += 1
                continue
            if HEADING_RE.match(candidate) and block_lines:
                break
            if j > i + 1 and not candidate.strip() and j + 1 < len(lines) and HEADING_RE.match(lines[j + 1]):
                block_lines.append(candidate)
                j += 1
                break
            block_lines.append(candidate)
            j += 1

        block_text = "\n".join(block_lines).rstrip()
        heading = block_lines[0].strip()
        item_id = block_id(rel, line_start, block_text)
        extracted.append(
            ExtractedBlock(
                id=item_id,
                file=rel,
                line_start=line_start,
                line_end=line_start + len(block_lines) - 1,
                heading=heading,
                hit_patterns=hits,
                block_sha256=block_sha(block_text),
                estimated_tokens=max(1, math.ceil(len(block_text) / 4)),
                rewrite_goal=build_rewrite_goal(hits),
                replacement_schema=(
                    "Lead with the preferred action. Explain why it matters. "
                    "Preserve detection or verification details already present."
                ),
                block_text=block_text,
            )
        )
        i = j

    return extracted


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract negatively framed instruction blocks")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Print JSON to stdout")
    parser.add_argument("--output", metavar="PATH", help="Write JSON output to a file")
    args = parser.parse_args()

    blocks: list[ExtractedBlock] = []
    for path in collect_targets():
        blocks.extend(extract_blocks(path))

    payload = {
        "total": len(blocks),
        "blocks": [asdict(block) for block in blocks],
    }

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.json_output:
        print(json.dumps(payload, indent=2))
    elif not args.output:
        print(f"Extracted {len(blocks)} block(s).")
        for block in blocks[:50]:
            print(f"{block.file}:{block.line_start}-{block.line_end} {block.hit_patterns} {block.heading}")
        if len(blocks) > 50:
            print(f"... {len(blocks) - 50} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
