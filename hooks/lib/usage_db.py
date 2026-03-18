#!/usr/bin/env python3
"""
Usage Database - SQLite-based skill and agent invocation tracking.

Tracks which skills and agents are actually invoked across Claude Code sessions.
Uses SQLite for robust concurrent access and efficient querying.

Design Principles:
- Reuses learning_db patterns (same DB directory, same connection style)
- Simple schema, easy to query
- Automatic table creation
- Thread-safe operations
- Graceful degradation on errors
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Database location - same directory as learning.db
_DEFAULT_DB_DIR = Path.home() / ".claude" / "learning"


def _get_db_dir() -> Path:
    """Get database directory, respecting CLAUDE_LEARNING_DIR env var."""
    env_dir = os.environ.get("CLAUDE_LEARNING_DIR")
    if env_dir:
        return Path(env_dir)
    return _DEFAULT_DB_DIR


def get_db_path() -> Path:
    """Get database path, creating directory if needed."""
    db_dir = _get_db_dir()
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "usage.db"


@contextmanager
def get_connection():
    """Get a database connection with automatic cleanup."""
    conn = sqlite3.connect(get_db_path(), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize database schema."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS skill_invocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                session_id TEXT,
                project_path TEXT,
                args_summary TEXT
            );

            CREATE TABLE IF NOT EXISTS agent_invocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_type TEXT NOT NULL,
                description TEXT,
                timestamp TEXT NOT NULL,
                session_id TEXT,
                project_path TEXT,
                isolation TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_skill_name ON skill_invocations(skill_name);
            CREATE INDEX IF NOT EXISTS idx_agent_type ON agent_invocations(agent_type);
            CREATE INDEX IF NOT EXISTS idx_skill_ts ON skill_invocations(timestamp);
            CREATE INDEX IF NOT EXISTS idx_agent_ts ON agent_invocations(timestamp);
        """)
        conn.commit()


def record_skill(
    skill_name: str,
    session_id: Optional[str] = None,
    project_path: Optional[str] = None,
    args_summary: Optional[str] = None,
) -> None:
    """Record a skill invocation.

    Args:
        skill_name: Name of the skill invoked
        session_id: Current Claude Code session ID
        project_path: Path to the project
        args_summary: First 200 chars of args for context
    """
    init_db()
    now = datetime.now(timezone.utc).isoformat()

    # Truncate args_summary to 200 chars
    if args_summary and len(args_summary) > 200:
        args_summary = args_summary[:200]

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO skill_invocations
            (skill_name, timestamp, session_id, project_path, args_summary)
            VALUES (?, ?, ?, ?, ?)
            """,
            (skill_name, now, session_id, project_path, args_summary),
        )
        conn.commit()


def record_agent(
    agent_type: str,
    description: Optional[str] = None,
    session_id: Optional[str] = None,
    project_path: Optional[str] = None,
    isolation: Optional[str] = None,
) -> None:
    """Record an agent invocation.

    Args:
        agent_type: Type/name of the agent
        description: Description of the agent task
        session_id: Current Claude Code session ID
        project_path: Path to the project
        isolation: Isolation mode (null or "worktree")
    """
    init_db()
    now = datetime.now(timezone.utc).isoformat()

    # Truncate description to 500 chars
    if description and len(description) > 500:
        description = description[:500]

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO agent_invocations
            (agent_type, description, timestamp, session_id, project_path, isolation)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (agent_type, description, now, session_id, project_path, isolation),
        )
        conn.commit()


def get_skill_usage(days: int = 30) -> list[dict]:
    """Get skill usage statistics for the given period.

    Args:
        days: Number of days to look back

    Returns:
        List of dicts with name, count, last_used sorted by count descending
    """
    init_db()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                skill_name AS name,
                COUNT(*) AS count,
                MAX(timestamp) AS last_used
            FROM skill_invocations
            WHERE timestamp >= datetime('now', ? || ' days')
            GROUP BY skill_name
            ORDER BY count DESC
            """,
            (f"-{days}",),
        ).fetchall()

        return [dict(row) for row in rows]


def get_agent_usage(days: int = 30) -> list[dict]:
    """Get agent usage statistics for the given period.

    Args:
        days: Number of days to look back

    Returns:
        List of dicts with type, count, last_used sorted by count descending
    """
    init_db()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                agent_type AS type,
                COUNT(*) AS count,
                MAX(timestamp) AS last_used
            FROM agent_invocations
            WHERE timestamp >= datetime('now', ? || ' days')
            GROUP BY agent_type
            ORDER BY count DESC
            """,
            (f"-{days}",),
        ).fetchall()

        return [dict(row) for row in rows]


def get_dormant_skills(
    days: int = 30,
    known_skills: Optional[list[str]] = None,
) -> list[str]:
    """Get skills with zero invocations in the given period.

    Args:
        days: Number of days to look back
        known_skills: List of all known skill names to check against

    Returns:
        List of skill names with no invocations
    """
    if not known_skills:
        return []

    init_db()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT skill_name
            FROM skill_invocations
            WHERE timestamp >= datetime('now', ? || ' days')
            """,
            (f"-{days}",),
        ).fetchall()

        used = {row["skill_name"] for row in rows}
        return sorted(s for s in known_skills if s not in used)


def get_dormant_agents(
    days: int = 30,
    known_agents: Optional[list[str]] = None,
) -> list[str]:
    """Get agents with zero invocations in the given period.

    Args:
        days: Number of days to look back
        known_agents: List of all known agent names to check against

    Returns:
        List of agent names with no invocations
    """
    if not known_agents:
        return []

    init_db()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT agent_type
            FROM agent_invocations
            WHERE timestamp >= datetime('now', ? || ' days')
            """,
            (f"-{days}",),
        ).fetchall()

        used = {row["agent_type"] for row in rows}
        return sorted(a for a in known_agents if a not in used)


if __name__ == "__main__":
    # Quick test
    init_db()
    print(f"Database initialized at: {get_db_path()}")
    print(f"Skill usage (30d): {get_skill_usage()}")
    print(f"Agent usage (30d): {get_agent_usage()}")
