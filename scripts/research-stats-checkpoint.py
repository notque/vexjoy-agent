#!/usr/bin/env python3
"""Phase-1.5 deterministic research stats checkpoint.

Walks a `research/{topic}/` directory, counts artifacts per agent, computes the
primary-source ratio, surfaces conflicting frontmatter values across artifacts,
and emits a Markdown table for human review. Exits non-zero when configurable
gate thresholds are not met, so the script can be wired into a pipeline as a
deterministic gate between GATHER and SYNTHESIZE phases.

Usage:
    python3 scripts/research-stats-checkpoint.py research/feynman/
    python3 scripts/research-stats-checkpoint.py research/feynman/ \\
        --min-primary 3 --max-agent-share 0.75

Exit codes:
    0 -- All gate thresholds satisfied; proceed to synthesis.
    1 -- One or more gates failed (insufficient primaries, single-agent
         dominance, empty/missing directory, etc.).

Design notes:
    * Stdlib only -- no third-party dependencies.
    * Agents are identified by the immediate subdirectory of the topic dir, or
      (when artifacts sit flat at the topic root) by a `{agent}__{name}.ext`
      filename prefix.
    * "Primary" vs "secondary" is detected from a `source_type:` line in the
      first ~30 lines of each artifact (frontmatter or near-top markup).
    * Conflicts are detected by parsing simple `key: value` frontmatter; any
      key that takes ≥2 distinct values across artifacts is reported.
    * Conflicts are advisory output, not a hard gate -- they surface for human
      review without blocking automated pipelines.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

ARTIFACT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml"}
FRONTMATTER_SCAN_LINES = 30
DEFAULT_MIN_PRIMARY = 3
DEFAULT_MAX_AGENT_SHARE = 0.75


@dataclass
class Artifact:
    """A single research artifact discovered on disk."""

    path: Path
    agent: str
    is_primary: bool
    frontmatter: dict[str, str] = field(default_factory=dict)


@dataclass
class CheckpointReport:
    """Aggregated stats across all artifacts in a topic directory."""

    topic_dir: Path
    artifacts: list[Artifact]
    conflicts: dict[str, dict[str, list[str]]]  # key -> value -> [paths]

    @property
    def total(self) -> int:
        return len(self.artifacts)

    @property
    def per_agent(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for art in self.artifacts:
            counts[art.agent] += 1
        return dict(counts)

    @property
    def primary_count(self) -> int:
        return sum(1 for a in self.artifacts if a.is_primary)

    @property
    def primary_ratio(self) -> float:
        return self.primary_count / self.total if self.total else 0.0

    @property
    def max_agent_share(self) -> float:
        if not self.artifacts:
            return 0.0
        return max(self.per_agent.values()) / self.total


# ---- Discovery --------------------------------------------------------------


def _read_frontmatter(path: Path) -> dict[str, str]:
    """Parse a YAML-ish frontmatter block from the first lines of a file.

    Recognises both fenced (`---` delimited) frontmatter and a near-top run of
    `key: value` lines. Values are stored as strings; nested structures are
    ignored. Designed to be lenient -- malformed input produces an empty dict.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    lines = text.splitlines()[:FRONTMATTER_SCAN_LINES]

    # Fenced frontmatter (--- ... ---).
    if lines and lines[0].strip() == "---":
        body_lines: list[str] = []
        for line in lines[1:]:
            if line.strip() == "---":
                break
            body_lines.append(line)
        return _parse_kv_lines(body_lines)

    # Otherwise scan the head for key: value lines.
    return _parse_kv_lines(lines)


def _parse_kv_lines(lines: Iterable[str]) -> dict[str, str]:
    """Parse `key: value` pairs from an iterable of lines. Tolerant of comments."""
    out: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip("\"'")
        if not key or not value or " " in key:
            continue
        # First occurrence wins -- avoid clobbering with nested-block remnants.
        if key not in out:
            out[key] = value
    return out


def _agent_for(path: Path, topic_dir: Path) -> str:
    """Determine the owning agent for an artifact.

    Prefer the immediate subdirectory under `topic_dir`. When the artifact is
    flat at the topic root, fall back to the `{agent}__rest.ext` filename
    convention. If neither is available, return ``"_root"``.
    """
    rel = path.relative_to(topic_dir)
    if len(rel.parts) > 1:
        return rel.parts[0]
    stem = rel.stem
    if "__" in stem:
        return stem.split("__", 1)[0]
    return "_root"


