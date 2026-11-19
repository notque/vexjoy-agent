# Database Engineering Reference

> **Scope**: Server databases such as PostgreSQL and MySQL: schema design (normalization, constraints, multi-tenant patterns), data modeling (ER diagrams, denormalization trade-offs, access patterns), query optimization (EXPLAIN, indexes, N+1), migrations (zero-downtime, backfill, rollback), transactions, isolation levels, locking, connection pooling.
> **Not here**: embedded SQLite or Peewee (`sqlite-peewee.md`), because the foreign-key and zero-downtime mandates below assume a server database and misfire on embedded SQLite; warehouses, ETL/ELT, dimensional models, and stream processing (`data.md`); OpenSearch or Elasticsearch tuning (`skills/infrastructure/kubernetes/references/opensearch-elasticsearch.md`); database deployment and scaling on Kubernetes (`skills/infrastructure/kubernetes/references/kubernetes-helm.md`); API and business logic (`programming` skill). Statistical analysis is this skill's Mode A; ML model training is out of scope.

Principles: normalize to 3NF and denormalize only for proven needs; index foreign keys and frequently queried columns; use transactions for multi-step operations; fix N+1 with eager loading or JOINs; plan migrations for zero downtime (nullable, backfill, then NOT NULL). Priorities: data integrity, performance, scalability (partitioning, sharding), maintainability.

## Hard rules

- **Foreign keys required**: every relationship has a foreign key constraint.
- **Index foreign keys**: every foreign key column is indexed for JOIN performance.
- **Migration safety**: every schema change has a rollback plan and a zero-downtime strategy for production.
- **Optimize with evidence**: foreign-key indexes are always required. Add any other index, or denormalize, only after an EXPLAIN plan or benchmark shows the problem.

## Defaults (on unless disabled)

- Show EXPLAIN plans in optimization discussions.
- Recommend indexes from query patterns, not speculation.
- Provide up and down migrations for every schema change.

## Optional (off unless enabled)

- PostgreSQL-specific features (JSONB, arrays), only when using PostgreSQL.
- Partitioning, only above 10M rows when query patterns fit.
- Replication, only when HA or read scaling is required.
- Stored procedures, only when logic must run in the database (prefer the application layer).

## Output

- **Before**: requirements, current schema (tables, relationships), access patterns, performance needs (SLAs, scale).
- **During**: show DDL, EXPLAIN plans, query results, migration scripts.
- **After**: schema changes, indexes added, queries optimized, migrations ready; report query time before and after, indexes added, schema change summary.
- Implementation Schema details: [output-schemas.md](../../../shared-patterns/output-schemas.md).

## Error handling

| Error | Cause | Fix |
|---|---|---|
| Missing index on foreign key | Slow JOINs | `CREATE INDEX idx_table_fk ON table(foreign_key_id)`; confirm with EXPLAIN |
| N+1 queries | One query per row in a loop | JOIN or ORM eager loading, for example `SELECT * FROM orders JOIN users ON orders.user_id = users.id` |
| Migration lock timeout | ALTER blocked by long-running queries | Add the column nullable, backfill, then add NOT NULL; split ALTERs on large tables across transactions |

More error messages and fixes: [database/database-quick-reference.md](database/database-quick-reference.md).

## Preferred patterns

- **Foreign keys on all relationships**: `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`. Choose the delete rule per relationship: `ON DELETE CASCADE` only for owned child rows that mean nothing without their parent, `SET NULL` for optional links. A default cascade turns one delete into silent loss of every dependent row.
- **Targeted indexing**: index foreign keys and columns in frequent WHERE and JOIN clauses only; balance reads against write speed, storage, and maintenance.
- **Normalize first, denormalize with proof**: start at 3NF; denormalize only after a benchmark proves the need.

## Rationalizations to reject

| Claim | Why it's wrong | Do this |
|---|---|---|
| "Foreign keys slow things down" | Integrity matters more; FKs rarely bottleneck | Add FKs, measure actual impact |
| "We can add indexes later" | Unindexed FKs make JOINs and parent deletes scan the child table | Index FKs now; add others when EXPLAIN shows a need |
| "Denormalization makes queries easier" | Duplicated data drifts | Normalize first, denormalize with proof |
| "Application code can enforce integrity" | Code can't guarantee ACID; races cause bugs | Use database constraints |
| "Migrations are risky, do it by hand" | Manual changes err and can't roll back | Migration scripts with rollback |

## Hard gates

Before implementing changes, check for these. If found: stop, report, fix before continuing.

| Pattern | Why blocked | Fix |
|---|---|---|
| Relationships without foreign keys | Integrity breach | Add `FOREIGN KEY` constraints |
| Unindexed foreign key columns | JOIN performance disaster | `CREATE INDEX idx_table_fk ON table(fk)` |
| `SELECT *` in application code | Wastes bandwidth, breaks on schema change | Select only needed columns |
| No PRIMARY KEY | Rows can't be identified | Add `PRIMARY KEY` (auto-increment or composite) |
| NOLOCK hints (SQL Server) | Dirty reads, corruption | Use a proper isolation level |

Detection SQL (tables without primary keys, foreign keys without indexes, stale statistics, slowest queries): [database/database-quick-reference.md](database/database-quick-reference.md).

## Verification stops

- After designing or changing a schema: have I checked it against the existing schema and current access patterns?
- After recommending an optimization (index, denormalization, rewrite): do I give before/after metrics, or say why measurement is impossible?
- After writing a migration: have I checked application queries, ORM models, dependent views, and foreign keys from other tables?

## Before destructive or live changes

- Before DROP TABLE, DROP COLUMN, or any destructive migration: confirm it is reversible or backups exist. Ship the rollback DDL with the forward migration; irreversible data loss is the costliest failure here.
- Before applying to production: validate the migration SQL in a dry run or staging. A syntax error mid-migration causes outages and partial schema states.

## Recommendation format

Each recommendation names the **component** (table, index, query, or constraint), **current state** (or "new"), **proposed state**, and **risk level** (Low, Medium, High) with a short reason.

## Blockers

Resolve routine issues from repository evidence and existing authorization. When sure, decide, record the assumption, and continue; ask Jev when genuinely unsure. Rows marked **(owner)** need explicit owner confirmation first.

| Situation | Why stop | Ask |
|---|---|---|
| Database choice unclear | PostgreSQL vs MySQL changes design; embedded SQLite goes to `sqlite-peewee.md` | "Which database: PostgreSQL or MySQL?" |
| Scale unknown | Partitioning and sharding | "Expected row count and query volume?" |
| Production migration timing **(owner)** | Downtime coordination | "Zero-downtime migration, or a maintenance window?" |
| Multi-tenant strategy unclear | Row-level vs schema-level isolation | "Shared tables (row-level) or separate schemas?" |
| Denormalization proposed | Needs proof | "Have you measured the problem? Benchmarks?" |

Decide explicitly first: database choice, scale, migration timing (owner confirms), denormalization (needs benchmarks).

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| Unindexed foreign keys, tables without primary keys, stale statistics, slow query triage, database error messages | [database/database-quick-reference.md](database/database-quick-reference.md) | Verbatim detection queries and error to fix mappings |
