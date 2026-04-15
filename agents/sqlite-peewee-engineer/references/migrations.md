# Migrations Reference

> **Scope**: Schema changes via `playhouse.migrate`, data migrations, SQLite ALTER TABLE limitations, and rollback procedures.
> **Version range**: Peewee 3.x playhouse, SQLite 3.25+ (for RENAME COLUMN support)
> **Generated**: 2026-04-15 — verify against Peewee playhouse changelog

---

## Overview

SQLite's ALTER TABLE is severely limited compared to other databases: before SQLite 3.35, you could not drop columns; before 3.25, you could not rename them. `playhouse.migrate` wraps these limitations by recreating tables when needed. Always use `playhouse.migrate` for schema changes — raw SQL migrations are untracked, unrollable, and may silently corrupt data on SQLite.

---

## Pattern Table

| Operation | SQLite version | playhouse approach | Notes |
|-----------|---------------|-------------------|-------|
| Add nullable column | all | `add_column` | Safe, no table rewrite |
| Add NOT NULL column | all | `add_column` with default | Must supply default |
| Drop column | 3.35+ | `drop_column` | Older: recreate table manually |
| Rename column | 3.25+ | `rename_column` | Older: recreate table |
| Add index | all | `add_index` | Non-destructive |
| Drop index | all | `drop_index` | Non-destructive |
| Rename table | all | `rename_table` | Updates FK references |
| Change column type | all | No direct support | Recreate table, migrate data |

---

## Correct Patterns

### Standard Schema Migration

All migrations should follow the setup → migrate → verify sequence.

```python
from playhouse.migrate import SqliteMigrator, migrate

# Setup — reuse the same db instance
migrator = SqliteMigrator(db)

# Run migrations in a single atomic block
with db.atomic():
    migrate(
        migrator.add_column('user', 'email', CharField(null=True)),
        migrator.add_index('user', ('email',), unique=True),
    )
```

**Why**: Wrapping in `db.atomic()` ensures all operations succeed or none do. SQLite doesn't support transactional DDL for all operations, but `atomic()` protects the data migration steps.

---

### Adding NOT NULL Column to Existing Table

NOT NULL columns require a default so existing rows aren't violated.

```python
from peewee import CharField, IntegerField

with db.atomic():
    migrate(
        # Approach 1: Add with default (safe for all row counts)
        migrator.add_column(
            'product',
            'quantity',
            IntegerField(default=0)
        ),
    )

# After migration: update rows if default is a placeholder
Product.update(quantity=0).where(Product.quantity.is_null(True)).execute()
```

**Why**: SQLite fills existing rows with the column default at migration time. Without a default, the migration fails with `NOT NULL constraint failed`.

---

### Data Migration Pattern

When migrating data (not just schema), do schema change first, then backfill.

```python
def migrate_add_full_name():
    """Add full_name column derived from first + last name."""

    with db.atomic():
        # Phase 1: schema change
        migrate(
            migrator.add_column('user', 'full_name', CharField(null=True)),
        )

    # Phase 2: backfill in batches (avoids locking DB for long time)
    batch_size = 500
    total = User.select().count()

    for offset in range(0, total, batch_size):
        with db.atomic():
            users = User.select().offset(offset).limit(batch_size)
            for user in users:
                User.update(
                    full_name=f"{user.first_name} {user.last_name}"
                ).where(User.id == user.id).execute()

    # Phase 3: add NOT NULL constraint (requires table recreate in SQLite)
    # — done in a follow-up migration after verifying backfill completed
```

**Why**: Large single-transaction backfills hold an exclusive lock on SQLite. Batching with separate `atomic()` blocks releases locks between batches.

---

### Rollback Script Pattern

Generate a rollback script before running any destructive migration.

```python
def migration_add_status_field():
    """Add status field to Order. Rollback: drop_column."""
    with db.atomic():
        migrate(
            migrator.add_column('order', 'status', CharField(default='pending')),
            migrator.add_index('order', ('status',), unique=False),
        )

def rollback_add_status_field():
    """Undo migration_add_status_field."""
    with db.atomic():
        migrate(
            migrator.drop_index('order', 'order_status'),
            migrator.drop_column('order', 'status'),
        )
```

**Why**: Having explicit rollback functions paired with each migration makes recovery deterministic. Comment at the top of the migration naming its inverse.

---

## Anti-Pattern Catalog

### ❌ Raw SQL for Schema Changes

**Detection**:
```bash
grep -rn "execute_sql.*ALTER\|execute_sql.*CREATE\|execute_sql.*DROP" --include="*.py"
rg "db\.execute_sql\(" --type py -A 1 | grep -i "alter\|create table\|drop"
```

