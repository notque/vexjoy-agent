#!/usr/bin/env python3
"""Validate agent reference files for structural correctness."""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

AGENTS_DIR = Path(__file__).parent.parent / "agents"
REPO_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Do-framing validation
# ---------------------------------------------------------------------------

_DO_FRAMING_SCAN_PATTERNS = [
    "agents/**/*.md",
    "agents/**/references/*.md",
    "skills/**/SKILL.md",
    "skills/**/references/*.md",
]

_ANTIPATTERN_HEADING = re.compile(
    r"(?:^#{1,4}\s+.*(?:anti.?pattern|bad\s+practice|wrong\s+way).*$"
    r"|^\*\*(?:Anti.?[Pp]attern|What it looks like|Why wrong)\*\*"
    r"|^##\s+.*(?:Anti.?[Pp]attern).*$)",
    re.IGNORECASE | re.MULTILINE,
)

_DO_INSTEAD = re.compile(
    r"(?:\*\*(?:do\s+instead|correct\s+approach|instead|do\s+this|right\s+way"
    r"|preferred|recommended|use\s+instead|better\s+approach|solution|right)\*\*"
    r"|^###?\s+.*(?:correct|preferred|instead|do\s+instead).*$"
    r"|\u2705\s+(?:do\s+instead|correct|instead|right)"
    r"|Do\s+instead:"
    r"|Correct\s+approach:"
    r"|Instead:"
    r"|\*\*Right\*\*:"
    r"|Right:)",
    re.IGNORECASE | re.MULTILINE,
)

_EXCEPTION_ANNOTATION = re.compile(r"<!--\s*no-pair-required\s*:", re.IGNORECASE)

# Table column headers that serve as an inline positive counterpart, making a
# separate "Do instead" section redundant.  Case-insensitive match against the
# header row of any Markdown table found inside the anti-pattern block.
_TABLE_POSITIVE_COLUMNS = re.compile(
    r"\b(?:Fix|Solution|Alternative|Better|Correct|Instead|Do\s+Instead"
    r"|Mitigation|Defense|What\s+to\s+Do|Prevention)\b",
    re.IGNORECASE,
)

_TABLE_HEADER_ROW = re.compile(r"^\|(.+)\|", re.MULTILINE)

_SKIP_FILENAMES = {"README.md"}


def _strip_fenced_blocks(content: str) -> str:
    """Replace content inside fenced code blocks with empty lines, preserving line count."""
    lines = content.splitlines()
    out: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in lines:
        stripped = line.strip()
        if not in_fence:
            m = re.match(r"^(`{3,}|~{3,})", stripped)
            if m:
                in_fence = True
                fence_marker = m.group(1)[0] * len(m.group(1))
                out.append(line)
            else:
                out.append(line)
        else:
            if re.match(r"^" + re.escape(fence_marker) + r"[\s]*$", stripped):
                in_fence = False
                out.append(line)
            else:
                out.append("")  # blank out code content, preserve line count
    return "\n".join(out)


def _split_blocks(content: str) -> list[tuple[int, str]]:
    """Split content by H1-H4 headings. Returns (start_line_1indexed, text) pairs."""
    lines = content.splitlines()
    blocks: list[tuple[int, str]] = []
    start = 0
    current: list[str] = []

    for i, line in enumerate(lines):
        if re.match(r"^#{1,4}\s+", line) and current:
            blocks.append((start + 1, "\n".join(current)))
            start = i
            current = [line]
        else:
            current.append(line)

    if current:
        blocks.append((start + 1, "\n".join(current)))

    return blocks


@dataclass
class DoFramingIssue:
    file: str
    line_start: int
    line_end: int
    snippet: str


