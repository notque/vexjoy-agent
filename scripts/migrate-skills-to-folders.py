#!/usr/bin/env python3
"""Migrate flat skills/ directory to category-folder structure.

Moves skills/foo/ → skills/category/foo/ based on a predefined mapping.
Supports --dry-run.

Usage:
    python3 scripts/migrate-skills-to-folders.py --dry-run   # preview
    python3 scripts/migrate-skills-to-folders.py             # execute
"""

import argparse
import shutil
import sys
from pathlib import Path

# Complete mapping: skill_name → category_folder
SKILL_MAPPING: dict[str, str] = {
    # analysis/ — assessment, data
    "assessment": "analysis",
    "data": "analysis",
    # business/
    "business-ops": "business",
    # code-quality/
    "code-quality": "code-quality",
    "comment-quality": "code-quality",
    "condense": "code-quality",
    "joy-check": "code-quality",
    # content/ — publishing, social, media, voice, comms
    "content": "content",
    "content-engine": "content",
    "headlines": "content",
    "series-planner": "content",
    "topic-brainstormer": "content",
    "image-to-video": "content",
    "video-editing": "content",
    "image-gen": "content",
    "writing": "content",
    # Private skills (voice-* persona clones and other private components)
    # live in ~/private-skills, not in this repo. Not mapped here.
    # domain/
    "domain": "domain",
    # engineering/
    "cli-design": "engineering",
    # frontend/
    "frontend": "frontend",
    "frontend-slides": "frontend",
    "webgl-card-effects": "frontend",
    # game/
    "game-asset-generator": "game",
    "game-dev": "game",
    "motion-pipeline": "game",
    # infrastructure/ — ops, k8s, deploy, browser
    "browser-jev-automation": "infrastructure",
    "kubernetes": "infrastructure",
    "headless-cron-creator": "infrastructure",
    "endpoint-validator": "infrastructure",
    "cve-source-check": "infrastructure",
    "deploy": "infrastructure",
    # integrations/
    "github": "integrations",
    # meta/ — toolkit self-management
    "building-with-jev": "meta",
    "codex": "meta",
    "d": "meta",
    "do": "meta",
    "auto-dream": "meta",
    "toolkit": "meta",
    "workflow-help": "meta",
    "docs-sync-checker": "meta",
    # process/ — methodologies, git, debugging, testing, workflow
    "debugging": "process",
    "quick": "process",
    "with-anti-rationalization": "process",
    "plant-seed": "process",
    "pr-workflow": "process",
    "worktree-agent": "process",
    "process": "process",
    "testing": "process",
    "workflow": "process",
    # programming/
    "programming": "programming",
    # research/ — investigation, analysis, decisions
    "research": "research",
    "news-collection": "research",
    "markdown-converter": "research",
    "video-transcript": "research",
    "architecture-deepening": "research",
    "codebase-analyzer": "research",
    "roast": "research",
    # review/
    "integration-checker": "review",
    "review": "review",
    "security": "review",
}

# Directories to keep at root level (no SKILL.md or special structure)
KEEP_AT_ROOT = {"shared-patterns", "kb", "voice-shared"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate skills to category folders.")
    parser.add_argument("--dry-run", action="store_true", help="Preview moves without executing")
    parser.add_argument("--skills-dir", default="skills", help="Path to skills directory")
    args = parser.parse_args()

    skills_dir = Path(args.skills_dir)
    if not skills_dir.is_dir():
        print(f"Error: {skills_dir} is not a directory", file=sys.stderr)
        return 1

    # Validate mapping covers all existing skills
    existing = set()
    for child in skills_dir.iterdir():
        if child.is_dir() and child.name not in KEEP_AT_ROOT:
            if (child / "SKILL.md").exists() or child.name in SKILL_MAPPING:
                existing.add(child.name)

    unmapped = existing - set(SKILL_MAPPING.keys()) - KEEP_AT_ROOT
    if unmapped:
        print(f"Warning: Unmapped skills (will stay at root): {sorted(unmapped)}", file=sys.stderr)

    missing = set(SKILL_MAPPING.keys()) - existing
    if missing:
        print(f"Info: Skills in mapping but not on disk (skipping): {sorted(missing)}", file=sys.stderr)

    # Group by category for summary
    categories: dict[str, list[str]] = {}
    for skill, cat in SKILL_MAPPING.items():
        categories.setdefault(cat, []).append(skill)

    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Migration Plan:")
    print(f"{'=' * 60}")
    for cat in sorted(categories):
        skills_in_cat = sorted(categories[cat])
        on_disk = [s for s in skills_in_cat if s in existing]
        print(f"\n  {cat}/ ({len(on_disk)} skills)")
        for s in on_disk:
            print(f"    {s}/")

    moved = 0
    errors = 0

    for skill_name, category in sorted(SKILL_MAPPING.items()):
        src = skills_dir / skill_name
        if not src.exists():
            continue

        cat_dir = skills_dir / category
        dst = cat_dir / skill_name

        if dst.exists():
            print(f"  [skip] {skill_name} → {category}/ (already exists)")
            continue

        if args.dry_run:
            print(f"  [move] {skill_name}/ → {category}/{skill_name}/")
            moved += 1
        else:
            try:
                cat_dir.mkdir(exist_ok=True)
                shutil.move(str(src), str(dst))
                print(f"  [moved] {skill_name}/ → {category}/{skill_name}/")
                moved += 1
            except OSError as e:
                print(f"  [ERROR] {skill_name}: {e}", file=sys.stderr)
                errors += 1

    print(f"\n{'=' * 60}")
    print(f"{'Would move' if args.dry_run else 'Moved'}: {moved} skills")
    if errors:
        print(f"Errors: {errors}")
    if unmapped:
        print(f"Unmapped (stayed at root): {sorted(unmapped)}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
