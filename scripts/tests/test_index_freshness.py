"""Tests for scripts/lib/index_freshness.py: regenerate a missing or stale generated index."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(Path(__file__).resolve().parent.parent / "lib"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import index_freshness as fresh

OLD = (1_000_000_000, 1_000_000_000)

_GENERATOR = (
    "from pathlib import Path\n"
    "Path('{surface}').mkdir(exist_ok=True)\n"
    "Path('{surface}/INDEX.json').write_text('{{\"{surface}\": {{\"regenerated\": {{}}}}}}')\n"
)

#: Stub generator that records the VEXJOY_INDEX_REGEN env var.
_GENERATOR_WITH_ENV_CHECK = (
    "import os\n"
    "from pathlib import Path\n"
    "Path('{surface}').mkdir(exist_ok=True)\n"
    "Path('{surface}/INDEX.json').write_text('{{\"{surface}\": {{\"regenerated\": {{}}}}}}')\n"
    "marker = Path('{surface}') / '.regen_env'\n"
    "marker.write_text(os.environ.get('VEXJOY_INDEX_REGEN', ''))\n"
)

#: Stub generator that writes through atomic_write_text.
_GENERATOR_ATOMIC = (
    "import sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, '{repo_root}')\n"
    "from scripts.lib.atomic_io import atomic_write_text\n"
    "Path('{surface}').mkdir(exist_ok=True)\n"
    "atomic_write_text(Path('{surface}/INDEX.json'), '{{\"{surface}\": {{\"regenerated\": {{}}}}}}')\n"
)


def make_repo(tmp_path: Path, *, generators: bool = True) -> Path:
    """A repo with one skill, one agent, both indexes current, and stub generators."""
    repo = tmp_path / "repo"
    skill = repo / "skills" / "meta" / "one"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: one\n---\n", encoding="utf-8")
    (repo / "agents").mkdir()
    (repo / "agents" / "a.md").write_text("---\nname: a\n---\n", encoding="utf-8")
    (repo / "scripts").mkdir()
    if generators:
        for surface, name in (("skills", "generate-skill-index.py"), ("agents", "generate-agent-index.py")):
            (repo / "scripts" / name).write_text(_GENERATOR.format(surface=surface), encoding="utf-8")
    for path in sorted(repo.rglob("*")):
        os.utime(path, OLD)
    for surface in fresh.SURFACES:
        (repo / surface / "INDEX.json").write_text(f'{{"{surface}": {{"original": {{}}}}}}', encoding="utf-8")
        os.utime(repo / surface, OLD)
    return repo


def index_text(repo: Path, surface: str) -> str:
    return (repo / surface / "INDEX.json").read_text(encoding="utf-8")


def test_current_indexes_are_left_alone(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    assert fresh.ensure_fresh_indexes(repo) == []
    assert "original" in index_text(repo, "skills")
    assert "original" in index_text(repo, "agents")


def test_missing_index_is_generated(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "agents" / "INDEX.json").unlink()

    assert fresh.ensure_fresh_indexes(repo) == ["agents"]
    assert "regenerated" in index_text(repo, "agents")
    assert "original" in index_text(repo, "skills")


def test_edited_skill_makes_the_skills_index_stale(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    os.utime(repo / "skills" / "INDEX.json", (OLD[0] + 10, OLD[1] + 10))
    os.utime(repo / "skills" / "meta" / "one" / "SKILL.md", (OLD[0] + 20, OLD[1] + 20))

    assert fresh.ensure_fresh_indexes(repo) == ["skills"]
    assert "regenerated" in index_text(repo, "skills")


def test_removed_agent_makes_the_agents_index_stale(tmp_path: Path) -> None:
    """Deleting a component changes only its directory's mtime."""
    repo = make_repo(tmp_path)
    os.utime(repo / "agents" / "INDEX.json", (OLD[0] + 10, OLD[1] + 10))
    (repo / "agents" / "a.md").unlink()

    assert fresh.newer_source(repo, "agents") == repo / "agents"
    assert fresh.ensure_fresh_indexes(repo, ["agents"]) == ["agents"]


