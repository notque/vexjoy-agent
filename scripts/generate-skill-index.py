#!/usr/bin/env python3
"""
Generate skill routing index from YAML frontmatter.

Reads skills/**/SKILL.md, extracts routing metadata
from YAML frontmatter, and generates a dict-keyed index file:
  - skills/INDEX.json   (skills only, v2.0)

Usage:
    python scripts/generate-skill-index.py
    python scripts/generate-skill-index.py --include-private
    python scripts/generate-skill-index.py --include-private --output skills/INDEX.local.json

Options:
    --include-private   Include symlinked directories (default: skip them)
    --output PATH       Output path (default: skills/INDEX.json)

Output:
    skills/INDEX.json    - Skill routing index for /do router (public, tracked)


Exit codes:
    0 - Success
    1 - Fatal error (directory not found, write failed)
    2 - Trigger collisions detected among force-routed entries
    3 - Regex fallback was used (non-strict mode warning)
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lib.frontmatter import extract_frontmatter_block

# Phase header regex: matches "## Phase 1:" or "### Phase 1:", "### Phase 0.5:", "### Phase 4b:", etc.
# Captures the NAME part after the colon, stopping before parenthetical or em-dash suffixes.
PHASE_HEADER_RE = re.compile(r"^##+ Phase [\d]+[a-z.]?[\d]*:\s*(.+?)(?:\s*\(|\s*--|\s*\u2014|$)")


def extract_frontmatter(content: str) -> tuple[dict | None, bool]:
    """Extract YAML frontmatter from markdown content.

    Attempts YAML parsing first, then falls back to regex extraction
    for key fields (name, description, version, user-invocable, routing,
    agent, model) when YAML parsing fails due to malformed or edge-case
    frontmatter.

    Returns:
        tuple: (frontmatter dict or None, used_fallback bool)
    """
    yaml_content = extract_frontmatter_block(content)
    if yaml_content is None:
        return None, False

    try:
        result = yaml.safe_load(yaml_content)
        return result, False
    except yaml.YAMLError as e:
        # Log the parsing failure - regex fallback will be attempted
        print(f"  Warning: YAML parsing failed, using regex fallback: {e}", file=sys.stderr)

    # Fallback: extract key fields via regex when YAML parsing fails
    frontmatter: dict = {}

    name_match = re.search(r"^name:\s*(.+)$", yaml_content, re.MULTILINE)
    if name_match:
        frontmatter["name"] = name_match.group(1).strip()

    # Handle YAML block scalar indicators (> for folded, | for literal)
    desc_match = re.search(
        r"^description:\s*(?:[>|][\-+]?\s*\n\s+)?(.+?)(?=\n[a-z_-]+:|$)",
        yaml_content,
        re.MULTILINE | re.DOTALL,
    )
    if desc_match:
        # Clean up multiline descriptions
        desc = desc_match.group(1).strip()
        desc = re.sub(r"\s+", " ", desc)
        frontmatter["description"] = desc

    version_match = re.search(r"^version:\s*(.+)$", yaml_content, re.MULTILINE)
    if version_match:
        frontmatter["version"] = version_match.group(1).strip()

    # Normalize to lowercase for boolean comparison (handles "True", "TRUE", etc.)
    user_invocable_match = re.search(r"^user-invocable:\s*(.+)$", yaml_content, re.MULTILINE)
    if user_invocable_match:
        val = user_invocable_match.group(1).strip().lower()
        frontmatter["user-invocable"] = val == "true"

    # Top-level agent field
    agent_match = re.search(r"^agent:\s*(.+)$", yaml_content, re.MULTILINE)
    if agent_match:
        frontmatter["agent"] = agent_match.group(1).strip()

    # Top-level model field
    model_match = re.search(r"^model:\s*(.+)$", yaml_content, re.MULTILINE)
    if model_match:
        frontmatter["model"] = model_match.group(1).strip()

    # Parse nested routing section structure:
    #   routing:
    #     triggers:
    #       - "trigger1"
    #       - trigger2
    #     category: category-name
    #     force_route: true
    #     pairs_with:
    #       - agent-name
    routing_match = re.search(r"^routing:\s*\n((?:\s+.+\n?)+)", yaml_content, re.MULTILINE)
    if routing_match:
        routing_content = routing_match.group(1)
        routing: dict = {}

        triggers_match = re.search(r"triggers:\s*\n((?:\s+-\s+.+\n?)+)", routing_content)
        if triggers_match:
            triggers = re.findall(r'-\s+["\']?([^"\'\n]+)["\']?', triggers_match.group(1))
            routing["triggers"] = [t.strip() for t in triggers]

        category_match = re.search(r"category:\s*(.+)$", routing_content, re.MULTILINE)
        if category_match:
            routing["category"] = category_match.group(1).strip()

        force_route_match = re.search(r"force_route:\s*(.+)$", routing_content, re.MULTILINE)
        if force_route_match:
            val = force_route_match.group(1).strip().lower()
            routing["force_route"] = val == "true"

        not_for_match = re.search(r'not_for:\s*["\'](.+?)["\']', routing_content)
        if not_for_match:
            routing["not_for"] = not_for_match.group(1).strip()

        pairs_match = re.search(r"pairs_with:\s*\n((?:\s+-\s+.+\n?)+)", routing_content)
        if pairs_match:
            pairs = re.findall(r'-\s+["\']?([^"\'\n]+)["\']?', pairs_match.group(1))
            routing["pairs_with"] = [p.strip() for p in pairs]

        # Also handle inline empty list: pairs_with: []
        pairs_empty_match = re.search(r"pairs_with:\s*\[\]", routing_content)
        if pairs_empty_match and "pairs_with" not in routing:
            routing["pairs_with"] = []

        if routing:
            frontmatter["routing"] = routing

    return (frontmatter if frontmatter else None), True


def extract_short_description(description: str) -> str:
    """Extract first sentence from description, truncating to 150 chars if needed."""
    if not description:
        return ""

    desc = description.replace("\\n", " ").strip()
    desc = re.sub(r"\s+", " ", desc)

    # First sentence - but don't split on dots in identifiers like t.Run, Next.js,
    # config.fish, CLAUDE.md (dot followed by lowercase letter or known extension)
    match = re.match(r"((?:[^.!?]|\.(?=[a-zA-Z0-9_]))+[.!?])", desc)
    if match and len(match.group(1)) <= 200:
        return match.group(1).strip()

    # Truncate if too long
    if len(desc) > 150:
        return desc[:147] + "..."

    return desc


def extract_phases(content: str) -> list[str]:
    """Extract phase names from pipeline SKILL.md body.

    Looks for ### Phase N: NAME headers and extracts the name part,
    uppercased. Handles variants like Phase 0.5, Phase 4b, Phase 2a.
    Strips parenthetical and em-dash suffixes from phase names.

    Args:
        content: Full SKILL.md file content.

    Returns:
        List of phase names in document order (e.g., ["CLASSIFY", "STAGE", "REVIEW"]).
    """
    phases = []
    for line in content.splitlines():
        m = PHASE_HEADER_RE.match(line)
        if m:
            phase_name = m.group(1).strip().upper()
            # Remove trailing whitespace artifacts
            phase_name = phase_name.strip()
            if phase_name:
                phases.append(phase_name)
    return phases


def _repo_relative_path(skill_dir: Path, dir_prefix: str, repo_root: Path | None) -> str | None:
    """If skill_dir resolves to a location inside the repo, return its repo-relative
    nested path (e.g. "skills/business/csuite/SKILL.md"); else None.

    In the synced/deployed layout, ~/.claude/skills/<name> is a SYMLINK back into
    the repo's nested skills/<category>/<name>. Resolving the symlink recovers the
    real, on-disk-valid nested path — the fix for the path-flattening bug that wrote
    "skills/<name>/SKILL.md" entries pointing at files that exist in no layout here.
    """
    if repo_root is None:
        return None
    try:
        real = skill_dir.resolve()
        rel = real.relative_to(repo_root.resolve())
    except (OSError, ValueError):
        return None
    # rel is already repo-relative and includes the leading skills/ component
    # (e.g. "skills/business/csuite"); do not re-prepend dir_prefix. Only honor
    # paths that actually sit under dir_prefix so the entry stays well-formed.
    if rel.parts and rel.parts[0] != dir_prefix:
        return None
    candidate = repo_root / rel / "SKILL.md"
    if candidate.is_file():
        return f"{rel.as_posix()}/SKILL.md"
    return None


def build_entry(
    frontmatter: dict,
    skill_dir: Path,
    dir_prefix: str,
    source_dir: Path | None = None,
    content: str | None = None,
    is_pipeline: bool = False,
    flatten: bool = False,
    repo_root: Path | None = None,
) -> dict:
    """Build a single index entry from frontmatter and optional content.

    Args:
        frontmatter: Parsed YAML frontmatter dict.
        skill_dir: Directory containing the SKILL.md file.
        dir_prefix: Path prefix for file field (e.g., "skills" or "pipelines").
        source_dir: Root scan directory; used to compute relative paths for nested skills.
        content: Full SKILL.md content (needed for pipeline phase extraction).
        is_pipeline: Whether this entry is a pipeline (enables phase extraction).
        flatten: When True, prefer the deployed flat layout — but a skill whose
            directory resolves back into the repo records its real repo-relative
            nested path so the entry always points at an on-disk file.
        repo_root: Repo root, used to recover nested paths through deployed symlinks.

    Returns:
        Dict representing the index entry for this skill/pipeline.
    """
    name = frontmatter.get("name", skill_dir.name)

    # Compute file path relative to source_dir for nested category folders.
    # Flat: skills/foo/SKILL.md → "skills/foo/SKILL.md"
    # Nested: skills/meta/foo/SKILL.md → "skills/meta/foo/SKILL.md"
    # Flatten: prefer the repo's real nested path when the (possibly symlinked)
    #   deployed dir resolves back into the repo; otherwise the flat deployed name.
    if flatten:
        nested = _repo_relative_path(skill_dir, dir_prefix, repo_root)
        file_path = nested if nested else f"{dir_prefix}/{skill_dir.name}/SKILL.md"
    elif source_dir:
        rel = skill_dir.relative_to(source_dir)
        file_path = f"{dir_prefix}/{rel}/SKILL.md"
    else:
        file_path = f"{dir_prefix}/{skill_dir.name}/SKILL.md"

    entry: dict = {
        "file": file_path,
        "description": extract_short_description(frontmatter.get("description", "")),
    }

    # Triggers: from routing.triggers or auto-generated from name
    routing = frontmatter.get("routing", {})
    if isinstance(routing, dict) and "triggers" in routing:
        entry["triggers"] = routing["triggers"]
    else:
        # Generate triggers from name as fallback
        name_parts = name.replace("-", " ").split()
        stop_words = {"skill", "pipeline", "the", "and", "for", "with"}
        triggers = [p for p in name_parts if len(p) > 2 and p.lower() not in stop_words]
        entry["triggers"] = [name] + triggers

    # Not-for disambiguation: from routing.not_for, omit if not present
    if isinstance(routing, dict) and "not_for" in routing:
        entry["not_for"] = routing["not_for"]

    # Category: from routing.category, omit if not present
    if isinstance(routing, dict) and "category" in routing:
        entry["category"] = routing["category"]

    # Force route: from routing.force_route, only include when true
    if isinstance(routing, dict) and routing.get("force_route") is True:
        entry["force_route"] = True

    # User invocable: normalize kebab-case to snake_case, default false
    user_invocable = frontmatter.get("user-invocable", False)
    entry["user_invocable"] = bool(user_invocable)

    # Version: from frontmatter, omit if not present
    if "version" in frontmatter:
        entry["version"] = frontmatter["version"]

    # Phases: pipelines only, extracted from body content
    if is_pipeline and content:
        phases = extract_phases(content)
        if phases:
            entry["phases"] = phases

    # Pairs with: from routing.pairs_with, omit if not present
    if isinstance(routing, dict) and "pairs_with" in routing:
        entry["pairs_with"] = routing["pairs_with"]

    # Agent: top-level frontmatter field, omit if not present
    if "agent" in frontmatter:
        entry["agent"] = frontmatter["agent"]

    # Model: top-level frontmatter field, omit if not present
    if "model" in frontmatter:
        entry["model"] = frontmatter["model"]

    return entry


def generate_index(
    source_dir: Path,
    dir_prefix: str,
    collection_key: str,
    is_pipeline: bool = False,
    include_private: bool = False,
    strict: bool = False,
    flatten: bool = False,
    repo_root: Path | None = None,
) -> tuple[dict, list[str]]:
    """Generate a dict-keyed routing index from all SKILL.md files in a directory.

    Args:
        source_dir: Directory to scan for subdirectories containing SKILL.md.
        dir_prefix: Path prefix for file field (e.g., "skills" or "pipelines").
        collection_key: Top-level key name in the index (e.g., "skills" or "pipelines").
        is_pipeline: Whether entries are pipelines (enables phase extraction).
        include_private: When True, include symlinked directories. When False (default),
            only directly-tracked directories are indexed.
        strict: When True, YAML parse failure skips the skill (no regex fallback).
        flatten: When True, use leaf directory name for paths (matches deployed layout).
        repo_root: Repo root, used to recover nested paths through deployed symlinks
            in flatten mode. Defaults to source_dir's parent when not supplied.

    Returns:
        tuple: (index dict with version/generated/generated_by/collection,
                list of warning messages)
    """
    if repo_root is None:
        repo_root = source_dir.parent
    index: dict = {
        "version": "2.0",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "scripts/generate-skill-index.py",
        collection_key: {},
    }
    warnings: list[str] = []

    def _process_skill_dir(skill_dir: Path, skill_file_override: Path | None = None) -> None:
        """Process a single skill directory: extract frontmatter and add to index.

        Args:
            skill_dir: The skill's directory (used for naming and path computation).
            skill_file_override: If set, read SKILL.md from this path instead of
                skill_dir / "SKILL.md". Used for nested layouts (skill/SKILL.md).
        """
        skill_file = skill_file_override or (skill_dir / "SKILL.md")
        if not skill_file.exists():
            return

        try:
            content_ = skill_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            warnings.append(f"  - {skill_dir.name}: Failed to read: {e}")
            return

        try:
            fm, used_fallback = extract_frontmatter(content_)
            if used_fallback:
                if strict:
                    warnings.append(
                        f"  - {skill_dir.name}: YAML parsing failed (strict mode: skipping, no regex fallback)"
                    )
                    return
                warnings.append(f"  - {skill_dir.name}: Used regex fallback (YAML parsing failed)")
        except re.error as e:
            warnings.append(f"  - {skill_dir.name}: Regex error in frontmatter: {e}")
            fm = None

        if not fm:
            warnings.append(f"  - {skill_dir.name}: No valid frontmatter found")
            return

        name = fm.get("name", skill_dir.name)

        promoted_to = fm.get("promoted_to")
        if promoted_to:
            print(f"  [skip] {name} promoted to {promoted_to}")
            return

        entry = build_entry(
            frontmatter=fm,
            skill_dir=skill_dir,
            dir_prefix=dir_prefix,
            source_dir=source_dir,
            content=content_ if is_pipeline else None,
            is_pipeline=is_pipeline,
            flatten=flatten,
            repo_root=repo_root,
        )
        # A skill can be reached twice in include_private mode: once at its
        # canonical repo location and again via a symlinked category (e.g.
        # skills/voice -> private-skills/voice). Keep the entry whose file
        # actually exists in the repo rather than letting a shadow copy with a
        # fabricated flat path clobber a good canonical path.
        existing = index[collection_key].get(name)
        if existing is not None:
            new_ok = (repo_root / entry["file"]).is_file() if repo_root else False
            old_ok = (repo_root / existing["file"]).is_file() if repo_root else False
            if old_ok and not new_ok:
                return
        index[collection_key][name] = entry

    for child in sorted(source_dir.iterdir()):
        if not child.is_dir():
            continue

        # Skip symlinked directories unless --include-private was passed.
        if child.is_symlink() and not include_private:
            continue

        # Check if this directory directly contains a SKILL.md (flat layout)
        if (child / "SKILL.md").exists():
            _process_skill_dir(child)
        # Check for nested skill/SKILL.md layout (e.g., voice-example/skill/SKILL.md)
        elif (child / "skill" / "SKILL.md").exists():
            _process_skill_dir(child, skill_file_override=child / "skill" / "SKILL.md")
        else:
            # Category folder: recurse into subdirectories
            for nested in sorted(child.iterdir()):
                if not nested.is_dir():
                    continue
                if nested.is_symlink() and not include_private:
                    continue
                if (nested / "SKILL.md").exists():
                    _process_skill_dir(nested)
                elif (nested / "skill" / "SKILL.md").exists():
                    # Nested skill/SKILL.md layout within category
                    _process_skill_dir(nested, skill_file_override=nested / "skill" / "SKILL.md")
                else:
                    # Third level: e.g., skills/voice/skills/{name}/SKILL.md
                    for deep in sorted(nested.iterdir()):
                        if not deep.is_dir():
                            continue
                        if deep.is_symlink() and not include_private:
                            continue
                        if (deep / "SKILL.md").exists():
                            _process_skill_dir(deep)
                        elif (deep / "skill" / "SKILL.md").exists():
                            _process_skill_dir(deep, skill_file_override=deep / "skill" / "SKILL.md")

    return index, warnings


def prune_phantom_entries(skills_index: dict, roots: list[Path]) -> list[str]:
    """Drop entries whose advertised `file` path exists under none of `roots`.

    The --include-private scans index deployed and private packages; some
    (e.g. voice packages with only a nested skill/SKILL.md) get a flat
    `skills/{name}/SKILL.md` path that exists in no layout. Advertising them
    creates phantom routes — the router selects a skill nothing can load.

    Args:
        skills_index: Index dict with entries under "skills".
        roots: Layout roots to resolve `file` against (repo root, deployed root).

    Returns:
        Sorted names of pruned entries.
    """
    pruned: list[str] = []
    skills = skills_index.get("skills", {})
    for name in sorted(skills):
        rel = skills[name].get("file", "")
        if rel and not any((root / rel).is_file() for root in roots):
            del skills[name]
            pruned.append(name)
    return pruned


def check_trigger_collisions(
    skills_index: dict,
) -> list[str]:
    """Check for trigger collisions among force-routed entries.

    Scans all entries where force_route is true, and reports any
    trigger phrase that appears in more than one force-routed skill.

    Args:
        skills_index: The skills index dict (keyed under "skills").

    Returns:
        List of collision warning strings (empty if no collisions).
    """
    # Build map: trigger -> list of entry names that claim it
    trigger_owners: dict[str, list[str]] = {}

    for name, entry in skills_index.get("skills", {}).items():
        if not entry.get("force_route"):
            continue
        for trigger in entry.get("triggers", []):
            trigger_lower = trigger.lower()
            trigger_owners.setdefault(trigger_lower, []).append(name)

    collisions = []
    for trigger, owners in sorted(trigger_owners.items()):
        if len(owners) > 1:
            collisions.append(f'  Trigger collision: "{trigger}" claimed by: {", ".join(owners)}')

    return collisions


def write_index(index: dict, output_path: Path) -> bool:
    """Write an index dict to a JSON file.

    Args:
        index: The index dict to serialize.
        output_path: File path to write to.

    Returns:
        True on success, False on error (error printed to stderr).
    """
    try:
        output_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
        return True
    except PermissionError:
        print(f"Error: Permission denied writing to {output_path}", file=sys.stderr)
        return False
    except OSError as e:
        print(f"Error: Failed to write index file: {e}", file=sys.stderr)
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate skill routing index from YAML frontmatter.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--include-private",
        action="store_true",
        default=False,
        help="Include symlinked directories. Use with --output for local-only workflows.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: skills/INDEX.json relative to repo root).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Disable regex fallback. YAML parse failure = skip the skill and log an error.",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    skills_dir = repo_root / "skills"

    if not skills_dir.exists():
        print(f"Error: skills directory not found at {skills_dir}", file=sys.stderr)
        return 1

    # Resolve output path
    output_path: Path = args.output if args.output is not None else skills_dir / "INDEX.json"

    # Generate skills index
    # When --include-private is used (for INDEX.local.json), flatten nested paths
    # to match the deployed layout where sync hook flattens skills to ~/.claude/skills/{name}/
    skills_index, skills_warnings = generate_index(
        source_dir=skills_dir,
        dir_prefix="skills",
        collection_key="skills",
        is_pipeline=False,
        include_private=args.include_private,
        strict=args.strict,
        flatten=args.include_private,
        repo_root=repo_root,
    )

    # Scan ~/.claude/skills/ for deployed skills not already indexed.
    # Only when --include-private: the repo skills/ scan skips symlinked
    # directories (private/voice skills), so this picks up voice-* profiles
    # and any other private skills deployed by the sync hook. Without --include-private, these entries would reference
    # files that don't exist in the repo and break CI.
    user_skills_dir = Path.home() / ".claude" / "skills"
    if args.include_private and user_skills_dir.is_dir():
        for skill_dir in sorted(user_skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            deploy_name = skill_dir.name
            # Skip if already indexed from repo skills/
            if deploy_name in skills_index["skills"]:
                continue
            # Check both flat (SKILL.md) and nested (skill/SKILL.md) layouts
            skill_md_path = skill_dir / "SKILL.md"
            if not skill_md_path.exists():
                skill_md_path = skill_dir / "skill" / "SKILL.md"
            if not skill_md_path.exists():
                continue
            try:
                content_ = skill_md_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            fm, used_fallback = extract_frontmatter(content_)
            if not fm:
                continue
            if used_fallback and args.strict:
                continue
            # Override name to match deployed name
            fm["name"] = deploy_name
            entry = build_entry(
                frontmatter=fm,
                skill_dir=skill_dir,
                dir_prefix="skills",
                source_dir=None,
                content=None,
                is_pipeline=False,
                flatten=True,
                repo_root=repo_root,
            )
            # build_entry already recovers the repo-relative nested path when this
            # deployed dir is a symlink back into the repo. Only force the flat
            # deployed name when the skill resolves OUTSIDE the repo (true private).
            if _repo_relative_path(skill_dir, "skills", repo_root) is None:
                entry["file"] = f"skills/{deploy_name}/SKILL.md"
            skills_index["skills"][deploy_name] = entry

    # When --include-private, also scan ~/private-skills/ for skills deployed
    # by the sync hook. These live outside the repo but get symlinked into
    # ~/.claude/skills/ at session start. Mirror the sync hook's naming:
    # voice category → voice-{name}, others → {name}.
    if args.include_private:
        private_skills_dir = Path.home() / "private-skills"
        if private_skills_dir.is_dir():
            for category_dir in sorted(private_skills_dir.iterdir()):
                if not category_dir.is_dir() or category_dir.name.startswith("."):
                    continue
                category = category_dir.name
                for skill_dir in sorted(category_dir.iterdir()):
                    if not skill_dir.is_dir():
                        continue
                    # Check both flat (SKILL.md) and nested (skill/SKILL.md) layouts
                    skill_md_path = skill_dir / "SKILL.md"
                    if not skill_md_path.exists():
                        skill_md_path = skill_dir / "skill" / "SKILL.md"
                    if not skill_md_path.exists():
                        continue
                    # Mirror sync hook naming convention
                    if category == "voice":
                        deploy_name = f"voice-{skill_dir.name}"
                    else:
                        deploy_name = skill_dir.name

                    # Skip if already indexed from repo skills/
                    if deploy_name in skills_index["skills"]:
                        continue

                    try:
                        content_ = skill_md_path.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError):
                        continue

                    fm, used_fallback = extract_frontmatter(content_)
                    if not fm:
                        continue
                    if used_fallback and args.strict:
                        continue

                    # Override name to match deployed name
                    fm["name"] = deploy_name
                    entry = build_entry(
                        frontmatter=fm,
                        skill_dir=skill_dir,
                        dir_prefix="skills",
                        source_dir=None,
                        content=None,
                        is_pipeline=False,
                        flatten=True,  # Always flat for private skills
                        repo_root=repo_root,
                    )
                    # Private skills live under ~/private-skills (outside the repo),
                    # so the flat deployed name is the correct path. Keep the nested
                    # path only if this skill happens to resolve back into the repo.
                    if _repo_relative_path(skill_dir, "skills", repo_root) is None:
                        entry["file"] = f"skills/{deploy_name}/SKILL.md"
                    skills_index["skills"][deploy_name] = entry

    # Phantom gate (include-private only): advertise only files that resolve
    # in a live layout — the repo (nested paths) or ~/.claude (flat deployed).
    if args.include_private:
        pruned = prune_phantom_entries(skills_index, [repo_root, Path.home() / ".claude"])
        for name in pruned:
            skills_warnings.append(f"  - {name}: advertised file exists in no layout (pruned)")

    # Report warnings if any
    if skills_warnings:
        print("Warnings during index generation:", file=sys.stderr)
        for warning in skills_warnings:
            print(warning, file=sys.stderr)

    # Validate index has content before writing
    if not skills_index["skills"]:
        print("Error: No skills found. Index file not written.", file=sys.stderr)
        return 1

    # Write to output path (default: skills/INDEX.json)
    skills_index_path = output_path
    if not write_index(skills_index, skills_index_path):
        return 1

    # Check for trigger collisions among force-routed entries
    collisions = check_trigger_collisions(skills_index)
    if collisions:
        print("\nTrigger collisions detected (force-routed entries):", file=sys.stderr)
        for collision in collisions:
            print(collision, file=sys.stderr)

    # Summary (to stdout)
    skills_count = len(skills_index["skills"])

    print(f"Generated {skills_index_path}")
    print(f"  Skills: {skills_count}")

    # Show skills breakdown by category
    skill_categories: dict[str, int] = {}
    for entry in skills_index["skills"].values():
        cat = entry.get("category", "uncategorized")
        skill_categories[cat] = skill_categories.get(cat, 0) + 1
    if skill_categories:
        print("  By category:")
        for cat, count in sorted(skill_categories.items()):
            print(f"    {cat}: {count}")

    # Trigger stats
    all_named = list(skills_index["skills"].items())
    with_explicit = sum(1 for name, e in all_named if (e.get("triggers") or [name])[0] != name)
    force_routed = sum(1 for _, e in all_named if e.get("force_route"))
    print(f"\nWith explicit triggers: {with_explicit}")
    print(f"Force-routed: {force_routed}")

    # Post-generation drift gate: warn when routing manifest falls out of sync.
    # Only runs for the default output (skills/INDEX.json); skips local override indexes.
    if args.output is None:
        drift_script = Path(__file__).parent / "check-routing-drift.py"
        if drift_script.exists():
            drift_result = subprocess.run(
                [sys.executable, str(drift_script)],
                capture_output=True,
                text=True,
            )
            if drift_result.returncode != 0:
                print(
                    "\nWARNING: routing manifest is out of sync with INDEX.json.",
                    file=sys.stderr,
                )
                print(drift_result.stdout.strip(), file=sys.stderr)

    if collisions:
        print(f"\nCompleted with {len(collisions)} trigger collision(s)", file=sys.stderr)
        return 2

    # Return exit code 3 if regex fallback was used (non-strict mode)
    fallback_warnings = [w for w in skills_warnings if "regex fallback" in w.lower()]
    if fallback_warnings:
        print(
            f"\nCompleted with {len(fallback_warnings)} regex fallback(s) — fix YAML in these skills",
            file=sys.stderr,
        )
        return 3

    # Report non-fallback warnings
    if skills_warnings:
        print(f"\nCompleted with {len(skills_warnings)} warning(s)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
