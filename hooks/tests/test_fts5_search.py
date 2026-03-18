#!/usr/bin/env python3
"""
Tests for FTS5 full-text search in learning_db_v2.

Verifies:
- FTS5 virtual table creation and trigger-based sync
- search_learnings() with BM25 ranking
- Porter stemming (morphological matching)
- OR/AND query syntax
- Prefix queries
- Migration backfill for pre-existing rows
- Backward compatibility with query_learnings()
- Edge cases: empty query, invalid syntax, no matches
"""

import os
import sqlite3
import sys
from pathlib import Path

import pytest

# Add hooks/lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

import learning_db_v2 as db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Use a fresh temp database for each test."""
    os.environ["CLAUDE_LEARNING_DIR"] = str(tmp_path)
    db._initialized = False
    yield tmp_path
    os.environ.pop("CLAUDE_LEARNING_DIR", None)
    db._initialized = False


def _record(topic: str, key: str, value: str, tags: list[str] | None = None, confidence: float = 0.7) -> dict:
    """Helper to record a learning with defaults."""
    return db.record_learning(
        topic=topic,
        key=key,
        value=value,
        category="design",
        confidence=confidence,
        tags=tags,
        source="test",
    )


class TestFTS5SchemaCreation:
    """Verify the FTS5 table and triggers exist after init."""

    def test_fts_table_exists(self):
        db.init_db()
        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='learnings_fts'"
            ).fetchone()
            assert row is not None, "learnings_fts table should exist"

    def test_triggers_exist(self):
        db.init_db()
        with db.get_connection() as conn:
            triggers = {
                r["name"]
                for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()
            }
            assert "learnings_ai" in triggers, "INSERT trigger missing"
            assert "learnings_ad" in triggers, "DELETE trigger missing"
            assert "learnings_au" in triggers, "UPDATE trigger missing"


class TestTriggerSync:
    """Verify FTS index stays in sync with learnings table."""

    def test_insert_syncs_to_fts(self):
        _record("go-patterns", "mutex-usage", "Always use sync.Mutex for shared state", tags=["go", "concurrency"])
        with db.get_connection() as conn:
            fts_count = conn.execute("SELECT COUNT(*) FROM learnings_fts").fetchone()[0]
            assert fts_count == 1

    def test_update_syncs_to_fts(self):
        _record("go-patterns", "mutex-usage", "Short value", tags=["go"])
        # Re-record with longer value triggers UPDATE path
        _record(
            "go-patterns", "mutex-usage",
            "Always use sync.Mutex for shared state access in goroutines", tags=["go"],
        )

        results = db.search_learnings("goroutines")
        assert len(results) == 1
        assert "goroutines" in results[0]["value"]

    def test_delete_syncs_to_fts(self):
        _record("temp-topic", "temp-key", "Temporary value for deletion test", tags=["temp"])

        # Verify it's searchable
        assert len(db.search_learnings("temporary")) >= 1

        # Delete directly
        with db.get_connection() as conn:
            conn.execute("DELETE FROM learnings WHERE topic = 'temp-topic' AND key = 'temp-key'")
            conn.commit()

        # FTS should no longer find it
        results = db.search_learnings("temporary")
        assert len(results) == 0


class TestSearchLearnings:
    """Test the search_learnings() function."""

    def test_basic_search(self):
        _record("go-patterns", "mutex-usage", "Use sync.Mutex for shared state", tags=["go", "concurrency"])
        _record("python-patterns", "dataclass-usage", "Use dataclasses for structured data", tags=["python"])

        results = db.search_learnings("mutex")
        assert len(results) == 1
        assert results[0]["topic"] == "go-patterns"

    def test_bm25_ranking(self):
        """More relevant results should rank higher (more negative BM25)."""
        _record("topic-a", "key-a", "goroutine goroutine goroutine channel", tags=["go"])
        _record("topic-b", "key-b", "some other content with goroutine once", tags=["misc"])

        results = db.search_learnings("goroutine")
        assert len(results) == 2
        # First result should have more negative rank (= more relevant)
        assert results[0]["rank"] <= results[1]["rank"]
        assert results[0]["topic"] == "topic-a"

    def test_porter_stemming(self):
        """Porter stemmer should match morphological variants."""
        _record("config", "config-patterns", "Configuring the application requires validation", tags=["config"])

        # All these forms should match via stemming
        for query in ["configuring", "configured", "configuration", "configure"]:
            results = db.search_learnings(query)
            assert len(results) >= 1, f"Stemming failed for '{query}'"

    def test_or_query(self):
        _record("topic-a", "key-a", "Worker pool implementation", tags=["go"])
        _record("topic-b", "key-b", "Circuit breaker pattern", tags=["resilience"])
        _record("topic-c", "key-c", "Unrelated topic about databases", tags=["sql"])

        results = db.search_learnings("worker OR circuit")
        assert len(results) == 2
        topics = {r["topic"] for r in results}
        assert topics == {"topic-a", "topic-b"}

    def test_and_query(self):
        _record("topic-a", "key-a", "State machine in Go", tags=["go", "state-machine"])
        _record("topic-b", "key-b", "State management in React", tags=["react"])
        _record("topic-c", "key-c", "Machine learning basics", tags=["ml"])

        results = db.search_learnings("state AND machine")
        assert len(results) == 1
        assert results[0]["topic"] == "topic-a"

    def test_prefix_query(self):
        _record("topic-a", "key-a", "Circuit breaker for resilience", tags=["circuit-breaker"])

        results = db.search_learnings("circuit*")
        assert len(results) >= 1
        assert results[0]["topic"] == "topic-a"

    def test_searches_across_all_columns(self):
        """FTS5 indexes topic, key, value, and tags — all should be searchable."""
        _record("goroutine-patterns", "pool-design", "Describes worker pool", tags=["concurrency"])

        # Match in topic column
        assert len(db.search_learnings("goroutine")) >= 1
        # Match in key column
        assert len(db.search_learnings("pool")) >= 1
        # Match in value column
        assert len(db.search_learnings("worker")) >= 1
        # Match in tags column
        assert len(db.search_learnings("concurrency")) >= 1

    def test_min_confidence_filter(self):
        _record("topic-a", "key-a", "Low confidence result", tags=["test"], confidence=0.3)
        _record("topic-b", "key-b", "High confidence result", tags=["test"], confidence=0.9)

        results = db.search_learnings("confidence result", min_confidence=0.5)
        assert len(results) == 1
        assert results[0]["topic"] == "topic-b"

    def test_exclude_graduated(self):
        _record("topic-a", "key-a", "Graduated entry about testing", tags=["test"])
        db.mark_graduated("topic-a", "key-a", "agent:test-agent")
        _record("topic-b", "key-b", "Active entry about testing", tags=["test"])

        # Default: exclude graduated
        results = db.search_learnings("testing")
        assert len(results) == 1
        assert results[0]["topic"] == "topic-b"

        # Include graduated
        results = db.search_learnings("testing", exclude_graduated=False)
        assert len(results) == 2

    def test_limit(self):
        for i in range(10):
            _record(f"topic-{i}", f"key-{i}", f"Entry number {i} about testing", tags=["test"])

        results = db.search_learnings("testing", limit=3)
        assert len(results) == 3

    def test_empty_query_returns_empty(self):
        _record("topic-a", "key-a", "Some content", tags=["test"])
        assert db.search_learnings("") == []
        assert db.search_learnings("   ") == []

    def test_invalid_fts_syntax_returns_empty(self):
        """Invalid FTS5 query syntax should not raise, just return empty."""
        _record("topic-a", "key-a", "Some content", tags=["test"])
        # Unbalanced quotes and other invalid FTS5 syntax
        assert db.search_learnings('"unclosed quote') == []

    def test_no_matches_returns_empty(self):
        _record("topic-a", "key-a", "Some content about Go", tags=["go"])
        results = db.search_learnings("xyznonexistent")
        assert results == []


class TestMigrationBackfill:
    """Test _migrate_fts() backfill for pre-existing databases."""

    def test_backfill_existing_rows(self, isolated_db):
        """Rows inserted before FTS5 schema should be backfilled."""
        db_path = isolated_db / "learning.db"

        # Create a database with just the learnings table (no FTS)
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS learnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                category TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                tags TEXT,
                source TEXT NOT NULL,
                source_detail TEXT,
                project_path TEXT,
                session_id TEXT,
                observation_count INTEGER DEFAULT 1,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                first_seen TEXT DEFAULT (datetime('now')),
                last_seen TEXT DEFAULT (datetime('now')),
                graduated_to TEXT,
                error_signature TEXT,
                error_type TEXT,
                fix_type TEXT,
                fix_action TEXT,
                UNIQUE(topic, key)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                start_time TEXT,
                end_time TEXT,
                project_path TEXT,
                files_modified INTEGER DEFAULT 0,
                tools_used INTEGER DEFAULT 0,
                errors_encountered INTEGER DEFAULT 0,
                errors_resolved INTEGER DEFAULT 0,
                learnings_captured INTEGER DEFAULT 0,
                summary TEXT
            )
        """)
        # Insert rows before FTS exists
        conn.execute(
            "INSERT INTO learnings (topic, key, value, category, source, tags) VALUES (?, ?, ?, ?, ?, ?)",
            ("pre-existing", "old-entry", "This is a pre-existing learning about goroutines",
             "design", "test", "go,concurrency"),
        )
        conn.commit()
        conn.close()

        # Now init_db with FTS schema — should backfill
        db._initialized = False
        db.init_db()

        # The pre-existing row should be searchable via FTS
        results = db.search_learnings("goroutines")
        assert len(results) == 1
        assert results[0]["topic"] == "pre-existing"


class TestBackwardCompatibility:
    """Verify query_learnings() still works unchanged."""

    def test_query_learnings_still_works(self):
        _record("go-patterns", "mutex-usage", "Use sync.Mutex", tags=["go", "concurrency"])
        _record("python-patterns", "dataclass", "Use dataclasses", tags=["python"])

        # Exact tag substring matching still works
        results = db.query_learnings(tags=["go"])
        assert len(results) >= 1
        assert any(r["topic"] == "go-patterns" for r in results)

    def test_query_learnings_by_topic(self):
        _record("go-patterns", "mutex-usage", "Use sync.Mutex", tags=["go"])

        results = db.query_learnings(topic="go-patterns")
        assert len(results) == 1

    def test_both_apis_find_same_entry(self):
        _record("shared", "shared-key", "Shared content about concurrency", tags=["go", "concurrency"])

        query_results = db.query_learnings(tags=["concurrency"])
        search_results = db.search_learnings("concurrency")

        assert len(query_results) >= 1
        assert len(search_results) >= 1
        # Both should find the same entry
        assert query_results[0]["topic"] == search_results[0]["topic"]
        assert query_results[0]["key"] == search_results[0]["key"]
