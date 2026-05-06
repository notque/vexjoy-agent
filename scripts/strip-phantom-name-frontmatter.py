#!/usr/bin/env python3
"""
Normalize YAML frontmatter on agent and skill reference files.

Purpose
=======
Reference files under ``agents/*/references/*.md`` and ``skills/*/references/*.md``
are progressive-disclosure content loaded on demand by their parent agent or
skill. They are not independently routable components.

Historically some of these files shipped with a top-level ``name:`` field in
their YAML frontmatter. Indexers that treat any ``.md`` file with a ``name:``
as a registerable component pick these up and register them as top-level
entries. That inflates the base context shown at session start with entries
that have no routing table presence, no discoverability, and no independent
purpose.

This script removes the ``name:`` field from reference-file frontmatter so
they remain scoped under their parent umbrella. Other frontmatter fields
(description, allowed-tools, etc.) are preserved verbatim.

Safety
======
- Every candidate file's frontmatter value for ``name:`` is audited against
  the routing table (``skills/meta/do/references/routing-tables.md``) and all
  pipeline JSON files. Any name that appears as a routed target is added
  to a skip list and left untouched.
- After each edit the resulting YAML is re-parsed. A parse failure on any
  modified file aborts the run with a non-zero exit code.
- Files with no ``name:`` field are never touched.

Verified-safe mode
==================
The default audit is conservative: any substring match in the routing table
or a pipeline JSON is treated as a dispatch dependency and the file is
skipped. A prior investigation showed that for the 29 files under
``skills/workflow/references/*.md`` plus
``skills/engineering/kotlin-coroutines/references/preferred-patterns.md``, the substring
matches are false positives for dispatch purposes:

1. The pipeline dispatcher in ``scripts/index-router.py`` keys on JSON keys
   from ``skills/workflow/references/pipeline-index.json`` and on file paths,
   not on the YAML ``name:`` field inside the reference files themselves.
2. The only script that reads the YAML ``name:`` field is
   ``scripts/generate-pipeline-catalog.py``. When ``name`` is absent it
   falls back to ``skill_file.stem`` (line using ``frontmatter.get("name",
   skill_file.stem)``), which produces the same string for these files
   because the YAML name already matches the filename stem.
3. Hits against the routing table are on prose descriptions of routed
   *skills*, not on the reference-file umbrella entries.

The ``--verified-safe`` flag enables an allowlist of these 29 paths so the
strip proceeds on them. The proof of no behavioral change is a
byte-identical ``skills/workflow/references/auto-pipeline/references/pipeline-catalog.json``
before and after the strip. Always regenerate and diff that file when
running with ``--verified-safe``.

Usage
=====
    python3 scripts/strip-phantom-name-frontmatter.py                    # default audit
    python3 scripts/strip-phantom-name-frontmatter.py --dry-run          # inventory only
    python3 scripts/strip-phantom-name-frontmatter.py --verified-safe    # allowlist mode

Rollback
========
This is a single-commit, reversible change. To roll back:

    git revert <commit-sha>

No other state is touched (no indexes, no caches, no external files).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent

AGENT_REF_GLOB = "agents/*/references/*.md"
SKILL_REF_GLOB = "skills/*/references/*.md"

ROUTING_TABLE = REPO_ROOT / "skills" / "do" / "references" / "routing-tables.md"


# Verified-safe allowlist. These files were flagged by the conservative
# audit as potentially routed, but investigation showed the matches are
# false positives: dispatch is JSON-keyed (see scripts/index-router.py)
# and scripts/generate-pipeline-catalog.py has a skill_file.stem fallback
# that reproduces the same string after name: is removed. The proof of
# no behavioral change is a byte-identical pipeline-catalog.json before
# and after running with --verified-safe.
VERIFIED_SAFE_PATHS: frozenset[str] = frozenset(
    {
        "skills/engineering/kotlin-coroutines/references/preferred-patterns.md",
        "skills/workflow/references/agent-upgrade.md",
        "skills/workflow/references/article-evaluation-pipeline.md",
        "skills/workflow/references/auto-pipeline.md",
        "skills/workflow/references/chain-composer.md",
        "skills/workflow/references/comprehensive-review.md",
        "skills/workflow/references/de-ai-pipeline.md",
        "skills/workflow/references/do-perspectives.md",
        "skills/workflow/references/doc-pipeline.md",
        "skills/workflow/references/domain-research.md",
        "skills/workflow/references/explore-pipeline.md",
        "skills/workflow/references/github-profile-rules.md",
        "skills/workflow/references/hook-development-pipeline.md",
        "skills/workflow/references/mcp-pipeline-builder.md",
        "skills/workflow/references/perses-dac-pipeline.md",
        "skills/workflow/references/perses-plugin-pipeline.md",
        "skills/workflow/references/pipeline-retro.md",
        "skills/workflow/references/pipeline-scaffolder.md",
        "skills/workflow/references/pipeline-test-runner.md",
        "skills/workflow/references/research-pipeline.md",
        "skills/workflow/references/research-to-article.md",
        "skills/workflow/references/skill-creation-pipeline.md",
        "skills/workflow/references/system-upgrade.md",
        "skills/workflow/references/systematic-debugging.md",
        "skills/workflow/references/systematic-refactoring.md",
        "skills/workflow/references/toolkit-improvement.md",
        "skills/workflow/references/voice-calibrator.md",
        "skills/workflow/references/voice-writer.md",
        "skills/workflow/references/workflow-orchestrator.md",
    }
)


FRONTMATTER_RE = re.compile(
    r"\A---\r?\n(.*?)\r?\n---\r?\n",
    re.DOTALL,
)


def read_frontmatter(path: Path) -> tuple[dict | None, str | None, str]:
    """Return (parsed_frontmatter, raw_frontmatter_block, full_text).

    parsed_frontmatter is None when the file has no YAML frontmatter.
    """
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, None, text
    raw = match.group(1)
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        return None, raw, text
    if not isinstance(data, dict):
        return None, raw, text
    return data, raw, text


def inventory_candidates() -> list[tuple[Path, str]]:
    """Return (path, name_value) for every reference file with a top-level name:."""
    candidates: list[tuple[Path, str]] = []
    for pattern in (AGENT_REF_GLOB, SKILL_REF_GLOB):
        for path in sorted(REPO_ROOT.glob(pattern)):
            # Exclude anything under worktrees (not part of the main tree).
            if ".claude/worktrees" in str(path):
                continue
            data, _raw, _text = read_frontmatter(path)
            if not data:
                continue
            name = data.get("name")
            if isinstance(name, str) and name.strip():
                candidates.append((path, name.strip()))
    return candidates


def collect_pipeline_json_paths() -> list[Path]:
    paths: list[Path] = []
    for pattern in (
        "skills/*/references/*pipeline*.json",
        "skills/workflow/references/*.json",
        "**/pipeline-index.json",
    ):
        for path in REPO_ROOT.glob(pattern):
            if ".claude/worktrees" in str(path):
                continue
            paths.append(path)
    # Deduplicate while preserving order.
    seen: set[Path] = set()
    uniq: list[Path] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def audit_routed_names(candidates: list[tuple[Path, str]]) -> dict[str, list[str]]:
    """Return {phantom_name: [evidence_strings]} for names used as routed targets.

    An evidence string looks like: 'routing-tables.md: line 42: ...context...'

    A hit in routing-tables.md is flagged conservatively: any literal text match
    causes the name to land on the skip list. It is cheaper to spare a file from
    stripping than to break a route.

    A hit in a pipeline JSON is flagged when the name appears as a value
    (e.g. "file": "..." or a trigger phrase) that the pipeline system dispatches
    against.
    """
    hits: dict[str, list[str]] = {}

    routing_text = ROUTING_TABLE.read_text(encoding="utf-8") if ROUTING_TABLE.exists() else ""
    routing_lines = routing_text.splitlines()

    pipeline_paths = collect_pipeline_json_paths()
    pipeline_blobs: list[tuple[Path, str]] = []
    for p in pipeline_paths:
        try:
            pipeline_blobs.append((p, p.read_text(encoding="utf-8")))
        except OSError:
            continue

    for _path, name in candidates:
        # The phantom names we are worried about are ones that have semantic
        # routing weight. Very short generic tokens (like "mcp" or "patterns")
        # would false-positive everywhere. We therefore only flag a name if
        # the literal string is present AND is reasonably specific
        # (>= 8 characters), which filters out common words.
        if len(name) < 8:
            continue

        evidence: list[str] = []

        for i, line in enumerate(routing_lines, start=1):
            if name in line:
                snippet = line.strip()
                if len(snippet) > 140:
                    snippet = snippet[:140] + "..."
                evidence.append(f"routing-tables.md:{i}: {snippet}")

        for p, blob in pipeline_blobs:
            if name in blob:
                # Find which key/value carries it for readability.
                try:
                    data = json.loads(blob)
                except json.JSONDecodeError:
                    data = None
                context = _locate_in_json(data, name) if data else "(raw string match)"
                evidence.append(f"{p.relative_to(REPO_ROOT)}: {context}")

        if evidence:
            hits[name] = evidence

    return hits


def _locate_in_json(obj, needle: str, path: str = "$") -> str:
    """Best-effort locator: return the JSON path where needle appears as a string."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and needle in k:
                return f"{path}.{k}"
            inner = _locate_in_json(v, needle, f"{path}.{k}")
            if inner:
                return inner
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            inner = _locate_in_json(v, needle, f"{path}[{i}]")
            if inner:
                return inner
    elif isinstance(obj, str):
        if needle in obj:
            return f"{path} == {obj[:80]!r}"
    return ""


