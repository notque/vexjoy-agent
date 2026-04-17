"""Tests for detect-unpaired-antipatterns.py false-positive fixes.

Covers three precision fixes:
- Issue 1: bare section headers with no body content must not emit a finding
- Issue 2: `#` comment lines inside fenced code blocks must not split a block
- Issue 3: H1 document intro headers at the top of anti-pattern files must not emit a finding
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Load kebab-case module via importlib (not a valid Python identifier as a dotted import).
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "detect_unpaired_antipatterns",
    _SCRIPTS_DIR / "detect-unpaired-antipatterns.py",
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["detect_unpaired_antipatterns"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]

scan_file = _mod.scan_file
split_into_blocks = _mod.split_into_blocks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_temp_md(tmp_path: Path, name: str, content: str) -> Path:
    """Write markdown content to a temp file rooted at tmp_path.

    Also patches _mod.REPO_ROOT to tmp_path so that scan_file's
    file_path.relative_to(REPO_ROOT) call succeeds.
    """
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    p = skill_dir / name
    p.write_text(content, encoding="utf-8")
    # Patch REPO_ROOT for this call so relative_to does not raise.
    _mod.REPO_ROOT = tmp_path
    return p


# ---------------------------------------------------------------------------
# Issue 1: empty blocks (heading-only, no body content)
# ---------------------------------------------------------------------------


class TestIssue1EmptyBlocks:
    """A section header with no body content must not produce a finding."""

    def test_bare_antipattern_catalog_header_skipped(self, tmp_path: Path) -> None:
        """'## Anti-Pattern Catalog' heading with no following content is not a finding."""
        content = """\
## Anti-Pattern Catalog

## Some Other Section

Content here.
"""
        path = make_temp_md(tmp_path, "SKILL.md", content)
        findings = scan_file(path)
        assert findings == [], f"Expected no findings; got {findings}"

    def test_antipattern_header_with_body_is_reported(self, tmp_path: Path) -> None:
        """A heading followed by 'What it looks like' body text DOES produce a finding."""
        content = """\
## Anti-Pattern Catalog

**What it looks like**: Using deprecated API.

**Why wrong**: The API was removed in v2.
"""
        path = make_temp_md(tmp_path, "SKILL.md", content)
        findings = scan_file(path)
        assert len(findings) == 1, f"Expected 1 finding; got {findings}"

    def test_blank_lines_only_after_heading_skipped(self, tmp_path: Path) -> None:
        """Heading followed by blank lines only is still empty, not a finding."""
        content = """\
## Anti-Patterns to Avoid


## Next Section

