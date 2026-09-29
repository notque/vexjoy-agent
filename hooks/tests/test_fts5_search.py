#!/usr/bin/env python3
"""
Schema contract tests for the learnings_fts FTS5 index in learning_db_v2.

Verifies:
- trigger-based sync of learnings_fts on UPDATE and DELETE
- migration backfill of rows written before the FTS table existed
- query_learnings() lookup by topic
"""

import sqlite3
import sys
from pathlib import Path

import pytest

# Add hooks/lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

import learning_db_v2 as db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Use a fresh temp database for each test."""
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    monkeypatch.setattr(db, "_initialized", False)
    return tmp_path


def _record(topic: str, key: str, value: str, tags: list[str] | None = None) -> dict:
    """Record a learning with defaults."""
    return db.record_learning(
        topic=topic,
        key=key,
        value=value,
        category="design",
        confidence=0.7,
        tags=tags,
        source="manual",
    )


def _fts_match(term: str) -> list[dict]:
    """Query learnings_fts directly and join back to the learnings row."""
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT l.topic, l.value FROM learnings_fts JOIN learnings l ON l.id = learnings_fts.rowid "
            "WHERE learnings_fts MATCH ?",
            (term,),
        ).fetchall()
        return [dict(row) for row in rows]


class TestTriggerSync:
    """Verify FTS index stays in sync with learnings table."""

    def test_update_syncs_to_fts(self):
        _record("go-patterns", "mutex-usage", "Short value", tags=["go"])
        # Re-record with longer value triggers UPDATE path
        _record(
            "go-patterns",
            "mutex-usage",
            "Always use sync.Mutex for shared state access in goroutines",
            tags=["go"],
        )

        results = _fts_match("goroutines")
        assert len(results) == 1
        assert "goroutines" in results[0]["value"]

    def test_delete_syncs_to_fts(self):
        _record("temp-topic", "temp-key", "Temporary value for deletion test", tags=["temp"])

        # Verify it's searchable
        assert len(_fts_match("temporary")) >= 1

        # Delete directly
        with db.get_connection() as conn:
            conn.execute("DELETE FROM learnings WHERE topic = 'temp-topic' AND key = 'temp-key'")
            conn.commit()

        # FTS should no longer find it
        assert _fts_match("temporary") == []


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
            (
                "pre-existing",
                "old-entry",
                "This is a pre-existing learning about goroutines",
                "design",
                "manual",
                "go,concurrency",
            ),
        )
        conn.commit()
        conn.close()

        # Now init_db with FTS schema — should backfill
        db._initialized = False
        db.init_db()

        # The pre-existing row should be searchable via FTS
        results = _fts_match("goroutines")
        assert len(results) == 1
        assert results[0]["topic"] == "pre-existing"


class TestBackwardCompatibility:
    """Verify query_learnings() still works unchanged."""

    def test_query_learnings_by_topic(self):
        _record("go-patterns", "mutex-usage", "Use sync.Mutex", tags=["go"])

        results = db.query_learnings(topic="go-patterns", exclude_test_sources=False)
        assert len(results) == 1
