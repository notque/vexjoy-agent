#!/usr/bin/env python3
"""
Learning Database v2 — Unified cross-session knowledge store.

Replaces both patterns.db (error-learner) and retro L2 markdown files
with a single SQLite database at ~/.claude/learning/learning.db.

All hooks and scripts use this interface to record and query learnings.
Designed for <50ms query performance with indexed columns.

Design Principles:
- Single source of truth for all learned knowledge
- Record liberally, inject conservatively (confidence thresholds)
- Automatic table creation and migration
- WAL mode for concurrent session reads
- Graceful degradation on errors
"""

import hashlib
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

# ─── Configuration ─────────────────────────────────────────────

_DEFAULT_DB_DIR = Path.home() / ".claude" / "learning"

_CURRENT_SCHEMA_VERSION = 3

CATEGORY_DEFAULTS = {
    "error": 0.55,
    "pivot": 0.60,
    "review": 0.70,
    "design": 0.65,
    "debug": 0.60,
    "gotcha": 0.70,
    "effectiveness": 0.50,
    "misroute": 0.80,
}

VALID_CATEGORIES = set(CATEGORY_DEFAULTS.keys())

# Carried over from learning_db.py for backward compatibility
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


# ─── Database Connection ───────────────────────────────────────


def _get_db_dir() -> Path:
    env_dir = os.environ.get("CLAUDE_LEARNING_DIR")
    if env_dir:
        return Path(env_dir)
    return _DEFAULT_DB_DIR


def get_db_path() -> Path:
    db_dir = _get_db_dir()
    db_dir.mkdir(parents=True, exist_ok=True)
    # Harden directory permissions (ADR-122)
    try:
        os.chmod(db_dir, 0o700)
    except OSError:
        pass
    return db_dir / "learning.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(get_db_path(), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        conn.close()


_initialized = False


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Run pending schema migrations based on PRAGMA user_version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]

    if current < 1:
        # v0 -> v1: Initial version tracking
        conn.execute("PRAGMA user_version = 1")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) VALUES (1, 'initial version tracking')"
        )

    if current < 2:
        # v1 -> v2: Add graduation_proposed_at column (moved from knowledge-graduation-proposer.py)
        try:
            conn.execute("ALTER TABLE learnings ADD COLUMN graduation_proposed_at TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists from old ad-hoc migration
        conn.execute("PRAGMA user_version = 2")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) "
            "VALUES (2, 'add graduation_proposed_at column to learnings')"
        )

    if current < 3:
        # v2 -> v3: Add performance indexes for timestamp range queries and ROI cohort scans
        for ddl in (
            "CREATE INDEX IF NOT EXISTS idx_learnings_last_seen ON learnings(last_seen)",
            "CREATE INDEX IF NOT EXISTS idx_learnings_first_seen ON learnings(first_seen)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time)",
            "CREATE INDEX IF NOT EXISTS idx_activations_timestamp ON activations(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_session_stats_had_retro ON session_stats(had_retro_knowledge)",
            "CREATE INDEX IF NOT EXISTS idx_session_stats_created_at ON session_stats(created_at)",
        ):
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass  # Index already exists
        conn.execute("PRAGMA user_version = 3")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) "
            "VALUES (3, 'add timestamp and cohort indexes for query performance')"
        )

    conn.commit()


def init_db():
    global _initialized
    if _initialized:
        return
    with get_connection() as conn:
        # Read version before migrations so _migrate_fts knows if triggers were active
        pre_migration_version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.executescript(_SCHEMA)
        _run_migrations(conn)
    _migrate_fts(pre_migration_version)
    # Harden DB file permissions after creation (ADR-122)
    try:
        os.chmod(get_db_path(), 0o600)
    except OSError:
        pass
    _initialized = True


def _migrate_fts(pre_migration_version: int = 0) -> None:
    """Rebuild the FTS5 inverted index from the learnings table.

    Called once from init_db() on each process start. The 'rebuild'
    command re-reads all content from the learnings table and
    reconstructs the inverted index. This is necessary for databases
    that predate the FTS5 schema -- the content-sync FTS5 table
    reports COUNT(*) from the content table even when the inverted
    index is empty, so we always rebuild on first init.

    Rebuild is idempotent and fast (<100ms for hundreds of rows).

    Args:
        pre_migration_version: The user_version before migrations ran. If >= 1,
            FTS triggers were active from table creation so the inverted index
            is already current and the expensive rebuild can be skipped.
    """
    if pre_migration_version >= 1:
        # Triggers have maintained the FTS index since the DB was first created
        return

    with get_connection() as conn:
        try:
            main_count = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
        except sqlite3.OperationalError:
            return  # Table doesn't exist yet

        if main_count > 0:
            try:
                conn.execute("INSERT INTO learnings_fts(learnings_fts) VALUES('rebuild')")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # FTS table doesn't exist yet


