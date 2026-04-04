# Database Performance Reference

> **Scope**: Index selection, query optimization, connection pooling, and EXPLAIN plan interpretation
> **Version range**: PostgreSQL 14+ / MySQL 8.0+ (notes where they differ)
> **Generated**: 2026-04-04 — benchmark before applying any optimization

---

## Overview

Database performance problems fall into three categories: the query is doing too much work (wrong query plan, missing index), the database is doing the right work but slowly (connection saturation, lock contention), or the schema makes efficient querying impossible (no partition, wrong column type). Always get an EXPLAIN plan before adding an index — the plan tells you what's slow and why.

---

## Pattern Table: Index Selection

| Scenario | Index to Add | Why |
|----------|-------------|-----|
| `WHERE user_id = $1` | `(user_id)` | Simple equality lookup |
| `WHERE status = 'active' AND created_at > $1` | `(status, created_at)` | Composite covers both filters; put equality first |
| `ORDER BY created_at DESC LIMIT 20` | `(created_at DESC)` | Covering sort avoids sort step |
| `WHERE user_id = $1 ORDER BY created_at DESC` | `(user_id, created_at DESC)` | Composite: filter then sort |
| `WHERE status = 'pending'` (2% of rows) | `(user_id) WHERE status = 'pending'` | Partial index — smaller, faster |
| `SELECT id, name FROM users WHERE email = $1` | `(email) INCLUDE (id, name)` | Covering index — no heap fetch (PG 11+) |
| `WHERE LOWER(email) = $1` | Expression: `(LOWER(email))` | Function on column needs expression index |

---

## Correct Patterns

### Covering Index to Eliminate Heap Fetches

```sql
-- PostgreSQL 11+: INCLUDE adds non-indexed columns to index leaf pages
-- Query only needs to read the index, never touches the main table heap

-- Without covering: index scan returns matching pages, then fetches each heap row
CREATE INDEX idx_users_email ON users(email);

-- With covering: all needed columns in the index, no heap fetch
CREATE INDEX idx_users_email_covering ON users(email)
  INCLUDE (id, name, created_at);

-- This query is now index-only (check EXPLAIN for "Index Only Scan")
SELECT id, name, created_at FROM users WHERE email = $1;
```

**Why**: On large tables, heap fetches involve random disk I/O for each result row. An index-only scan reads only the index (sequential I/O). For queries that return many rows from a large table, this is 10-100× faster.

---

### Composite Index Column Order Rule

```sql
-- Rule: equality columns first, range/sort columns last
-- Query: WHERE status = 'active' AND created_at > '2026-01-01' ORDER BY created_at DESC

-- Wrong order: range column first
CREATE INDEX idx_orders_wrong ON orders(created_at, status);
-- Only the leading column (created_at) is used for range scan; status filter is post-filter

-- Correct order: equality column first, range column second
CREATE INDEX idx_orders_correct ON orders(status, created_at DESC);
-- PostgreSQL can use status for equality lookup, then created_at for range scan within that
EXPLAIN SELECT * FROM orders WHERE status = 'active' AND created_at > '2026-01-01'
ORDER BY created_at DESC LIMIT 20;
-- Should show: Index Scan using idx_orders_correct
```

**Why**: B-tree indexes are traversed left-to-right. The query planner can skip a range-column prefix but not an equality-column prefix. Putting equality before range allows the index to filter both conditions.

---

### Connection Pooling with PgBouncer

```ini
# /etc/pgbouncer/pgbouncer.ini
[databases]
myapp = host=localhost dbname=myapp

[pgbouncer]
pool_mode = transaction         # Transaction pooling: connection returned after each transaction
max_client_conn = 1000          # Max app connections PgBouncer accepts
default_pool_size = 20          # Connections to actual PostgreSQL per database

# Transaction mode limits:
# - Cannot use SET/RESET (affects all pool connections)
# - Cannot use prepared statements (unless server_reset_query is configured)
# - Cannot use LISTEN/NOTIFY
```

