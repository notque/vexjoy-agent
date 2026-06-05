"""
Pytest configuration and fixtures for voice analyzer and validator tests.

Provides:
- Path fixtures for the fixtures directory
- Content fixtures for sample good/bad files
- Expected output fixtures for golden file testing
- Skill-eval-ablation fixtures (ADR skill-eval-pr-ablation): temp_db variants,
  mock_skill_tree, mock_evals, git_range
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Skill-eval-ablation fixtures (ADR: skill-eval-pr-ablation)
#
# Shared by test_detect_skill_changes.py and test_skill_eval_ablation.py.
# They mirror the throwaway-DB + throwaway-git-repo patterns already used in
# hooks/tests/test_routing_decision_recorder.py and
# scripts/tests/test_check_index_colocation.py.
# ---------------------------------------------------------------------------

_LIB_DIR = Path(__file__).resolve().parents[2] / "hooks" / "lib"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a git command in `repo`, raising on failure."""
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )


def _skill_md(name: str, version: str = "1.0.0", body: str = "Body.") -> str:
    """Minimal valid SKILL.md frontmatter (name + version) plus a body."""
    return f"---\nname: {name}\nversion: {version}\ndescription: {name} skill.\n---\n\n# {name}\n\n{body}\n"


def _init_temp_db(db_dir: Path, monkeypatch, *, envelope: bool):
    """Create a throwaway learning.db under db_dir from the real schema.

    PR-A shipped the envelope as a dedicated `telemetry_runs` table (schema v5+),
    not as columns on `learnings`. `init_db()` builds that table. So the
    with-envelope DB is just the real, fully-migrated schema. The no-envelope DB
    simulates a pre-PR-A install by dropping `telemetry_runs` after init.

    Returns the learning.db path. Points CLAUDE_LEARNING_DIR at db_dir and
    resets the learning_db_v2 init cache so the DB is built fresh.
    """
    db_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    if str(_LIB_DIR) not in sys.path:
        sys.path.insert(0, str(_LIB_DIR))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    db_path = db_dir / "learning.db"

    if not envelope:
        # Simulate a pre-PR-A DB: remove the telemetry_runs table so the runner's
        # envelope probe takes the degraded (log-file) path.
        import sqlite3

        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS telemetry_runs")
            conn.commit()
    return db_path


@pytest.fixture
def temp_db_no_envelope(tmp_path, monkeypatch) -> Path:
    """Throwaway learning.db simulating pre-PR-A (no telemetry_runs table)."""
    return _init_temp_db(tmp_path / "learning_noenv", monkeypatch, envelope=False)


@pytest.fixture
def temp_db_with_envelope(tmp_path, monkeypatch) -> Path:
    """Throwaway learning.db with PR-A's telemetry_runs table (real schema)."""
    return _init_temp_db(tmp_path / "learning_env", monkeypatch, envelope=True)


@pytest.fixture
def mock_skill_tree(tmp_path) -> Path:
    """A skills/ tree: skills/<cat>/<name>/SKILL.md with minimal frontmatter.

    Returns the root holding skills/. Names chosen to exercise the mapper.
    """
    root = tmp_path / "tree"
    layout = {
        ("process", "planning"): "planning",
        ("process", "quick"): "quick",
        ("meta", "skill-creator"): "skill-creator",
    }
    for (cat, dirname), name in layout.items():
        d = root / "skills" / cat / dirname
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(_skill_md(name), encoding="utf-8")
    return root


@pytest.fixture
def mock_evals(tmp_path) -> Path:
    """An evals/ tree exercising all three resolution rules.

    - evals/planning/            -> exact-dir match for skill "planning"
    - evals/quick-eval/          -> "-eval" suffix match for skill "quick"
    - evals/grouped/README.md    -> README whole-word mention of "skill-creator"
    Returns the root holding evals/.
    """
    root = tmp_path / "evalsroot"
    (root / "evals" / "planning").mkdir(parents=True)
    (root / "evals" / "planning" / "README.md").write_text("# planning eval\n", encoding="utf-8")
    (root / "evals" / "quick-eval").mkdir(parents=True)
    (root / "evals" / "quick-eval" / "README.md").write_text("# quick eval\n", encoding="utf-8")
    (root / "evals" / "grouped").mkdir(parents=True)
    (root / "evals" / "grouped" / "README.md").write_text(
        "# grouped\n\nTests the skill-creator skill against baseline.\n", encoding="utf-8"
    )
    return root