_SCHEMA = """
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
);

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
);

CREATE INDEX IF NOT EXISTS idx_learnings_topic ON learnings(topic);
CREATE INDEX IF NOT EXISTS idx_learnings_category ON learnings(category);
CREATE INDEX IF NOT EXISTS idx_learnings_confidence ON learnings(confidence);
CREATE INDEX IF NOT EXISTS idx_learnings_tags ON learnings(tags);
CREATE INDEX IF NOT EXISTS idx_learnings_project ON learnings(project_path);
CREATE INDEX IF NOT EXISTS idx_learnings_graduated ON learnings(graduated_to);
CREATE INDEX IF NOT EXISTS idx_learnings_error_sig ON learnings(error_signature);
CREATE INDEX IF NOT EXISTS idx_learnings_last_seen ON learnings(last_seen);
CREATE INDEX IF NOT EXISTS idx_learnings_first_seen ON learnings(first_seen);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_path);
CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time);

CREATE VIRTUAL TABLE IF NOT EXISTS learnings_fts USING fts5(
    topic,
    key,
    value,
    tags,
    content='learnings',
    content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    key TEXT NOT NULL,
    session_id TEXT,
    timestamp TEXT DEFAULT (datetime('now')),
    outcome TEXT DEFAULT 'success'
);

CREATE TABLE IF NOT EXISTS session_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    had_retro_knowledge INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    waste_tokens INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_activations_topic_key ON activations(topic, key);
CREATE INDEX IF NOT EXISTS idx_activations_session ON activations(session_id);
CREATE INDEX IF NOT EXISTS idx_activations_timestamp ON activations(timestamp);
CREATE INDEX IF NOT EXISTS idx_session_stats_session ON session_stats(session_id);
CREATE INDEX IF NOT EXISTS idx_session_stats_had_retro ON session_stats(had_retro_knowledge);
CREATE INDEX IF NOT EXISTS idx_session_stats_created_at ON session_stats(created_at);

CREATE TRIGGER IF NOT EXISTS learnings_ai AFTER INSERT ON learnings BEGIN
    INSERT INTO learnings_fts(rowid, topic, key, value, tags)
    VALUES (new.id, new.topic, new.key, new.value, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS learnings_ad AFTER DELETE ON learnings BEGIN
    INSERT INTO learnings_fts(learnings_fts, rowid, topic, key, value, tags)
    VALUES ('delete', old.id, old.topic, old.key, old.value, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS learnings_au AFTER UPDATE ON learnings BEGIN
    INSERT INTO learnings_fts(learnings_fts, rowid, topic, key, value, tags)
    VALUES ('delete', old.id, old.topic, old.key, old.value, old.tags);
    INSERT INTO learnings_fts(rowid, topic, key, value, tags)
    VALUES (new.id, new.topic, new.key, new.value, new.tags);
END;

CREATE TABLE IF NOT EXISTS governance_events (
    id          TEXT PRIMARY KEY,
    session_id  TEXT,
    event_type  TEXT NOT NULL,
    tool_name   TEXT,
    hook_phase  TEXT,
    severity    TEXT,
    payload     TEXT,
    blocked     INTEGER DEFAULT 0,
    resolved_at TEXT,
    resolution  TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gov_session   ON governance_events(session_id);
CREATE INDEX IF NOT EXISTS idx_gov_type      ON governance_events(event_type);
CREATE INDEX IF NOT EXISTS idx_gov_severity  ON governance_events(severity);
CREATE INDEX IF NOT EXISTS idx_gov_created   ON governance_events(created_at);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now')),
    description TEXT
);
"""


# ─── Injection Defense ────────────────────────────────────────


def sanitize_for_context(text: str) -> str:
    """Neutralize known injection patterns in text before agent context injection.

    Replaces role boundary tags and strips zero-width Unicode characters to prevent
    second-order prompt injection via stored learning database values.
    """
    if not text:
        return text
    # Neutralize role boundary tags
    for tag in ("system", "user", "assistant", "human"):
        text = text.replace(f"<{tag}>", f"[{tag}]")
        text = text.replace(f"</{tag}>", f"[/{tag}]")
    # Strip zero-width Unicode characters
    zero_width = "\u200b\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\ufeff"
    for ch in zero_width:
        text = text.replace(ch, "")
    return text


