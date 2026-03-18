#!/usr/bin/env python3
"""
Learning Database - SQLite-based cross-session pattern storage.

Stores error patterns, solutions, and confidence scores across Claude Code sessions.
Uses SQLite for robust concurrent access and efficient querying.

Design Principles:
- Simple schema, easy to understand
- Automatic table creation
- Thread-safe operations
- Graceful degradation on errors
"""

import hashlib
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

# Database location - can be overridden with CLAUDE_LEARNING_DIR env var
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
    return db_dir / "patterns.db"


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
            -- Error patterns and solutions
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signature TEXT UNIQUE NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                solution TEXT,
                confidence REAL DEFAULT 0.5,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                last_seen TEXT,
                project_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                -- Auto-fix fields
                fix_type TEXT DEFAULT 'manual',  -- manual | auto | skill | agent
                fix_action TEXT                   -- action name, skill name, or agent name
            );

            -- Session metrics
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                start_time TEXT,
                end_time TEXT,
                files_modified INTEGER DEFAULT 0,
                tools_used INTEGER DEFAULT 0,
                errors_encountered INTEGER DEFAULT 0,
                errors_resolved INTEGER DEFAULT 0,
                project_path TEXT
            );

            -- Indexes for fast lookups
            CREATE INDEX IF NOT EXISTS idx_patterns_signature ON patterns(signature);
            CREATE INDEX IF NOT EXISTS idx_patterns_error_type ON patterns(error_type);
            CREATE INDEX IF NOT EXISTS idx_patterns_confidence ON patterns(confidence);
            CREATE INDEX IF NOT EXISTS idx_patterns_project ON patterns(project_path);
            CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_path);
        """)
        conn.commit()

    # Run migrations for existing databases
    migrate_db()


# Error classification
ERROR_TYPES = {
    "missing_file": [
        r"no such file",
        r"file not found",
        r"cannot find",
        r"does not exist",
    ],
    "permissions": [r"permission denied", r"access denied", r"not permitted"],
    "syntax_error": [r"syntax ?error", r"unexpected token", r"parse error"],
    "type_error": [r"type error", r"cannot convert", r"incompatible type"],
    "import_error": [r"import error", r"module not found", r"no module named"],
    "timeout": [r"timeout", r"timed out", r"deadline exceeded"],
    "connection": [r"connection refused", r"network error", r"unreachable"],
    "memory": [r"out of memory", r"memory error", r"heap"],
    "multiple_matches": [r"multiple matches", r"found \d+ matches", r"replace_all"],
}

# Default fix actions for error types
# fix_type: manual (suggest only), auto (retry with fix), skill (invoke skill), agent (spawn agent)
DEFAULT_FIX_ACTIONS = {
    "missing_file": {"fix_type": "auto", "fix_action": "create_file"},
    "permissions": {"fix_type": "manual", "fix_action": "check_permissions"},
    "syntax_error": {"fix_type": "skill", "fix_action": "systematic-debugging"},
    "type_error": {"fix_type": "skill", "fix_action": "systematic-debugging"},
    "import_error": {"fix_type": "auto", "fix_action": "install_module"},
    "timeout": {"fix_type": "auto", "fix_action": "retry_with_timeout"},
    "connection": {"fix_type": "auto", "fix_action": "retry"},
    "memory": {"fix_type": "manual", "fix_action": "reduce_memory"},
    "multiple_matches": {"fix_type": "auto", "fix_action": "use_replace_all"},
}


def migrate_db():
    """Migrate database schema to add new columns."""
    with get_connection() as conn:
        # Check if fix_type column exists
        cursor = conn.execute("PRAGMA table_info(patterns)")
        columns = [row[1] for row in cursor.fetchall()]

        if "fix_type" not in columns:
            conn.execute("ALTER TABLE patterns ADD COLUMN fix_type TEXT DEFAULT 'manual'")
            conn.execute("ALTER TABLE patterns ADD COLUMN fix_action TEXT")
            conn.commit()


def classify_error(message: str) -> str:
    """Classify error message into a category."""
    message_lower = message.lower()
    for error_type, patterns in ERROR_TYPES.items():
        if any(re.search(p, message_lower) for p in patterns):
            return error_type
    return "unknown"


def normalize_error(message: str) -> str:
    """Normalize error message for consistent hashing."""
    normalized = message.lower().strip()
    # Remove file paths (keep just filename)
    normalized = re.sub(r"[/\\][\w./\\-]+[/\\]", "", normalized)
    # Remove line numbers
    normalized = re.sub(r"line \d+", "line N", normalized)
    # Remove memory addresses
    normalized = re.sub(r"0x[0-9a-f]+", "0xADDR", normalized)
    # Remove timestamps (case-insensitive for T/t separator)
    normalized = re.sub(r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}", "TIMESTAMP", normalized)
    return normalized


def generate_signature(error_message: str, error_type: str) -> str:
    """Generate unique signature for an error pattern."""
    normalized = normalize_error(error_message)
    content = f"{error_type}:{normalized}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def record_error(
    error_message: str,
    solution: Optional[str] = None,
    success: bool = False,
    project_path: Optional[str] = None,
    fix_type: Optional[str] = None,
    fix_action: Optional[str] = None,
) -> dict:
    """Record an error pattern and optionally its solution.

    Args:
        error_message: The error message to record
        solution: Human-readable solution description
        success: Whether this was a successful resolution
        project_path: Path to the project where error occurred
        fix_type: Type of fix - manual, auto, skill, or agent
        fix_action: Action to take - command, skill name, or agent name

    Returns the pattern record.
    """
    init_db()

    error_type = classify_error(error_message)
    signature = generate_signature(error_message, error_type)
    now = datetime.now().isoformat()

    # Get default fix action if not provided
    if fix_type is None and error_type in DEFAULT_FIX_ACTIONS:
        fix_type = DEFAULT_FIX_ACTIONS[error_type]["fix_type"]
        fix_action = DEFAULT_FIX_ACTIONS[error_type]["fix_action"]

    with get_connection() as conn:
        # Check if pattern exists
        row = conn.execute("SELECT * FROM patterns WHERE signature = ?", (signature,)).fetchone()

        if row:
            # Update existing pattern
            new_confidence = row["confidence"]
            success_count = row["success_count"]
            failure_count = row["failure_count"]

            if success:
                # Boost by 0.15 so 0.55 + 0.15 = 0.70 (reaches threshold)
                new_confidence = min(1.0, new_confidence + 0.15)
                success_count += 1
            else:
                # Decay slower to give patterns time to prove themselves
                new_confidence = max(0.0, new_confidence - 0.1)
                failure_count += 1

            # Update solution if provided and better
            new_solution = solution if solution else row["solution"]
            # Preserve existing fix info unless explicitly overridden
            new_fix_type = fix_type if fix_type else row["fix_type"]
            new_fix_action = fix_action if fix_action else row["fix_action"]

            conn.execute(
                """
                UPDATE patterns
                SET confidence = ?, success_count = ?, failure_count = ?,
                    solution = ?, last_seen = ?, fix_type = ?, fix_action = ?
                WHERE signature = ?
                """,
                (
                    new_confidence,
                    success_count,
                    failure_count,
                    new_solution,
                    now,
                    new_fix_type,
                    new_fix_action,
                    signature,
                ),
            )
            conn.commit()

            return {
                "signature": signature,
                "error_type": error_type,
                "confidence": new_confidence,
                "solution": new_solution,
                "fix_type": new_fix_type,
                "fix_action": new_fix_action,
                "is_new": False,
            }
        else:
            # Insert new pattern with fix info
            # Start at 0.55 so ONE success (+0.15) reaches 0.7 threshold
            initial_confidence = 0.65 if success else 0.55
            conn.execute(
                """
                INSERT INTO patterns
                (signature, error_type, error_message, solution, confidence,
                 success_count, failure_count, last_seen, project_path,
                 fix_type, fix_action)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signature,
                    error_type,
                    error_message[:500],  # Truncate long messages
                    solution,
                    initial_confidence,
                    1 if success else 0,
                    0 if success else 1,
                    now,
                    project_path,
                    fix_type or "manual",
                    fix_action,
                ),
            )
            conn.commit()

            return {
                "signature": signature,
                "error_type": error_type,
                "confidence": initial_confidence,
                "solution": solution,
                "fix_type": fix_type or "manual",
                "fix_action": fix_action,
                "is_new": True,
            }