@pytest.fixture
def git_range(tmp_path):
    """A git repo with a base commit and a head commit that edits three skills.

    Builds skills/ and evals/ trees, commits the base, edits three skills
    (two map to evals, one is uncovered), commits the head. Returns a dict:
    {repo, base, head} where base/head are full SHAs.
    """
    repo = tmp_path / "repo"
    (repo / "skills").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.test")
    _git(repo, "config", "user.name", "t")

    # Three skills; planning + quick map to evals, orphan is uncovered.
    skills = {
        ("process", "planning"): "planning",
        ("process", "quick"): "quick",
        ("process", "orphan"): "orphan",
    }
    for (cat, dirname), name in skills.items():
        d = repo / "skills" / cat / dirname
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(_skill_md(name, body="Base body."), encoding="utf-8")

    # Evals: exact-dir for planning, -eval suffix for quick. No eval for orphan.
    (repo / "evals" / "planning").mkdir(parents=True)
    (repo / "evals" / "planning" / "README.md").write_text("# planning\n", encoding="utf-8")
    (repo / "evals" / "quick-eval").mkdir(parents=True)
    (repo / "evals" / "quick-eval" / "README.md").write_text("# quick\n", encoding="utf-8")

    # A non-SKILL.md file that also changes (must be ignored by the mapper).
    (repo / "README.md").write_text("base\n", encoding="utf-8")

    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()

    # Head: edit all three SKILL.md bodies + the non-skill file.
    for (cat, dirname), name in skills.items():
        f = repo / "skills" / cat / dirname / "SKILL.md"
        f.write_text(_skill_md(name, version="1.1.0", body="Head body changed."), encoding="utf-8")
    (repo / "README.md").write_text("head\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "head")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()

    return {"repo": repo, "base": base, "head": head}


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_voice_good(fixtures_dir: Path) -> str:
    """Load sample content that should pass Voice A validation."""
    return (fixtures_dir / "sample_voice_good.md").read_text()


@pytest.fixture
def sample_voice_bad(fixtures_dir: Path) -> str:
    """Load sample content that should fail Voice A validation."""
    return (fixtures_dir / "sample_voice_bad.md").read_text()


@pytest.fixture
def expected_voice_profile(fixtures_dir: Path) -> dict:
    """Load expected voice analysis profile for Voice A sample."""
    return json.loads((fixtures_dir / "expected_voice_profile.json").read_text())


@pytest.fixture
def expected_violations(fixtures_dir: Path) -> dict:
    """Load expected validation violations output."""
    return json.loads((fixtures_dir / "expected_violations.json").read_text())


@pytest.fixture
def sample_text_short() -> str:
    """Short sample text for unit tests."""
    return "The fire burns bright. It warms the soul."


@pytest.fixture
def sample_text_varied() -> str:
    """Sample text with varied sentence lengths for rhythm tests."""
    return """Sometimes the brightest lights shine in the darkest corners.
    She inspires.
    She grows.
    She shines.
    The community came together to celebrate this moment, and what a celebration it was, filled with joy and laughter and the kind of warmth that only comes from shared experience.
    Together, we rise."""


@pytest.fixture
def sample_text_monotonous() -> str:
    """Sample text with monotonous sentence lengths for rhythm violation tests."""
    return """The match was exciting. The crowd was loud. The performers were great. The finish was good. The show was fun. The ending was nice. The fans were happy."""


@pytest.fixture
def sample_text_with_contractions() -> str:
    """Sample text containing contractions."""
    return """She can't stop smiling. It's wonderful to see. They've worked hard. We're proud of them. That's the spirit."""


@pytest.fixture
def sample_text_with_em_dashes() -> str:
    """Sample text containing em-dashes (should always be flagged)."""
    return """The match — one of the best of the year — set a new standard.
    The underdog finally won — and the crowd erupted."""


@pytest.fixture
def sample_text_with_banned_words() -> str:
    """Sample text containing banned words."""
    return """Let me delve into this exciting journey through the robust ecosystem of technology.
    In today's dynamic landscape, we explore the innovative approaches that leverage cutting-edge techniques."""


@pytest.fixture
def voice_a_profile() -> dict:
    """Expected voice profile characteristics for Voice A."""
    return {
        "voice": "voice_a",
        "metrics": {
            "sentence_length_distribution": {
                "short": {"min": 3, "max": 10},
                "medium": {"min": 11, "max": 20},
                "long": {"min": 21, "max": 30},
                "very_long": {"min": 31},
            },
            "comma_density_target": {"min": 0.08, "max": 0.15},
            "contraction_rate_target": {"min": 0.02, "max": 0.10},
            "fragment_rate_target": {"min": 0.05, "max": 0.20},
        },
        "patterns": {
            "uses_light_imagery": True,
            "uses_community_language": True,
            "uses_triple_rhythm": True,
            "allows_sentence_start_conjunctions": True,
        },
    }


@pytest.fixture
def voice_b_profile() -> dict:
    """Expected voice profile characteristics for Voice B."""
    return {
        "voice": "voice_b",
        "metrics": {
            "sentence_length_distribution": {
                "short": {"min": 3, "max": 10},
                "medium": {"min": 11, "max": 20},
                "long": {"min": 21, "max": 30},
                "very_long": {"min": 31},
            },
            "comma_density_target": {"min": 0.05, "max": 0.12},
            "contraction_rate_target": {"min": 0.01, "max": 0.08},
        },
        "patterns": {
            "uses_systems_metaphors": True,
            "uses_constraint_accumulation": True,
            "uses_calibration_questions": True,
            "uses_second_person": True,
        },
    }
