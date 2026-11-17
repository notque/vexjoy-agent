"""Tests for validate-decomposition.py — runs the CLI as a subprocess on tmp_path fixtures."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "validate-decomposition.py"

BEFORE_SKILL = """\
---
name: example
---

# Example Skill

## Phase 1: Setup

Do setup things.

```python
print("hello")
```

## Error Handling

Handle errors.

| Signal | File |
|---|---|
| setup | references/setup.md |
"""

AFTER_SKILL = """\
---
name: example
---

# Example Skill

## Phase 1: Setup

See references/setup.md.

## Error Handling

Handle errors.

| Signal | File |
|---|---|
| setup | references/setup.md |
"""

REF_CONTENT = """\
# Setup Reference

Do setup things.

```python
print("hello")
```
"""


def _run(
    before: Path,
    after: Path,
    refs: Path,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    """Run the validator script and return the completed process."""
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--before",
        str(before),
        "--after",
        str(after),
        "--refs",
        str(refs),
        *extra_args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def test_passing_input(tmp_path: Path) -> None:
    """All content preserved, routes present, structure intact: exit 0."""
    before = tmp_path / "before.md"
    before.write_text(BEFORE_SKILL, encoding="utf-8")
    after = tmp_path / "after.md"
    after.write_text(AFTER_SKILL, encoding="utf-8")
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "setup.md").write_text(REF_CONTENT, encoding="utf-8")

    result = _run(before, after, refs)
    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_missing_code_block_fails(tmp_path: Path) -> None:
    """Code block from the original missing in after-state: exit 1, names the check."""
    before = tmp_path / "before.md"
    before.write_text(BEFORE_SKILL, encoding="utf-8")
    after = tmp_path / "after.md"
    after.write_text(AFTER_SKILL, encoding="utf-8")
    # Reference file without the code block
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "setup.md").write_text("# Setup Reference\n\nDo setup things.\n", encoding="utf-8")

    result = _run(before, after, refs)
    assert result.returncode == 1
    assert "code-block" in result.stdout.lower() or "FAIL" in result.stdout


def test_missing_before_file_fails(tmp_path: Path) -> None:
    """Non-existent --before file: exit 1, error on stderr."""
    after = tmp_path / "after.md"
    after.write_text(AFTER_SKILL, encoding="utf-8")
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "setup.md").write_text(REF_CONTENT, encoding="utf-8")

    result = _run(tmp_path / "nonexistent.md", after, refs)
    assert result.returncode == 1
    assert "not found" in result.stderr.lower()


def test_missing_route_entry_fails(tmp_path: Path) -> None:
    """A reference file with no loading table entry: exit 1, names the file."""
    before = tmp_path / "before.md"
    before.write_text(BEFORE_SKILL, encoding="utf-8")
    after = tmp_path / "after.md"
    # After-skill with no loading table at all
    after.write_text(
        "---\nname: example\n---\n\n# Example Skill\n\n## Phase 1: Setup\n\nSee refs.\n\n## Error Handling\n\nOk.\n",
        encoding="utf-8",
    )
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "setup.md").write_text(BEFORE_SKILL, encoding="utf-8")

    result = _run(before, after, refs)
    assert result.returncode == 1
    assert "setup.md" in result.stdout
