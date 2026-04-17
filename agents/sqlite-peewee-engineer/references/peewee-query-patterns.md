# Peewee Query Patterns & Optimization

> **Scope**: N+1 prevention, prefetch patterns, index strategy, and SQLite-specific query optimization using Peewee ORM.
> **Version range**: Peewee 3.x, SQLite 3.35+ (generated columns), Python 3.8+
> **Generated**: 2026-04-14 — verify against current Peewee changelog

---

## Overview

The most common performance failures in Peewee/SQLite are N+1 queries (accessing related models
inside a loop without prefetch) and missing indexes on foreign keys. Peewee's `prefetch()` and
`join()` solve N+1 in fundamentally different ways — choosing the wrong one produces either
cartesian products or extra round-trips. SQLite adds a constraint: `EXPLAIN QUERY PLAN` is the
primary tool for diagnosing slow queries, not pg_explain.

---

## Pattern Table

| Pattern | Peewee Version | Use When | Avoid When |
|---------|---------------|----------|------------|
| `prefetch(Model)` | 3.0+ | Loading reverse FK relations in lists | Loading single object or filtering on related |
| `join(Model)` | 3.0+ | Filtering/ordering on related field | Loading many related objects (cartesian product) |
| `select_related()` | 3.0+ | Loading FK (forward) in loops | Reverse relations (use prefetch instead) |
| `join_lazy(Model)` | 3.15+ | Optional related load, query-time decision | Always-needed related data |
| `SQL('EXPLAIN QUERY PLAN ...')` | all | Diagnosing full table scans | N/A |
| `WITHOUT ROWID` table | SQLite 3.8.2+ | Small lookup tables, composite PK | Tables needing rowid access patterns |

---

## Correct Patterns

### Prefetch for Reverse FK Relations

`prefetch()` executes exactly 2 SQL queries: one for the primary model, one for each prefetched
relation. Related objects are attached in Python, not via JOIN.

```python
# Load users with all their posts — 2 queries total
users = User.select().prefetch(Post)
for user in users:
    for post in user.posts:  # No additional queries
        print(post.title)
```

**Why**: Each `user.posts` access without prefetch executes a new SELECT. With 100 users that's
101 queries. Prefetch flattens this to 2 queries regardless of user count.

---

### Join for Filter/Order on Related Field

Use `join()` when you need to filter or order by a related model's field, not to load the related
model itself.

```python
# Find users who have published posts — efficient single query
users = (User
    .select()
    .join(Post)
    .where(Post.status == 'published')
    .distinct())

# Order users by most recent post date
users = (User
    .select(User, fn.MAX(Post.created_at).alias('last_post'))
    .join(Post, JOIN.LEFT_OUTER)
    .group_by(User.id)
    .order_by(fn.MAX(Post.created_at).desc()))
```

**Why**: `prefetch()` can't filter — it loads all related rows. Use `join()` when the related
table drives the WHERE or ORDER BY clause.

---

### WAL Mode for Read-Heavy Workloads

Enable Write-Ahead Logging to allow concurrent readers during writes. Set once at connection time.

```python
from peewee import SqliteDatabase

db = SqliteDatabase('app.db', pragmas={
    'journal_mode': 'wal',       # Allow concurrent reads during writes
    'cache_size': -1024 * 64,    # 64MB cache
    'foreign_keys': 1,            # Enforce FK constraints
    'synchronous': 'normal',      # Balance safety/speed (vs. 'full')
})
```

**Why**: Default SQLite journal mode blocks all readers during any write. WAL mode allows
readers to continue while a write transaction is open, essential for web applications.

---

### Targeted SELECT to Avoid Overfetch
<!-- no-pair-required: positive pattern section, title contains 'avoid' triggering false positive -->

Specify only needed columns — prevents loading TEXT/BLOB columns when only IDs or names needed.