def discover_artifacts(topic_dir: Path) -> list[Artifact]:
    """Walk `topic_dir` and return one Artifact per recognised file."""
    artifacts: list[Artifact] = []
    for path in sorted(topic_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ARTIFACT_SUFFIXES:
            continue
        frontmatter = _read_frontmatter(path)
        is_primary = frontmatter.get("source_type", "").lower() == "primary"
        artifacts.append(
            Artifact(
                path=path,
                agent=_agent_for(path, topic_dir),
                is_primary=is_primary,
                frontmatter=frontmatter,
            )
        )
    return artifacts


def detect_conflicts(artifacts: list[Artifact]) -> dict[str, dict[str, list[str]]]:
    """Return keys whose frontmatter values disagree across artifacts.

    Output shape: ``{key: {value: [path, ...]}}`` only for keys with ≥2
    distinct values. Keys that appear in only one artifact, or that always
    carry the same value, are omitted. Per-artifact ``url`` keys are skipped
    because they're inherently unique per source.
    """
    skip_keys = {"url", "source_url", "source_id"}
    by_key: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for art in artifacts:
        for key, value in art.frontmatter.items():
            if key in skip_keys:
                continue
            by_key[key][value].append(str(art.path))
    return {key: dict(values) for key, values in by_key.items() if len(values) >= 2}


# ---- Reporting --------------------------------------------------------------


def render_table(report: CheckpointReport) -> str:
    """Render the human-readable Markdown report."""
    lines: list[str] = []
    lines.append(f"# Research Stats Checkpoint -- {report.topic_dir}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Total artifacts | {report.total} |")
    lines.append(f"| Primary sources | {report.primary_count} |")
    lines.append(f"| Primary-source ratio | {report.primary_ratio:.0%} |")
    lines.append(f"| Distinct agents | {len(report.per_agent)} |")
    lines.append(f"| Max single-agent share | {report.max_agent_share:.0%} |")
    lines.append("")

    lines.append("## Per-Agent Counts")
    lines.append("")
    lines.append("| Agent | Artifacts | Primary | Share |")
    lines.append("|---|---|---|---|")
    primary_by_agent: dict[str, int] = defaultdict(int)
    for art in report.artifacts:
        if art.is_primary:
            primary_by_agent[art.agent] += 1
    for agent, count in sorted(report.per_agent.items()):
        share = count / report.total if report.total else 0.0
        primary = primary_by_agent.get(agent, 0)
        lines.append(f"| {agent} | {count} | {primary} | {share:.0%} |")
    lines.append("")

    lines.append("## Conflicts")
    lines.append("")
    if not report.conflicts:
        lines.append("_None detected._")
    else:
        lines.append("| Key | Distinct values | Counts |")
        lines.append("|---|---|---|")
        for key, values in sorted(report.conflicts.items()):
            vlist = "; ".join(sorted(values.keys()))
            counts = "; ".join(f"{value} ({len(paths_for_value)})" for value, paths_for_value in sorted(values.items()))
            lines.append(f"| {key} | {vlist} | {counts} |")
    lines.append("")
    return "\n".join(lines)


# ---- Gate logic -------------------------------------------------------------


def evaluate_gates(
    report: CheckpointReport,
    *,
    min_primary: int,
    max_agent_share: float,
) -> list[str]:
    """Return a list of human-readable failure reasons. Empty list = pass."""
    failures: list[str] = []
    if report.total == 0:
        failures.append("No artifacts found in research directory (empty).")
        return failures
    if report.primary_count < min_primary:
        failures.append(
            f"Only {report.primary_count} primary source(s); "
            f"minimum is {min_primary}. Add primary-source artifacts before synthesis."
        )
    if report.max_agent_share > max_agent_share:
        dominant = max(report.per_agent.items(), key=lambda kv: kv[1])
        failures.append(
            f"Single-agent dominance: '{dominant[0]}' owns "
            f"{report.max_agent_share:.0%} of artifacts (max allowed {max_agent_share:.0%}). "
            f"Dispatch additional researchers for cross-source coverage."
        )
    return failures


# ---- CLI --------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase-1.5 deterministic stats checkpoint for research/{topic}/.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("topic_dir", type=Path, help="Path to the research/{topic}/ directory.")
    parser.add_argument(
        "--min-primary",
        type=int,
        default=DEFAULT_MIN_PRIMARY,
        help=f"Minimum primary sources required (default: {DEFAULT_MIN_PRIMARY}).",
    )
    parser.add_argument(
        "--max-agent-share",
        type=float,
        default=DEFAULT_MAX_AGENT_SHARE,
        help=(
            "Maximum share of artifacts a single agent may own "
            f"(default: {DEFAULT_MAX_AGENT_SHARE:.2f}). Above this, gate fails."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    topic_dir: Path = args.topic_dir
    if not topic_dir.exists():
        print(f"ERROR: research directory not found: {topic_dir}", file=sys.stderr)
        return 1
    if not topic_dir.is_dir():
        print(f"ERROR: not a directory: {topic_dir}", file=sys.stderr)
        return 1

    artifacts = discover_artifacts(topic_dir)
    conflicts = detect_conflicts(artifacts)
    report = CheckpointReport(topic_dir=topic_dir, artifacts=artifacts, conflicts=conflicts)

    print(render_table(report))

    failures = evaluate_gates(
        report,
        min_primary=args.min_primary,
        max_agent_share=args.max_agent_share,
    )

    if failures:
        print("## Gate: FAIL")
        print("")
        for reason in failures:
            print(f"- {reason}")
        return 1

    print("## Gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
