#!/usr/bin/env python3
"""Deterministic health scorer for agents and skills.

Checks structural quality of agent and skill markdown files without any LLM calls.
Pure filesystem validation against the component rubric defined in ADR-031.

Usage:
    python3 scripts/score-component.py agents/golang-general-engineer.md
    python3 scripts/score-component.py --all-agents
    python3 scripts/score-component.py --all-skills
    python3 scripts/score-component.py --all-agents --all-skills --json
    python3 scripts/score-component.py agents/golang-general-engineer.md --check-secrets

Exit codes:
    0 — All scored components grade B or above
    1 — One or more components grade C or below
    2 — Script error (bad arguments, missing files)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"glpat-[a-zA-Z0-9\-]{20,}"),
    re.compile(r"xox[bprs]-"),
]

PLACEHOLDER_INDICATORS = {"your-", "xxx", "example", "placeholder", "todo", "change_me", "<", ">"}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """Result of a single rubric check."""

    name: str
    max_points: int
    earned_points: int
    detail: str = ""

    @property
    def status(self) -> str:
        if self.earned_points == self.max_points:
            return "PASS"
        elif self.earned_points == 0:
            return "FAIL"
        else:
            return "PART"


@dataclass
class ComponentScore:
    """Aggregated score for a single component."""

    file_path: str
    component_type: str  # "agent" or "skill"
    checks: list[CheckResult] = field(default_factory=list)
    secret_penalty: int = 0
    secrets_found: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        raw = sum(c.earned_points for c in self.checks) + self.secret_penalty
        return max(raw, 0)

    @property
    def max_total(self) -> int:
        return sum(c.max_points for c in self.checks)

    @property
    def grade(self) -> str:
        t = self.total
        if t >= 90:
            return "A"
        elif t >= 75:
            return "B"
        elif t >= 60:
            return "C"
        elif t >= 40:
            return "D"
        else:
            return "F"


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def extract_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter from markdown content."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    yaml_content = match.group(1)
    try:
        return yaml.safe_load(yaml_content)
    except yaml.YAMLError:
        pass

    # Fallback: regex extraction for complex frontmatter with unquoted colons
    frontmatter: dict = {}
    name_match = re.search(r"^name:\s*(.+)$", yaml_content, re.MULTILINE)
    if name_match:
        frontmatter["name"] = name_match.group(1).strip()

    desc_match = re.search(r"^description:\s*(.+?)(?=\n[a-z]+:|$)", yaml_content, re.MULTILINE | re.DOTALL)
    if desc_match:
        frontmatter["description"] = desc_match.group(1).strip()

    return frontmatter if frontmatter else None


# ---------------------------------------------------------------------------
# Component type detection
# ---------------------------------------------------------------------------


def detect_component_type(file_path: Path) -> str | None:
    """Detect whether a file is an agent or skill based on path conventions."""
    parts = file_path.parts
    if "agents" in parts and file_path.suffix == ".md":
        return "agent"
    if "skills" in parts and file_path.name == "SKILL.md":
        return "skill"
    return None


def get_skill_name(file_path: Path) -> str:
    """Extract skill directory name from a SKILL.md path."""
    # skills/<name>/SKILL.md -> <name>
    return file_path.parent.name


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_yaml_frontmatter(content: str) -> CheckResult:
    """Check: Valid YAML frontmatter with name and description fields (10 pts)."""
    fm = extract_frontmatter(content)
    if fm is None:
        return CheckResult("Valid YAML frontmatter", 10, 0, "No frontmatter found")

    has_name = "name" in fm and fm["name"]
    has_desc = "description" in fm and fm["description"]

    if has_name and has_desc:
        return CheckResult("Valid YAML frontmatter", 10, 10)

    missing = []
    if not has_name:
        missing.append("name")
    if not has_desc:
        missing.append("description")
    return CheckResult("Valid YAML frontmatter", 10, 5, f"Missing: {', '.join(missing)}")


def check_referenced_files(content: str) -> CheckResult:
    """Check: Referenced backtick-quoted paths exist on disk (15 pts)."""
    # Match backtick-quoted strings that look like filesystem paths
    backtick_paths = re.findall(r"`([^`]+)`", content)
    file_like: list[str] = []

    for p in backtick_paths:
        # Must contain / to look like a path — dot-only matches (iter.Seq, slices.All)
        # are overwhelmingly code references, not file paths
        if "/" not in p:
            continue
        # Filter out things that are clearly not filesystem paths
        if p.startswith(("http", "$", "git ", "go ", "npm ", "pip ")):
            continue
        # Filter out command invocations (spaces in non-path-prefixed strings)
        if " " in p and not p.startswith(("scripts/", "skills/", "agents/", "hooks/", "adr/", "docs/")):
            continue
        # Filter out Go/JS import paths, npm packages
        if p.startswith(("golang.org/", "github.com/", "@", "gopkg.in/")):
            continue
        # Filter out template/pattern paths with brackets or glob wildcards
        if "[" in p or "*" in p or "{" in p:
            continue
        # Filter out CLI flag-like patterns and slash-command invocations
        if p.startswith("-"):
            continue
        # Filter out slash commands like /pr-review, /do, etc.
        if p.startswith("/") and not p.startswith("/home"):
            continue
        # Filter out dot-prefixed directories (.claude/, .feature/) — these are
        # environment-specific paths, not repo-relative references
        if p.startswith(".") and "/" in p:
            continue
        file_like.append(p)

    if not file_like:
        return CheckResult("Referenced files exist", 15, 15, "No file references found")

    valid = 0
    invalid_paths: list[str] = []
    for p in file_like:
        resolved = REPO_ROOT / p
        if resolved.exists():
            valid += 1
        else:
            invalid_paths.append(p)

    total = len(file_like)
    ratio = valid / total if total > 0 else 1.0
    earned = round(ratio * 15)

    detail = f"{valid}/{total} valid"
    if invalid_paths:
        shown = invalid_paths[:5]
        detail += f" (missing: {', '.join(shown)})"
        if len(invalid_paths) > 5:
            detail += f" +{len(invalid_paths) - 5} more"

    return CheckResult("Referenced files exist", 15, earned, detail)


def check_anti_patterns_section(content: str) -> CheckResult:
    """Check: Has anti-patterns section heading (10 pts)."""
    if re.search(r"^#{1,3}\s+.*anti.?pattern", content, re.IGNORECASE | re.MULTILINE):
        return CheckResult("Anti-patterns section", 10, 10)
    return CheckResult("Anti-patterns section", 10, 0, "No '## Anti-Pattern*' heading found")


def check_error_handling_section(content: str) -> CheckResult:
    """Check: Has error handling section heading (10 pts)."""
    if re.search(r"^#{1,3}\s+.*error", content, re.IGNORECASE | re.MULTILINE):
        return CheckResult("Error handling section", 10, 10)
    return CheckResult("Error handling section", 10, 0, "No '## Error*' heading found")


def check_routing_registration(component_type: str, file_path: Path, fm: dict | None) -> CheckResult:
    """Check: Component is registered in routing (10 pts)."""
    if fm is None:
        return CheckResult("Registered in routing", 10, 0, "No frontmatter to extract name")

    component_name = fm.get("name", "")
    if not component_name:
        return CheckResult("Registered in routing", 10, 0, "No name in frontmatter")

    if component_type == "agent":
        index_path = REPO_ROOT / "agents" / "INDEX.json"
        if not index_path.exists():
            return CheckResult("Registered in routing", 10, 0, "agents/INDEX.json not found")

        try:
            index_data = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return CheckResult("Registered in routing", 10, 0, "Failed to parse agents/INDEX.json")

        agents = index_data.get("agents", {})
        if component_name in agents:
            return CheckResult("Registered in routing", 10, 10)
        return CheckResult("Registered in routing", 10, 0, f"'{component_name}' not in agents/INDEX.json")

    elif component_type == "skill":
        skill_dir_name = get_skill_name(file_path)

        # Check /do SKILL.md
        do_skill = REPO_ROOT / "skills" / "do" / "SKILL.md"
        routing_tables = REPO_ROOT / "skills" / "do" / "references" / "routing-tables.md"

        found_in: list[str] = []
        for check_path, label in [(do_skill, "do/SKILL.md"), (routing_tables, "routing-tables.md")]:
            if check_path.exists():
                try:
                    text = check_path.read_text(encoding="utf-8")
                    if skill_dir_name in text:
                        found_in.append(label)
                except OSError:
                    pass

        # Also check skills/INDEX.json
        skills_index = REPO_ROOT / "skills" / "INDEX.json"
        if skills_index.exists():
            try:
                si_data = json.loads(skills_index.read_text(encoding="utf-8"))
                skills_map = si_data.get("skills", {})
                if skill_dir_name in skills_map:
                    found_in.append("skills/INDEX.json")
            except (json.JSONDecodeError, OSError):
                pass

        if found_in:
            return CheckResult("Registered in routing", 10, 10, f"Found in: {', '.join(found_in)}")
        return CheckResult("Registered in routing", 10, 0, f"'{skill_dir_name}' not in /do routing or INDEX")

    return CheckResult("Registered in routing", 10, 0, f"Unknown type: {component_type}")


def check_reference_files(component_type: str, file_path: Path) -> CheckResult:
    """Check: Has reference files directory (10 pts)."""
    if component_type == "agent":
        # Agents share agents/references/
        refs_dir = REPO_ROOT / "agents" / "references"
    else:
        # Skills have per-skill references/
        refs_dir = file_path.parent / "references"

    if refs_dir.is_dir():
        ref_count = len(list(refs_dir.iterdir()))
        return CheckResult("Reference files", 10, 10, f"{ref_count} files in {refs_dir.relative_to(REPO_ROOT)}")
    return CheckResult("Reference files", 10, 0, f"No references/ directory at {refs_dir.relative_to(REPO_ROOT)}")


def check_operator_context(content: str) -> CheckResult:
    """Check: Operator Context with Hardcoded/Default/Optional subsections (15 pts)."""
    subsections = {
        "Hardcoded Behaviors": bool(re.search(r"#{2,4}\s+Hardcoded Behaviors", content, re.IGNORECASE)),
        "Default Behaviors": bool(re.search(r"#{2,4}\s+Default Behaviors", content, re.IGNORECASE)),
        "Optional Behaviors": bool(re.search(r"#{2,4}\s+Optional Behaviors", content, re.IGNORECASE)),
    }

    found = sum(1 for v in subsections.values() if v)
    earned = round((found / 3) * 15)

    if found == 3:
        return CheckResult("Operator Context", 15, 15)

    missing = [k for k, v in subsections.items() if not v]
    return CheckResult("Operator Context", 15, earned, f"{found}/3 subsections (missing: {', '.join(missing)})")


def check_can_cannot_sections(content: str) -> CheckResult:
    """Check: CAN and CANNOT sections present (10 pts)."""
    has_can = bool(re.search(r"#{2,4}\s+What This .* CAN Do", content, re.IGNORECASE))
    has_cannot = bool(re.search(r"#{2,4}\s+What This .* CANNOT Do", content, re.IGNORECASE))

    if has_can and has_cannot:
        return CheckResult("CAN/CANNOT sections", 10, 10)
    elif has_can or has_cannot:
        present = "CAN" if has_can else "CANNOT"
        missing = "CANNOT" if has_can else "CAN"
        return CheckResult("CAN/CANNOT sections", 10, 5, f"Has {present}, missing {missing}")
    return CheckResult("CAN/CANNOT sections", 10, 0, "Neither CAN nor CANNOT section found")


def check_broken_internal_links(content: str, file_path: Path) -> CheckResult:
    """Check: No broken markdown internal links (10 pts)."""
    # Match markdown links: [text](path) — exclude URLs and anchors
    # Only match links outside of code blocks
    # Strip fenced code blocks first to avoid false positives from code examples
    stripped = re.sub(r"```.*?```", "", content, flags=re.DOTALL)

    link_pattern = re.compile(r"\[(?:[^\]]+)\]\(([^)]+)\)")
    links = link_pattern.findall(stripped)

    relative_links: list[str] = []
    for link in links:
        # Skip URLs, anchors, mailto, and template variables
        if link.startswith(("http://", "https://", "#", "mailto:", "<", "{")):
            continue
        # Strip anchor fragment from path
        path_part = link.split("#")[0]
        if not path_part:
            continue
        # Skip very short "paths" that are likely code references (e.g., err, ctx, ok)
        if "/" not in path_part and "." not in path_part:
            continue
        relative_links.append(path_part)

    if not relative_links:
        return CheckResult("No broken internal links", 10, 10, "No internal links found")

    valid = 0
    broken: list[str] = []
    base_dir = file_path.parent

    for link in relative_links:
        # Resolve relative to the file's directory
        resolved = (base_dir / link).resolve()
        # Also try relative to repo root (some links use repo-relative paths)
        resolved_from_root = (REPO_ROOT / link).resolve()

        if resolved.exists() or resolved_from_root.exists():
            valid += 1
        else:
            broken.append(link)

    total = len(relative_links)
    if total == 0:
        return CheckResult("No broken internal links", 10, 10)

    ratio = valid / total
    earned = round(ratio * 10)

    detail = f"{valid}/{total} valid"
    if broken:
        shown = broken[:5]
        detail += f" (broken: {', '.join(shown)})"
        if len(broken) > 5:
            detail += f" +{len(broken) - 5} more"

    return CheckResult("No broken internal links", 10, earned, detail)


# ---------------------------------------------------------------------------
# Secret detection
# ---------------------------------------------------------------------------


def _is_placeholder(match_text: str) -> bool:
    """Check if a secret match is actually a placeholder/example."""
    lower = match_text.lower()
    return any(indicator in lower for indicator in PLACEHOLDER_INDICATORS)


def check_secrets(content: str) -> tuple[int, list[str]]:
    """Scan for leaked secrets. Returns (penalty, list of findings)."""
    findings: list[str] = []

    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(content):
            matched = match.group()
            if not _is_placeholder(matched):
                # Truncate for display
                preview = matched[:12] + "..." if len(matched) > 12 else matched
                findings.append(preview)

    # -10 per secret, max -20
    penalty = max(-10 * len(findings), -20) if findings else 0
    return penalty, findings


# ---------------------------------------------------------------------------
# Scoring orchestration
# ---------------------------------------------------------------------------


def score_component(file_path: Path, do_check_secrets: bool = False) -> ComponentScore:
    """Run all checks against a single component file."""
    component_type = detect_component_type(file_path)
    if component_type is None:
        print(f"Error: Cannot detect component type for {file_path}", file=sys.stderr)
        sys.exit(2)

    try:
        content = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(2)
    except OSError as e:
        print(f"Error: Cannot read {file_path}: {e}", file=sys.stderr)
        sys.exit(2)

    fm = extract_frontmatter(content)

    score = ComponentScore(
        file_path=str(file_path.relative_to(REPO_ROOT)),
        component_type=component_type,
    )

    score.checks.append(check_yaml_frontmatter(content))
    score.checks.append(check_referenced_files(content))
    score.checks.append(check_anti_patterns_section(content))
    score.checks.append(check_error_handling_section(content))
    score.checks.append(check_routing_registration(component_type, file_path, fm))
    score.checks.append(check_reference_files(component_type, file_path))
    score.checks.append(check_operator_context(content))
    score.checks.append(check_can_cannot_sections(content))
    score.checks.append(check_broken_internal_links(content, file_path))

    if do_check_secrets:
        penalty, findings = check_secrets(content)
        score.secret_penalty = penalty
        score.secrets_found = findings

    return score


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_score(score: ComponentScore) -> str:
    """Format a ComponentScore as human-readable text."""
    lines = [
        "=== Component Health Score ===",
        f"File: {score.file_path}",
        f"Type: {score.component_type}",
        "",
    ]

    for check in score.checks:
        status_tag = f"[{check.status}]"
        label = check.name
        if check.detail:
            label += f" ({check.detail})"
        points = f"{check.earned_points}/{check.max_points}"
        lines.append(f"  {status_tag:6s}  {label:<50s} {points:>5s}")

    if score.secrets_found:
        lines.append("")
        lines.append(f"  [WARN]  Secrets detected: {len(score.secrets_found)} found         {score.secret_penalty:>5d}")
        for s in score.secrets_found:
            lines.append(f"          - {s}")

    lines.append("")
    lines.append(f"  TOTAL: {score.total}/{score.max_total} ({score.grade})")
    lines.append("")
    lines.append("  Grade: A (90-100) | B (75-89) | C (60-74) | D (40-59) | F (0-39)")

    return "\n".join(lines)


def format_summary_table(scores: list[ComponentScore]) -> str:
    """Format a summary table for multiple components."""
    lines = [
        "",
        "=== Summary ===",
        f"  {'Component':<50s} {'Score':>7s}  {'Grade':>5s}",
        f"  {'─' * 50}  {'─' * 7}  {'─' * 5}",
    ]

    for s in sorted(scores, key=lambda x: x.total, reverse=True):
        name = s.file_path
        lines.append(f"  {name:<50s} {s.total:>3d}/{s.max_total:<3d}  {s.grade:>5s}")

    # Aggregate stats
    if scores:
        avg = sum(s.total for s in scores) / len(scores)
        passing = sum(1 for s in scores if s.grade in ("A", "B"))
        lines.append("")
        lines.append(f"  Average: {avg:.1f}/{scores[0].max_total}  |  Passing (B+): {passing}/{len(scores)}")

    return "\n".join(lines)


def score_to_dict(score: ComponentScore) -> dict:
    """Convert ComponentScore to a JSON-serializable dict."""
    return {
        "file": score.file_path,
        "type": score.component_type,
        "total": score.total,
        "max_total": score.max_total,
        "grade": score.grade,
        "checks": [
            {
                "name": c.name,
                "status": c.status,
                "earned": c.earned_points,
                "max": c.max_points,
                "detail": c.detail,
            }
            for c in score.checks
        ],
        "secret_penalty": score.secret_penalty,
        "secrets_found": score.secrets_found,
    }


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def find_all_agents() -> list[Path]:
    """Find all agent markdown files."""
    agents_dir = REPO_ROOT / "agents"
    if not agents_dir.is_dir():
        return []
    return sorted(p for p in agents_dir.glob("*.md") if p.name != "INDEX.json")


def find_all_skills() -> list[Path]:
    """Find all skill SKILL.md files."""
    skills_dir = REPO_ROOT / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(skills_dir.glob("*/SKILL.md"))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Deterministic health scorer for Claude Code agents and skills.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 scripts/score-component.py agents/golang-general-engineer.md\n"
            "  python3 scripts/score-component.py --all-agents\n"
            "  python3 scripts/score-component.py --all-skills --json\n"
            "  python3 scripts/score-component.py --all-agents --all-skills --check-secrets\n"
        ),
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Component file(s) to score (agents/*.md or skills/*/SKILL.md)",
    )
    parser.add_argument(
        "--all-agents",
        action="store_true",
        help="Score all agents in agents/",
    )
    parser.add_argument(
        "--all-skills",
        action="store_true",
        help="Score all skills in skills/*/SKILL.md",
    )
    parser.add_argument(
        "--check-secrets",
        action="store_true",
        help="Enable secret detection (negative scoring for leaked credentials)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON for CI integration",
    )
    return parser


def main() -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args()

    # Collect target files
    targets: list[Path] = []

    for f in args.files:
        p = Path(f)
        if not p.is_absolute():
            p = REPO_ROOT / p
        if not p.exists():
            print(f"Error: File not found: {f}", file=sys.stderr)
            return 2
        if detect_component_type(p) is None:
            print(f"Error: Cannot detect component type for {f}", file=sys.stderr)
            print("  Expected: agents/*.md or skills/*/SKILL.md", file=sys.stderr)
            return 2
        targets.append(p)

    if args.all_agents:
        targets.extend(find_all_agents())

    if args.all_skills:
        targets.extend(find_all_skills())

    # Deduplicate while preserving order
    seen: set[Path] = set()
    unique_targets: list[Path] = []
    for t in targets:
        resolved = t.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_targets.append(t)

    if not unique_targets:
        print("Error: No files to score. Provide file paths or use --all-agents / --all-skills.", file=sys.stderr)
        return 2

    # Score all targets
    scores: list[ComponentScore] = []
    for target in unique_targets:
        scores.append(score_component(target, do_check_secrets=args.check_secrets))

    # Output
    if args.json_output:
        output = {
            "results": [score_to_dict(s) for s in scores],
            "summary": {
                "total_components": len(scores),
                "average_score": round(sum(s.total for s in scores) / len(scores), 1) if scores else 0,
                "passing": sum(1 for s in scores if s.grade in ("A", "B")),
                "failing": sum(1 for s in scores if s.grade not in ("A", "B")),
            },
        }
        print(json.dumps(output, indent=2))
    else:
        for i, score in enumerate(scores):
            if i > 0:
                print()
            print(format_score(score))

        if len(scores) > 1:
            print(format_summary_table(scores))

    # Exit code: 0 if all pass (B+), 1 if any fail
    has_failures = any(s.grade not in ("A", "B") for s in scores)
    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
