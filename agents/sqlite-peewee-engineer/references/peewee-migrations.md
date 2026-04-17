# Peewee Migrations & SQLite Schema Patterns

> **Scope**: Playhouse migrate operations, SQLite ALTER TABLE limitations, data migrations, and rollback procedures.
> **Version range**: Peewee 3.x playhouse.migrate, SQLite 3.25+ (window functions), SQLite 3.35+ (DROP COLUMN)
> **Generated**: 2026-04-14 — verify SQLite version availability in target deployment

---

## Overview

SQLite's ALTER TABLE support is intentionally minimal — before SQLite 3.35, only `ADD COLUMN`
and `RENAME TABLE` were available. All other schema changes require the "12-step" table rebuild
procedure. Peewee's `playhouse.migrate` abstracts this correctly, but only if you use it.
Manual `execute_sql()` schema changes are the primary source of environment drift and broken
rollbacks in SQLite applications.

---

## Pattern Table

| Operation | SQLite Support | Playhouse Method | Notes |
|-----------|---------------|-----------------|-------|
| Add column | All versions | `add_column()` | NULL default required for existing rows |
| Rename column | 3.25+ | `rename_column()` | Before 3.25: table rebuild |
| Drop column | 3.35+ | `drop_column()` | Before 3.35: table rebuild required |
| Add index | All versions | `add_index()` | Non-blocking in SQLite |
| Drop index | All versions | `drop_index()` | By index name, not column |
| Add NOT NULL | Never directly | Table rebuild | SQLite can't modify column constraints |
| Change column type | Never directly | Table rebuild | SQLite ignores type affinity changes |
| Add FK constraint | Never directly | Table rebuild | FK constraints are table-level in SQLite |

---

## Correct Patterns

### Standard Column Addition

Add a nullable column first, then backfill, then add constraints in a separate migration.

```python
from playhouse.migrate import SqliteMigrator, migrate
from peewee import TextField, IntegerField

def run_migration(db):
    migrator = SqliteMigrator(db)

    with db.atomic():
        migrate(
            # NULL required — existing rows cannot satisfy NOT NULL without backfill
            migrator.add_column('user', 'bio', TextField(null=True)),
            migrator.add_column('post', 'view_count', IntegerField(default=0)),
        )

    # Backfill after schema change, within same transaction if small dataset
    with db.atomic():
        db.execute_sql("UPDATE user SET bio = '' WHERE bio IS NULL")
```

**Why**: SQLite requires all existing rows to satisfy the column's default. Adding a NOT NULL
column without a default fails on non-empty tables. The two-step (add nullable, backfill, then
constrain) is the safe pattern for any non-empty production table.

---

### Table Rebuild for Unsupported Changes

For changes SQLite can't do directly (changing column type, removing NOT NULL, adding FK),
use the explicit 12-step rebuild. Playhouse does this internally for some operations.

```python
def rebuild_table_with_new_schema(db):
    """Manual table rebuild when ALTER TABLE can't handle the change."""
    with db.atomic():
        # Step 1: Create new table with desired schema
        db.execute_sql('''
            CREATE TABLE user_new (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,          -- Changed from nullable
                created_at REAL NOT NULL       -- Changed from INTEGER
            )
        ''')

        # Step 2: Copy data with any needed transforms
        db.execute_sql('''
            INSERT INTO user_new (id, username, email, created_at)
            SELECT id, username,
                   COALESCE(email, 'unknown@example.com'),  -- Backfill nulls
                   CAST(created_at AS REAL)
            FROM user
        ''')

        # Step 3: Drop old table
        db.execute_sql('DROP TABLE user')

        # Step 4: Rename new table
        db.execute_sql('ALTER TABLE user_new RENAME TO user')

        # Step 5: Recreate indexes (dropped with old table)
        db.execute_sql('CREATE INDEX idx_user_email ON user(email)')
```

**Why**: SQLite's ALTER TABLE cannot change column types, remove NOT NULL, or add FK constraints
to existing tables. The rebuild copies data while applying transformations, then atomically
swaps the table. All steps in one `db.atomic()` block ensure the table never exists in a
partial state.

---

### Tracking Migration State

A simple migration version table avoids re-running migrations on restart.

```python
from peewee import Model, CharField, DateTimeField
from datetime import datetime

class Migration(Model):
    name = CharField(unique=True)
    applied_at = DateTimeField(default=datetime.utcnow)

    class Meta:
        database = db

def has_run(name: str) -> bool:
    return Migration.select().where(Migration.name == name).exists()

def mark_run(name: str):
    Migration.create(name=name)

def run_migrations(db):
    Migration.create_table(safe=True)

    if not has_run('001_add_email_to_user'):
        migrator = SqliteMigrator(db)
        with db.atomic():
            migrate(migrator.add_column('user', 'email', TextField(null=True)))
            mark_run('001_add_email_to_user')

    if not has_run('002_add_post_index'):
        migrator = SqliteMigrator(db)
        with db.atomic():
            migrate(migrator.add_index('post', ('user_id', 'created_at'), False))
            mark_run('002_add_post_index')
```

