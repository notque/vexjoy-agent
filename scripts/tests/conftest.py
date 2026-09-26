"""
Pytest configuration and shared fixtures.

Provides:
- Jev state isolation (autouse): every test gets its own JEV_STATE_DIR so
  no test reads or writes the real ~/.claude/state breaker/cache files.
- Live-key isolation (autouse): gateway keys and transport switches are cleared
  so no test calls a live service because the shell had a key set.
- Path fixtures for the fixtures directory
- Content fixtures for sample good/bad files
- Expected output fixtures for golden file testing
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Jev state isolation — autouse so every test is sandboxed
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_jev_state(tmp_path, monkeypatch):
    """Point JEV_STATE_DIR at a per-test temp directory.

    Ensures no test reads or writes the real ``~/.claude/state`` breaker
    or cache files. Also clears the in-process breaker flag and forces the
    cache connection to reopen against the new path.
    """
    state_dir = tmp_path / "jev_state"
    state_dir.mkdir()
    monkeypatch.setenv("JEV_STATE_DIR", str(state_dir))

    # Clear in-process breaker so a previous test's trip does not leak.
    scripts_dir = Path(__file__).resolve().parents[1]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        import jev_router_common as _jrc

        _jrc._jev_down = None
        # Force the cache connection to reopen on the new path.
        if _jrc._cache_conn is not None:
            try:
                _jrc._cache_conn.close()
            except Exception:
                pass
            _jrc._cache_conn = None
            _jrc._cache_conn_path = None
    except Exception:
        pass  # Module may not be importable in every test context


# Live-service credentials and transport switches. A developer shell often has
# these set; any of them turns an offline test into a live call. Tests that need
# a key set it with monkeypatch.setenv, which runs after this fixture.
_LIVE_KEY_ENV = (
    "AI_GATEWAY_API_KEY",
    "TYPESAFE_API_KEY",
    "JEV_TRANSPORT",
    "JEV_KEY_ONLY",
    "TEXT_MODEL_API_KEY",
    "ANTHROPIC_API_KEY",
)


@pytest.fixture(autouse=True)
def _no_live_keys(monkeypatch):
    """Clear live gateway keys so every test runs the same with or without them."""
    for var in _LIVE_KEY_ENV:
        monkeypatch.delenv(var, raising=False)


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


@pytest.fixture(autouse=True)
def _isolate_installed_index(tmp_path, monkeypatch):
    """Pin routing readers to their repo/fixture index (installer spec 7.2).

    ``VEXJOY_INDEX_DIR`` set to an absent dir makes ``resolve_index`` skip the
    real ``~/.claude/vexjoy/index`` and fall back to the tracked + legacy local
    index each test supplies. Tests of the resolver override this. Also sets
    ``VEXJOY_NO_GIT_HOOKS`` so install.sh runs never touch the real
    checkout's ``.git/hooks``.
    """
    monkeypatch.setenv("VEXJOY_NO_GIT_HOOKS", "1")
    monkeypatch.setenv("VEXJOY_INDEX_DIR", str(tmp_path / "no-installed-index"))
    monkeypatch.delenv("VEXJOY_INDEX_TARGET", raising=False)