def check_do_framing_in_file(path: Path) -> list[DoFramingIssue]:
    """Return unpaired anti-pattern blocks in a single file."""
    if path.name in _SKIP_FILENAMES:
        return []
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    issues: list[DoFramingIssue] = []
    try:
        rel = str(path.relative_to(REPO_ROOT))
    except ValueError:
        rel = str(path)

    all_lines = content.splitlines()
    stripped_content = _strip_fenced_blocks(content)

    for start_line, block in _split_blocks(stripped_content):
        heading_line = block.splitlines()[0] if block.splitlines() else ""
        if not _ANTIPATTERN_HEADING.search(heading_line):
            continue
        if _DO_INSTEAD.search(block):
            continue
        # Check if the block contains a table whose header row includes a
        # positive-counterpart column (Fix, Solution, Alternative, etc.).
        # Such tables are self-paired — no separate "Do instead" section needed.
        table_headers = _TABLE_HEADER_ROW.findall(block)
        if any(_TABLE_POSITIVE_COLUMNS.search(hdr) for hdr in table_headers):
            continue
        if _EXCEPTION_ANNOTATION.search(block):
            continue
        # Also check up to 3 lines immediately before the block for an annotation.
        # This handles the common pattern of placing <!-- no-pair-required: ... -->
        # on the line just before the heading.
        pre_start = max(0, start_line - 4)  # start_line is 1-indexed
        pre_context = "\n".join(all_lines[pre_start : start_line - 1])
        if _EXCEPTION_ANNOTATION.search(pre_context):
            continue
        end_line = start_line + len(block.splitlines()) - 1
        snippet = block.splitlines()[0][:120]
        issues.append(DoFramingIssue(file=rel, line_start=start_line, line_end=end_line, snippet=snippet))

    return issues


def _load_allowlist(allowlist_path: Path) -> set[tuple[str, int]]:
    """Load a backlog JSON file and return a set of (file, line_start) keys to skip."""
    if not allowlist_path.exists():
        return set()
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
        keys: set[tuple[str, int]] = set()
        for entry in data.get("findings", []):
            keys.add((entry["file"], entry["line_range"][0]))
        return keys
    except (OSError, KeyError, json.JSONDecodeError):
        return set()


_DEFAULT_ALLOWLIST = REPO_ROOT / "artifacts" / "joy-check-sweep-backlog.json"


def run_check_do_framing(json_output: bool, allowlist_path: Path | None = None) -> int:
    """Scan all skill and agent files for unpaired anti-pattern blocks.

    Violations already listed in the allowlist (backlog) are skipped so that
    pre-existing findings do not block CI while new violations do.
    """
    if allowlist_path is None:
        allowlist_path = _DEFAULT_ALLOWLIST
    known: set[tuple[str, int]] = _load_allowlist(allowlist_path)

    seen: set[Path] = set()
    targets: list[Path] = []
    for pattern in _DO_FRAMING_SCAN_PATTERNS:
        for p in sorted(REPO_ROOT.glob(pattern)):
            if p.is_file() and p not in seen:
                seen.add(p)
                targets.append(p)

    all_issues: list[DoFramingIssue] = []
    skipped = 0
    for target in targets:
        for issue in check_do_framing_in_file(target):
            if (issue.file, issue.line_start) in known:
                skipped += 1
            else:
                all_issues.append(issue)

    if json_output:
        out = {
            "total": len(all_issues),
            "skipped_known": skipped,
            "issues": [
                {"file": i.file, "line_start": i.line_start, "line_end": i.line_end, "snippet": i.snippet}
                for i in all_issues
            ],
            "exit_code": 1 if all_issues else 0,
        }
        print(json.dumps(out, indent=2))
    else:
        if all_issues:
            print(f"DO-FRAMING: {len(all_issues)} NEW unpaired anti-pattern block(s) found\n")
            for issue in all_issues:
                print(f"  {issue.file}:{issue.line_start}-{issue.line_end}")
                print(f"    {issue.snippet}")
            print(
                "\nFix: add a 'Do instead' / 'Correct approach' block, or annotate with"
                " <!-- no-pair-required: reason -->"
            )
        else:
            known_msg = f" ({skipped} known backlog item(s) skipped)" if skipped else ""
            print(f"DO-FRAMING: no new unpaired anti-pattern blocks.{known_msg}")

    return 1 if all_issues else 0


# VERDICT template headings are output-format instructions (e.g.
# ``## VERDICT: [PASS | NEEDS_CHANGES | BLOCK]``). They are intentionally
# empty — the section body is filled at review time. Exempt from EMPTY_SECTION.
_VERDICT_HEADING = re.compile(r"^##\s+VERDICT:", re.IGNORECASE)