def sanitize_fts_query(term: str) -> str:
    """Strip FTS5 operators from a search term to prevent query injection.

    FTS5 operators (NOT, NEAR, AND, OR, *, quotes, parens, minus, colon) are removed
    to ensure terms are treated as plain text matches.
    """
    import re as _re

    # Remove FTS5 special characters
    term = _re.sub(r'["\(\)\*:\-\^\+]', "", term)
    # Remove FTS5 keyword operators (case-insensitive, whole word)
    term = _re.sub(r"\b(NOT|NEAR|AND|OR)\b", "", term, flags=_re.IGNORECASE)
    return term.strip()


# ─── Error Classification (from learning_db.py) ───────────────


def classify_error(message: str) -> str:
    message_lower = message.lower()
    for error_type, patterns in ERROR_TYPES.items():
        if any(re.search(p, message_lower) for p in patterns):
            return error_type
    return "unknown"


def normalize_error(message: str) -> str:
    normalized = message.lower().strip()
    normalized = re.sub(r"[/\\][\w./\\-]+[/\\]", "", normalized)
    normalized = re.sub(r"line \d+", "line N", normalized)
    normalized = re.sub(r"0x[0-9a-f]+", "0xADDR", normalized)
    normalized = re.sub(r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}", "TIMESTAMP", normalized)
    return normalized


def generate_signature(error_message: str, error_type: str) -> str:
    normalized = normalize_error(error_message)
    content = f"{error_type}:{normalized}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


# ─── Core API ──────────────────────────────────────────────────