def lookup_solution(error_message: str) -> Optional[dict]:
    """Look up a solution for an error pattern.

    Returns pattern with solution and fix info if confidence > 0.7, else None.
    """
    init_db()

    error_type = classify_error(error_message)
    signature = generate_signature(error_message, error_type)

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT signature, error_type, solution, confidence, fix_type, fix_action
            FROM patterns
            WHERE signature = ? AND confidence >= 0.7 AND solution IS NOT NULL
            """,
            (signature,),
        ).fetchone()

        if row:
            return dict(row)
        return None


def get_high_confidence_patterns(
    min_confidence: float = 0.7,
    project_path: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Get high-confidence patterns for context injection.

    Returns patterns sorted by confidence descending.
    """
    init_db()

    with get_connection() as conn:
        if project_path:
            # Get both global and project-specific patterns
            rows = conn.execute(
                """
                SELECT signature, error_type, error_message, solution, confidence
                FROM patterns
                WHERE confidence >= ? AND solution IS NOT NULL
                  AND (project_path IS NULL OR project_path = ?)
                ORDER BY confidence DESC
                LIMIT ?
                """,
                (min_confidence, project_path, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT signature, error_type, error_message, solution, confidence
                FROM patterns
                WHERE confidence >= ? AND solution IS NOT NULL
                ORDER BY confidence DESC
                LIMIT ?
                """,
                (min_confidence, limit),
            ).fetchall()

        return [dict(row) for row in rows]


def record_session(
    session_id: str,
    files_modified: int = 0,
    tools_used: int = 0,
    errors_encountered: int = 0,
    errors_resolved: int = 0,
    project_path: Optional[str] = None,
    end_session: bool = False,
) -> None:
    """Record session metrics."""
    init_db()
    now = datetime.now().isoformat()

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()

        if row:
            # Update existing session
            conn.execute(
                """
                UPDATE sessions
                SET files_modified = files_modified + ?,
                    tools_used = tools_used + ?,
                    errors_encountered = errors_encountered + ?,
                    errors_resolved = errors_resolved + ?,
                    end_time = CASE WHEN ? THEN ? ELSE end_time END
                WHERE session_id = ?
                """,
                (
                    files_modified,
                    tools_used,
                    errors_encountered,
                    errors_resolved,
                    end_session,
                    now if end_session else None,
                    session_id,
                ),
            )
        else:
            # Insert new session
            conn.execute(
                """
                INSERT INTO sessions
                (session_id, start_time, files_modified, tools_used,
                 errors_encountered, errors_resolved, project_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    now,
                    files_modified,
                    tools_used,
                    errors_encountered,
                    errors_resolved,
                    project_path,
                ),
            )
        conn.commit()


def get_stats() -> dict:
    """Get overall learning statistics."""
    init_db()

    with get_connection() as conn:
        pattern_stats = conn.execute(
            """
            SELECT
                COUNT(*) as total_patterns,
                SUM(CASE WHEN confidence >= 0.7 THEN 1 ELSE 0 END) as high_confidence,
                SUM(success_count) as total_successes,
                SUM(failure_count) as total_failures,
                AVG(confidence) as avg_confidence
            FROM patterns
            """
        ).fetchone()

        session_stats = conn.execute(
            """
            SELECT
                COUNT(*) as total_sessions,
                SUM(files_modified) as total_files_modified,
                SUM(errors_encountered) as total_errors,
                SUM(errors_resolved) as total_resolved
            FROM sessions
            """
        ).fetchone()

        return {
            "patterns": dict(pattern_stats) if pattern_stats else {},
            "sessions": dict(session_stats) if session_stats else {},
        }


if __name__ == "__main__":
    # Quick test
    init_db()
    print(f"Database initialized at: {get_db_path()}")
    stats = get_stats()
    print(f"Stats: {stats}")
