# SQLite and Peewee Reference

> **Scope**: SQLite with the Peewee ORM: models (fields, foreign keys, indexes, Meta options, custom fields, inheritance), query optimization (prefetch, joins, N+1), playhouse migrations, transactions (atomic, savepoints), SQLite features (pragmas, WAL, JSON1, FTS5, WITHOUT ROWID, generated columns), SQL logging.
> **Not here**: server databases such as PostgreSQL or MySQL (`database.md`); general Python outside the data layer (`programming` skill); API and frontend code (`programming` or `frontend` skill).

Principles: ForeignKeyField with backref, prefetch related data, `atomic()` for multi-step work, index foreign keys and queried fields, work within SQLite limits (one writer, limited ALTER TABLE). Priorities: query efficiency, data integrity, SQLite constraints, code clarity.

## Hard rules

- **Read before editing**: never edit a file you have not read in this session.
- **Run tests before reporting done**: run the project's suite and show the actual output. Don't summarize as "tests pass."
- **Feature branch**: never commit to main; branch first.
- **Verify dependencies**: check `requirements.txt` or `pyproject.toml` for `peewee` and any playhouse extension before importing.
- **Backrefs required**: every ForeignKeyField sets `backref`.
- **Transactions**: wrap multi-step operations in `atomic()`.
- **Prefetch for lists**: load related data in loops with `prefetch()`, not N queries.
- **Migrations via playhouse**: schema changes use `playhouse.migrate`, not manual SQL.

## Defaults (on unless disabled)

- Show the SQL Peewee generates for complex queries.
- Give models docstrings that explain purpose and relationships.

## Optional (off unless enabled)

- JSON1, only when storing or querying JSON.
- FTS5, only for search.
- Custom fields, only when built-in fields fall short.
- Deep query optimization, only after profiling confirms a problem.

## Output

- **Before**: requirements, models needed (tables, relationships), query patterns, SQLite limits that apply.
- **During**: show models, query code, generated SQL, migration scripts.
- **After**: models, optimized queries, migrations, passing tests; report N+1 fixes, where prefetch was added, indexes added.
- Implementation Schema details: [output-schemas.md](../../../shared-patterns/output-schemas.md).

## Error handling

| Error | Cause | Fix |
|---|---|---|
| `IntegrityError` (foreign key) | Insert with a missing parent, or delete of a parent with children | Create the parent first, set `on_delete='CASCADE'` on the ForeignKeyField, or delete children first |
| `OperationalError: database is locked` | Concurrent writes (SQLite allows one writer) | `atomic()`, shorter transactions, `PRAGMA journal_mode=WAL`, no long-running transactions |
| N+1 queries | Related data loaded in a loop | `User.select().prefetch(Post)` loads all posts in 2 queries |

## Preferred patterns

- **Prefetch related data**: `users = User.select().prefetch(Post); for user in users: print(len(user.posts))`. `for user in User.select(): print(user.posts.count())` runs one query per user.
- **Wrap multi-step work in `atomic()`**: signal `user.save(); post.save(); comment.save()` without it, which commits partially on error. Use `with db.atomic(): ...`.
- **Use playhouse migrate**: signal `db.execute_sql("ALTER TABLE users ADD COLUMN email TEXT")`, which has no rollback, no tracking, and hits SQLite ALTER limits. Use `migrator.add_column('users', 'email', TextField(null=True))`.

## Rationalizations to reject

| Claim | Why it's wrong | Do this |
|---|---|---|
| "Prefetch makes queries complex" | N+1 kills performance; prefetch is 2 queries | Use `prefetch()` |
| "SQLite is fine without indexes" | Queries slow down fast | Index foreign keys and query fields |
| "Transactions are overkill for simple saves" | Multi-step work needs atomicity | Wrap in `atomic()` |
| "Skip migrations for small changes" | Manual changes drift across environments | `playhouse.migrate` for every schema change |

## Hard gates

Before writing Peewee code, check for these. If found: stop, report, fix before continuing.

| Pattern | Why blocked | Fix |
|---|---|---|
| Related data in a loop: `for user in users: user.posts` | N+1 queries | `User.select().prefetch(Post)` |
| ForeignKeyField without backref | No reverse access | `ForeignKeyField(User, backref='posts')` |
| Multi-step save without `atomic()` | Partial commits | `with db.atomic(): user.save(); post.save()` |
| Raw SQL for schema changes | Untracked, breaks migrations | `playhouse.migrate` |
| Selecting all fields when few are needed | Wastes bandwidth | `.select(User.id, User.name)` |

Detection by review: `.select()` followed by related access in a loop without prefetch; ForeignKeyField without `backref`; several `.save()` or `.create()` calls outside `atomic()`. Grep-based detection: [sqlite-peewee/peewee-query-patterns.md](sqlite-peewee/peewee-query-patterns.md) and [sqlite-peewee/peewee-migrations.md](sqlite-peewee/peewee-migrations.md).

## Blockers

Resolve routine issues from repository evidence and existing authorization. When sure, decide, record the assumption, and continue; ask Jev when genuinely unsure. Rows marked **(owner)** need explicit owner confirmation first.

| Situation | Why stop | Ask |
|---|---|---|
| Concurrent writes needed | SQLite limit | "Need concurrent writes? Consider PostgreSQL instead of SQLite." |
| Large dataset (over 100k rows) | Performance | "How many rows expected? SQLite is efficient to about 1M rows." |
| Complex data migration **(owner)** | Rewrites existing rows | "Transform existing data during the migration?" |
| Full-text search | FTS5 choices | "Which fields to index? Tokenizer preference?" |

Decide explicitly first: concurrent write patterns, data scale, migration data transforms (owner confirms before one runs against existing data), FTS5 setup.

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| N+1, prefetch, join, slow query, index, WAL, EXPLAIN | [sqlite-peewee/peewee-query-patterns.md](sqlite-peewee/peewee-query-patterns.md) | Query optimization, N+1 prevention, index strategy, pragmas |
| test, pytest, fixture, in-memory, `:memory:`, `bind_ctx`, migration test | [sqlite-peewee/peewee-testing.md](sqlite-peewee/peewee-testing.md) | Per-test isolation, factory fixtures, rollback tests |
| migration, ALTER, schema change, add column, drop column, playhouse.migrate | [sqlite-peewee/peewee-migrations.md](sqlite-peewee/peewee-migrations.md) | Playhouse operations, SQLite ALTER limits, rebuild procedure |