---

### Data Migration with Progress Tracking

For large table transforms, batch updates avoid locking the database.

```python
def backfill_in_batches(db, batch_size=1000):
    """Backfill with batches to avoid long-running write locks."""
    offset = 0
    total = db.execute_sql('SELECT COUNT(*) FROM post WHERE slug IS NULL').fetchone()[0]

    while offset < total:
        with db.atomic():
            rows = db.execute_sql(
                'SELECT id, title FROM post WHERE slug IS NULL LIMIT ? OFFSET ?',
                (batch_size, offset)
            ).fetchall()

            if not rows:
                break

            for row_id, title in rows:
                slug = title.lower().replace(' ', '-')
                db.execute_sql('UPDATE post SET slug = ? WHERE id = ?', (slug, row_id))

        offset += batch_size
        print(f'Backfilled {min(offset, total)}/{total} rows')
```

**Why**: Long-running write transactions block all other writes in SQLite (WAL mode) or all
reads AND writes (default journal mode). Batching limits each lock window to `batch_size` rows.

---

## Anti-Pattern Catalog
<!-- no-pair-required: section header with no content -->

### ❌ Manual SQL for Schema Changes

**Detection**:
```bash
# Find raw execute_sql calls that look like schema changes
grep -rn 'execute_sql.*ALTER TABLE\|execute_sql.*CREATE TABLE\|execute_sql.*DROP TABLE' --include="*.py"
rg 'execute_sql\([\'\"](ALTER|CREATE|DROP)' --type py
```

**Do instead:** Use `playhouse.migrate` — see fix below.

**What it looks like**:
```python
# WRONG: Bypasses Playhouse migration tracking and SQLite safety checks
db.execute_sql("ALTER TABLE user ADD COLUMN phone TEXT")
db.execute_sql("DROP TABLE IF EXISTS temp_data")
```

**Why wrong**: Raw schema SQL skips Playhouse's pre-flight checks (e.g., does column already
exist?), produces no migration record, and on SQLite may silently succeed when the operation
has unintended side effects (like dropping all triggers on a table).

**Do instead:**

Use `playhouse.migrate` for all schema changes so operations are tracked, pre-flight checked,
and wrapped in a single atomic call:

```python
from playhouse.migrate import SqliteMigrator, migrate
from peewee import TextField

migrator = SqliteMigrator(db)
with db.atomic():
    migrate(migrator.add_column('user', 'phone', TextField(null=True)))
```

---

### ❌ Adding NOT NULL Column Without Default on Non-Empty Table

**Detection**:
```bash
grep -rn 'add_column' --include="*.py" -A 2 | grep -v 'null=True\|default='
rg 'add_column\([^)]*\)' --type py | grep -v 'null=True|default='
```

**Do instead:** Add the column as `null=True` first, backfill existing rows, then constrain in a later migration.

**What it looks like**:
```python
# FAILS on any non-empty table — existing rows have no value for 'status'
migrate(migrator.add_column('post', 'status', CharField()))
```

**Why wrong**: SQLite requires all existing rows to have a valid value for the new column.
A non-null column with no default fails with `OperationalError: Cannot add a NOT NULL column
with default value NULL`.

**Do instead:**

Add the column as nullable, backfill existing rows, then enforce the constraint via a table
rebuild in a separate migration if strictly required:

```python
# Step 1: Add as nullable
migrate(migrator.add_column('post', 'status', CharField(null=True)))

# Step 2: Backfill
db.execute_sql("UPDATE post SET status = 'draft' WHERE status IS NULL")

# Step 3: In a later migration — if NOT NULL constraint truly needed,
# requires table rebuild (SQLite can't ADD CONSTRAINT to existing column)
```

---

### ❌ Dropping Column on SQLite < 3.35

**Detection**:
```bash
grep -rn 'drop_column' --include="*.py"
rg 'migrator\.drop_column\(' --type py
```

**Do instead:** Guard with a SQLite version check and fall back to a table rebuild on older SQLite.

**What it looks like**:
```python
# Fails silently or errors on SQLite < 3.35
migrate(migrator.drop_column('user', 'legacy_field'))
```

**Why wrong**: `DROP COLUMN` was not supported in SQLite before version 3.35 (released 2021-03-12).
Many Linux distributions ship SQLite 3.31 or earlier. Calling `drop_column()` on older SQLite
either raises `OperationalError` or does nothing depending on Playhouse version.

