#!/usr/bin/env python3
"""Map skills changed in a git range to their eval directories under evals/.

ADR: skill-eval-pr-ablation (Decision 1). A mapper, not a gate: it always
exits 0. Uncovered skills are data, not errors.

Usage:
    python3 scripts/detect-skill-changes.py --base <REF> --head <REF> [--format human|json]

Changed skills: `git diff --name-only <base> <head>`, keep paths matching the
SKILL.md regex (identical to hooks/posttooluse-sync-skill-index.py), reduce each
to its skill `name` from frontmatter.

Mapping (first hit wins):
    1. exact dir:    evals/<name>/        exists
    2. -eval suffix: evals/<name>-eval/   exists
    3. README:       whole-word, case-insensitive mention of <name> in any
                     evals/*/README.md
    4. no match -> uncovered

JSON output is a single object: base, head (full hashes), changed_skills
(sorted, deduped), mapped (list of {skill, eval_dir}, sorted by skill, no
trailing slash), uncovered (sorted). Invariant:
    set(changed_skills) == {m["skill"] for m in mapped} | set(uncovered)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Identical to hooks/posttooluse-sync-skill-index.py:42 (keep in sync).
SKILL_FILE_RE = re.compile(r"skills/(?:[^/]+/)+SKILL\.md$")


def run_git(repo: Path, *args: str) -> str:
    """Run a git command in `repo`, return stdout (stripped). Raise on failure."""
    res = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def resolve_sha(repo: Path, ref: str) -> str:
    """Resolve a ref to its full commit hash."""
    return run_git(repo, "rev-parse", ref)


def changed_skill_md_paths(repo: Path, base: str, head: str) -> list[str]:
    """Repo-relative SKILL.md paths changed in base..head (POSIX separators)."""
    out = run_git(repo, "diff", "--name-only", base, head)
    paths = [p.strip() for p in out.splitlines() if p.strip()]
    return [p for p in paths if SKILL_FILE_RE.search(p)]


def skill_name_from_md(skill_md: Path) -> str | None:
    """Read the `name:` frontmatter field from a SKILL.md file.

    Falls back to the parent directory name when frontmatter has no name.
    Returns None if the file is unreadable.
    """
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("name:"):
            return stripped[len("name:") :].strip().strip('"').strip("'")
        # Stop at the closing frontmatter delimiter (the second `---`).
        if idx > 0 and stripped == "---":
            break
    # No name field: use the directory name (skills/<cat>/<name>/SKILL.md).
    return skill_md.parent.name


def skill_names_from_paths(paths: list[str], repo: Path) -> list[str]:
    """Reduce changed SKILL.md paths to sorted, deduped skill names."""
    names: set[str] = set()
    for p in paths:
        if not SKILL_FILE_RE.search(p):
            continue
        name = skill_name_from_md(repo / p)
        if name:
            names.add(name)
    return sorted(names)


def map_skill_to_eval(skill: str, repo: Path) -> str | None:
    """Map a skill name to an eval dir (repo-relative, no trailing slash).

    Resolution order, first hit wins: exact dir, -eval suffix, README mention.
    Returns None when nothing matches (the skill is uncovered).
    """
    evals_root = repo / "evals"
    if not evals_root.is_dir():
        return None

    # 1. exact dir: evals/<skill>/
    if (evals_root / skill).is_dir():
        return f"evals/{skill}"

    # 2. -eval suffix: evals/<skill>-eval/
    if (evals_root / f"{skill}-eval").is_dir():
        return f"evals/{skill}-eval"

    # 3. README whole-word mention (case-insensitive). Sort dirs for a stable
    #    first hit.
    word_re = re.compile(rf"(?<![\w-]){re.escape(skill)}(?![\w-])", re.IGNORECASE)
    for sub in sorted(p for p in evals_root.iterdir() if p.is_dir()):
        readme = sub / "README.md"
        if not readme.is_file():
            continue
        try:
            content = readme.read_text(encoding="utf-8")
        except OSError:
            continue
        if word_re.search(content):
            return f"evals/{sub.name}"

    return None


def build_report(repo: Path, base: str, head: str) -> dict:
    """Build the mapping report object for the given range."""
    base_sha = resolve_sha(repo, base)
    head_sha = resolve_sha(repo, head)
    paths = changed_skill_md_paths(repo, base_sha, head_sha)
    changed = skill_names_from_paths(paths, repo)

    mapped: list[dict[str, str]] = []
    uncovered: list[str] = []
    for skill in changed:
        eval_dir = map_skill_to_eval(skill, repo)
        if eval_dir:
            mapped.append({"skill": skill, "eval_dir": eval_dir})
        else:
            uncovered.append(skill)

    mapped.sort(key=lambda m: m["skill"])
    uncovered.sort()
    return {
        "base": base_sha,
        "head": head_sha,
        "changed_skills": changed,
        "mapped": mapped,
        "uncovered": uncovered,
    }


def render_human(report: dict) -> str:
    """Render the report as a human-readable coverage map."""
    lines: list[str] = []
    lines.append(f"Skill-eval coverage  base={report['base'][:12]}  head={report['head'][:12]}")
    if not report["changed_skills"]:
        lines.append("  no changed skills in range")
        return "\n".join(lines)
    for m in report["mapped"]:
        lines.append(
            f"  {m['skill']} -> eval {m['eval_dir']}. "
            f"Run locally: make skill-eval-ablation BASE={report['base'][:12]} "
            f"HEAD={report['head'][:12]} SKILL={m['skill']}"
        )
    if report["uncovered"]:
        joined = ", ".join(report["uncovered"])
        lines.append(f"  no eval coverage for changed skill(s): {joined}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Map changed skills to eval dirs (report-only, exit 0 always).")
    parser.add_argument("--base", required=True, help="Base ref")
    parser.add_argument("--head", required=True, help="Head ref")
    parser.add_argument("--format", choices=["human", "json"], default="human")
    parser.add_argument("--repo", default=".", help="Repo root (default: cwd)")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    try:
        report = build_report(repo, args.base, args.head)
    except subprocess.CalledProcessError as e:
        # Never fail the build: report the git error to stderr, emit an empty
        # report, exit 0.
        print(f"[detect-skill-changes] git error: {e.stderr.strip()}", file=sys.stderr)
        report = {"base": args.base, "head": args.head, "changed_skills": [], "mapped": [], "uncovered": []}

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(render_human(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
