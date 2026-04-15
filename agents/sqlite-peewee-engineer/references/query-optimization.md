# Query Optimization Reference

> **Scope**: N+1 prevention, prefetch patterns, join strategies, and index usage for Peewee ORM with SQLite.
> **Version range**: Peewee 3.x (3.14+), SQLite 3.35+
> **Generated**: 2026-04-15 — verify against current Peewee changelog

---

## Overview

The most common performance failure in Peewee is the N+1 query problem: loading a parent list then accessing related data per item, each triggering a separate SELECT. Peewee provides `prefetch()` and `join()` to collapse this into 1-2 queries. SQLite amplifies N+1 pain more than server databases because each query carries file I/O overhead.

---

## Pattern Table

| Pattern | Peewee Version | Use When | Avoid When |
|---------|---------------|----------|------------|
| `prefetch()` | 3.x+ | Loading reverse FK collections (posts per user) | Single item lookup |
| `join().switch()` | 3.x+ | Filtering on related fields | Pulling full related objects (use prefetch) |
| `select_related()` | via `playhouse.shortcuts` | Forward FK traversal, single depth | Deep nested relationships |
| `join_lazy()` | deprecated 3.17+ | — | Use `join()` instead |
| `.tuples()` | 3.x+ | High-volume reads where model overhead matters | When you need model methods |
| `.dicts()` | 3.x+ | JSON serialization of large result sets | — |
| `Model.index()` in Meta | 3.x+ | Compound index on frequently queried pairs | Single-column FK (auto-indexed) |

---

## Correct Patterns

### prefetch() for Reverse FK Collections

Use `prefetch()` when loading a list of parents and accessing their children. Executes exactly 2 queries regardless of parent count.

```python
from peewee import prefetch

# 2 queries total — one for users, one for all their posts
users = User.select().prefetch(Post)

for user in users:
    # user.posts is already populated, no extra queries
    for post in user.posts:
        print(post.title)
```

**Why**: Without `prefetch()`, `user.posts` triggers a SELECT per user. 100 users = 101 queries. With prefetch: always 2.

---

### join() for Filter-and-Return

Use `join()` when filtering parent records by related field values, but returning only parent data.

```python
# Find users who have posts with > 10 comments — one query
users = (User
    .select()
    .join(Post)
    .where(Post.comment_count > 10)
    .distinct())

# join().switch() for multiple joins
posts = (Post
    .select(Post, User, Category)
    .join(User)
    .switch(Post)
    .join(Category)
    .where(Category.name == 'tech'))
```

**Why**: `join()` generates a single SQL JOIN. The `.switch(Post)` resets the join point to `Post` for the second join.

---

### select() with Specific Columns

Avoid selecting all columns when only a subset is needed — Peewee fetches all by default.

```python
# Only fetch what you need
users = User.select(User.id, User.username, User.email)

# Count without loading rows
count = User.select().where(User.active == True).count()

# Exists check — more efficient than count
exists = User.select().where(User.username == 'alice').exists()
```

**Why**: SQLite reads full rows from disk even for narrow queries unless you project. Selecting 2 columns from a 20-column table is measurably faster at scale.

---

### Index Definition in Meta

```python
class EventLog(Model):
    user = ForeignKeyField(User, backref='events')
    action = CharField(max_length=50)
    created_at = DateTimeField()

    class Meta:
        database = db
        indexes = (
            # Compound index for user+time range queries
            (('user', 'created_at'), False),  # False = not unique
            # Single unique index
            (('user', 'action'), True),  # True = unique
        )
```

**Why**: ForeignKeyField auto-creates a single-column index. For queries like `WHERE user_id = ? AND created_at > ?`, the compound index is used; the single-column index is not.

---

## Anti-Pattern Catalog

### ❌ Accessing Related Data in Loop Without prefetch

**Detection**:
```bash
# Find .select() loops that access related via dot notation
grep -rn "for.*in.*\.select()" --include="*.py" -A 3 | grep -E "\.(posts|comments|items|children)\b"

# Broader: any attribute access on select() results inside loop
rg "for \w+ in \w+\.select\(" --type py -A 5
```

**What it looks like**:
```python
users = User.select()
for user in users:
    print(f"{user.username}: {user.posts.count()}")  # SELECT per user!
```