```python
# Bad: loads all columns including large blob fields
users = User.select()

# Good: load only what the template needs
users = User.select(User.id, User.username, User.email)

# Named tuples for clean attribute access on partial selects
from peewee import ModelSelect
users = User.select(User.id, User.username).namedtuples()
for u in users:
    print(u.username)  # Works without model overhead
```

---

## Pattern Catalog
<!-- no-pair-required: section header with no content -->

### ❌ N+1 Queries via Loop Attribute Access

**Detection**:
```bash
# Find .select() followed by attribute access on related model in loop
grep -rn '\.select()' --include="*.py" -A 10 | grep -B 5 'for .* in '
# More targeted: find ForeignKeyField backrefs accessed in for loops
rg 'for \w+ in \w+\.\w+:' --type py
rg '\.select\(\)' --type py -A 5 | grep '\.\w+\.\w+'
```

**Do instead:** Use `User.select().prefetch(Post)` to load all related data in 2 queries instead of N+1.

**What it looks like**:
```python
users = User.select()
for user in users:
    # BAD: executes SELECT for every iteration
    post_count = user.posts.count()
    latest = user.posts.order_by(Post.created_at.desc()).first()
```

**Why wrong**: Each `user.posts` access opens a new database connection and executes a SELECT.
With 500 users this is 1001 queries. SQLite holds a read lock per query — accumulated latency
grows linearly with row count.

**Do instead:**

Use `prefetch()` to load all related data in 2 queries, or annotate with a subquery to compute
aggregates in a single SQL statement:

```python
# Option 1: prefetch + Python aggregation
users = User.select().prefetch(Post)
for user in users:
    posts = list(user.posts)  # Already loaded — no query
    post_count = len(posts)
    latest = max(posts, key=lambda p: p.created_at, default=None)

# Option 2: annotate with subquery at SELECT time
from peewee import fn, ModelSelect
post_count_q = (Post
    .select(fn.COUNT(Post.id))
    .where(Post.user == User.id)
    .scalar_subquery())

users = User.select(User, post_count_q.alias('post_count'))
for user in users:
    print(user.post_count)  # Available as attribute, 1 query total
```

---

### ❌ Missing Index on ForeignKeyField

**Detection**:
```bash
# Find ForeignKeyField definitions — verify each has an index
grep -rn 'ForeignKeyField' --include="*.py"
# Check if index=True is absent
rg 'ForeignKeyField\([^)]*\)' --type py | grep -v 'index=True'
```

**Do instead:** Add `index=True` to every `ForeignKeyField` and declare composite indexes in `Meta.indexes` for multi-column query patterns.

**What it looks like**:
```python
class Post(Model):
    user = ForeignKeyField(User, backref='posts')  # No index!
    category = ForeignKeyField(Category, backref='posts')  # No index!
```

**Why wrong**: Peewee does NOT automatically index ForeignKeyField (unlike Django). Queries
filtering on `Post.user == user_id` do a full table scan. At 10k rows this is noticeable; at
100k rows it's a reported bug.

**Do instead:**

Declare `index=True` on every `ForeignKeyField` and add composite indexes in `Meta.indexes`
for any query patterns that filter on multiple columns:

```python
class Post(Model):
    user = ForeignKeyField(User, backref='posts', index=True)
    category = ForeignKeyField(Category, backref='posts', index=True)

    class Meta:
        # Composite index for queries that filter on both
        indexes = (
            (('user', 'created_at'), False),  # Non-unique
        )
```

**Version note**: Peewee 3.0+ changed FK index behavior. In 2.x, FKs had implicit indexes.
In 3.x you must declare `index=True` explicitly.

---

### ❌ Cartesian Product from Prefetch + Join Combination

**Detection**:
```bash
rg '\.prefetch\(' --type py -A 2 | grep '\.join\('
grep -rn 'prefetch' --include="*.py" -A 3 | grep 'join'
```

**Do instead:** Use `join()` alone when filtering on a related field, or `prefetch()` alone when loading related data. Never combine both for the same model.