```python
# Application: connect to PgBouncer port (6432), not PostgreSQL (5432)
DATABASE_URL = "postgresql://user:pass@localhost:6432/myapp"

# SQLAlchemy: set pool_pre_ping to handle stale connections
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,         # Check connection health before use
    pool_size=5,                # Connections per worker process
    max_overflow=10,            # Additional connections when pool exhausted
)
```

**Why**: PostgreSQL has a hard limit on concurrent connections (default 100). Each connection uses ~5-10MB RAM. A 100-connection pool with 20 workers × 5 connections each = connection exhaustion. PgBouncer multiplexes thousands of application connections onto a small PostgreSQL connection pool.

---

### Identifying Lock Contention

```sql
-- Find blocked queries and what's blocking them
SELECT
  blocked.pid AS blocked_pid,
  blocked.query AS blocked_query,
  blocking.pid AS blocking_pid,
  blocking.query AS blocking_query,
  blocked.wait_event_type,
  blocked.wait_event
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking
  ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
WHERE NOT blocked.granted;

-- Find long-running transactions (common cause of lock pile-up)
SELECT
  pid,
  now() - pg_stat_activity.query_start AS duration,
  query,
  state
FROM pg_stat_activity
WHERE state != 'idle'
  AND query_start < NOW() - INTERVAL '30 seconds'
ORDER BY duration DESC;
```

**Why**: Lock pile-ups are multiplicative: one long-running transaction blocks one query, which holds a lock that blocks five more, which hold locks that block twenty more. Finding the root blocker early prevents cascading failures.

---

## Anti-Pattern Catalog

### ❌ Over-Indexing (Index on Every Column)

**Detection**:
```sql
-- Find tables with unusually high index count
SELECT
  schemaname,
  tablename,
  COUNT(*) AS index_count
FROM pg_indexes
WHERE schemaname = 'public'
GROUP BY schemaname, tablename
HAVING COUNT(*) > 8
ORDER BY index_count DESC;

-- Find unused indexes (no scans since last statistics reset)
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan AS times_used
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexname NOT LIKE '%pkey%'  -- Exclude primary keys
ORDER BY pg_relation_size(indexrelid) DESC;
```

**What it looks like**:
```sql
-- Every column gets an index "just in case"
CREATE INDEX idx_users_name ON users(name);
CREATE INDEX idx_users_created ON users(created_at);
CREATE INDEX idx_users_updated ON users(updated_at);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_country ON users(country);
-- Plus 4 more indexes that are never queried
```

**Why wrong**: Every index slows down writes (INSERT/UPDATE/DELETE must update all indexes). A table with 10 indexes has 10× write amplification. Index maintenance during VACUUM is slower. Buffer cache fills with index pages instead of table data.

**Fix**: Check `pg_stat_user_indexes.idx_scan = 0` after running the application under production load for 1+ weeks. Drop indexes with zero usage. Keep only indexes that serve known query patterns.

---

### ❌ Running ALTER TABLE on a Large Production Table Without a Plan

**Detection**:
```bash
# Find ALTER TABLE statements in pending migrations
grep -rn "ALTER TABLE\|ADD COLUMN.*NOT NULL\|CHANGE COLUMN\|MODIFY COLUMN" \
  migrations/ db/ --include="*.sql" --include="*.py"

# Check table size before running migration
psql -c "SELECT pg_size_pretty(pg_total_relation_size('orders'));"
```

**What it looks like**:
```sql
-- This takes an ExclusiveLock for the duration on a 500GB table
ALTER TABLE orders ADD COLUMN processed BOOLEAN NOT NULL DEFAULT false;
-- PostgreSQL 11+: default value is safe — metadata-only change
-- PostgreSQL < 11: rewrites entire table with new column!
```