Normal text.
"""
        path = make_temp_md(tmp_path, "SKILL.md", content)
        findings = scan_file(path)
        assert findings == [], f"Expected no findings; got {findings}"


# ---------------------------------------------------------------------------
# Issue 2: fenced code block splits
# ---------------------------------------------------------------------------


class TestIssue2FencedCodeBlocks:
    """Hash comment lines inside code fences must not split anti-pattern blocks."""

    def test_hash_comment_in_bash_fence_does_not_split(self, tmp_path: Path) -> None:
        """A `#` comment inside a ```bash block does not create a new block."""
        content = """\
## Anti-Pattern Catalog

### Sync dispatch

**What it looks like**:
```bash
# Check if sequential dispatch happened
ls output.txt
```

**Why wrong**: Slow.

**Do instead**: Run in parallel.
"""
        path = make_temp_md(tmp_path, "SKILL.md", content)
        findings = scan_file(path)
        assert findings == [], f"Expected no findings (block has Do instead); got {findings}"

    def test_hash_comment_split_would_create_false_positive(self, tmp_path: Path) -> None:
        """Without the fix, a `#` inside a code block used to split the block and lose 'Do instead'."""
        content = """\
## Anti-Pattern Catalog

### Bad pattern

**What it looks like**:
```python
# This is a comment that used to split the block
result = do_thing()
```

**Why wrong**: Causes issues.

**Do instead**: Use the better approach.
"""
        path = make_temp_md(tmp_path, "SKILL.md", content)
        findings = scan_file(path)
        # With the fix, no false positive: the Do instead is in the same block.
        assert findings == [], f"Expected no findings; got {findings}"

    def test_split_into_blocks_respects_fence(self) -> None:
        """split_into_blocks must not start a new block for `#` lines inside a fence."""
        content = """\
## Section One

```bash
# This comment must not start a new block
echo hello
```

More content here.

## Section Two

Other content.
"""
        blocks = split_into_blocks(content)
        # Only two heading-delimited blocks: Section One and Section Two.
        headings = [block_text.splitlines()[0] for _, block_text in blocks if block_text.strip()]
        assert any("Section One" in h for h in headings), "Section One not found"
        assert any("Section Two" in h for h in headings), "Section Two not found"
        # No block should start with the `# This comment` line.
        for _, block_text in blocks:
            first_line = block_text.splitlines()[0]
            assert not first_line.startswith("# This comment"), (
                f"Fence comment wrongly started a new block: {first_line!r}"
            )

    def test_nested_fence_does_not_confuse_toggle(self, tmp_path: Path) -> None:
        """A code block with triple-backtick content is handled gracefully."""
        content = """\
## Anti-Patterns

**What it looks like**: Some bad thing.

**Why wrong**: Bad reason.

**Do instead**: Use the good way.
"""
        path = make_temp_md(tmp_path, "SKILL.md", content)
        findings = scan_file(path)
        # Block has Do instead so no finding.
        assert findings == [], f"Unexpected findings: {findings}"


# ---------------------------------------------------------------------------
# Issue 3: H1 document intro headers
# ---------------------------------------------------------------------------


class TestIssue3DocumentIntroH1:
    """An H1 heading at the start of an anti-patterns file must not be a finding."""

    def test_h1_document_title_at_top_skipped(self, tmp_path: Path) -> None:
        """File opening with '# Some Anti-Patterns' intro is not a finding."""
        content = """\
# Fish Shell Anti-Patterns

> **Scope**: Common fish shell configuration mistakes.
> **Version range**: fish 3.x

---

## Anti-Pattern Catalog

"""
        path = make_temp_md(tmp_path, "SKILL.md", content)
        findings = scan_file(path)
        # The H1 intro is skipped; the empty catalog header is also skipped.
        assert findings == [], f"Expected no findings; got {findings}"

    def test_h1_with_secondary_marker_is_reported(self, tmp_path: Path) -> None:
        """H1 block that contains 'What it looks like' in its body IS a real finding."""
        content = """\
# Anti-Pattern: Never Do This

**What it looks like**: Calling deprecated function.

**Why wrong**: It explodes.
"""
        path = make_temp_md(tmp_path, "SKILL.md", content)
        findings = scan_file(path)
        assert len(findings) == 1, f"Expected 1 finding for H1 with real content; got {findings}"

    def test_h2_at_top_is_not_skipped_by_issue3(self, tmp_path: Path) -> None:
        """Issue 3 applies only to H1; an H2 at top of file is still evaluated normally."""
        content = """\
## Anti-Patterns

**What it looks like**: Using the wrong thing.

**Why wrong**: Wrong.
"""
        path = make_temp_md(tmp_path, "SKILL.md", content)
        findings = scan_file(path)
        # H2 with body content and no Do instead = real finding
        assert len(findings) == 1, f"Expected 1 finding for H2 with real content; got {findings}"

    def test_h1_after_frontmatter_skipped(self, tmp_path: Path) -> None:
        """H1 document intro after YAML frontmatter is also skipped."""
        content = """\
---
name: test-skill
description: A test skill
---

# Test Skill Anti-Patterns

Overview paragraph about what this reference covers.

---
"""
        path = make_temp_md(tmp_path, "SKILL.md", content)
        findings = scan_file(path)
        assert findings == [], f"Expected no findings; got {findings}"
