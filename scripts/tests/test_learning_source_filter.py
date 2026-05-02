"""Tests for the source filter in query_learnings and the purge-test-learnings script.

Covers:
- query_learnings excludes test-source rows by default
- query_learnings includes test-source rows with exclude_test_sources=False
- purge-test-learnings dry-run reports rows without deleting
- purge-test-learnings --commit deletes test-source rows only
"""

from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path

import pytest

# Ensure repo hooks/lib is on the path for learning_db_v2
_repo_root = Path(__file__).resolve().parent.parent.parent
_repo_hooks_lib = str(_repo_root / "hooks" / "lib")
if _repo_hooks_lib not in sys.path:
    sys.path.insert(0, _repo_hooks_lib)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point learning DB to a temp directory so tests never touch production data."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))

    import learning_db_v2

    monkeypatch.setattr(learning_db_v2, "_initialized", False)
    if "learning_db_v2" in sys.modules:
        importlib.reload(sys.modules["learning_db_v2"])
    return db_dir


def _seed_mixed(isolated_db: Path) -> None:
    """Insert two real rows and two test-source rows into the temp DB."""
    from learning_db_v2 import init_db, record_learning

    init_db()
    record_learning(
        topic="go-patterns",
        key="mutex-over-atomics",
        value="Use sync.Mutex for complex state; atomics for simple counters.",
        category="design",
        confidence=0.8,
        source="manual:learn",
    )
    record_learning(
        topic="debugging",
        key="log-before-panic",
        value="Always log state before calling panic() so postmortem has context.",
        category="gotcha",
        confidence=0.75,
        source="hook:user-correction-capture",
    )
    record_learning(
        topic="test-bounds",
        key="bounds-abc123",
        value="Test fixture — confidence boundary check.",
        category="error",
        confidence=0.55,
        source="test",
    )
    record_learning(
        topic="multiple_matches",
        key="sig-deadbeef1234",
        value="Test fixture — multiple match error pattern.",
        category="error",
        confidence=0.70,
        source="test",
    )


# ---------------------------------------------------------------------------
# query_learnings source filter
# ---------------------------------------------------------------------------


class TestQueryLearningsSourceFilter:
    """query_learnings must exclude test-source rows by default."""

    def test_excludes_test_sources_by_default(self, isolated_db: Path) -> None:
        _seed_mixed(isolated_db)
        from learning_db_v2 import query_learnings

        results = query_learnings()
        sources = {r["source"] for r in results}
        assert not any(s.startswith("test") for s in sources), f"Default query returned test-source rows: {sources}"

    def test_real_rows_still_returned(self, isolated_db: Path) -> None:
        _seed_mixed(isolated_db)
        from learning_db_v2 import query_learnings

        results = query_learnings()
        keys = {r["key"] for r in results}
        assert "mutex-over-atomics" in keys
        assert "log-before-panic" in keys

    def test_include_tests_flag_returns_all(self, isolated_db: Path) -> None:
        _seed_mixed(isolated_db)
        from learning_db_v2 import query_learnings

        results = query_learnings(exclude_test_sources=False)
        keys = {r["key"] for r in results}
        assert "bounds-abc123" in keys
        assert "sig-deadbeef1234" in keys

    def test_test_prefix_variants_excluded(self, isolated_db: Path) -> None:
        """source='test-harness' and source='test:fixture' are also excluded."""
        from learning_db_v2 import init_db, query_learnings, record_learning

        init_db()
        record_learning(
            topic="misc",
            key="harness-row",
            value="Row with test-harness source.",
            category="design",
            confidence=0.6,
            source="test-harness",
        )
        record_learning(
            topic="misc",
            key="testcolon-row",
            value="Row with test:fixture source.",
            category="design",
            confidence=0.6,
            source="test:fixture",
        )
        record_learning(
            topic="misc",
            key="real-row",
            value="Real row from hook.",
            category="design",
            confidence=0.6,
            source="hook:session-guard",
        )

        results = query_learnings()
        keys = {r["key"] for r in results}
        assert "harness-row" not in keys
        assert "testcolon-row" not in keys
        assert "real-row" in keys

    def test_category_filter_still_applies(self, isolated_db: Path) -> None:
        """When filtering by category, test sources are still excluded."""
        _seed_mixed(isolated_db)
        from learning_db_v2 import query_learnings

        # category=error has two test-source rows; with the filter none should appear
        results = query_learnings(category="error")
        assert results == [], f"Expected empty list, got: {results}"

    def test_category_filter_with_include_tests(self, isolated_db: Path) -> None:
        """exclude_test_sources=False lets test rows through even with category filter."""
        _seed_mixed(isolated_db)
        from learning_db_v2 import query_learnings

        results = query_learnings(category="error", exclude_test_sources=False)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# purge-test-learnings script
# ---------------------------------------------------------------------------

# Import the script as a module
_scripts_dir = str(_repo_root / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)


def _import_purge_script():
    """Import purge-test-learnings as a module (hyphen in filename)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "purge_test_learnings",
        _repo_root / "scripts" / "purge-test-learnings.py",
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestPurgeTestLearnings:
    """purge-test-learnings.py dry-run and --commit behaviour."""

    def test_dry_run_does_not_delete(self, isolated_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _seed_mixed(isolated_db)
        db_path = isolated_db / "learning.db"
        mod = _import_purge_script()

        # Patch argparse so we can call main() without sys.argv conflicts
        monkeypatch.setattr(
            "sys.argv",
            ["purge-test-learnings.py", "--db", str(db_path)],
        )
        mod.main()

        # Rows must still be present after dry run
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM learnings WHERE source LIKE 'test%'").fetchone()[0]
        conn.close()
        assert count == 2, f"Dry run deleted rows — expected 2 test rows, found {count}"

    def test_commit_deletes_test_rows(self, isolated_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _seed_mixed(isolated_db)
        db_path = isolated_db / "learning.db"
        mod = _import_purge_script()

        monkeypatch.setattr(
            "sys.argv",
            ["purge-test-learnings.py", "--db", str(db_path), "--commit"],
        )
        mod.main()

        conn = sqlite3.connect(db_path)
        test_count = conn.execute("SELECT COUNT(*) FROM learnings WHERE source LIKE 'test%'").fetchone()[0]
        real_count = conn.execute("SELECT COUNT(*) FROM learnings WHERE source NOT LIKE 'test%'").fetchone()[0]
        conn.close()
        assert test_count == 0, f"Expected 0 test rows after --commit, found {test_count}"
        assert real_count == 2, f"Expected 2 real rows preserved, found {real_count}"

    def test_dry_run_output_lists_rows(
        self, isolated_db: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_mixed(isolated_db)
        db_path = isolated_db / "learning.db"
        mod = _import_purge_script()

        monkeypatch.setattr(
            "sys.argv",
            ["purge-test-learnings.py", "--db", str(db_path)],
        )
        mod.main()
        output = capsys.readouterr().out

        assert "2" in output  # row count
        assert "DRY RUN" in output
        assert "--commit" in output

    def test_empty_db_no_crash(self, isolated_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from learning_db_v2 import init_db

        init_db()  # empty DB
        db_path = isolated_db / "learning.db"
        mod = _import_purge_script()

        monkeypatch.setattr(
            "sys.argv",
            ["purge-test-learnings.py", "--db", str(db_path)],
        )
        mod.main()  # should not raise