VALID_IMPACT_LEVELS = {"CRITICAL", "HIGH", "MEDIUM-HIGH", "MEDIUM", "LOW-MEDIUM", "LOW"}

IMPACT_PATTERN = re.compile(r"\*\*Impact:\*\*\s+(\S+)")

REFERENCE_LINK_PATTERN = re.compile(r"\[(?:[^\]]+)\]\(([^)]*references/[^)]+\.md|[^)]+(?<!/)[a-z][^/)]+\.md)\)")


@dataclass
class ReferenceIssue:
    kind: str
    path: str
    detail: str = ""


@dataclass
class AgentResult:
    name: str
    declared: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    issues: list[ReferenceIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing and not self.issues


def find_declared_references(agent_file: Path) -> list[str]:
    """Extract all references/... paths mentioned in an agent .md file."""
    content = agent_file.read_text(encoding="utf-8")
    agent_dir = AGENTS_DIR / agent_file.stem

    raw_paths: list[str] = []

    for match in REFERENCE_LINK_PATTERN.finditer(content):
        link_target = match.group(1)
        if "references/" in link_target:
            raw_paths.append(link_target)

    resolved: list[str] = []
    seen: set[str] = set()

    for raw in raw_paths:
        if raw.startswith("references/"):
            candidate = str(agent_dir / raw)
        elif raw.startswith("../"):
            candidate = str((agent_file.parent / raw).resolve())
        else:
            candidate = str(AGENTS_DIR / raw)

        if candidate not in seen:
            seen.add(candidate)
            resolved.append(candidate)

    return resolved


def validate_reference_file(ref_path: Path) -> list[ReferenceIssue]:
    """Check structural requirements of a single reference .md file."""
    issues: list[ReferenceIssue] = []
    content = ref_path.read_text(encoding="utf-8")
    try:
        rel = str(ref_path.relative_to(AGENTS_DIR))
    except ValueError:
        rel = str(ref_path.relative_to(REPO_ROOT))

    headings = [line for line in content.splitlines() if line.startswith("## ")]
    if not headings:
        issues.append(ReferenceIssue("no-headings", rel, "No ## headings found"))
        return issues

    sections = re.split(r"^## .+", content, flags=re.MULTILINE)
    body_sections = sections[1:] if sections[0].strip() == "" or not sections[0].startswith("## ") else sections
    for heading, body in zip(headings, body_sections):
        stripped = body.strip()
        if not stripped:
            # VERDICT template headings are intentionally body-less output templates
            if _VERDICT_HEADING.match(heading.strip()):
                continue
            issues.append(ReferenceIssue("empty-section", rel, f"Section '{heading.strip()}' has no body text"))

    if "```" not in content:
        issues.append(ReferenceIssue("no-code-examples", rel, "No code blocks found (consider adding examples)"))

    for match in IMPACT_PATTERN.finditer(content):
        level = match.group(1).rstrip(".,;")
        if level not in VALID_IMPACT_LEVELS:
            issues.append(
                ReferenceIssue(
                    "invalid-impact",
                    rel,
                    f"Impact level '{level}' not in {sorted(VALID_IMPACT_LEVELS)}",
                )
            )

    return issues


def validate_agent(agent_file: Path, check_structure: bool = True) -> AgentResult:
    """Validate all declared references for a single agent."""
    result = AgentResult(name=agent_file.stem)
    declared_paths = find_declared_references(agent_file)
    result.declared = declared_paths

    for path_str in declared_paths:
        ref_path = Path(path_str)
        if not ref_path.exists():
            result.missing.append(path_str)
        elif check_structure:
            result.issues.extend(validate_reference_file(ref_path))

    return result


# Generic signals that cannot disambiguate which reference to load.
PLACEHOLDER_SIGNALS = (
    "tasks related to this reference",
    "implementation patterns",
    "workflow steps",
    "example-driven tasks",
)

_PLACEHOLDER_SCAN_PATTERNS = ["agents/*.md", "skills/**/SKILL.md"]


def find_placeholder_signals() -> list[tuple[str, int, str]]:
    """Return (relative path, line number, signal) for loading-table rows with placeholder signals."""
    found: list[tuple[str, int, str]] = []
    for pattern in _PLACEHOLDER_SCAN_PATTERNS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if not path.is_file():
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for lineno, line in enumerate(lines, start=1):
                cells = [c.strip() for c in line.split("|")]
                if len(cells) < 3 or not line.lstrip().startswith("|"):
                    continue
                signal = cells[1].lower()
                if signal in PLACEHOLDER_SIGNALS:
                    found.append((str(path.relative_to(REPO_ROOT)), lineno, cells[1]))
    return found


def run_check_placeholders(json_output: bool) -> int:
    """Scan loading tables for placeholder signals; return the exit code."""
    hits = find_placeholder_signals()
    if json_output:
        out = {
            "total": len(hits),
            "placeholder_signals": [{"file": rel, "line": lineno, "signal": signal} for rel, lineno, signal in hits],
            "exit_code": 1 if hits else 0,
        }
        print(json.dumps(out, indent=2))
    else:
        for rel, lineno, signal in hits:
            print(f"  PLACEHOLDER_SIGNAL: {rel}:{lineno} — {signal!r}")
        print(f"\n{len(hits)} placeholder signal(s) found" if hits else "PLACEHOLDERS: all loading-table signals OK")
    return 1 if hits else 0


# ---------------------------------------------------------------------------
# Reference size and discoverability (--check-size)
# ---------------------------------------------------------------------------

SKILLS_DIR = REPO_ROOT / "skills"
REFERENCE_LINE_LIMIT = 500

# Agent reference files over the limit, keyed agent/references/file.md.
_KNOWN_OVERSIZED_AGENT_REFS: set[str] = {
    "typescript-debugging-engineer/references/debugging-workflows.md",
}

# Skill reference files over the limit, keyed relative to skills/, with the
# baseline date. This is the dated debt register for gradual decomposition.
# The check rejects both unregistered oversized files and stale entries, so a
# new violation cannot hide here: decompose it instead.
_KNOWN_OVERSIZED_SKILL_REFS: dict[str, str] = {
    "frontend/frontend/references/distinctive-frontend-design-refs/animation-patterns.md": "2026-09-18",
    "frontend/frontend/references/distinctive-frontend-design-refs/shader-integration-react.md": "2026-09-18",
    "frontend/frontend/references/threejs-builder-refs/react-three-fiber.md": "2026-09-18",
    "frontend/frontend/references/threejs-builder-refs/visual-polish.md": "2026-09-18",
    "frontend/frontend/references/threejs-builder-refs/webgpu.md": "2026-09-18",
    "frontend/webgl-card-effects/references/shader-integration-react.md": "2026-09-18",
    "meta/toolkit/references/skill-composer/examples.md": "2026-09-18",
    "meta/toolkit/references/skill-creator/agent-template.md": "2026-09-18",
    "meta/toolkit/references/skill-creator.md": "2026-09-18",
    "process/pr-workflow/references/commit-staging-rules.md": "2026-07-09",
    "process/pr-workflow/references/miner.md": "2026-07-09",
    "process/pr-workflow/references/pipeline.md": "2026-07-09",
    "process/process/references/cbw-implementation-patterns.md": "2026-09-18",
    "process/testing/references/patterns-preferred-pattern-catalog.md": "2026-09-18",
    "process/testing/references/tdd-examples.md": "2026-09-18",
    "process/testing/references/verify-verification-examples.md": "2026-09-18",
    "process/workflow/references/comprehensive-review.md": "2026-07-09",
    "process/workflow/references/domain-research.md": "2026-07-09",
    "process/workflow/references/pipeline-scaffolder/references/pipeline-spec-format.md": "2026-07-09",
    "process/workflow/references/toolkit-improvement.md": "2026-07-09",
    "process/workflow/references/workflow-orchestrator/references/task-patterns.md": "2026-07-09",
    "programming/programming/references/go/sapcc-conventions/api-design-detailed.md": "2026-09-18",
    "programming/programming/references/go/sapcc-conventions/architecture-patterns.md": "2026-09-18",
    "programming/programming/references/go/sapcc-conventions/build-ci-detailed.md": "2026-09-18",
    "programming/programming/references/go/sapcc-conventions/error-handling-detailed.md": "2026-09-18",
    "programming/programming/references/go/sapcc-conventions/sapcc-code-patterns.md": "2026-09-18",
    "programming/programming/references/go/sapcc-conventions.md": "2026-09-18",
}


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def collect_agent_reference_files(agents_dir: Path) -> list[Path]:
    """Every .md directly under agents/<name>/references/."""
    files: list[Path] = []
    if not agents_dir.is_dir():
        return files
    for agent_dir in sorted(agents_dir.iterdir()):
        refs = agent_dir / "references"
        if refs.is_dir():
            files.extend(sorted(refs.glob("*.md")))
    return files


def collect_skill_reference_files(skills_dir: Path) -> list[Path]:
    """Every .md at any depth under a skill's references/ dir (skills nest by category)."""
    files: list[Path] = []
    if not skills_dir.is_dir():
        return files
    for skill_file in sorted(skills_dir.rglob("SKILL.md")):
        refs = skill_file.parent / "references"
        if refs.is_dir():
            files.extend(sorted(refs.rglob("*.md")))
    return files


def collect_skills_with_references(skills_dir: Path) -> list[Path]:
    """Skill dirs that declare a references/ dir."""
    if not skills_dir.is_dir():
        return []
    return sorted(s.parent for s in skills_dir.rglob("SKILL.md") if (s.parent / "references").is_dir())


def check_reference_sizes(
    agents_dir: Path = AGENTS_DIR,
    skills_dir: Path = SKILLS_DIR,
    agent_register: set[str] | None = None,
    skill_register: dict[str, str] | None = None,
) -> list[str]:
    """Return failures for the reference size, debt-register, and discoverability rules.

    - A reference file over REFERENCE_LINE_LIMIT lines must be in its register.
    - Each register must name exactly the current violations (no stale entries).
    - Skill register dates must be ISO-8601.
    - A skill references/ dir must hold at least one .md file.
    - An agent reference file must resolve inside its own agent dir.
    """
    from datetime import date

    agent_register = _KNOWN_OVERSIZED_AGENT_REFS if agent_register is None else agent_register
    skill_register = _KNOWN_OVERSIZED_SKILL_REFS if skill_register is None else skill_register
    failures: list[str] = []

    agent_files = collect_agent_reference_files(agents_dir)
    agent_over = {
        str(f.relative_to(agents_dir)): _line_count(f) for f in agent_files if _line_count(f) > REFERENCE_LINE_LIMIT
    }
    for ref_id, lines in sorted(agent_over.items()):
        if ref_id not in agent_register:
            failures.append(f"agents/{ref_id}: {lines} lines exceeds {REFERENCE_LINE_LIMIT}; split it")
    for ref_id in sorted(agent_register - set(agent_over)):
        failures.append(f"agents/{ref_id}: stale size-debt entry (now within limit or gone); remove it")
    for f in agent_files:
        agent_dir = f.parent.parent
        if not f.resolve().is_relative_to(agent_dir.resolve()):
            failures.append(f"{f}: resolves outside its agent dir to {f.resolve()}")

    skill_over = {
        str(f.relative_to(skills_dir)): _line_count(f)
        for f in collect_skill_reference_files(skills_dir)
        if _line_count(f) > REFERENCE_LINE_LIMIT
    }
    for ref_id, lines in sorted(skill_over.items()):
        if ref_id not in skill_register:
            failures.append(f"skills/{ref_id}: {lines} lines exceeds {REFERENCE_LINE_LIMIT}; split it")
    for ref_id in sorted(set(skill_register) - set(skill_over)):
        failures.append(f"skills/{ref_id}: stale size-debt entry (now within limit or gone); remove it")
    for ref_id, baseline in sorted(skill_register.items()):
        try:
            date.fromisoformat(baseline)
        except ValueError:
            failures.append(f"skills/{ref_id}: invalid baseline date {baseline!r}")

    for skill_dir in collect_skills_with_references(skills_dir):
        if not any((skill_dir / "references").rglob("*.md")):
            failures.append(f"skills/{skill_dir.relative_to(skills_dir)}/references/ has no .md files")
    return failures


def run_check_size(json_output: bool) -> int:
    """Run --check-size and return the exit code."""
    failures = check_reference_sizes()
    if json_output:
        print(json.dumps({"failures": failures, "exit_code": 1 if failures else 0}, indent=2))
    else:
        for line in failures:
            print(f"  SIZE: {line}")
        print(f"\n{len(failures)} reference size issue(s)" if failures else "SIZE: all reference files OK")
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# Skill-tool call contract (--check-skill-calls)
# ---------------------------------------------------------------------------

_SKILL_CALL_RUNTIME_ROOTS = ("agents", "commands", "docs", "hooks", "skills")
_SKILL_CALL_SUFFIXES = {".js", ".md", ".mjs", ".py"}
CONCRETE_SKILL_CALL = re.compile(r"(?i)call the Skill tool with `([a-z0-9][a-z0-9-]*)`")
_COMMAND_LEGACY_HANDOFF = re.compile(
    r"(?i)(?:read|load) and follow (?:the )?(?:full )?skill(?: file)? at|invoke the [a-z0-9-]+ skill"
)


def _skill_call_runtime_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for name in _SKILL_CALL_RUNTIME_ROOTS:
        base = root / name
        if base.is_dir():
            files.extend(
                p
                for p in base.rglob("*")
                if p.is_file() and p.suffix in _SKILL_CALL_SUFFIXES and "tests" not in p.parts
            )
    return sorted(files)


def check_skill_calls(root: Path = REPO_ROOT) -> list[str]:
    """Return failures for the Skill-tool call contract.

    - A command that says "Call the Skill tool with `x`" must grant the Skill tool.
    - Commands hand off with that exact call, not "read and follow the skill at" wording.
    - A pipeline that is not also a skill is reached through the workflow skill,
      never by a direct "invoke/route to/hand off to <pipeline>" instruction.
    """
    repo = str(REPO_ROOT.resolve())
    if repo not in sys.path:
        sys.path.insert(0, repo)
    from scripts.lib.frontmatter import parse_frontmatter

    failures: list[str] = []
    for path in sorted((root / "commands").glob("*.md")):
        source = path.read_text(encoding="utf-8")
        rel = path.relative_to(root)
        if CONCRETE_SKILL_CALL.search(source):
            frontmatter, _ = parse_frontmatter(source)
            tools = frontmatter.get("allowed-tools", []) if frontmatter else []
            if "Skill" not in tools:
                failures.append(f"{rel}: calls the Skill tool but allowed-tools lacks Skill")
        if _COMMAND_LEGACY_HANDOFF.search(source):
            failures.append(f"{rel}: legacy skill handoff wording; use 'Call the Skill tool with `name`.'")

    skills_index = root / "skills" / "INDEX.json"
    pipeline_index = root / "skills" / "process" / "workflow" / "references" / "pipeline-index.json"
    if not skills_index.is_file() or not pipeline_index.is_file():
        failures.append("skills/INDEX.json or pipeline-index.json missing; run scripts/generate-skill-index.py")
        return failures
    skills = set(json.loads(skills_index.read_text(encoding="utf-8"))["skills"])
    pipelines = set(json.loads(pipeline_index.read_text(encoding="utf-8"))["pipelines"])
    patterns = [
        (
            name,
            re.compile(
                rf"(?i)\b(?:hand off to|invoke(?::| the)?|route to|follow(?: the)?)\s+"
                rf"(?:/)?`?{re.escape(name)}`?(?![a-z0-9-])"
            ),
        )
        for name in sorted(pipelines - skills)
    ]
    for path in _skill_call_runtime_files(root):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for name, rx in patterns:
                if rx.search(line):
                    failures.append(f"{path.relative_to(root)}:{lineno}: direct handoff to pipeline {name!r}")
    return failures


def run_check_skill_calls(json_output: bool) -> int:
    """Run --check-skill-calls and return the exit code."""
    failures = check_skill_calls()
    if json_output:
        print(json.dumps({"failures": failures, "exit_code": 1 if failures else 0}, indent=2))
    else:
        for line in failures:
            print(f"  SKILL-CALL: {line}")
        print(f"\n{len(failures)} skill-call issue(s)" if failures else "SKILL-CALLS: contract OK")
    return 1 if failures else 0


def find_all_reference_files() -> list[Path]:
    """Find every .md file inside any references/ subdirectory under agents/."""
    return list(AGENTS_DIR.rglob("references/*.md"))


def find_orphan_references(all_results: list[AgentResult]) -> list[Path]:
    """Return reference files that exist on disk but aren't declared by any agent."""
    declared_set: set[str] = set()
    for result in all_results:
        for path_str in result.declared:
            declared_set.add(str(Path(path_str).resolve()))

    orphans: list[Path] = []
    for ref_file in find_all_reference_files():
        if str(ref_file.resolve()) not in declared_set:
            orphans.append(ref_file)
    return orphans


def print_text_results(
    results: list[AgentResult],
    orphans: list[Path],
    placeholders: list[tuple[str, int, str]] | None = None,
) -> None:
    """Print human-readable validation output."""
    for result in results:
        total = len(result.declared)
        missing_count = len(result.missing)
        present_count = total - missing_count
        issue_count = len(result.issues)

        if result.ok:
            print(f"  {result.name}: {present_count}/{total} references present, 0 issues")
        else:
            print(f"  {result.name}: {present_count}/{total} references present, {issue_count} issues")
            for path_str in result.missing:
                rel = Path(path_str).relative_to(AGENTS_DIR) if AGENTS_DIR in Path(path_str).parents else path_str
                print(f"    MISSING: {rel}")
            for issue in result.issues:
                label = issue.kind.upper().replace("-", "_")
                print(f"    {label}: {issue.path} — {issue.detail}")

    if orphans:
        print("\nOrphan reference files (not declared by any agent):")
        for orphan in orphans:
            print(f"  ORPHAN: {orphan.relative_to(AGENTS_DIR)}")

    if placeholders:
        print("\nPlaceholder loading-table signals (cannot disambiguate which reference to load):")
        for rel, lineno, signal in placeholders:
            print(f"  PLACEHOLDER_SIGNAL: {rel}:{lineno} — {signal!r}")

    ok_count = sum(1 for r in results if r.ok)
    issue_count = sum(1 for r in results if not r.ok)
    total_missing = sum(len(r.missing) for r in results)
    total_issues = sum(len(r.issues) for r in results)

    parts = [f"{ok_count} agents OK"]
    if issue_count:
        parts.append(f"{issue_count} agent(s) with issues")
    if total_missing:
        parts.append(f"{total_missing} file(s) missing")
    if total_issues:
        parts.append(f"{total_issues} structure issue(s)")
    if orphans:
        parts.append(f"{len(orphans)} orphan(s)")
    if placeholders:
        parts.append(f"{len(placeholders)} placeholder signal(s)")

    print(f"\nSummary: {', '.join(parts)}")


def build_json_results(
    results: list[AgentResult],
    orphans: list[Path],
    placeholders: list[tuple[str, int, str]] | None = None,
) -> dict:
    """Build JSON-serializable results dict."""
    agents_out = []
    for result in results:
        agents_out.append(
            {
                "agent": result.name,
                "ok": result.ok,
                "declared": len(result.declared),
                "present": len(result.declared) - len(result.missing),
                "missing": [str(p) for p in result.missing],
                "issues": [{"kind": i.kind, "path": i.path, "detail": i.detail} for i in result.issues],
            }
        )

    ok_count = sum(1 for r in results if r.ok)
    issue_count = sum(1 for r in results if not r.ok)
    missing_count = sum(len(r.missing) for r in results)
    structure_issues = sum(len(r.issues) for r in results)
    has_failures = issue_count > 0 or missing_count > 0

    placeholders = placeholders or []
    return {
        "agents": agents_out,
        "orphans": [str(o.relative_to(AGENTS_DIR)) for o in orphans],
        "placeholder_signals": [
            {"file": rel, "line": lineno, "signal": signal} for rel, lineno, signal in placeholders
        ],
        "summary": {
            "ok": ok_count,
            "issues": issue_count,
            "missing_files": missing_count,
            "structure_issues": structure_issues,
            "orphans": len(orphans),
            "placeholder_signals": len(placeholders),
        },
        "exit_code": 1 if has_failures or orphans or placeholders else 0,
    }


def main() -> None:
    """Entry point for reference validation CLI."""
    parser = argparse.ArgumentParser(description="Validate agent reference files")
    parser.add_argument("--agent", help="Validate references for specific agent")
    parser.add_argument("--all", action="store_true", help="Validate all agents")
    parser.add_argument("--check-declared", action="store_true", help="Only check declared refs exist")
    parser.add_argument("--check-do-framing", action="store_true", help="Check all files for unpaired anti-patterns")
    parser.add_argument(
        "--check-placeholders",
        action="store_true",
        help="Check loading tables for placeholder signals only",
    )
    parser.add_argument(
        "--check-size",
        action="store_true",
        help="Check reference file sizes against the debt registers and empty references/ dirs",
    )
    parser.add_argument(
        "--check-skill-calls",
        action="store_true",
        help="Check Skill-tool call wording in commands and pipeline handoffs",
    )
    parser.add_argument(
        "--allowlist",
        metavar="PATH",
        help="Backlog JSON to skip known violations (default: artifacts/joy-check-sweep-backlog.json)",
    )
    parser.add_argument("--json", dest="json_output", action="store_true", help="JSON output for CI")
    parser.add_argument(
        "--failures-only",
        action="store_true",
        help="Only output agents with issues (compact mode for LLM context)",
    )
    args = parser.parse_args()

    if args.check_do_framing:
        allowlist = Path(args.allowlist) if args.allowlist else None
        sys.exit(run_check_do_framing(json_output=args.json_output, allowlist_path=allowlist))

    if args.check_placeholders:
        sys.exit(run_check_placeholders(json_output=args.json_output))

    if args.check_size:
        sys.exit(run_check_size(json_output=args.json_output))

    if args.check_skill_calls:
        sys.exit(run_check_skill_calls(json_output=args.json_output))

    if not args.agent and not args.all:
        parser.error(
            "Specify --agent <name>, --all, --check-do-framing, --check-placeholders, --check-size, or --check-skill-calls"
        )

    check_structure = not args.check_declared

    agent_files: list[Path] = []
    if args.agent:
        candidate = AGENTS_DIR / f"{args.agent}.md"
        if not candidate.exists():
            print(f"ERROR: Agent file not found: {candidate}", file=sys.stderr)
            sys.exit(1)
        agent_files = [candidate]
    else:
        agent_files = sorted(AGENTS_DIR.glob("*.md"))
        agent_files = [f for f in agent_files if f.name not in {"README.md"}]

    results: list[AgentResult] = []
    for agent_file in agent_files:
        if not agent_file.is_file():
            continue
        result = validate_agent(agent_file, check_structure=check_structure)
        if result.declared or not check_structure:
            results.append(result)

    all_results_for_orphans = results if args.all else []
    orphans: list[Path] = []
    placeholders: list[tuple[str, int, str]] = []
    if args.all and check_structure:
        all_agent_results = [validate_agent(f, check_structure=False) for f in sorted(AGENTS_DIR.glob("*.md"))]
        orphans = find_orphan_references(all_agent_results)
        placeholders = find_placeholder_signals()

    # Filter for --failures-only: only agents with issues
    total_agents = len(results)
    passing_agents = sum(1 for r in results if r.ok)
    display_results = [r for r in results if not r.ok] if args.failures_only else results
    display_orphans = orphans  # always show orphans (they are issues)

    if args.json_output:
        output = build_json_results(display_results, display_orphans, placeholders)
        if args.failures_only:
            output["summary"]["message"] = f"{passing_agents} of {total_agents} agents passed validation"
        print(json.dumps(output, indent=2))
        sys.exit(1 if any(not r.ok for r in results) or bool(orphans) or bool(placeholders) else 0)
    else:
        print_text_results(display_results, display_orphans, placeholders)
        if args.failures_only:
            print(f"\n{passing_agents} of {total_agents} agents passed validation")
        has_failures = any(not r.ok for r in results) or bool(orphans) or bool(placeholders)
        sys.exit(1 if has_failures else 0)


if __name__ == "__main__":
    main()
