"""Deterministic tests for the skills/ folder reorganization.

Validates INDEX.json integrity, category structure, cross-references,
hook regex patterns, generator scripts, and path consistency.
All checks are file-existence, regex, or subprocess — zero LLM logic.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]  # vexjoy-agent/
SKILLS_DIR = ROOT / "skills"
INDEX_PATH = SKILLS_DIR / "INDEX.json"

# ---------------------------------------------------------------------------
# Import SKILL_MAPPING from migration script (hyphenated filename)
# ---------------------------------------------------------------------------

_spec = importlib.util.spec_from_file_location(
    "migrate_skills_to_folders",
    ROOT / "scripts" / "migrate-skills-to-folders.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
SKILL_MAPPING: dict[str, str] = _mod.SKILL_MAPPING
KEEP_AT_ROOT: set[str] = _mod.KEEP_AT_ROOT

# Expected categories from the migration
CATEGORIES = {
    "business",
    "code-quality",
    "content",
    "engineering",
    "frontend",
    "game",
    "infrastructure",
    "meta",
    "process",
    "research",
    "review",
    "testing",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def index_data() -> dict:
    """Load INDEX.json once per module."""
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def index_skills(index_data: dict) -> dict[str, dict]:
    """Return the skills dict from INDEX.json."""
    return index_data["skills"]


@pytest.fixture(scope="module")
def skill_md_paths() -> list[Path]:
    """Find all SKILL.md files on disk under skills/."""
    return sorted(SKILLS_DIR.rglob("SKILL.md"))


# ═══════════════════════════════════════════════════════════════
# 1. INDEX.json Integrity
# ═══════════════════════════════════════════════════════════════


class TestIndexIntegrity:
    """Validate INDEX.json correctness."""

    def test_every_index_entry_has_existing_file(self, index_skills: dict[str, dict]) -> None:
        """Every skill in INDEX.json must point to a file that exists on disk."""
        missing = []
        for name, meta in index_skills.items():
            file_path = ROOT / meta["file"]
            if not file_path.is_file():
                missing.append(f"{name} -> {meta['file']}")
        assert not missing, f"INDEX.json entries with missing files:\n" + "\n".join(missing)

    def test_every_skill_md_is_in_index(self, index_skills: dict[str, dict], skill_md_paths: list[Path]) -> None:
        """Every SKILL.md on disk must be represented in INDEX.json."""
        indexed_files = {meta["file"] for meta in index_skills.values()}
        orphaned = []
        for path in skill_md_paths:
            rel = str(path.relative_to(ROOT))
            if rel not in indexed_files:
                orphaned.append(rel)
        assert not orphaned, f"SKILL.md files not in INDEX.json:\n" + "\n".join(orphaned)

    def test_no_duplicate_skill_names(self, index_data: dict) -> None:
        """INDEX.json must not contain duplicate skill names.

        JSON parsing silently keeps last-wins for duplicate keys, so we
        re-parse looking for duplicates via raw text scanning.
        """
        raw = INDEX_PATH.read_text(encoding="utf-8")
        # Find all top-level keys in the "skills" block — pattern: 4-space indent + quoted key
        key_pattern = re.compile(r'^    "([^"]+)":\s*\{', re.MULTILINE)
        keys = key_pattern.findall(raw)
        seen: set[str] = set()
        dupes: list[str] = []
        for k in keys:
            if k in seen:
                dupes.append(k)
            seen.add(k)
        assert not dupes, f"Duplicate skill names in INDEX.json: {dupes}"

    def test_every_index_entry_has_file_key(self, index_skills: dict[str, dict]) -> None:
        """Every skill entry must contain a 'file' key."""
        missing_key = [name for name, meta in index_skills.items() if "file" not in meta]
        assert not missing_key, f"Skills missing 'file' key: {missing_key}"


# ═══════════════════════════════════════════════════════════════
# 2. Skill Structure Validation
# ═══════════════════════════════════════════════════════════════


class TestSkillStructure:
    """Validate directory structure conventions."""

    def test_category_folders_contain_only_subdirs(self) -> None:
        """Category folders should only contain subdirectories (no loose files except README.md)."""
        allowed_files = {"README.md"}
        violations = []
        for cat in CATEGORIES:
            cat_dir = SKILLS_DIR / cat
            if not cat_dir.is_dir():
                continue
            for child in cat_dir.iterdir():
                if child.is_file() and child.name not in allowed_files:
                    violations.append(str(child.relative_to(ROOT)))
        assert not violations, f"Loose files in category folders:\n" + "\n".join(violations)

    def test_every_skill_dir_has_skill_md(self) -> None:
        """Every skill subdirectory within a category should contain a SKILL.md.

        Some voice-profile directories only have profile.json + references/
        without a SKILL.md — these are data-only directories, not full skills.
        The test reports them but does not fail on data-only voice profiles.
        """
        missing = []
        for cat in CATEGORIES:
            cat_dir = SKILLS_DIR / cat
            if not cat_dir.is_dir():
                continue
            for child in cat_dir.iterdir():
                if child.is_dir() and not (child / "SKILL.md").is_file():
                    # Voice profile dirs without SKILL.md are data-only (have profile.json)
                    is_voice_profile = child.name.startswith("voice-") and (child / "profile.json").is_file()
                    if not is_voice_profile:
                        missing.append(str(child.relative_to(ROOT)))
        assert not missing, f"Skill dirs without SKILL.md:\n" + "\n".join(missing)

    def test_no_flat_root_skills(self) -> None:
        """No skills should remain at flat root level (skills/foo/SKILL.md).

        Only category folders, KEEP_AT_ROOT dirs, and allowed root files
        should exist directly under skills/.
        """
        allowed_root = CATEGORIES | KEEP_AT_ROOT | {"INDEX.json", "INDEX.local.json", "README.md"}
        flat_skills = []
        for child in SKILLS_DIR.iterdir():
            if child.name in allowed_root:
                continue
            if child.is_dir() and (child / "SKILL.md").is_file():
                flat_skills.append(child.name)
        assert not flat_skills, f"Skills at flat root level (should be nested):\n" + "\n".join(flat_skills)

    def test_skill_mapping_covers_all_categorized_skills(self) -> None:
        """SKILL_MAPPING should cover every skill found in category folders."""
        on_disk = set()
        for cat in CATEGORIES:
            cat_dir = SKILLS_DIR / cat
            if not cat_dir.is_dir():
                continue
            for child in cat_dir.iterdir():
                if child.is_dir() and (child / "SKILL.md").is_file():
                    on_disk.add(child.name)

        mapped = set(SKILL_MAPPING.keys())
        unmapped = on_disk - mapped
        assert not unmapped, f"Skills on disk but not in SKILL_MAPPING: {sorted(unmapped)}"

    def test_all_category_folders_exist(self) -> None:
        """Every expected category folder must exist."""
        missing = [cat for cat in CATEGORIES if not (SKILLS_DIR / cat).is_dir()]
        assert not missing, f"Missing category folders: {missing}"


# ═══════════════════════════════════════════════════════════════
# 3. Cross-Reference Validation
# ═══════════════════════════════════════════════════════════════


class TestCrossReferences:
    """Verify no stale flat-path references remain."""

    @pytest.fixture(scope="class")
    def skill_names_set(self) -> set[str]:
        """Set of all known mapped skill names."""
        return set(SKILL_MAPPING.keys())

    @pytest.fixture(scope="class")
    def flat_path_pattern(self, skill_names_set: set[str]) -> re.Pattern[str]:
        """Regex matching old-style flat skill paths.

        Matches skills/SKILL_NAME/ but NOT skills/CATEGORY/SKILL_NAME/.
        Sorted by length (longest first) to avoid partial matches.
        """
        sorted_names = sorted(skill_names_set, key=len, reverse=True)
        return re.compile(r"skills/(" + "|".join(re.escape(n) for n in sorted_names) + r")/")

    @pytest.fixture(scope="class")
    def scannable_files(self) -> list[Path]:
        """Collect all .md and .py files to scan for references."""
        scan_dirs = [ROOT / d for d in ("skills", "agents", "scripts", "hooks", "docs")]
        extensions = {".md", ".py"}
        files: list[Path] = []
        for d in scan_dirs:
            if d.is_dir():
                for f in d.rglob("*"):
                    if f.is_file() and f.suffix in extensions and "__pycache__" not in str(f):
                        files.append(f)
        # Include root CLAUDE.md
        root_claude = ROOT / "CLAUDE.md"
        if root_claude.is_file():
            files.append(root_claude)
        return files

    def test_no_old_flat_paths_in_md_py_files(
        self,
        scannable_files: list[Path],
        flat_path_pattern: re.Pattern[str],
        skill_names_set: set[str],
    ) -> None:
        """No .md or .py file should reference skills/SKILL_NAME/ without the category prefix.

        Excludes the migration/fix scripts themselves and this test file.
        """
        excluded_stems = {
            "migrate-skills-to-folders",
            "migrate_skills_to_folders",
            "fix-skill-paths",
            "fix_skill_paths",
            "test_skill_reorganization",
        }
        violations = []

        for filepath in scannable_files:
            if filepath.stem in excluded_stems:
                continue
            try:
                content = filepath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for match in flat_path_pattern.finditer(content):
                skill_name = match.group(1)
                # Check the character before to verify it's NOT already prefixed with a category
                start = match.start()
                prefix_start = max(0, start - 30)
                prefix_text = content[prefix_start:start]

                # If the path is already preceded by a category, it's correct
                already_nested = any(prefix_text.endswith(f"{cat}/") for cat in CATEGORIES)
                if not already_nested:
                    rel_path = filepath.relative_to(ROOT)
                    line_num = content[:start].count("\n") + 1
                    violations.append(f"  {rel_path}:{line_num}: skills/{skill_name}/")

        assert not violations, f"Old-style flat skill paths found ({len(violations)}):\n" + "\n".join(violations[:20])

    @pytest.mark.slow
    def test_fix_skill_paths_dry_run_zero_fixes(self) -> None:
        """Running fix-skill-paths.py --dry-run should report 0 fixes needed."""
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "fix-skill-paths.py"), "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=30,
        )
        assert result.returncode == 0, f"fix-skill-paths.py failed:\n{result.stderr}"
        # Last line should indicate 0 replacements
        assert "0 references in 0 files" in result.stdout, f"fix-skill-paths.py found fixes needed:\n{result.stdout}"


# ═══════════════════════════════════════════════════════════════
# 4. Hook Regex Validation
# ═══════════════════════════════════════════════════════════════


class TestHookRegex:
    """Verify hook regex patterns match both nested and flat (KEEP_AT_ROOT) paths."""

    # Key regex patterns from hooks, reproduced to test independently
    POSTTOOL_FRONTMATTER_RE = re.compile(r"skills/(?:[^/]+/)+SKILL\.md$")
    PRETOOL_ADR_CREATION_RE = re.compile(r"/skills/(?:[^/]+/)?([^/]+)/SKILL\.md$")
    PRETOOL_UNIFIED_SKILL_RE = re.compile(r"/(skills|pipelines)/[^/]+/SKILL\.md$")
    POSTTOOL_INJECTION_RE = re.compile(r"/skills/[^/]+/SKILL\.md$")
    PRETOOL_INJECTION_RE = re.compile(r"/skills/[^/]+/SKILL\.md$")

    # Sample paths for testing
    NESTED_PATHS: ClassVar[list[str]] = [
        "/home/user/project/skills/meta/do/SKILL.md",
        "/home/user/project/skills/content/publish/SKILL.md",
        "/home/user/project/skills/engineering/go-patterns/SKILL.md",
        "/home/user/project/skills/testing/vitest-runner/SKILL.md",
    ]

    FLAT_PATHS: ClassVar[list[str]] = [
        "/home/user/project/skills/workflow/SKILL.md",
    ]

    def test_frontmatter_re_matches_nested(self) -> None:
        """posttool-skill-frontmatter-check regex must match nested paths."""
        for path in self.NESTED_PATHS:
            assert self.POSTTOOL_FRONTMATTER_RE.search(path), f"SKILL_FILE_RE failed to match nested path: {path}"

    def test_frontmatter_re_matches_flat_root(self) -> None:
        """posttool-skill-frontmatter-check regex must match KEEP_AT_ROOT paths."""
        for path in self.FLAT_PATHS:
            assert self.POSTTOOL_FRONTMATTER_RE.search(path), f"SKILL_FILE_RE failed to match flat path: {path}"

    def test_adr_creation_re_matches_nested(self) -> None:
        """pretool-adr-creation-gate regex must match nested paths."""
        for path in self.NESTED_PATHS:
            match = self.PRETOOL_ADR_CREATION_RE.search(path)
            assert match, f"_SKILL_RE failed to match: {path}"
            # The captured group should be the skill name, not the category
            skill_name = match.group(1)
            assert "/" not in skill_name, f"Captured category instead of skill name: {skill_name}"

    def test_adr_creation_re_matches_flat(self) -> None:
        """pretool-adr-creation-gate regex must match flat paths."""
        for path in self.FLAT_PATHS:
            match = self.PRETOOL_ADR_CREATION_RE.search(path)
            assert match, f"_SKILL_RE failed to match flat path: {path}"

    def test_unified_gate_re_known_limitation(self) -> None:
        """pretool-unified-gate _SKILL_PATTERN only matches flat paths.

        This documents the known limitation: the pattern /(skills|pipelines)/[^/]+/SKILL.md$
        matches skills/foo/SKILL.md but NOT skills/category/foo/SKILL.md.
        If the pattern is updated, this test should be updated too.
        """
        # Flat paths should match
        for path in self.FLAT_PATHS:
            assert self.PRETOOL_UNIFIED_SKILL_RE.search(path), f"_SKILL_PATTERN should match flat path: {path}"
        # Document current behavior for nested paths
        # The pattern [^/]+ only matches one path segment, so nested paths won't match
        # This is expected to be either fixed or handled by a different mechanism
        for path in self.NESTED_PATHS:
            matches = self.PRETOOL_UNIFIED_SKILL_RE.search(path) is not None
            if not matches:
                # Nested paths don't match — this is the known state.
                # If this changes (pattern updated), the test documents it.
                pass

    def test_injection_scan_re_known_limitation(self) -> None:
        """posttool-bash-injection-scan and pretool-prompt-injection-scanner use flat-only patterns.

        Pattern: /skills/[^/]+/SKILL.md$ — does NOT match nested.
        Document the limitation; if fixed, update tests.
        """
        for path in self.FLAT_PATHS:
            assert self.POSTTOOL_INJECTION_RE.search(path)

        # Nested paths do NOT match the flat-only pattern
        for path in self.NESTED_PATHS:
            assert not self.POSTTOOL_INJECTION_RE.search(path), f"Flat-only pattern unexpectedly matched nested: {path}"

    @pytest.mark.parametrize(
        "skill_name,category",
        [("do", "meta"), ("publish", "content"), ("go-patterns", "engineering"), ("vitest-runner", "testing")],
    )
    def test_frontmatter_re_parametrized(self, skill_name: str, category: str) -> None:
        """SKILL_FILE_RE must match specific known nested paths."""
        path = f"skills/{category}/{skill_name}/SKILL.md"
        assert self.POSTTOOL_FRONTMATTER_RE.search(path), f"Failed: {path}"


# ═══════════════════════════════════════════════════════════════
# 5. Generator Validation
# ═══════════════════════════════════════════════════════════════


class TestGenerators:
    """Verify skill index and manifest generators work correctly."""

    @pytest.mark.slow
    def test_generate_skill_index_exits_zero(self) -> None:
        """generate-skill-index.py --include-private must exit 0."""
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "generate-skill-index.py"), "--include-private"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=30,
        )
        assert result.returncode == 0, (
            f"generate-skill-index.py failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    @pytest.mark.slow
    def test_generated_index_has_expected_skill_count(self) -> None:
        """Generated INDEX.json should have ~113 skills."""
        data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        count = len(data["skills"])
        # Allow small variance (new skills may be added)
        assert count >= 100, f"Too few skills in INDEX.json: {count} (expected >=100)"
        assert count <= 150, f"Too many skills in INDEX.json: {count} (expected <=150)"

    @pytest.mark.slow
    def test_routing_manifest_exits_zero(self) -> None:
        """routing-manifest.py must exit 0 and produce output."""
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "routing-manifest.py")],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=30,
        )
        assert result.returncode == 0, (
            f"routing-manifest.py failed (exit {result.returncode}):\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert len(result.stdout) > 100, "routing-manifest.py produced no meaningful output"


# ═══════════════════════════════════════════════════════════════
# 6. Path Consistency
# ═══════════════════════════════════════════════════════════════


class TestPathConsistency:
    """Verify SKILL_MAPPING paths exist on disk."""

    @pytest.mark.parametrize(
        "skill_name,category",
        sorted(SKILL_MAPPING.items()),
        ids=[f"{cat}/{name}" for name, cat in sorted(SKILL_MAPPING.items())],
    )
    def test_mapped_skill_exists_on_disk(self, skill_name: str, category: str) -> None:
        """Every mapped skill must have either a SKILL.md or a directory on disk.

        Voice profile directories may have profile.json instead of SKILL.md.
        Skills with neither are truly missing.
        """
        skill_dir = SKILLS_DIR / category / skill_name
        skill_md = skill_dir / "SKILL.md"
        profile_json = skill_dir / "profile.json"
        assert skill_md.is_file() or profile_json.is_file(), (
            f"Missing: {skill_dir.relative_to(ROOT)}/ has neither SKILL.md nor profile.json"
        )

    @pytest.mark.parametrize("root_dir", sorted(KEEP_AT_ROOT))
    def test_keep_at_root_dirs_exist(self, root_dir: str) -> None:
        """Each KEEP_AT_ROOT directory must exist at skills root level."""
        path = SKILLS_DIR / root_dir
        assert path.is_dir(), f"Missing root dir: skills/{root_dir}/"

    def test_index_paths_match_mapping(self, index_skills: dict[str, dict]) -> None:
        """INDEX.json file paths must agree with SKILL_MAPPING categories."""
        mismatches = []
        for name, meta in index_skills.items():
            file_path = meta["file"]
            if name in SKILL_MAPPING:
                expected_prefix = f"skills/{SKILL_MAPPING[name]}/{name}/"
                if not file_path.startswith(expected_prefix):
                    mismatches.append(f"  {name}: INDEX={file_path}, expected prefix={expected_prefix}")
        assert not mismatches, f"INDEX.json paths don't match SKILL_MAPPING:\n" + "\n".join(mismatches)
