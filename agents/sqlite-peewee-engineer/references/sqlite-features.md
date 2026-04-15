# SQLite Features Reference

> **Scope**: SQLite-specific capabilities and constraints relevant to Peewee apps: WAL mode, pragmas, JSON1, FTS5, concurrency limits, and EXPLAIN QUERY PLAN usage.
> **Version range**: SQLite 3.35+ (3.38+ for JSON functions), all Peewee 3.x
> **Generated**: 2026-04-15 — SQLite version bundled with Python can lag behind; check `sqlite3.sqlite_version`

---

## Overview

SQLite is a file-based database with no separate server process. Its main constraints are: one writer at a time (in WAL mode: one writer plus multiple concurrent readers), no user management, and limited ALTER TABLE support. Its strengths are zero-config setup, embedded JSON1 and FTS5 extensions, and excellent read concurrency with WAL enabled.

---

## Pattern Table

| Feature | SQLite Version | Peewee Access | Notes |
|---------|---------------|--------------|-------|
| WAL mode | 3.7.0+ | `PRAGMA journal_mode=WAL` | Enables concurrent readers during writes |
| JSON1 extension | 3.38+ (built-in), 3.9+ (loadable) | `JSONField` from playhouse | Bundled in Python 3.12+ SQLite |
| FTS5 full-text search | 3.9+ | `FTSModel` from playhouse | Replaces FTS4 |
| Generated columns | 3.31+ | Raw SQL only | Not exposed in Peewee ORM |
| WITHOUT ROWID | 3.8.2+ | Raw SQL only | For wide tables with natural PKs |
| RENAME COLUMN | 3.25+ | `migrator.rename_column` | |
| DROP COLUMN | 3.35+ | `migrator.drop_column` | |
| RETURNING clause | 3.35+ | `Model.insert().returning()` | Peewee 3.15+ |

---

## Correct Patterns

### WAL Mode Pragma (Always Set)

Enable WAL and key performance pragmas on database initialization.

```python
from peewee import SqliteDatabase

db = SqliteDatabase(
    'app.db',
    pragmas={
        'journal_mode': 'wal',        # WAL enables concurrent reads
        'cache_size': -1 * 64 * 1000, # 64MB page cache
        'foreign_keys': 1,            # Enforce FK constraints
        'ignore_check_constraints': 0,
        'synchronous': 1,             # NORMAL — safe and faster than FULL
    }
)
```

**Why**: Default journal mode is DELETE (rollback journal), which blocks all reads during writes. WAL allows readers to continue while a write is in progress. `foreign_keys=1` is OFF by default in SQLite — required for ON DELETE CASCADE to work.

---

### EXPLAIN QUERY PLAN for Index Verification

Verify that queries actually use indexes before claiming they're optimized.

```python
# Check if a query uses the index you added
cursor = db.execute_sql(
    "EXPLAIN QUERY PLAN SELECT * FROM post WHERE user_id=? AND created_at>?",
    (1, '2026-01-01')
)
for row in cursor.fetchall():
    print(row)
# Output showing SEARCH post USING INDEX ... means index hit
# Output showing SCAN post means full table scan
```

```bash
# From command line
sqlite3 app.db "EXPLAIN QUERY PLAN SELECT * FROM post WHERE user_id=1 AND created_at>'2026-01-01'"
```

**Why**: Adding an index to a model doesn't guarantee SQLite uses it. Query planner uses indexes only when the leading column of a compound index matches the WHERE clause. EXPLAIN QUERY PLAN catches this before it hits production.

---

### JSON1 Extension with Peewee

```python
from playhouse.sqlite_ext import JSONField, SqliteExtDatabase

db = SqliteExtDatabase('app.db', pragmas={'foreign_keys': 1})

class Config(Model):
    key = CharField(unique=True)
    value = JSONField()  # Stored as TEXT, queried with JSON functions

    class Meta:
        database = db

# Store arbitrary JSON
Config.create(key='feature_flags', value={'beta': True, 'max_items': 100})

# Query into JSON — Peewee exposes JSON_EXTRACT via fn
from peewee import fn
result = Config.select().where(
    fn.JSON_EXTRACT(Config.value, '$.beta') == True
)
```

**Version note**: `JSON_EXTRACT()` available since SQLite 3.9. If using Python's bundled SQLite on older systems, check `import sqlite3; sqlite3.sqlite_version` before relying on JSON1.

---

### FTS5 Full-Text Search

```python
from playhouse.sqlite_ext import FTS5Model, SearchField, RowIDField

class DocumentIndex(FTS5Model):
    rowid = RowIDField()
    title = SearchField()
    body = SearchField()

    class Meta:
        database = db
        options = {
            'tokenize': 'porter unicode61',  # Stemming + Unicode support
        }

# Create virtual table
db.create_tables([DocumentIndex])

# Populate from main table
for doc in Document.select():
    DocumentIndex.create(rowid=doc.id, title=doc.title, body=doc.body)

# Search — BM25 ranking built in
results = (DocumentIndex
    .search_bm25('python database patterns', weights={'title': 2.0, 'body': 1.0})
    .limit(10))

for result in results:
    doc = Document.get_by_id(result.rowid)
    print(doc.title, result.bm25())
```