**Why wrong**: `user.posts` on a `ModelSelect` result triggers a fresh `SELECT * FROM post WHERE user_id=?` on every iteration. 1000 users = 1001 queries. Undetectable in development with small datasets; catastrophic in production.

**Fix**:
```python
users = User.select().prefetch(Post)
for user in users:
    print(f"{user.username}: {len(user.posts)}")  # No extra queries
```

---

### ❌ Using count() Inside Loop

**Detection**:
```bash
grep -rn "\.count()" --include="*.py" | grep -v "test_"
rg "in.*loop|for.*\n.*\.count\(\)" --type py --multiline
```

**What it looks like**:
```python
for user in User.select():
    active_posts = user.posts.where(Post.active == True).count()
```

**Why wrong**: Each `.count()` call is a subquery. This is N+1 with aggregation overhead.

**Fix**:
```python
from peewee import fn, Case

# Single query with conditional aggregation
query = (User
    .select(User, fn.COUNT(Post.id).alias('active_post_count'))
    .join(Post, JOIN.LEFT_OUTER)
    .where(Post.active == True)
    .group_by(User.id))

for user in query:
    print(user.active_post_count)
```

---

### ❌ Missing Index on Filter Fields

**Detection**:
```bash
# Find where() calls on non-FK, non-primary-key fields
grep -rn "\.where(" --include="*.py" -A 1 | grep -v "\.id\b\|_id\b"

# Check model definitions for missing indexes
grep -rn "class Meta" --include="*.py" -A 5 | grep -v "indexes\|index_together"
```

**What it looks like**:
```python
class Order(Model):
    user = ForeignKeyField(User, backref='orders')
    status = CharField()  # No index, but queried constantly
    created_at = DateTimeField()

# This does a full table scan
recent = Order.select().where(Order.status == 'pending')
```

**Why wrong**: SQLite performs a full table scan on unindexed columns. At 100k rows, this takes milliseconds; at 1M rows, seconds.

**Fix**:
```python
class Order(Model):
    user = ForeignKeyField(User, backref='orders')
    status = CharField(index=True)  # Single column index
    created_at = DateTimeField()

    class Meta:
        indexes = (
            (('status', 'created_at'), False),  # Compound for status + time range
        )
```

---

### ❌ Calling .execute() Prematurely

**Detection**:
```bash
grep -rn "\.execute()" --include="*.py" | grep -v "db\.execute\|execute_sql"
```

**What it looks like**:
```python
query = User.select().where(User.active == True).execute()
for user in query:  # Re-iterates cached result
    ...

# Then later someone passes the query object expecting lazy eval
paginate(query, page=2)  # Already executed, pagination broken
```

**Why wrong**: Peewee queries are lazy by default. Calling `.execute()` immediately materializes the full result set. This prevents further chaining, breaks pagination, and loads all rows into memory.

**Fix**: Iterate directly — Peewee auto-executes on first iteration.
```python
query = User.select().where(User.active == True)
for user in query:  # Executes lazily on first iteration
    ...
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `AttributeError: 'SelectBase' has no attribute 'username'` | Accessing field on query object instead of iterating | Add `for user in query:` wrapper |
| `peewee.ProgrammingError: no such column: t2.id` | join() without matching ForeignKeyField | Verify FK points to correct model |
| `OperationalError: too many SQL variables` | `Model.id << [...]` with >999 items | Batch into chunks of 900: `[ids[i:i+900] for i in range(0, len(ids), 900)]` |
| `AttributeError: 'NoneType' object has no attribute 'posts'` | `.get()` returned None, FK traverse failed | Use `.get_or_none()` and check before accessing |

---

## Detection Commands Reference

```bash
# N+1: related access in loop without prefetch
grep -rn "for.*in.*\.select()" --include="*.py" -A 3

# .count() inside loops
rg "\.count\(\)" --type py

# Missing indexes on queried fields
grep -rn "\.where(" --include="*.py" -A 1

# Premature .execute() calls
grep -rn "\.execute()" --include="*.py" | grep -v "db\.\|execute_sql"
```

---

## See Also

- `sqlite-features.md` — WAL mode, EXPLAIN QUERY PLAN, PRAGMA analysis
- `migrations.md` — Adding indexes to existing tables via playhouse.migrate
- [Peewee Querying docs](https://docs.peewee-orm.com/en/latest/peewee/querying.html)