def test_changed_generator_makes_the_index_stale(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    os.utime(repo / "skills" / "INDEX.json", (OLD[0] + 10, OLD[1] + 10))
    os.utime(repo / "scripts" / "generate-skill-index.py", (OLD[0] + 20, OLD[1] + 20))

    assert fresh.ensure_fresh_indexes(repo, ["skills"]) == ["skills"]


def test_missing_index_without_generator_raises(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, generators=False)
    (repo / "skills" / "INDEX.json").unlink()

    with pytest.raises(RuntimeError, match="cannot be generated"):
        fresh.ensure_fresh_indexes(repo)


def test_stale_index_without_generator_is_kept(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, generators=False)
    os.utime(repo / "skills" / "INDEX.json", (OLD[0] - 10, OLD[1] - 10))

    assert fresh.ensure_fresh_indexes(repo) == []
    assert "original" in index_text(repo, "skills")


def test_failing_generator_raises_with_its_stderr(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "agents" / "INDEX.json").unlink()
    (repo / "scripts" / "generate-agent-index.py").write_text(
        "import sys\nprint('boom', file=sys.stderr)\nsys.exit(3)\n", encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match=r"exited 3: boom"):
        fresh.ensure_fresh_indexes(repo, ["agents"])


def test_generator_that_writes_nothing_raises_when_index_is_missing(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "skills" / "INDEX.json").unlink()
    (repo / "scripts" / "generate-skill-index.py").write_text("pass\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="did not create required index"):
        fresh.ensure_fresh_indexes(repo, ["skills"])


# --- R2 tests: env var and cycle bounding ---


def _make_repo_with_env_check(tmp_path: Path, surface: str = "agents") -> Path:
    """Build a repo whose generator records the regen env var."""
    repo = tmp_path / "repo"
    (repo / surface).mkdir(parents=True)
    (repo / surface / "a.md").write_text("---\nname: a\n---\n", encoding="utf-8")
    (repo / "scripts").mkdir()
    (repo / "scripts" / fresh._GENERATORS[surface]).write_text(
        _GENERATOR_WITH_ENV_CHECK.format(surface=surface), encoding="utf-8"
    )
    # Frontmatter stub (source list needs it).
    (repo / "scripts" / "lib").mkdir(parents=True)
    (repo / "scripts" / "lib" / "frontmatter.py").write_text("", encoding="utf-8")
    for path in sorted(repo.rglob("*")):
        os.utime(path, OLD)
    return repo


def test_ensure_fresh_passes_regen_env_var(tmp_path: Path) -> None:
    """ensure_fresh_indexes passes VEXJOY_INDEX_REGEN=1 to the generator."""
    repo = _make_repo_with_env_check(tmp_path, "agents")
    # Index is missing, so generator runs.
    fresh.ensure_fresh_indexes(repo, ["agents"])
    marker = repo / "agents" / ".regen_env"
    assert marker.read_text(encoding="utf-8") == "1"


def _make_repo_with_atomic_generator(tmp_path: Path, surface: str = "agents") -> Path:
    """Build a repo whose stub generator writes through atomic_write_text."""
    repo = tmp_path / "repo"
    (repo / surface).mkdir(parents=True)
    (repo / surface / "a.md").write_text("---\nname: a\n---\n", encoding="utf-8")
    (repo / "scripts").mkdir()
    (repo / "scripts" / fresh._GENERATORS[surface]).write_text(
        _GENERATOR_ATOMIC.format(surface=surface, repo_root=str(_REPO_ROOT)),
        encoding="utf-8",
    )
    (repo / "scripts" / "lib").mkdir(parents=True)
    (repo / "scripts" / "lib" / "frontmatter.py").write_text("", encoding="utf-8")
    for path in sorted(repo.rglob("*")):
        os.utime(path, OLD)
    return repo


def test_atomic_write_does_not_create_loop(tmp_path: Path) -> None:
    """After ensure_fresh_indexes runs a generator that uses atomic_write_text, newer_source returns None."""
    repo = _make_repo_with_atomic_generator(tmp_path, "agents")
    # Index is missing, so ensure_fresh_indexes runs the stub generator.
    fresh.ensure_fresh_indexes(repo, ["agents"])
    assert fresh.newer_source(repo, "agents") is None


def _load_gsi():
    """Load generate-skill-index.py as a module."""
    import importlib.util

    script = _REPO_ROOT / "scripts" / "generate-skill-index.py"
    spec = importlib.util.spec_from_file_location("generate_skill_index", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestShouldRunDriftGate:
    """Tests for the extracted _should_run_drift_gate function."""

    def test_default_case_returns_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default args (no --output, same repo root, no env var) returns True."""
        monkeypatch.delenv("VEXJOY_INDEX_REGEN", raising=False)
        mod = _load_gsi()
        script_dir = _REPO_ROOT / "scripts"
        assert mod._should_run_drift_gate(None, script_dir.parent.resolve(), script_dir) is True

    def test_regen_env_var_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """VEXJOY_INDEX_REGEN=1 makes the gate return False."""
        monkeypatch.setenv("VEXJOY_INDEX_REGEN", "1")
        mod = _load_gsi()
        script_dir = _REPO_ROOT / "scripts"
        assert mod._should_run_drift_gate(None, script_dir.parent.resolve(), script_dir) is False

    def test_custom_output_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A non-None output path makes the gate return False."""
        monkeypatch.delenv("VEXJOY_INDEX_REGEN", raising=False)
        mod = _load_gsi()
        script_dir = _REPO_ROOT / "scripts"
        assert mod._should_run_drift_gate("/tmp/custom.json", script_dir.parent.resolve(), script_dir) is False

    def test_different_repo_root_returns_false(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A repo_root that differs from the script's own checkout returns False."""
        monkeypatch.delenv("VEXJOY_INDEX_REGEN", raising=False)
        mod = _load_gsi()
        script_dir = _REPO_ROOT / "scripts"
        assert mod._should_run_drift_gate(None, tmp_path, script_dir) is False