def record_learning(
    topic: str,
    key: str,
    value: str,
    category: str,
    *,
    confidence: float | None = None,
    tags: list[str] | None = None,
    source: str = "manual",
    source_detail: str | None = None,
    project_path: str | None = None,
    session_id: str | None = None,
    error_signature: str | None = None,
    error_type: str | None = None,
    fix_type: str | None = None,
    fix_action: str | None = None,
) -> dict:
    """Record or update a learning entry.

    If topic+key exists: increment observation_count, update last_seen,
    keep higher confidence, update value only if new is longer.
    """
    init_db()
    now = datetime.now().isoformat()

    if confidence is None:
        confidence = CATEGORY_DEFAULTS.get(category, 0.5)

    tags_str = ",".join(tags) if tags else None

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO learnings
                (topic, key, value, category, confidence, tags,
                 source, source_detail, project_path, session_id,
                 first_seen, last_seen,
                 error_signature, error_type, fix_type, fix_action)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(topic, key) DO UPDATE SET
                value = CASE WHEN length(excluded.value) > length(value) THEN excluded.value ELSE value END,
                confidence = max(confidence, excluded.confidence),
                observation_count = observation_count + 1,
                last_seen = excluded.last_seen,
                source = excluded.source,
                source_detail = excluded.source_detail,
                tags = COALESCE(excluded.tags, tags),
                error_signature = COALESCE(excluded.error_signature, error_signature),
                error_type = COALESCE(excluded.error_type, error_type),
                fix_type = COALESCE(excluded.fix_type, fix_type),
                fix_action = COALESCE(excluded.fix_action, fix_action)
            """,
            (
                topic,
                key,
                value,
                category,
                confidence,
                tags_str,
                source,
                source_detail,
                project_path,
                session_id,
                now,
                now,
                error_signature,
                error_type,
                fix_type,
                fix_action,
            ),
        )
        conn.commit()

        row = conn.execute(
            "SELECT value, confidence, observation_count FROM learnings WHERE topic = ? AND key = ?",
            (topic, key),
        ).fetchone()
        is_new = row["observation_count"] == 1
        return {
            "topic": topic,
            "key": key,
            "value": row["value"],
            "category": category,
            "confidence": row["confidence"],
            "observation_count": row["observation_count"],
            "is_new": is_new,
        }


def query_learnings(
    *,
    topic: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    min_confidence: float = 0.0,
    project_path: str | None = None,
    session_id: str | None = None,
    exclude_graduated: bool = True,
    order_by: str = "confidence DESC",
    limit: int = 50,
) -> list[dict]:
    """Query learnings with filtering and ordering."""
    init_db()

    conditions = ["confidence >= ?"]
    params: list = [min_confidence]

    if topic:
        conditions.append("topic = ?")
        params.append(topic)
    if category:
        conditions.append("category = ?")
        params.append(category)
    if project_path:
        conditions.append("(project_path IS NULL OR project_path = ?)")
        params.append(project_path)
    if session_id:
        conditions.append("session_id = ?")
        params.append(session_id)
    if exclude_graduated:
        conditions.append("graduated_to IS NULL")

    if tags:
        tag_clauses = []
        for tag in tags:
            tag_clauses.append("tags LIKE ?")
            params.append(f"%{tag}%")
        conditions.append(f"({' OR '.join(tag_clauses)})")

    # Whitelist valid ORDER BY to prevent injection
    valid_orders = {
        "confidence DESC",
        "confidence ASC",
        "last_seen DESC",
        "last_seen ASC",
        "observation_count DESC",
        "observation_count ASC",
        "first_seen DESC",
        "first_seen ASC",
    }
    if order_by not in valid_orders:
        order_by = "confidence DESC"

    where = " AND ".join(conditions)
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM learnings WHERE {where} ORDER BY {order_by} LIMIT ?",
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def search_learnings(
    query: str,
    *,
    min_confidence: float = 0.0,
    exclude_graduated: bool = True,
    limit: int = 50,
) -> list[dict]:
    """Full-text search across learnings with BM25 ranking.

    Unlike query_learnings() which matches exact tag substrings,
    this uses FTS5 with porter stemming for fuzzy, ranked retrieval.

    Args:
        query: FTS5 query string. Supports OR/AND operators and prefix
            matching (e.g. "goroutine OR channel", "circuit*").
        min_confidence: Minimum confidence threshold for results.
        exclude_graduated: If True, omit entries that have graduated.
        limit: Maximum number of results to return.

    Returns:
        List of learning dicts ordered by BM25 relevance (best first),
        each with an additional 'rank' key containing the BM25 score.
    """
    init_db()

    if not query or not query.strip():
        return []

    # Sanitize FTS query terms before matching
    query_str = query
    if query_str:
        terms = query_str.split(" OR ")
        terms = [sanitize_fts_query(t.strip()) for t in terms if t.strip()]
        terms = [t for t in terms if t]  # Remove empty after sanitization
        if terms:
            query_str = " OR ".join(terms)
        else:
            return []  # All terms were FTS operators — no valid query

    conditions = ["l.confidence >= ?"]
    params: list = [min_confidence]

    if exclude_graduated:
        conditions.append("l.graduated_to IS NULL")

    where = " AND ".join(conditions)

    with get_connection() as conn:
        try:
            rows = conn.execute(
                f"""
                SELECT l.*, bm25(learnings_fts) AS rank
                FROM learnings_fts fts
                JOIN learnings l ON l.id = fts.rowid
                WHERE learnings_fts MATCH ?
                  AND {where}
                ORDER BY rank
                LIMIT ?
                """,
                (query_str, *params, limit),
            ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.OperationalError:
            # Invalid FTS5 query syntax — fall back to empty results
            return []


def query_graduation_candidates(
    *,
    min_confidence: float = 0.9,
    min_observations: int = 3,
    limit: int = 10,
) -> list[dict]:
    """Return learning entries that are candidates for graduation into agent/skill files.

    Graduation criteria (all must be met):
    - confidence >= min_confidence
    - observation_count >= min_observations
    - graduated_to IS NULL (not already graduated)
    - topic is scoped (starts with 'skill:' or 'agent:')

    Args:
        min_confidence: Minimum confidence threshold (default 0.9).
        min_observations: Minimum observation count (default 3).
        limit: Maximum number of results to return (default 10).

    Returns:
        List of learning dicts sorted by confidence DESC, then observation_count DESC.
        Each dict contains: id, topic, key, value, category, confidence,
        observation_count, first_seen, last_seen, tags.
    """
    init_db()

    params: list = [min_confidence, min_observations]

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, topic, key, value, category, confidence,
                   observation_count, first_seen, last_seen, tags
            FROM learnings
            WHERE confidence >= ?
              AND observation_count >= ?
              AND graduated_to IS NULL
              AND (topic LIKE 'skill:%' OR topic LIKE 'agent:%')
            ORDER BY confidence DESC, observation_count DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def lookup_error_solution(
    error_message: str,
    min_confidence: float = 0.7,
) -> dict | None:
    """Look up a solution for an error pattern. Backward-compatible with error-learner."""
    init_db()

    error_type = classify_error(error_message)
    signature = generate_signature(error_message, error_type)

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT topic, key, value, confidence, fix_type, fix_action, error_signature
            FROM learnings
            WHERE error_signature = ? AND confidence >= ? AND category = 'error'
            """,
            (signature, min_confidence),
        ).fetchone()

        if row:
            return dict(row)
        return None