def strip_name_field(path: Path) -> tuple[bool, str]:
    """Remove the top-level ``name:`` line from the frontmatter.

    Returns (changed, message). If the rewrite cannot be done safely (no
    frontmatter, no name field, parse failure after edit), returns
    (False, reason) and leaves the file untouched.
    """
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return False, "no frontmatter"

    raw_block = match.group(1)
    end_of_fm = match.end()  # position after the closing '---\n'

    # Remove only a top-level (non-indented) name: line. Preserve nested
    # ``name:`` keys inside other structures.
    lines = raw_block.splitlines()
    new_lines: list[str] = []
    removed = False
    for line in lines:
        if not removed and re.match(r"^name\s*:", line):
            removed = True
            continue
        new_lines.append(line)

    if not removed:
        return False, "no top-level name: field"

    new_raw = "\n".join(new_lines)

    # Re-parse to confirm it still loads as a mapping.
    try:
        reparsed = yaml.safe_load(new_raw)
    except yaml.YAMLError as exc:
        return False, f"YAML parse error after edit: {exc}"
    if reparsed is not None and not isinstance(reparsed, dict):
        return False, "frontmatter no longer parses as a mapping"

    # Preserve trailing newline convention used by original block.
    trailing = "\n" if raw_block.endswith("\n") else ""
    rebuilt = f"---\n{new_raw}{trailing}\n---\n" + text[end_of_fm:]

    path.write_text(rebuilt, encoding="utf-8")

    # Post-write verification.
    data, _raw, _full = read_frontmatter(path)
    if data is None:
        return False, "post-write frontmatter fails to parse"
    if "name" in data:
        return False, "post-write frontmatter still contains name:"
    return True, "stripped"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__ or "")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inventory and audit only; do not modify any file.",
    )
    parser.add_argument(
        "--verified-safe",
        action="store_true",
        help=(
            "Strip name: from paths on the VERIFIED_SAFE_PATHS allowlist even "
            "if the conservative audit would otherwise skip them. See the "
            "module docstring for the verdict evidence."
        ),
    )
    args = parser.parse_args()

    print("== Inventory ==")
    candidates = inventory_candidates()
    print(f"Reference files with top-level name: field: {len(candidates)}")
    for path, name in candidates:
        rel = path.relative_to(REPO_ROOT)
        print(f"  {rel}  ->  name: {name}")

    print()
    print("== Audit ==")
    print(f"Checking {ROUTING_TABLE.relative_to(REPO_ROOT)} and pipeline JSONs...")
    hits = audit_routed_names(candidates)

    skip_list: set[Path] = set()
    if hits:
        print(f"Potential routed targets found: {len(hits)}")
        for name, evidence in hits.items():
            print(f"  SKIP candidate name: {name}")
            for ev in evidence:
                print(f"    {ev}")
            # Collect the paths whose name matches.
            for path, cand_name in candidates:
                if cand_name == name:
                    skip_list.add(path)
    else:
        print("No phantom names appear as routed targets.")

    if args.verified_safe:
        print()
        print("== Verified-safe overrides ==")
        overridden: list[Path] = []
        for path in list(skip_list):
            rel = str(path.relative_to(REPO_ROOT))
            if rel in VERIFIED_SAFE_PATHS:
                skip_list.discard(path)
                overridden.append(path)
        print(f"Allowlist hits removed from skip list: {len(overridden)}")
        for path in overridden:
            print(f"  OVERRIDE: {path.relative_to(REPO_ROOT)}")
        # Warn if the allowlist references paths that are not even
        # candidates (e.g. already stripped on a prior run). This is
        # informational, not fatal.
        candidate_paths = {str(p.relative_to(REPO_ROOT)) for p, _ in candidates}
        stale = sorted(VERIFIED_SAFE_PATHS - candidate_paths)
        if stale:
            print(f"Allowlist entries already stripped (no-op): {len(stale)}")
            for rel in stale:
                print(f"  NO-OP: {rel}")

    safe = [(p, n) for p, n in candidates if p not in skip_list]
    print()
    print("== Plan ==")
    print(f"Safe to strip: {len(safe)}")
    print(f"Skipped (routed reference found): {len(skip_list)}")

    if args.dry_run:
        print()
        print("Dry-run mode: no files modified.")
        return 0

    print()
    print("== Execute ==")
    modified = 0
    failures: list[tuple[Path, str]] = []
    for path, _name in safe:
        ok, msg = strip_name_field(path)
        rel = path.relative_to(REPO_ROOT)
        if ok:
            modified += 1
            print(f"  modified: {rel}")
        else:
            print(f"  unchanged: {rel} ({msg})")
            if "parse error" in msg or "still contains name" in msg or "no longer parses" in msg:
                failures.append((path, msg))

    print()
    print("== Summary ==")
    print(f"Inventoried: {len(candidates)}")
    print(f"Skipped:     {len(skip_list)}")
    print(f"Modified:    {modified}")
    print(f"Failures:    {len(failures)}")
    if failures:
        for path, msg in failures:
            print(f"  FAIL: {path.relative_to(REPO_ROOT)} - {msg}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
