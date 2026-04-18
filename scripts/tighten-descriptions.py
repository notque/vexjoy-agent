#!/usr/bin/env python3
"""Tighten skill description frontmatter to minimum routing words.

Reads each skills/*/SKILL.md, replaces the description field with a
compact version that preserves routing signal and drops filler.

Usage:
    python3 scripts/tighten-descriptions.py --dry-run   # show changes
    python3 scripts/tighten-descriptions.py              # apply changes
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

# old description (exact match) -> new description
REWRITES: dict[str, str] = {
    # --- Meta / Routing ---
    "Classify user requests and route to the correct agent + skill.": "Route requests to agents with skills.",
    "Structured multi-phase workflows: review, debug, refactor, deploy, create, research, and more.": "Multi-phase workflows: review, debug, refactor, deploy, create, research.",
    "Interactive guide to workflow system: agents, skills, routing, execution patterns.": "Guide to agents, skills, routing, and execution.",
    "Maintain /do routing tables when skills or agents change.": "Update routing tables when skills or agents change.",
    "Tracked lightweight execution with composable rigor flags: --trivial, --discuss, --research, --full.": "Lightweight execution with rigor flags: --trivial, --discuss, --research, --full.",
    # --- Planning / Process ---
    "Planning lifecycle umbrella: spec, pre-plan ambiguity resolution, file-backed planning, plan validation, plan-lifecycle management, and session pause/resume.": "Spec, plan, validate, and manage task plans.",
    "Defense-in-depth verification before declaring any task complete.": "Verify task completion before reporting done.",
    "Anti-rationalization enforcement for maximum-rigor task execution.": "Maximum-rigor task execution with anti-rationalization.",
    "Collaborative coding with enforced micro-steps and user-paced control.": "Collaborative coding with micro-steps and user pacing.",
    "Capture forward-looking idea as a seed for future feature design.": "Capture ideas as seeds for future features.",
    "Weighted decision scoring for architectural choices.": "Score architectural choices with weighted criteria.",
    "Fresh-subagent-per-task execution with two-stage review gates.": "One subagent per task with review gates.",
    "Read-only exploration, inspection, and reporting without modifications.": "Read-only exploration and reporting.",
    "Manually teach error pattern and solution to learning database.": "Teach error patterns to the learning database.",
    "Question-only debugging: guide users to find root causes themselves.": "Guide users to find root causes via questions only.",
    # --- Code Review ---
    "4-phase code review: UNDERSTAND, VERIFY, ASSESS risks, DOCUMENT findings.": "Code review: understand, verify, assess risks, document.",
    "Parallel 3-reviewer code review: Security, Business-Logic, Architecture.": "3-reviewer parallel code review: security, logic, architecture.",
    "Comprehensive 3-wave review of all repo source files, producing a prioritized issue backlog.": "Full-repo review producing prioritized issue backlog.",
    "Constructive critique via 5 HackerNews personas with claim validation.": "Critique via 5 HackerNews personas with claim validation.",
    "Parallel critique of proposals via 5 philosophical personas with consensus synthesis.": "5-persona parallel critique with consensus synthesis.",
    # --- Testing ---
    "RED-GREEN-REFACTOR cycle with strict phase gates for TDD.": "TDD: red-green-refactor with phase gates.",
    "Playwright-based end-to-end testing workflow.": "Playwright end-to-end testing.",
    "Run Vitest tests and parse results into actionable output.": "Run Vitest tests and parse results.",
    "Test agents via subagents: known inputs, captured outputs, verification.": "Test agents with known inputs and verified outputs.",
    "Identify and fix testing mistakes: flaky, brittle, over-mocked tests.": "Fix flaky, brittle, and over-mocked tests.",
    # --- Code Quality ---
    "Detect stale TODOs, unused imports, and dead code.": "Detect stale TODOs, unused imports, dead code.",
    "Run Python (ruff) and JavaScript (Biome) linting.": "Run ruff (Python) and Biome (JS) linting.",
    "Review and fix temporal references in code comments.": "Fix temporal references in code comments.",
    "Python quality checks: ruff, pytest, mypy, bandit in deterministic order.": "Python quality: ruff, pytest, mypy, bandit.",
    "Multi-language code quality gate with auto-detection and linters.": "Multi-language quality gate with auto-detected linters.",
    "TypeScript type checking via tsc --noEmit with actionable error output.": "TypeScript type checking via tsc --noEmit.",
    "Detect documentation drift against filesystem state.": "Detect documentation drift against filesystem.",
    # --- Research ---
    "Formal 5-phase research pipeline with artifact saving and source quality gates: SCOPE, GATHER, SYNTHESIZE, VALIDATE, DELIVER.": "Research pipeline: scope, gather, synthesize, validate, deliver.",
    "Read public Bluesky feeds via AT Protocol API.": "Read Bluesky feeds via AT Protocol.",
    "Statistical rule discovery from Go codebase patterns.": "Discover Go codebase patterns and rules.",
    "Systematic codebase exploration and architecture mapping.": "Explore codebase and map architecture.",
    "Analyze external repositories for adoptable ideas and patterns.": "Analyze external repos for adoptable patterns.",
    # --- Content ---
    "Unified voice content generation pipeline with mandatory validation and joy-check.": "Voice content generation with validation and joy-check.",
    "Critique-and-rewrite loop for voice fidelity validation.": "Validate and rewrite for voice fidelity.",
    "Create voice profiles from writing samples.": "Create voice profiles from writing samples.",
    "Remove AI-sounding patterns from content.": "Remove AI-sounding patterns from content.",
    "Validate content framing on joy-grievance spectrum.": "Validate content framing on joy-grievance spectrum.",
    "Content-publishing umbrella covering the blog pipeline from blueprint to upload: post outlining, pre-publication validation, SEO optimization, bulk...": "Blog pipeline: outline, validate, SEO, upload.",
    "Generate blog topic ideas: problem mining, gap analysis, expansion.": "Generate blog topic ideas via problem mining and gap analysis.",
    "Plan multi-part content series: structure, cross-linking, cadence.": "Plan multi-part content series.",
    "Manage editorial content through 6 pipeline stages.": "Manage editorial content through pipeline stages.",
    "Repurpose source assets into platform-native social content.": "Repurpose assets into platform-native social content.",
    "Transform technical communication into structured business formats.": "Transform technical communication into business formats.",
    "Blog post SEO: keywords, titles, meta descriptions, internal linking.": "Blog SEO: keywords, titles, meta descriptions, linking.",
    # --- Voice ---
    "Apply Andy Nemmity's voice profile for content generation: precision-driven improvisation, constraint accumulation, systems framing, calibration qu...": "Andy Nemmity voice profile for content generation.",
    # --- Infrastructure ---
    "Service health monitoring: Discover, Check, Report in 3 phases.": "Service health: discover, check, report.",
    "Kubernetes debugging for pod failures and networking.": "Debug Kubernetes pod failures and networking.",
    "Kubernetes security: RBAC, PodSecurity, network policies.": "Kubernetes security: RBAC, PodSecurity, network policies.",
    "Polling, retry, and backoff patterns.": "Polling, retry, and backoff patterns.",
    "Audit cron scripts for reliability and safety.": "Audit cron scripts for reliability and safety.",
    "Generate headless Claude Code cron jobs with safety.": "Generate headless Claude Code cron jobs.",
    "Verify cross-component wiring and data flow.": "Verify cross-component wiring and data flow.",
    # --- Meta-tooling ---
    "A/B test agent variants for quality and token cost.": "A/B test agent variants for quality and cost.",
    "Evaluate agents and skills for quality and standards compliance.": "Evaluate agent and skill quality.",
    "Background memory consolidation and learning graduation \u2014 overnight knowledge lifecycle.": "Overnight memory consolidation and learning graduation.",
    "Closed-loop toolkit self-improvement: discover gaps, diagnose, propose, critique, build, test, evolve.": "Toolkit self-improvement: discover, diagnose, propose, build, test, evolve.",
    "Analyze agent/skill reference depth and generate missing domain-specific reference files.": "Generate missing reference files for agents and skills.",
    "DAG-based multi-skill orchestration with dependency resolution.": "Orchestrate multiple skills with dependency resolution.",
    "Create and iteratively improve skills through eval-driven validation.": "Create and improve skills via eval-driven validation.",
    "Evaluate skills: trigger testing, A/B benchmarks, structure validation.": "Evaluate skills: triggers, benchmarks, structure.",
    "Learning system interface: stats, search, graduate learnings.": "Learning system: stats, search, graduate.",
    # --- Language-specific ---
    "Go development patterns: testing, concurrency, errors, review, and conventions.": "Go patterns: testing, concurrency, errors, review.",
    "Kotlin structured concurrency, Flow, and Channel patterns.": "Kotlin coroutines, Flow, and Channel patterns.",
    "Kotlin testing with JUnit 5, Kotest, and coroutine dispatchers.": "Kotlin testing: JUnit 5, Kotest, coroutine dispatchers.",
    "PHP code quality: PSR standards, strict types, framework idioms.": "PHP quality: PSR standards, strict types, framework idioms.",
    "PHP testing patterns: PHPUnit, test doubles, database testing.": "PHP testing: PHPUnit, test doubles, database.",
    "Swift concurrency: async/await, Actor, Task, Sendable patterns.": "Swift concurrency: async/await, Actor, Task, Sendable.",
    "Swift testing: XCTest, Swift Testing framework, async patterns.": "Swift testing: XCTest, Swift Testing, async.",
    # --- Frontend ---
    "Context-driven aesthetic exploration with anti-cliche validation.": "Aesthetic exploration with anti-cliche validation.",
    "Browser-based HTML presentation generation.": "Generate browser-based HTML presentations.",
    "Three.js app builder: imperative, React Three Fiber, and WebGPU in 4 phases.": "Three.js apps: imperative, React Three Fiber, WebGPU.",
    "Standalone WebGL fragment shaders for card visual effects: holographic foil, shimmer, rarity glow.": "WebGL card effects: holographic foil, shimmer, rarity glow.",
    "PPTX presentation generation with visual QA: slides, pitch decks.": "Generate PPTX presentations with visual QA.",
    # --- Game ---
    "Phaser 3 2D game dev: scenes, physics, tilemaps, sprites, polish.": "Phaser 3 game dev: scenes, physics, tilemaps, sprites.",
    "CPU-only motion data processing pipeline for game animation: BVH import, contact detection, root decomposition, motion blending, FABRIK IK.": "Game animation from BVH: contact detection, root decomposition, motion blending, IK.",
    "AI game asset generation: 3D models, environments, sprites, images.": "AI game asset generation: models, environments, sprites.",
    # --- Publishing / External ---
    "Post tweets, build threads, upload media via the X API.": "Post tweets and threads via X API.",
    "Validate published WordPress posts in browser via Playwright.": "Validate published WordPress posts in browser.",
    "Reddit moderation via PRAW: fetch modqueue, classify reports, take actions.": "Reddit moderation: modqueue, classify reports, take actions.",
    "Video editing pipeline: cut footage, assemble clips via FFmpeg and Remotion.": "Video editing via FFmpeg and Remotion.",
    "FFmpeg-based video creation from image and audio.": "Create video from image and audio via FFmpeg.",
    "Image generation and post-processing via Gemini Nano Banana APIs.": "Image generation via Gemini Nano Banana.",
    "Generate images from text prompts via Google Gemini.": "Generate images from text via Gemini.",
    "Triage GitHub notifications and report actions needed.": "Triage GitHub notifications.",
    # --- Security ---
    "Security threat model: scan toolkit for attack surface, supply-chain risks.": "Scan for attack surface and supply-chain risks.",
    # --- Git ---
    "Generate and validate Git branch names.": "Generate and validate Git branch names.",
    "Mandatory rules for agents in git worktree isolation.": "Rules for agents in git worktree isolation.",
    # --- Misc ---
    "Proactive monitoring \u2014 checks GitHub, CI, and toolkit health, produces briefings.": "Monitor GitHub, CI, and toolkit health.",
    "Verify Claude Code Toolkit installation, diagnose issues, and guide first-time setup.": "Verify toolkit installation and diagnose issues.",
    "Post-mortem diagnostic analysis of failed workflows.": "Diagnose failed workflows post-mortem.",
    "Generate project-specific CLAUDE.md from repo analysis.": "Generate CLAUDE.md from repo analysis.",
    "Feature lifecycle: design, plan, implement, validate, release.": "Feature lifecycle: design, plan, implement, validate, release.",
    "Fish shell configuration and PATH management.": "Fish shell configuration and PATH management.",
    "Data analysis with statistical rigor gates.": "Data analysis with statistical rigor.",
    "Decision-first data analysis with statistical rigor gates.": "Data analysis with statistical rigor.",
    "Batch find/replace and frontmatter updates across Hugo posts.": "Batch find/replace across Hugo posts.",
    "Multi-agent consultation for architecture decisions.": "Consult on architecture decisions.",
    "Knowledge base operations on `research/{topic}/` wikis: compile raw sources into wiki articles, query the wiki for answers, or health-check wiki consistency.": "Knowledge base: compile, query, and health-check research wikis.",
    "Query and display structured decision traces from routing, agent selection, and skill execution.": "Query routing and skill execution traces.",
    "Full-repo SAP CC Go compliance audit against review standards.": "SAP CC Go compliance audit.",
    "Gold-standard SAP CC Go code review: 10 parallel domain specialists.": "SAP CC Go code review: 10 parallel specialists.",
    "Cobalt Core infrastructure knowledge: KVM exporters, hypervisor tooling, OpenStack compute.": "Cobalt Core: KVM exporters, hypervisor tooling, OpenStack.",
    "Perses platform operations: dashboards, plugins, deployment, migration, and quality.": "Perses: dashboards, plugins, deployment, migration.",
    "C-suite executive decision support: strategy, technology, growth, competitive intelligence, project evaluation.": "C-suite decision support: strategy, technology, growth, competitive intel.",
    "Pull request lifecycle: commit, codex review, sync, review, fix, status, cleanup, and PR mining.": "PR lifecycle: commit, review, sync, fix, cleanup.",
    "Extract coding conventions and style rules from GitHub user profiles via API.": "Extract coding conventions from GitHub profiles.",
    # --- Skipped batch (actual SKILL.md descriptions) ---
    "Classify user requests and route to the correct agent + skill. Primary entry point for all delegated work.": "Route requests to agents with skills.",
    "Deterministic API endpoint validation with pass/fail reporting.": "API endpoint validation with pass/fail reporting.",
    "Game lifecycle orchestrator: scaffold, assets, audio, QA, deploy.": "Game lifecycle: scaffold, assets, audio, QA, deploy.",
    "Triage GitHub notifications: fetch, classify, report actions needed.": "Triage GitHub notifications.",
    "Extract programming rules and coding conventions from a GitHub user": "Extract coding conventions from GitHub profiles.",
    "Extract programming rules and coding conventions from a GitHub user's public profile.": "Extract coding conventions from GitHub profiles.",
    "CPU-only motion data processing pipeline for game animation: BVH import, contact detection, root decomposition, motion blending, FABRIK IK. No GPU required.": "Game animation from BVH: contact detection, root decomposition, motion blending, IK.",
    "First-time Perses setup: discover/deploy server, configure MCP, create project": "First-time Perses setup: server, MCP, project.",
    "Comprehensive PR review using specialized agents, with automatic retro knowledge capture": "PR review with specialized agents and retro capture.",
    "Tracked lightweight execution with composable rigor flags: --trivial, --discuss, --research, --full. Covers zero-ceremony inline fixes (\u2264\u0033 edits) through contained multi-file changes.": "Lightweight execution with rigor flags: --trivial, --discuss, --research, --full.",
    "Learning system interface: stats, search, graduate learnings. Backed by learning.db (SQLite + FTS5).": "Learning system: stats, search, graduate.",
}


def update_description_in_file(skill_md: Path, new_desc: str, dry_run: bool) -> tuple[str, str] | None:
    """Replace the description field in YAML frontmatter. Returns (old, new) or None."""
    text = skill_md.read_text(encoding="utf-8")

    # Match description in YAML frontmatter
    pattern = re.compile(
        r'^(description:\s*["\'])(.+?)(["\'])\s*$',
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return None

    old_desc = match.group(2)
    if old_desc == new_desc:
        return None

    if not dry_run:
        new_text = text[: match.start(2)] + new_desc + text[match.end(2) :]
        skill_md.write_text(new_text, encoding="utf-8")

    return (old_desc, new_desc)


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    total_old = 0
    total_new = 0
    changed = 0
    skipped = []

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        text = skill_md.read_text(encoding="utf-8")
        pattern = re.compile(r'^description:\s*["\'](.+?)["\']\s*$', re.MULTILINE)
        match = pattern.search(text)
        if not match:
            continue

        old_desc = match.group(1)
        total_old += len(old_desc)

        if old_desc in REWRITES:
            new_desc = REWRITES[old_desc]
            result = update_description_in_file(skill_md, new_desc, dry_run)
            if result:
                changed += 1
                total_new += len(new_desc)
                saved = len(old_desc) - len(new_desc)
                if dry_run:
                    print(f"  {skill_dir.name}:")
                    print(f"    OLD: {old_desc}")
                    print(f"    NEW: {new_desc}")
                    print(f"    saved: {saved} chars")
                    print()
            else:
                total_new += len(old_desc)
        else:
            total_new += len(old_desc)
            skipped.append((skill_dir.name, old_desc))

    mode = "DRY RUN" if dry_run else "APPLIED"
    print(f"\n=== {mode} ===")
    print(f"Changed: {changed} skills")
    print(f"Total description chars: {total_old:,} -> {total_new:,} (saved {total_old - total_new:,})")
    print(f"Avg chars: {total_old // max(changed + len(skipped), 1)} -> {total_new // max(changed + len(skipped), 1)}")

    if skipped:
        print(f"\nSkipped (no rewrite rule): {len(skipped)}")
        for name, desc in skipped:
            print(f"  {name}: {desc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
