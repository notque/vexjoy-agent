"""docs-sync-checker targets docs that exist and finds seeded drift in them.

Its target list once named agents/README.md and commands/README.md, which no
longer existed, so every agent and command came back "missing" (120 false
issues at HEAD). These tests pin the target list to real files and check
detection on a fixture repo.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "skills" / "meta" / "docs-sync-checker" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Unique module names: other skills ship their own validate.py.
parse_docs = _load("docs_sync_parse_docs", "parse_docs.py")
scan_tools = _load("docs_sync_scan_tools", "scan_tools.py")
validate = _load("docs_sync_validate", "validate.py")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_every_primary_doc_exists_in_repo() -> None:
    missing = [rel for rel in parse_docs.PRIMARY_DOCS.values() if not (REPO_ROOT / rel).is_file()]
    assert missing == [], f"docs-sync-checker targets missing files: {missing}"


def test_validator_passes_at_head() -> None:
    proc = subprocess.run([sys.executable, str(SCRIPTS / "validate.py")], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_validator_fails_when_a_target_is_missing(tmp_path: Path) -> None:
    results = validate.validate_primary_docs(repo_root=tmp_path)
    failed = [name for name, passed, _ in results if not passed]
    assert "primary doc exists: docs/routing-map.md" in failed
    assert "primary doc exists: docs/REFERENCE.md" in failed


def test_parser_exits_2_on_missing_target(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "skills.md", "| Skill | Description |\n|---|---|\n")
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "parse_docs.py"), "--repo-root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "docs/routing-map.md" in proc.stderr


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    """A repo with seeded drift in each primary doc."""
    skill = "---\nname: {n}\ndescription: {n} skill\n{extra}routing:\n  category: x\n---\n"
    _write(tmp_path / "skills" / "x" / "listed" / "SKILL.md", skill.format(n="listed", extra=""))
    _write(tmp_path / "skills" / "x" / "unlisted" / "SKILL.md", skill.format(n="unlisted", extra=""))
    _write(
        tmp_path / "skills" / "x" / "retired" / "SKILL.md",
        skill.format(n="retired", extra="promoted_to: listed\n"),
    )
    _write(tmp_path / "agents" / "alpha-engineer.md", "---\nname: alpha-engineer\ndescription: Alpha\n---\n")
    _write(tmp_path / "agents" / "base-instructions.md", "# Shared prompt, no frontmatter\n")
    _write(tmp_path / "commands" / "go.md", "---\ndescription: Go command\n---\n# /go\n")
    _write(tmp_path / "commands" / "new.md", "---\ndescription: New command\n---\n# /new\n")
    _write(
        tmp_path / "commands" / "block.md",
        "---\nname: block\ndescription: |\n  Block scalar\n  description.\nversion: 1.0.0\n---\n# /block\n",
    )

    _write(
        tmp_path / "docs" / "skills.md",
        "# Skills\n\n## X\n\n| Skill | Description | Invoke |\n|---|---|---|\n| `listed` | Listed | |\n",
    )
    _write(
        tmp_path / "docs" / "routing-map.md",
        "# Routing Map\n\n## AGENTS (2)\n\n| name | when |\n|---|---|\n"
        "| alpha-engineer | Alpha |\n| ghost-engineer | Deleted |\n\n## SKILLS (1)\n\n"
        "| name | when |\n|---|---|\n| not-an-agent | Skill row |\n",
    )
    _write(
        tmp_path / "docs" / "REFERENCE.md",
        "# Reference\n\n## Slash Commands\n\n| Command | Purpose |\n|---|---|\n| `/go` | Go |\n\n"
        "| Want This? | Try This |\n|---|---|\n| Testing | `/do test` |\n\n## Other\n\n"
        "| Command | Purpose |\n|---|---|\n| `/outside` | Not in the section |\n",
    )
    return tmp_path


def _issues(repo: Path) -> dict:
    scan = scan_tools.ToolScanner(repo).scan_all()
    parser = parse_docs.DocumentationParser(repo)
    documented = {doc: parser.parse_primary(kind) for kind, doc in parse_docs.PRIMARY_DOCS.items()}
    return parser.detect_issues(scan, documented)


def test_seeded_drift_is_found_by_name(fixture_repo: Path) -> None:
    issues = _issues(fixture_repo)
    missing = {(i["tool_type"], i["tool_name"]) for i in issues["missing_entries"]}
    stale = {(i["tool_type"], i["tool_name"]) for i in issues["stale_entries"]}
    assert missing == {("skill", "unlisted"), ("command", "new"), ("command", "block")}
    assert stale == {("agent", "ghost-engineer")}


def test_fixes_point_at_generator_or_reference_row(fixture_repo: Path) -> None:
    issues = _issues(fixture_repo)
    fixes = {i["tool_name"]: i["suggested_fix"] for i in issues["missing_entries"] + issues["stale_entries"]}
    assert "scripts/generate-skills-doc.py" in fixes["unlisted"]
    assert "scripts/generate-routing-map.py" in fixes["ghost-engineer"]
    assert "| `/new` | New command |" in fixes["new"]
    assert "| `/block` | Block scalar description. |" in fixes["block"]


@pytest.mark.parametrize(
    ("doc", "old", "new"),
    [
        ("docs/routing-map.md", "## AGENTS (2)", "## Agents (2)"),
        ("docs/REFERENCE.md", "## Slash Commands", "## Commands"),
        ("docs/skills.md", "| `listed` |", "| listed |"),
    ],
)
def test_zero_entries_for_a_type_exits_2(fixture_repo: Path, doc: str, old: str, new: str) -> None:
    """A moved section or changed first cell is an error, not an empty documented set."""
    path = fixture_repo / doc
    path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "parse_docs.py"), "--repo-root", str(fixture_repo)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "Entry count is zero for a type" in proc.stderr
    assert doc in proc.stderr
    failed = [name for name, passed, _ in validate.validate_primary_docs_parse(fixture_repo) if not passed]
    assert failed == [f"primary doc parses: {doc}"]


def test_head_pipeline_reports_no_false_layout_issues(tmp_path: Path) -> None:
    """No agent or command is reported missing just because its doc moved."""
    scan_out = tmp_path / "scan.json"
    subprocess.run(
        [sys.executable, str(SCRIPTS / "scan_tools.py"), "--repo-root", str(REPO_ROOT), "--output", str(scan_out)],
        capture_output=True,
        check=False,
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "parse_docs.py"),
            "--repo-root",
            str(REPO_ROOT),
            "--scan-results",
            str(scan_out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in (0, 1), proc.stderr
    documented = json.loads(proc.stdout)["documented"]
    for rel in parse_docs.PRIMARY_DOCS.values():
        assert documented[rel], f"parsed 0 entries from {rel}; the parser no longer reads its format"
