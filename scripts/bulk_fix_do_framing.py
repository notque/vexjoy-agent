#!/usr/bin/env python3
"""Bulk-fix safe do-framing backlog items.

This script reuses the existing unpaired anti-pattern detector and applies a
very narrow deterministic fix: insert a `no-pair-required` annotation ahead of
structural anti-pattern section headers that were flagged even though the block
is acting as an organizer, index, or table header rather than as a standalone
anti-pattern entry.

Anything that looks like a real anti-pattern remains in backlog for manual or
LLM-assisted rewriting.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
DETECTOR_PATH = REPO_ROOT / "scripts" / "detect-unpaired-antipatterns.py"
DEFAULT_ANNOTATION = (
    "<!-- no-pair-required: section-header-only; individual anti-patterns below "
    "carry Do-instead blocks -->"
)
STRUCTURAL_HEADING = re.compile(
    r"^#{1,6}\s+(?:.*anti-pattern(?:s)?(?:\s+catalog)?|examples,\s*anti-patterns,\s*error handling)\s*$",
    re.IGNORECASE,
)
REAL_ANTIPATTERN_MARKERS = (
    "**What it looks like**",
    "**Why wrong**",
    "**Do instead**",
    "**Correct approach**",
    "Do instead:",
    "Correct approach:",
)
TABLE_LINE = re.compile(r"^\|.*\|\s*$")
REFERENCE_SUMMARY = re.compile(r"^(See\s+[`\[]|See\s+references?/|---$)", re.IGNORECASE)
BULLET_SUMMARY = re.compile(r"^[-*]\s+\*\*")


@dataclass
class Candidate:
    file: str
    line_start: int
    line_end: int
    heading: str
    action: str
    reason: str


def _load_detector():
    spec = importlib.util.spec_from_file_location("detect_unpaired_antipatterns", DETECTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load detector: {DETECTOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def classify_finding(finding) -> Candidate | None:
    lines = finding.block_text.splitlines()
    if not lines:
        return None

    heading = lines[0].strip()
    body = [line.strip() for line in lines[1:] if line.strip()]

    if not STRUCTURAL_HEADING.match(heading):
        return None
    if any(marker in finding.block_text for marker in REAL_ANTIPATTERN_MARKERS):
        return None
    if heading.startswith("# ") and "anti-pattern" in heading.lower():
        return Candidate(finding.file, finding.line_range[0], finding.line_range[1], heading, "skip", "document-title")
    if not body:
        return Candidate(
            finding.file,
            finding.line_range[0],
            finding.line_range[1],
            heading,
            "annotate",
            "empty-structural-header",
        )
    if any(TABLE_LINE.match(line) for line in body):
        return Candidate(
            finding.file,
            finding.line_range[0],
            finding.line_range[1],
            heading,
            "annotate",
            "table-backed-section-header",
        )
    if REFERENCE_SUMMARY.match(body[0]):
        return Candidate(
            finding.file,
            finding.line_range[0],
            finding.line_range[1],
            heading,
            "annotate",
            "reference-summary-header",
        )
    if all(BULLET_SUMMARY.match(line) or line == "---" for line in body):
        return Candidate(
            finding.file,
            finding.line_range[0],
            finding.line_range[1],
            heading,
            "annotate",
            "summary-list-header",
        )
    return None


def insert_annotation(path: Path, line_start: int, annotation: str) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    idx = max(0, line_start - 1)
    if idx > 0 and "no-pair-required" in lines[idx - 1]:
        return False
    lines.insert(idx, annotation)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk-fix safe do-framing backlog items")
    parser.add_argument("--apply", action="store_true", help="Apply safe annotations in place")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Emit JSON report")
    parser.add_argument("--output", metavar="PATH", help="Write JSON report to file")
    parser.add_argument("--annotation", default=DEFAULT_ANNOTATION, help="Annotation text to insert")
    args = parser.parse_args()

    detector = _load_detector()
    findings = []
    for path in detector.collect_scan_targets():
        findings.extend(detector.scan_file(path))

    candidates: list[Candidate] = []
    applied = 0
    for finding in findings:
        candidate = classify_finding(finding)
        if candidate is None:
            continue
        candidates.append(candidate)
        if args.apply and candidate.action == "annotate":
            changed = insert_annotation(REPO_ROOT / candidate.file, candidate.line_start, args.annotation)
            if changed:
                applied += 1

    payload = {
        "total_findings": len(findings),
        "safe_candidates": len(candidates),
        "applied": applied,
        "candidates": [asdict(candidate) for candidate in candidates],
    }

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.json_output:
        print(json.dumps(payload, indent=2))
    elif not args.output:
        print(f"total findings: {len(findings)}")
        print(f"safe candidates: {len(candidates)}")
        print(f"applied: {applied}")
        for candidate in candidates[:50]:
            print(f"{candidate.file}:{candidate.line_start} [{candidate.reason}] {candidate.heading}")
        if len(candidates) > 50:
            print(f"... {len(candidates) - 50} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