**Do instead:**

Check the SQLite version at migration time and either call `drop_column()` on 3.35+ or raise
with a clear message directing the developer to implement a table rebuild:

```python
import sqlite3

def sqlite_version(db):
    return db.execute_sql('SELECT sqlite_version()').fetchone()[0]

def drop_column_safe(db, table, column):
    version = tuple(int(x) for x in sqlite_version(db).split('.'))
    if version >= (3, 35, 0):
        migrator = SqliteMigrator(db)
        migrate(migrator.drop_column(table, column))
    else:
        # Must do table rebuild — log warning and implement manually
        raise RuntimeError(
            f'SQLite {sqlite_version(db)} does not support DROP COLUMN. '
            'Implement table rebuild or upgrade SQLite.'
        )
```

**Version note**: SQLite 3.35 shipped 2021-03-12. Ubuntu 20.04 LTS ships SQLite 3.31.1.
Ubuntu 22.04 LTS ships SQLite 3.37.2 (supports DROP COLUMN).

---

### ❌ Running Schema Changes Outside Transaction

**Detection**:
```bash
grep -rn 'migrate(' --include="*.py" -B 3 | grep -v 'atomic\|with db'
rg 'migrate\(' --type py -B 3 | grep -v 'atomic'
```

**Do instead:** Wrap all `migrate()` calls in a single `db.atomic()` block so they commit together or roll back together.

**What it looks like**:
```python
migrator = SqliteMigrator(db)
migrate(migrator.add_column('user', 'email', TextField(null=True)))  # No atomic()!
migrate(migrator.add_index('user', ('email',), False))               # Separate call
# If second migrate() fails, first is committed — schema partially updated
```

**Why wrong**: Each `migrate()` call is its own implicit transaction. If the second call fails,
the first is already committed. The schema is now partially updated with no clean rollback path.

**Do instead:**

Pass all related operations to a single `migrate()` call inside `db.atomic()` so they form
one atomic unit:

```python
with db.atomic():
    migrate(
        migrator.add_column('user', 'email', TextField(null=True)),
        migrator.add_index('user', ('email',), False),
    )
# All operations committed together or all rolled back
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `OperationalError: Cannot add a NOT NULL column with default value NULL` | Adding non-null column to non-empty table | Add as `null=True`, then backfill, then rebuild table if constraint needed |
| `OperationalError: table {name} already exists` | Migration ran twice, no tracking | Implement migration version table; use `safe=True` for `create_tables()` |
| `OperationalError: duplicate column name: {name}` | `add_column` on existing column | Check `PRAGMA table_info({table})` before adding; use migration tracking |
| `OperationalError: no such column: {name}` | Accessing column that doesn't exist in current schema | Run missing migration; verify migration order |
| `OperationalError: near "DROP": syntax error` | DROP COLUMN on SQLite < 3.35 | Check SQLite version; use table rebuild for older SQLite |
| `IntegrityError: UNIQUE constraint failed` | Backfilling duplicate values into unique column | Deduplicate data before adding unique index |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| SQLite 3.25 | `RENAME COLUMN` added | Before 3.25: column rename requires table rebuild |
| SQLite 3.35 | `DROP COLUMN` added | Before 3.35: column removal requires table rebuild |
| SQLite 3.37 | `STRICT` tables | Enforces strict type checking; opt-in per table |
| SQLite 3.38 | `RETURNING` clause | `INSERT ... RETURNING id` available (Peewee uses rowid instead) |
| Peewee 3.17 | `MigrationError` added | Better error messages for failed migrate() calls |

---

## Detection Commands Reference

```bash
# Raw SQL schema changes (should use Playhouse instead)
grep -rn 'execute_sql.*ALTER TABLE\|execute_sql.*CREATE TABLE' --include="*.py"

# NOT NULL column added without null=True (will fail on non-empty tables)
rg 'add_column\([^)]*\)' --type py | grep -v 'null=True|default='

# Drop column usage (check SQLite version compatibility)
grep -rn 'drop_column' --include="*.py"

# migrate() outside atomic() context
rg 'migrate\(' --type py -B 3 | grep -v 'atomic'

# No migration tracking table (re-run risk)
grep -rn 'run_migration\|apply_migration\|migrate(' --include="*.py" | grep -v 'Migration\.'
```

---

## See Also

- `peewee-query-patterns.md` — query optimization and index strategy
- `peewee-testing.md` — testing migration scripts with in-memory databases
- [Playhouse Migrations Docs](https://docs.peewee-orm.com/en/latest/peewee/playhouse.html#schema-migrations)
- [SQLite ALTER TABLE Docs](https://www.sqlite.org/lang_altertable.html)