**Why**: FTS5 uses BM25 ranking by default (vs FTS4's TF-IDF). Always use `unicode61` tokenizer for non-ASCII content. FTS virtual tables can't use foreign keys or indexes.

---

## Anti-Pattern Catalog

### ❌ Missing foreign_keys Pragma

**Detection**:
```bash
grep -rn "SqliteDatabase\|pragmas" --include="*.py" | grep -v "foreign_keys"
grep -rn "SqliteDatabase(" --include="*.py" -A 5 | grep -v "foreign_keys"
```

**What it looks like**:
```python
db = SqliteDatabase('app.db')
# No pragmas — foreign keys OFF by default
```

**Why wrong**: SQLite ships with foreign key enforcement disabled for backwards compatibility. `ON DELETE CASCADE`, `ON UPDATE CASCADE`, and FK constraint violations are silently ignored without `PRAGMA foreign_keys=1`. You discover this when production data has orphaned rows.

**Fix**:
```python
db = SqliteDatabase('app.db', pragmas={'foreign_keys': 1})
```

---

### ❌ Concurrent Writes Without WAL

**Detection**:
```bash
grep -rn "SqliteDatabase(" --include="*.py" -A 5 | grep -v "journal_mode\|wal"
grep -rn "threading\|concurrent\|ThreadPool\|asyncio" --include="*.py"
```

**What it looks like**:
```python
db = SqliteDatabase('app.db')  # Default: DELETE journal mode

# In a Flask/FastAPI app with multiple workers or threads
# → OperationalError: database is locked
```

**Why wrong**: Default DELETE mode uses an exclusive lock for the entire write duration. Any concurrent reader blocks. In web servers with thread workers, this causes frequent `database is locked` errors under load.

**Fix**:
```python
db = SqliteDatabase('app.db', pragmas={
    'journal_mode': 'wal',
    'busy_timeout': 5000,  # Wait up to 5s before raising "database is locked"
})
```

**Version note**: WAL mode is available since SQLite 3.7.0 (2010). Safe to use universally.

---

### ❌ Using FTS4 Instead of FTS5

**Detection**:
```bash
grep -rn "FTS4Model\|fts4" --include="*.py"
grep -rn "using fts4\|create virtual.*fts4" --include="*.py" -i
```

**What it looks like**:
```python
from playhouse.sqlite_ext import FTS4Model, SearchField

class SearchIndex(FTS4Model):
    content = SearchField()
```

**Why wrong**: FTS4 is deprecated since SQLite 3.9 (2015). FTS5 has better ranking (BM25), better Unicode support, and active development. FTS4 will not receive bug fixes.

**Fix**:
```python
from playhouse.sqlite_ext import FTS5Model, SearchField

class SearchIndex(FTS5Model):
    content = SearchField()

    class Meta:
        options = {'tokenize': 'porter unicode61'}
```

---

### ❌ Long-Running Transactions on SQLite

**Detection**:
```bash
grep -rn "with db.atomic()" --include="*.py" -A 20 | grep -E "sleep|time\.sleep|\.all()\b|len\("
```

**What it looks like**:
```python
with db.atomic():
    # Process 50,000 records
    for record in LargeTable.select():
        process_and_update(record)  # Holds write lock entire time
```

**Why wrong**: SQLite write lock is held for the entire transaction duration. Other processes (web workers, cron jobs) can't write during this time. `busy_timeout` eventually raises `OperationalError`.

**Fix**: Batch into chunks, committing each batch separately.
```python
batch_size = 500
query = LargeTable.select()
total = query.count()

for offset in range(0, total, batch_size):
    with db.atomic():  # Lock held only for batch duration
        batch = list(query.offset(offset).limit(batch_size))
        for record in batch:
            process_and_update(record)
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `OperationalError: database is locked` | Concurrent write in non-WAL mode, or long transaction | Enable WAL mode; set `busy_timeout`; batch long transactions |
| `OperationalError: unable to open database file` | Path doesn't exist or permissions issue | Verify directory exists; check filesystem permissions |
| `OperationalError: no such function: json_extract` | SQLite < 3.9 or JSON1 not compiled in | Check `sqlite3.sqlite_version`; upgrade Python/SQLite |
| `OperationalError: no such module: fts5` | SQLite compiled without FTS5 (rare on modern systems) | Check `sqlite3.sqlite_version_info >= (3, 9, 0)` |
| `IntegrityError: FOREIGN KEY constraint failed` | FK enforcement is OFF — this means you added `foreign_keys=1` and found a bug | Audit orphaned rows; add pragma permanently |
| `OperationalError: table user has no column named email` | Migration not run; model and DB out of sync | Run pending migrations; check migration version table |

---

## SQLite Version Check

```python
import sqlite3

version = sqlite3.sqlite_version_info
print(f"SQLite {sqlite3.sqlite_version}")

# Feature availability
features = {
    'WAL mode': version >= (3, 7, 0),
    'FTS5': version >= (3, 9, 0),
    'JSON1': version >= (3, 9, 0),
    'RENAME COLUMN': version >= (3, 25, 0),
    'DROP COLUMN': version >= (3, 35, 0),
    'RETURNING': version >= (3, 35, 0),
    'JSON built-in (no ext)': version >= (3, 38, 0),
}

for feature, available in features.items():
    status = "✓" if available else "✗"
    print(f"  {status} {feature}")
```

---

## Detection Commands Reference

```bash
# Missing foreign_keys pragma
grep -rn "SqliteDatabase(" --include="*.py" -A 5 | grep -v "foreign_keys"

# Missing WAL mode
grep -rn "SqliteDatabase(" --include="*.py" -A 5 | grep -v "journal_mode\|wal"

# FTS4 usage (deprecated)
grep -rn "FTS4Model\|fts4" --include="*.py"

# Long transactions (heuristic — large selects inside atomic)
grep -rn "with db.atomic()" --include="*.py" -A 10 | grep "\.select()"
```

---

## See Also

- `query-optimization.md` — EXPLAIN QUERY PLAN usage and index strategies
- `migrations.md` — SQLite ALTER TABLE version constraints
- [SQLite pragma documentation](https://www.sqlite.org/pragma.html)
- [Peewee SQLite Extensions](https://docs.peewee-orm.com/en/latest/peewee/sqlite_ext.html)