**What it looks like**:
```python
db.execute_sql("ALTER TABLE user ADD COLUMN phone TEXT")
db.execute_sql("CREATE INDEX idx_user_email ON user(email)")
```

**Why wrong**: Raw DDL bypasses playhouse tracking. No rollback path. On SQLite, `ALTER TABLE` silently ignores constraints that work on PostgreSQL. Leads to schema drift across environments.

**Fix**:
```python
from playhouse.migrate import SqliteMigrator, migrate

migrator = SqliteMigrator(db)
with db.atomic():
    migrate(
        migrator.add_column('user', 'phone', CharField(null=True)),
        migrator.add_index('user', ('phone',), unique=False),
    )
```

---

### ❌ Running Migrations Outside of atomic()

**Detection**:
```bash
grep -rn "^migrate(" --include="*.py"
grep -rn "migrator\." --include="*.py" -B 2 | grep -v "atomic\|with db"
```

**What it looks like**:
```python
migrator = SqliteMigrator(db)
migrate(
    migrator.add_column('user', 'email', CharField(null=True)),
    migrator.add_column('user', 'phone', CharField(null=True)),
)
# If second add_column fails, first is already committed — schema is half-migrated
```

**Why wrong**: Multiple DDL operations without `atomic()` can partially apply. On SQLite, DDL is implicitly committed after each statement. A failed second operation leaves a corrupted schema state.

**Fix**:
```python
with db.atomic():
    migrate(
        migrator.add_column('user', 'email', CharField(null=True)),
        migrator.add_column('user', 'phone', CharField(null=True)),
    )
```

**Version note**: SQLite does not support transactional DDL for all statement types. For table recreations (e.g., drop column on SQLite < 3.35), playhouse falls back to CREATE + INSERT + DROP, which `atomic()` protects.

---

### ❌ Skipping Migration for "Simple" Changes

**Detection**:
```bash
# Find schema changes in model files that aren't in a migration function
grep -rn "class Meta" --include="*.py" -A 10 | grep "indexes\|constraints"
# Compare against migration files
grep -rn "add_column\|add_index\|drop_column" --include="*.py"
```

**What it looks like**:
```python
class User(Model):
    username = CharField()
    # "I'll just add this directly, it's a test DB"
    phone = CharField(null=True)  # Added to model but no migration
```

**Why wrong**: Model changes without migrations cause `OperationalError: no such column: user.phone` in any environment where the DB was created before the change. This is always discovered at the worst time.

**Fix**: Every model field addition must have a corresponding migration. Verify schema matches model on startup with:
```python
# Check column exists on startup
db.execute_sql("SELECT phone FROM user LIMIT 1")
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `OperationalError: no such column: table.column` | Migration not run in this environment | Run migration, or check migration version tracking |
| `IntegrityError: NOT NULL constraint failed` | Added NOT NULL column without default | Add `default=value` to field definition in migration |
| `OperationalError: duplicate column name: column` | Migration ran twice | Add migration version tracking (see below) |
| `OperationalError: no such table: old_table` | rename_table migration partially applied | Check if atomic() was used; recreate if corrupted |
| `OperationalError: Cannot add a NOT NULL column with default value NULL` | SQLite strict NULL check | Always provide a non-None default for NOT NULL additions |

---

## Migration Version Tracking

Peewee does not ship a migrations table by default. Implement a simple one:

```python
class MigrationHistory(Model):
    name = CharField(unique=True)
    applied_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        database = db

def run_migration(name: str, fn):
    """Run migration only if not previously applied."""
    db.create_tables([MigrationHistory], safe=True)

    if MigrationHistory.select().where(MigrationHistory.name == name).exists():
        print(f"[skip] {name} already applied")
        return

    fn()
    MigrationHistory.create(name=name)
    print(f"[done] {name}")

# Usage
run_migration("2026-01-01_add_user_email", migration_add_email)
```

---

## Detection Commands Reference

```bash
# Raw DDL bypassing playhouse
grep -rn "execute_sql.*ALTER\|execute_sql.*CREATE\|execute_sql.*DROP" --include="*.py"

# Migrations outside atomic()
grep -rn "^migrate(" --include="*.py"

# Model fields without corresponding migrations
grep -rn "ForeignKeyField\|CharField\|IntegerField" --include="*.py" models/
grep -rn "add_column\|drop_column" --include="*.py" migrations/
```

---

## See Also

- `query-optimization.md` — Adding indexes to improve query performance
- `sqlite-features.md` — SQLite ALTER TABLE limitations by version
- [Peewee Migrations docs](https://docs.peewee-orm.com/en/latest/peewee/playhouse.html#schema-migrations)
