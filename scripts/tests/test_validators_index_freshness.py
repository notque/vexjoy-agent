"""Validators that read skills/INDEX.json or agents/INDEX.json refresh it first.

Each validator calls ``ensure_fresh_indexes`` (scripts/lib/index_freshness.py)
before it reads an index, and exits non-zero when the index cannot be made
current. A stale index lets a renamed or removed component resolve.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
OLD = (1_000_000_000, 1_000_000_000)


def load(script: str) -> ModuleType:
    """Import a hyphen-named validator as a module."""
    name = "freshness_" + script.replace("-", "_").removesuffix(".py")
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolves a class's module by name
    spec.loader.exec_module(module)
    return module


class Recorder:
    """Stands in for ensure_fresh_indexes: records the call, then fails."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __call__(self, repo_root: Path, surfaces: tuple[str, ...] = ("skills", "agents")) -> list[str]:
        self.calls.append((Path(repo_root).resolve(), tuple(surfaces)))
        raise RuntimeError("generator exploded")


@pytest.mark.parametrize(
    ("script", "argv", "surfaces"),
    [
        ("validate-index-integrity.py", [], ("skills", "agents")),
        ("validate-do-references.py", [], ("skills", "agents")),
        ("validate-promoted-successors.py", [], ("skills",)),
        ("validate-merged-index.py", ["--strict"], ("skills", "agents")),
    ],
)
def test_validator_refreshes_indexes_first_and_fails_when_it_cannot(
    script: str, argv: list[str], surfaces: tuple[str, ...], monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    module = load(script)
    recorder = Recorder()
    monkeypatch.setattr(module, "ensure_fresh_indexes", recorder)
    monkeypatch.setattr(sys, "argv", [script, *argv])

    assert module.main() == 1

    assert recorder.calls == [(REPO_ROOT, surfaces)]
    captured = capsys.readouterr()
    assert "generator exploded" in captured.out + captured.err


def test_workflow_conformance_refreshes_indexes_first_and_fails_when_it_cannot(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    module = load("validate-workflow-conformance.py")
    recorder = Recorder()
    monkeypatch.setattr(module, "ensure_fresh_indexes", recorder)
    monkeypatch.setattr(module, "validate_dir", lambda *_a, **_kw: pytest.fail("read an index that is not current"))

    assert module.main([]) == 1

    assert recorder.calls == [(REPO_ROOT, ("skills", "agents"))]
    captured = capsys.readouterr()
    assert "generator exploded" in captured.out + captured.err


def test_check_skill_calls_refreshes_indexes_first_and_fails_when_it_cannot(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    module = load("validate-references.py")
    sys.path.append(str(SCRIPTS / "lib"))
    import index_freshness

    recorder = Recorder()
    monkeypatch.setattr(index_freshness, "ensure_fresh_indexes", recorder)
    monkeypatch.setattr(module, "check_skill_calls", lambda: pytest.fail("read an index that is not current"))

    assert module.run_check_skill_calls(json_output=False) == 1

    assert recorder.calls == [(REPO_ROOT, ("skills", "agents"))]
    assert "generator exploded" in capsys.readouterr().out


_GENERATOR = (
    "import json\n"
    "from pathlib import Path\n"
    "entry = {{'file': '{surface}/fresh.md', 'description': 'd', 'category': 'testing'}}\n"
    "Path('{surface}/INDEX.json').write_text(json.dumps({{'{surface}': {{'fresh-{surface}': entry}}}}))\n"
)


def _stale_repo(tmp_path: Path) -> Path:
    """A repo whose indexes name ``stale-*`` and whose generators write ``fresh-*``."""
    repo = tmp_path / "repo"
    for surface, generator in (("skills", "generate-skill-index.py"), ("agents", "generate-agent-index.py")):
        (repo / surface).mkdir(parents=True)
        (repo / surface / "fresh.md").write_text("stub\n", encoding="utf-8")
        entry = {"file": f"{surface}/fresh.md", "description": "d", "category": "testing"}
        index = repo / surface / "INDEX.json"
        index.write_text(json.dumps({surface: {f"stale-{surface}": entry}}), encoding="utf-8")
        os.utime(index, OLD)
        (repo / "scripts").mkdir(exist_ok=True)
        (repo / "scripts" / generator).write_text(_GENERATOR.format(surface=surface), encoding="utf-8")
    (repo / "scripts" / "category-registry.json").write_text(json.dumps({"categories": []}), encoding="utf-8")
    return repo


def test_merged_index_validator_reads_the_regenerated_index(tmp_path: Path) -> None:
    repo = _stale_repo(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "validate-merged-index.py"),
            "--repo-root",
            str(repo),
            "--claude-dir",
            str(tmp_path / "claude"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "UNKNOWN-CATEGORY fresh-skills" in result.stdout
    assert "UNKNOWN-CATEGORY fresh-agents" in result.stdout
    assert "stale-" not in result.stdout


def test_do_references_validator_regenerates_a_stale_index(tmp_path: Path) -> None:
    repo = _stale_repo(tmp_path)

    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "validate-do-references.py"),
            "--repo-root",
            str(repo),
            "--skill-file",
            str(tmp_path / "absent.md"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert "fresh-skills" in (repo / "skills" / "INDEX.json").read_text(encoding="utf-8")
    assert "fresh-agents" in (repo / "agents" / "INDEX.json").read_text(encoding="utf-8")