def boost_confidence(topic: str, key: str, delta: float = 0.10) -> float:
    """Boost confidence for an entry. Returns new confidence."""
    init_db()
    now = datetime.now().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT confidence, success_count FROM learnings WHERE topic = ? AND key = ?",
            (topic, key),
        ).fetchone()
        if not row:
            return 0.0
        new_conf = min(1.0, row["confidence"] + delta)
        conn.execute(
            "UPDATE learnings SET confidence = ?, success_count = success_count + 1, last_seen = ? WHERE topic = ? AND key = ?",
            (new_conf, now, topic, key),
        )
        conn.commit()
        return new_conf


def decay_confidence(topic: str, key: str, delta: float = 0.10) -> float:
    """Decay confidence for an entry. Returns new confidence."""
    init_db()
    now = datetime.now().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT confidence, failure_count FROM learnings WHERE topic = ? AND key = ?",
            (topic, key),
        ).fetchone()
        if not row:
            return 0.0
        new_conf = max(0.0, row["confidence"] - delta)
        conn.execute(
            "UPDATE learnings SET confidence = ?, failure_count = failure_count + 1, last_seen = ? WHERE topic = ? AND key = ?",
            (new_conf, now, topic, key),
        )
        conn.commit()
        return new_conf


def mark_graduated(topic: str, key: str, target: str) -> None:
    """Mark entry as graduated to a permanent location."""
    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE learnings SET graduated_to = ? WHERE topic = ? AND key = ?",
            (target, topic, key),
        )
        conn.commit()


VALID_EVENT_TYPES = {
    "secret_detected",
    "approval_requested",
    "policy_violation",
    "security_finding",
    "hook_blocked",
}

VALID_SEVERITIES = {"critical", "high", "medium", "warning"}

VALID_RESOLUTIONS = {"dismissed", "false_positive", "remediated"}


def record_governance_event(
    event_type: str,
    *,
    session_id: str | None = None,
    tool_name: str | None = None,
    hook_phase: str | None = None,
    severity: str | None = None,
    payload: dict | None = None,
    blocked: bool = False,
    event_id: str | None = None,
) -> str | None:
    """Record a governance event to the governance_events table.

    Recording failures are always silent — this function never raises and
    never causes a hook to block. Returns the event id on success, None on failure.

    Args:
        event_type: One of secret_detected | approval_requested |
                    policy_violation | security_finding | hook_blocked.
        session_id: Claude Code session identifier.
        tool_name: Tool that triggered the event (Bash, Write, Edit, ...).
        hook_phase: 'pre' or 'post'.
        severity: One of critical | high | medium | warning.
        payload: Arbitrary dict serialised as JSON (command fingerprint,
                 matched pattern, secret types, etc.).
        blocked: True if the hook returned exit 2 to block the action.
        event_id: Override auto-generated id (for testing / idempotency).
    """
    import json as _json
    import time as _time

    try:
        init_db()

        ts_ms = int(_time.time() * 1000)
        suffix = hashlib.md5(f"{event_type}{session_id}{ts_ms}".encode()).hexdigest()[:6]
        eid = event_id or f"gov-{ts_ms}-{suffix}"

        payload_str = _json.dumps(payload) if payload else None
        created_at = datetime.now().isoformat()

        with get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO governance_events
                (id, session_id, event_type, tool_name, hook_phase,
                 severity, payload, blocked, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eid,
                    session_id,
                    event_type,
                    tool_name,
                    hook_phase,
                    severity,
                    payload_str,
                    1 if blocked else 0,
                    created_at,
                ),
            )
            conn.commit()
        return eid
    except Exception:
        return None


def resolve_governance_event(
    event_id: str,
    resolution: str,
) -> bool:
    """Mark a governance event as resolved.

    Args:
        event_id: The event id to resolve.
        resolution: One of dismissed | false_positive | remediated.

    Returns:
        True if the event was found and updated, False otherwise.
    """
    if resolution not in VALID_RESOLUTIONS:
        return False

    try:
        init_db()
        resolved_at = datetime.now().isoformat()
        with get_connection() as conn:
            result = conn.execute(
                "UPDATE governance_events SET resolved_at = ?, resolution = ? WHERE id = ?",
                (resolved_at, resolution, event_id),
            )
            conn.commit()
            return result.rowcount > 0
    except Exception:
        return False