**What it looks like**:
```python
# BUG: join + prefetch on same model produces cartesian product rows
users = (User
    .select()
    .join(Post)  # Creates JOIN
    .prefetch(Post))  # Also prefetches — duplicates Post rows
```

**Why wrong**: `join()` and `prefetch()` for the same model are mutually exclusive operations.
Using both causes Post rows to appear multiple times in `user.posts` after prefetch populates
from the JOIN result set.

**Do instead:**

Pick one strategy per query: `join()` for filter/order operations, `prefetch()` for loading
related objects into memory:

```python
# For filtering: use join only, no prefetch
users = User.select().join(Post).where(Post.status == 'published').distinct()

# For loading related data: use prefetch only, no join
users = User.select().prefetch(Post)
```

---

### ❌ SELECT * on Wide Tables

**Detection**:
```bash
# Model.select() with no arguments — loads all columns
rg '\.select\(\s*\)' --type py
grep -rn '\.select()' --include="*.py" | grep -v 'select(.*\.'
```

**Do instead:** Specify only the columns you need: `Post.select(Post.id, Post.title, Post.created_at)`.

**What it looks like**:
```python
# Loads all columns including large TEXT/BLOB fields
posts = Post.select()  # Includes body, attachments_json, etc.
for post in posts:
    print(post.title)  # Only needed title
```

**Why wrong**: SQLite reads entire row pages into cache. Loading unused large columns wastes
cache and increases I/O, especially in list views rendering only titles or IDs.

**Do instead:**

Select only the columns required for the operation, keeping queries narrow and cache-efficient:

```python
posts = Post.select(Post.id, Post.title, Post.created_at)
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `OperationalError: database is locked` | Concurrent writes or long read transaction | Enable WAL: `PRAGMA journal_mode=WAL`; shorten transaction scope |
| `DoesNotExist: {Model} instance matching query does not exist` | `.get()` on empty result set | Use `.get_or_none()` or wrap in `try/except DoesNotExist` |
| `IntegrityError: FOREIGN KEY constraint failed` | FK enforcement not enabled by default | Add `'foreign_keys': 1` to pragma dict or call `db.execute_sql('PRAGMA foreign_keys=ON')` |
| `AttributeError: 'SelectQuery' object has no attribute 'posts'` | Accessing backref before query executes | Call `list()` or iterate the queryset first |
| `ProgrammingError: not all arguments converted during string formatting` | Using `%s` placeholders (not `?`) in raw SQL | SQLite uses `?` as placeholder: `db.execute_sql('SELECT ? + ?', (1, 2))` |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| Peewee 3.0 | FK indexes no longer implicit | Add `index=True` to all ForeignKeyField |
| Peewee 3.15 | `join_lazy()` added | Prefer over manual deferred loading patterns |
| SQLite 3.35 | `DROP COLUMN` supported | Before 3.35, column removal required table rebuild |
| SQLite 3.37 | `STRICT` table mode | Enforces type affinity — opt-in per table |
| SQLite 3.38 | `unixepoch()` function | Use instead of strftime for Unix timestamps |

---

## Detection Commands Reference

```bash
# N+1 loop access pattern
rg 'for \w+ in \w+\.\w+:' --type py

# Missing FK index
rg 'ForeignKeyField\([^)]*\)' --type py | grep -v 'index=True'

# Cartesian product risk (join + prefetch same model)
rg '\.prefetch\(' --type py -A 2 | grep '\.join\('

# Bare select() calls (potential overfetch)
rg '\.select\(\s*\)' --type py

# No WAL mode configured
rg 'SqliteDatabase' --type py -A 5 | grep -v 'journal_mode'
```

---

## See Also

- `peewee-testing.md` — in-memory SQLite test isolation patterns
- `peewee-migrations.md` — Playhouse migrate and SQLite ALTER limitations
- [Peewee Querying Docs](https://docs.peewee-orm.com/en/latest/peewee/querying.html)