**Why wrong**: On PostgreSQL < 11, adding a column with a default value requires rewriting the entire table. On a 500GB table, this takes hours with an ExclusiveLock that blocks ALL reads and writes.

**Fix**:
```sql
-- PostgreSQL 11+: adding column with DEFAULT is safe (metadata only), do it directly

-- PostgreSQL < 11: safe pattern
-- Step 1: Add nullable column (instant)
ALTER TABLE orders ADD COLUMN processed BOOLEAN;

-- Step 2: Add default for new rows (instant)
ALTER TABLE orders ALTER COLUMN processed SET DEFAULT false;

-- Step 3: Backfill in batches (no lock)
UPDATE orders SET processed = false WHERE processed IS NULL AND id BETWEEN 1 AND 100000;

-- Step 4: Add NOT NULL constraint after backfill complete
ALTER TABLE orders ALTER COLUMN processed SET NOT NULL;
```

**Version note**: PostgreSQL 11+ changed `ADD COLUMN ... DEFAULT` to be a metadata-only operation. For 11+, adding a column with a constant default is instant with no table rewrite.

---

### ❌ No Query Timeout Set (Runaway Queries)

**Detection**:
```sql
-- Find queries running longer than 5 minutes
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
  AND query_start < NOW() - INTERVAL '5 minutes';
```

**What it looks like**: Application has no statement timeout configured. A user runs `SELECT * FROM orders` (full table scan, no WHERE clause) that runs for 30 minutes and holds shared locks.

**Why wrong**: Long-running queries on PostgreSQL prevent autovacuum from cleaning dead rows (transaction ID wraparound risk), hold shared memory, and block DDL operations that need ExclusiveLock.

**Fix**:
```sql
-- Set per-session timeout (application layer)
SET statement_timeout = '30s';

-- Set default for all connections in postgresql.conf
statement_timeout = '60s'

-- Set per-role timeout (for reporting users who need longer)
ALTER ROLE reporter SET statement_timeout = '300s';
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `ERROR: canceling statement due to statement timeout` | Query exceeded statement_timeout | Optimize query with EXPLAIN; add missing index; or increase timeout for specific role |
| `ERROR: could not obtain lock on relation` | Conflicting lock from long-running transaction | Find and terminate blocker: `SELECT pg_terminate_backend(blocking_pid)` |
| `FATAL: sorry, too many clients already` | Max connections exceeded | Add PgBouncer connection pooler; reduce application connection pool size |
| `ERROR: could not write to file "base/pgsql_tmp"` | Temp file limit exceeded (work_mem too low) | Increase `work_mem` for session: `SET work_mem = '256MB'` |
| `Seq Scan despite index existing` | Index statistics stale, or planner chose seq scan | Run `ANALYZE tablename`; check if index is actually selective |

---

## Detection Commands Reference

```sql
-- Unused indexes
SELECT indexname, idx_scan, pg_size_pretty(pg_relation_size(indexrelid))
FROM pg_stat_user_indexes WHERE idx_scan = 0;

-- Table sizes with index overhead
SELECT relname,
  pg_size_pretty(pg_table_size(oid)) AS table,
  pg_size_pretty(pg_indexes_size(oid)) AS indexes
FROM pg_class WHERE relkind = 'r' ORDER BY pg_total_relation_size(oid) DESC LIMIT 20;

-- Active long-running queries
SELECT pid, duration, query FROM (
  SELECT pid, now()-query_start AS duration, query FROM pg_stat_activity
  WHERE state='active'
) q WHERE duration > interval '10 seconds' ORDER BY duration DESC;

-- Lock contention
SELECT blocked.pid, blocked.query, blocking.pid, blocking.query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
WHERE NOT blocked.granted;
```

---

## See Also

- `postgres.md` — PostgreSQL-specific index types, EXPLAIN interpretation, JSONB patterns
- `sql.md` — Cross-database SQL patterns, N+1 detection, migration safety