def query_governance_events(
    *,
    days: int | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    unresolved_only: bool = False,
    session_id: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """Query governance events with optional filters.

    Args:
        days: Restrict to events created within the last N days.
        event_type: Filter by event type.
        severity: Filter by severity level.
        unresolved_only: If True, return only events with no resolution.
        session_id: Filter by session.
        limit: Maximum rows to return.

    Returns:
        List of event dicts ordered by created_at descending.
    """
    try:
        init_db()

        conditions: list[str] = []
        params: list = []

        if days is not None:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            conditions.append("created_at >= ?")
            params.append(cutoff)

        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)

        if severity:
            conditions.append("severity = ?")
            params.append(severity)

        if unresolved_only:
            conditions.append("resolved_at IS NULL")

        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)

        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM governance_events {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


def record_session(
    session_id: str,
    *,
    files_modified: int = 0,
    tools_used: int = 0,
    errors_encountered: int = 0,
    errors_resolved: int = 0,
    learnings_captured: int = 0,
    project_path: str | None = None,
    end_session: bool = False,
    summary: str | None = None,
) -> None:
    """Record or update session metrics."""
    init_db()
    now = datetime.now().isoformat()

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()

        if row:
            conn.execute(
                """
                UPDATE sessions SET
                    files_modified = files_modified + ?,
                    tools_used = tools_used + ?,
                    errors_encountered = errors_encountered + ?,
                    errors_resolved = errors_resolved + ?,
                    learnings_captured = learnings_captured + ?,
                    end_time = CASE WHEN ? THEN ? ELSE end_time END,
                    summary = COALESCE(?, summary)
                WHERE session_id = ?
                """,
                (
                    files_modified,
                    tools_used,
                    errors_encountered,
                    errors_resolved,
                    learnings_captured,
                    end_session,
                    now if end_session else None,
                    summary,
                    session_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO sessions
                (session_id, start_time, project_path,
                 files_modified, tools_used,
                 errors_encountered, errors_resolved,
                 learnings_captured, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    now,
                    project_path,
                    files_modified,
                    tools_used,
                    errors_encountered,
                    errors_resolved,
                    learnings_captured,
                    summary,
                ),
            )
        conn.commit()


def get_stats() -> dict:
    """Get learning statistics for dashboards."""
    init_db()

    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
        high_conf = conn.execute("SELECT COUNT(*) FROM learnings WHERE confidence >= 0.7").fetchone()[0]
        graduated = conn.execute("SELECT COUNT(*) FROM learnings WHERE graduated_to IS NOT NULL").fetchone()[0]

        by_category = {}
        for row in conn.execute("SELECT category, COUNT(*) as cnt FROM learnings GROUP BY category").fetchall():
            by_category[row["category"]] = row["cnt"]

        by_topic = {}
        for row in conn.execute(
            "SELECT topic, COUNT(*) as cnt FROM learnings GROUP BY topic ORDER BY cnt DESC LIMIT 20"
        ).fetchall():
            by_topic[row["topic"]] = row["cnt"]

        sessions_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        learnings_per_session = total / max(sessions_count, 1)

        return {
            "total_learnings": total,
            "by_category": by_category,
            "by_topic": by_topic,
            "high_confidence": high_conf,
            "graduated": graduated,
            "sessions_tracked": sessions_count,
            "learnings_per_session": round(learnings_per_session, 2),
        }


def prune_ancillary(
    governance_days: int = 180,
    sessions_days: int = 365,
    activations_days: int = 90,
) -> dict[str, int]:
    """Prune old rows from ancillary tables. Returns per-table deletion counts.

    Args:
        governance_days: Delete governance_events older than this many days.
        sessions_days: Delete sessions and session_stats older than this many days.
        activations_days: Delete activations older than this many days.

    Returns:
        Dict mapping table name to number of rows deleted.
    """
    init_db()
    counts: dict[str, int] = {}

    # Table name → (timestamp column, cutoff days)
    table_specs = [
        ("governance_events", "created_at", governance_days),
        ("sessions", "start_time", sessions_days),
        ("session_stats", "created_at", sessions_days),
        ("activations", "timestamp", activations_days),
    ]

    with get_connection() as conn:
        for table, ts_col, days in table_specs:
            try:
                cursor = conn.execute(
                    f"DELETE FROM {table} WHERE {ts_col} < datetime('now', ?)",
                    (f"-{days} days",),
                )
                counts[table] = cursor.rowcount
            except sqlite3.OperationalError:
                counts[table] = 0  # Table may not exist yet
        conn.commit()

    return counts


def prune(min_confidence: float = 0.3, older_than_days: int = 90) -> int:
    """Remove low-confidence entries older than threshold."""
    init_db()
    cutoff = (datetime.now() - timedelta(days=older_than_days)).isoformat()
    with get_connection() as conn:
        result = conn.execute(
            "DELETE FROM learnings WHERE confidence < ? AND last_seen < ? AND graduated_to IS NULL",
            (min_confidence, cutoff),
        )
        conn.commit()
        return result.rowcount


# ─── Import / Export ───────────────────────────────────────────


def import_from_retro(retro_dir: str) -> dict:
    """Import existing retro L2 markdown files into learning.db."""
    retro_path = Path(retro_dir)
    l2_dir = retro_path / "L2"
    if not l2_dir.is_dir():
        return {"imported": 0, "skipped": 0, "errors": ["L2 directory not found"]}

    imported = 0
    skipped = 0
    errors = []

    for md_file in sorted(l2_dir.glob("*.md")):
        try:
            content = md_file.read_text()
            topic = md_file.stem

            # Extract metadata from header
            conf_match = re.search(r"\*\*Confidence\*\*:\s*(\w+)", content)
            confidence_str = conf_match.group(1) if conf_match else "MEDIUM"
            conf_map = {"HIGH": 0.85, "MEDIUM": 0.65, "LOW": 0.45}
            base_confidence = conf_map.get(confidence_str.upper(), 0.65)

            tags_match = re.search(r"\*\*Tags\*\*:\s*(.+)", content)
            tags = [t.strip() for t in tags_match.group(1).split(",")] if tags_match else []

            source_match = re.search(r"\*\*Source\*\*:\s*(.+)", content)
            source_str = f"migrated:{source_match.group(1).strip()}" if source_match else "migrated:retro"

            # Parse entries by ### heading
            parts = re.split(r"(?=^### )", content, flags=re.MULTILINE)
            for part in parts[1:] if len(parts) > 1 else []:
                heading_match = re.match(r"### (.+?)(?:\n|$)", part)
                if not heading_match:
                    continue

                raw_key = heading_match.group(1).strip()

                # Check for graduation marker
                graduated_to = None
                grad_match = re.search(r"\[GRADUATED\s*→\s*(.+?)\]", raw_key)
                if grad_match:
                    graduated_to = grad_match.group(1).strip()
                    raw_key = re.sub(r"\s*\[GRADUATED\s*→\s*.+?\]", "", raw_key).strip()

                # Check for observation count
                obs_match = re.search(r"\[(\d+)x\]", raw_key)
                obs_count = int(obs_match.group(1)) if obs_match else 1
                raw_key = re.sub(r"\s*\[\d+x\]", "", raw_key).strip()

                key = raw_key.lower().replace(" ", "-")
                value = part[len(heading_match.group(0)) :].strip()

                if not value:
                    skipped += 1
                    continue

                result = record_learning(
                    topic=topic,
                    key=key,
                    value=value,
                    category="design",  # Best guess for retro entries
                    confidence=base_confidence,
                    tags=tags if tags else None,
                    source=source_str,
                )

                # Apply graduated_to if present
                if graduated_to:
                    mark_graduated(topic, key, graduated_to)

                # Set observation count directly if > 1
                if obs_count > 1:
                    with get_connection() as conn:
                        conn.execute(
                            "UPDATE learnings SET observation_count = ? WHERE topic = ? AND key = ?",
                            (obs_count, topic, key),
                        )
                        conn.commit()

                imported += 1

        except Exception as e:
            errors.append(f"{md_file.name}: {e}")

    return {"imported": imported, "skipped": skipped, "errors": errors}


def import_from_patterns_db(db_path: str) -> dict:
    """Import existing patterns.db into learning.db."""
    patterns_path = Path(db_path)
    if not patterns_path.exists():
        return {"imported": 0, "skipped": 0, "errors": ["patterns.db not found"]}

    imported = 0
    skipped = 0
    errors = []

    try:
        with sqlite3.connect(patterns_path) as conn_old:
            conn_old.row_factory = sqlite3.Row

            rows = conn_old.execute("SELECT * FROM patterns").fetchall()
            for row in rows:
                try:
                    error_type = row["error_type"]
                    signature = row["signature"]
                    message = row["error_message"]
                    solution = row["solution"] or ""
                    value = f"{message[:200]}"
                    if solution:
                        value += f" → {solution}"

                    record_learning(
                        topic=error_type,
                        key=signature,
                        value=value,
                        category="error",
                        confidence=row["confidence"],
                        source="migrated:patterns-db",
                        project_path=row["project_path"],
                        error_signature=signature,
                        error_type=error_type,
                        fix_type=row["fix_type"],
                        fix_action=row["fix_action"],
                    )

                    # Set counts directly
                    with get_connection() as conn:
                        conn.execute(
                            """
                            UPDATE learnings SET
                                success_count = ?, failure_count = ?,
                                observation_count = ?
                            WHERE topic = ? AND key = ?
                            """,
                            (
                                row["success_count"],
                                row["failure_count"],
                                row["success_count"] + row["failure_count"],
                                error_type,
                                signature,
                            ),
                        )
                        conn.commit()

                    imported += 1
                except Exception as e:
                    errors.append(f"pattern {row['signature']}: {e}")
                    skipped += 1

            # Import sessions too
            try:
                session_rows = conn_old.execute("SELECT * FROM sessions").fetchall()
                for srow in session_rows:
                    record_session(
                        srow["session_id"],
                        files_modified=srow["files_modified"] or 0,
                        tools_used=srow["tools_used"] or 0,
                        errors_encountered=srow["errors_encountered"] or 0,
                        errors_resolved=srow["errors_resolved"] or 0,
                        project_path=srow["project_path"],
                    )
            except Exception:
                pass  # Sessions are nice-to-have

    except Exception as e:
        errors.append(f"database: {e}")

    return {"imported": imported, "skipped": skipped, "errors": errors}


def export_markdown(fmt: str = "l2", output_dir: str | None = None) -> str:
    """Export learnings as markdown for human reading."""
    init_db()

    if fmt == "l1":
        return _export_l1()
    elif fmt == "l2":
        return _export_l2(output_dir)
    elif fmt == "full":
        return _export_full()
    else:
        return f"Unknown format: {fmt}"


def _export_l1() -> str:
    """Generate L1-style summary from learnings."""
    entries = query_learnings(
        min_confidence=0.5,
        exclude_graduated=True,
        order_by="confidence DESC",
        limit=30,
    )

    lines = ["# Accumulated Knowledge (L1 Summary)", ""]

    # Group by topic
    by_topic: dict[str, list[dict]] = {}
    for e in entries:
        t = e["topic"]
        if t not in by_topic:
            by_topic[t] = []
        by_topic[t].append(e)

    line_budget = 30
    lines_used = 2
    for topic, topic_entries in by_topic.items():
        if lines_used >= line_budget:
            break
        heading = topic.replace("-", " ").title() + " Patterns"
        lines.append(f"## {heading}")
        lines_used += 1
        for e in topic_entries:
            if lines_used >= line_budget:
                break
            first_line = e["value"].split("\n")[0][:120]
            lines.append(f"- {e['key']}: {first_line}")
            lines_used += 1
        lines.append("")
        lines_used += 1

    return "\n".join(lines) + "\n"


def _export_l2(output_dir: str | None) -> str:
    """Generate L2-style topic files from learnings."""
    entries = query_learnings(
        exclude_graduated=False,
        order_by="confidence DESC",
        limit=500,
    )

    by_topic: dict[str, list[dict]] = {}
    for e in entries:
        t = e["topic"]
        if t not in by_topic:
            by_topic[t] = []
        by_topic[t].append(e)

    files_written = []
    for topic, topic_entries in by_topic.items():
        all_tags = set()
        for e in topic_entries:
            if e["tags"]:
                all_tags.update(e["tags"].split(","))

        lines = [
            f"# Retro: {topic.replace('-', ' ').title()}",
            "**Source**: learning.db",
            f"**Tags**: {', '.join(sorted(all_tags)) if all_tags else topic}",
            "",
        ]

        for e in topic_entries:
            key_display = e["key"].replace("-", " ").title()
            suffix = ""
            if e["observation_count"] > 1:
                suffix += f" [{e['observation_count']}x]"
            if e["graduated_to"]:
                suffix += f" [GRADUATED → {e['graduated_to']}]"
            lines.append(f"### {key_display}{suffix}")
            lines.append(e["value"])
            lines.append("")

        content = "\n".join(lines)

        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            (out_path / f"{topic}.md").write_text(content)
            files_written.append(f"{topic}.md")
        else:
            files_written.append(content)

    if output_dir:
        return f"Wrote {len(files_written)} files: {', '.join(files_written)}"
    return "\n---\n".join(files_written)


def _export_full() -> str:
    """Full dump with metadata."""
    entries = query_learnings(
        min_confidence=0.0,
        exclude_graduated=False,
        limit=1000,
    )

    lines = ["# Full Learning Database Export", ""]
    for e in entries:
        lines.append(f"## [{e['category']}] {e['topic']}/{e['key']}")
        lines.append(f"- Confidence: {e['confidence']:.2f}")
        lines.append(f"- Observations: {e['observation_count']}")
        lines.append(f"- Source: {e['source']}")
        if e["graduated_to"]:
            lines.append(f"- Graduated to: {e['graduated_to']}")
        lines.append(f"- First seen: {e['first_seen']}")
        lines.append(f"- Last seen: {e['last_seen']}")
        lines.append("")
        lines.append(e["value"])
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    init_db()
    print(f"Database: {get_db_path()}")
    stats = get_stats()
    print(f"Stats: {stats}")
