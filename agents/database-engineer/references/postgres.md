# PostgreSQL Patterns Reference

> **Scope**: PostgreSQL-specific features, index types, EXPLAIN analysis, isolation levels, and JSONB patterns
> **Version range**: PostgreSQL 14+ (notes for 12–13 where behavior differs)
> **Generated**: 2026-04-04 — verify against current PostgreSQL release notes

---

## Overview

PostgreSQL is the primary production database for most web applications in this toolkit. The most common performance failures are: missing index on a foreign key (every JOIN scans the FK column), wrong index type (B-tree on a full-text search column), and incorrect isolation level causing phantom reads or serialization errors. Read the EXPLAIN plan before adding any index.

---

## Pattern Table: Index Types

| Index Type | Use When | Avoid When | Version |
|------------|----------|------------|---------|
| `B-tree` (default) | Equality, range, ORDER BY, most queries | No use case where other types apply | all |
| `GIN` | Array contains, JSONB key search, full-text search | Small datasets (slower writes) | all |
| `GiST` | Geometric types, full-text search (alternative to GIN), IP ranges | When GIN is available for same use case | all |
| `Hash` | Exact equality only (rarely better than B-tree) | Range queries, ORDER BY | all |
| `BRIN` | Very large tables with natural physical ordering (timestamps, sequential IDs) | Tables without physical ordering | 9.5+ |
| `Partial` | Index only subset of rows (e.g., `WHERE status = 'active'`) | When all rows need to be indexed | all |
| Expression | Index on computed expression (`lower(email)`) | When B-tree on column suffices | all |

---

## Correct Patterns

### Reading EXPLAIN ANALYZE Output

```sql
-- Always run EXPLAIN (ANALYZE, BUFFERS) for performance analysis
-- ANALYZE actually executes the query — use on replica or with small dataset for writes
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT u.name, COUNT(o.id) AS order_count
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE u.created_at > NOW() - INTERVAL '30 days'
GROUP BY u.name;
```

Key metrics to read in output:
```
Seq Scan on orders (cost=0.00..45234.00 rows=1200000 width=8)
                    ^start cost  ^total cost  ^estimated rows
  (actual time=0.034..892.445 rows=1189432 loops=1)
  ^actual stats (run ANALYZE to get these)
  Buffers: shared hit=3421 read=28943
           ^from cache          ^from disk (expensive)
```

- **`Seq Scan`** on a large table = missing index. Add index if this table has >10K rows and query is frequent.
- **`Buffers: read=N`** large = cold cache or bad query. High read count indicates disk I/O bottleneck.
- **`rows=1000 → actual rows=1`** large discrepancy = stale statistics. Run `ANALYZE tablename`.
- **`Nested Loop` with large outer** = often N+1 pattern. Rewrite as single JOIN.

---

### Partial Index for Status-Filtered Queries

```sql
-- Application queries active orders 99% of the time
-- Only ~2% of orders are 'active' at any moment

-- Bad: full index on status column (indexes all 10M rows)
CREATE INDEX idx_orders_status ON orders(status);

-- Good: partial index (only indexes the 200K active rows)
CREATE INDEX idx_orders_active ON orders(user_id, created_at)
WHERE status = 'active';

-- Query that uses this partial index (must match WHERE clause exactly)
SELECT * FROM orders
WHERE status = 'active'
  AND user_id = $1
ORDER BY created_at DESC;
```

**Why**: A partial index on 200K rows is 50x smaller than a full index on 10M rows. Index scans are faster, index builds are faster, writes are faster. Application queries that always filter by status benefit significantly.

---

### JSONB Indexing and Query Patterns

```sql
-- PostgreSQL 14+: JSONB for flexible schema attributes
-- Table: products with varying attributes per category
CREATE TABLE products (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  attributes JSONB NOT NULL DEFAULT '{}'
);

-- GIN index for containment queries (@>)
CREATE INDEX idx_products_attributes ON products USING GIN (attributes);

-- Correct: containment query (uses GIN index)
SELECT * FROM products
WHERE attributes @> '{"color": "red", "size": "large"}';

-- Correct: key existence check (uses GIN index)
SELECT * FROM products
WHERE attributes ? 'waterproof';

-- Expression index for specific key (B-tree on JSONB field)
CREATE INDEX idx_products_brand ON products ((attributes->>'brand'));

-- Correct: specific key query (uses expression index)
SELECT * FROM products
WHERE attributes->>'brand' = 'Acme';
```

**Why**: Without a GIN index, every JSONB containment query is a full table scan. GIN indexes JSONB keys and values for `@>` (contains) and `?` (key exists) operators. For frequent queries on a specific key, an expression index on that key is faster than GIN.

---

### Transaction Isolation Levels

```sql
-- READ COMMITTED (PostgreSQL default): sees committed data at each statement
-- Use for: most web application reads
BEGIN;
SELECT balance FROM accounts WHERE id = 1;
-- Another transaction commits a change here
SELECT balance FROM accounts WHERE id = 1;  -- May see different value
COMMIT;

-- REPEATABLE READ: consistent snapshot for entire transaction
-- Use for: reports, analytics queries that must see consistent state
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT SUM(balance) FROM accounts WHERE region = 'east';
-- No phantom reads within this transaction
COMMIT;

-- SERIALIZABLE: full serialization (prevents all anomalies)
-- Use for: financial transfers, inventory decrements
BEGIN ISOLATION LEVEL SERIALIZABLE;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;  -- Lock the row
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;
-- May throw: ERROR: could not serialize access due to concurrent update
-- Application must retry on serialization failure
```

**Why**: `READ COMMITTED` is appropriate for most reads but allows non-repeatable reads. For financial operations or any multi-statement "read → decide → write" pattern, use `SERIALIZABLE` with retry logic.

---

## Anti-Pattern Catalog

### ❌ Unindexed Foreign Key Column

**Detection**:
```sql
-- Find all foreign keys without corresponding indexes (PostgreSQL)
SELECT
  tc.table_name,
  kcu.column_name,
  ccu.table_name AS references_table
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.referential_constraints AS rc
  ON tc.constraint_name = rc.constraint_name
JOIN information_schema.key_column_usage AS ccu
  ON rc.unique_constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND (tc.table_name, kcu.column_name) NOT IN (
  SELECT t.relname, a.attname
  FROM pg_index i
  JOIN pg_class t ON t.oid = i.indrelid
  JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(i.indkey)
);
```

**What it looks like**: `orders.user_id` references `users.id` but has no index. Every `JOIN orders ON user_id = users.id` scans the entire orders table.

**Why wrong**: A JOIN on an unindexed foreign key does a sequential scan of the child table for every parent row. On a 1M row orders table with 100K users, that's 100K × 10ms sequential scans = 16 minutes for a simple user-orders join.

**Fix**:
```sql
CREATE INDEX idx_orders_user_id ON orders(user_id);
-- Verify with EXPLAIN that query now uses Index Scan instead of Seq Scan
```

---

### ❌ Using LIKE '%term%' Without Full-Text Search

**Detection**:
```bash
# Find LIKE patterns with leading wildcards in application queries
grep -rn "LIKE '%\|ilike '%\|SIMILAR TO '%" src/ --include="*.py" --include="*.go" --include="*.ts"
```

**What it looks like**:
```sql
-- Scans entire table — no index can help with leading wildcard
SELECT * FROM products WHERE name ILIKE '%laptop%';
```

**Why wrong**: B-tree indexes require a known prefix. `LIKE '%term%'` always does a full sequential scan regardless of indexes. On 100K products, this is 100K string comparisons per query.

**Fix**:
```sql
-- Option 1: PostgreSQL full-text search (for natural language)
ALTER TABLE products ADD COLUMN search_vector tsvector
  GENERATED ALWAYS AS (to_tsvector('english', name || ' ' || description)) STORED;

CREATE INDEX idx_products_fts ON products USING GIN (search_vector);

SELECT * FROM products
WHERE search_vector @@ plainto_tsquery('english', 'laptop');

-- Option 2: pg_trgm for fuzzy/partial matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_products_name_trgm ON products USING GIN (name gin_trgm_ops);

SELECT * FROM products
WHERE name ILIKE '%laptop%';  -- Now uses trigram index
```

**Version note**: `GENERATED ALWAYS AS ... STORED` for computed columns available since PostgreSQL 12.

---

### ❌ Not Updating Table Statistics After Bulk Loads

**Detection**:
```sql
-- Find tables with stale statistics (last analyzed > 7 days for busy tables)
SELECT
  schemaname,
  tablename,
  n_live_tup,
  last_analyze,
  last_autoanalyze,
  now() - last_analyze AS time_since_analyze
FROM pg_stat_user_tables
WHERE (last_analyze < NOW() - INTERVAL '7 days' OR last_analyze IS NULL)
  AND n_live_tup > 10000
ORDER BY n_live_tup DESC;
```

**What it looks like**: After a bulk insert of 500K rows into a table that previously had 10K rows, the query planner still thinks the table has 10K rows and uses nested loops instead of hash joins.

**Why wrong**: PostgreSQL's query planner uses row count estimates to choose join strategies and index selection. Stale statistics (50x off) cause the planner to pick catastrophically wrong query plans.

**Fix**:
```sql
-- After bulk loads, run ANALYZE immediately
ANALYZE orders;

-- For very large tables, ANALYZE a sample
ANALYZE (VERBOSE) orders;

-- Ensure autovacuum settings are tuned for high-write tables
ALTER TABLE orders SET (
  autovacuum_analyze_scale_factor = 0.01,  -- Analyze after 1% change (default: 20%)
  autovacuum_vacuum_scale_factor = 0.05    -- Vacuum after 5% change
);
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `ERROR: duplicate key value violates unique constraint` | INSERT of duplicate PK or unique key | Use `INSERT ... ON CONFLICT DO UPDATE` or check before insert |
| `ERROR: deadlock detected` | Two transactions acquiring locks in opposite order | Ensure consistent lock ordering; use `SELECT ... FOR UPDATE SKIP LOCKED` for queues |
| `ERROR: could not serialize access due to concurrent update` | Serializable isolation conflict | Implement retry loop with exponential backoff on serialization failure |
| `FATAL: remaining connection slots reserved for replication` | Connection pool exhausted | Configure PgBouncer or reduce `max_connections`; add pool in application |
| `ERROR: column x is of type jsonb but expression is of type text` | Comparing JSONB to string literal | Cast: `attributes->>'key'` returns text; `attributes->'key'` returns jsonb |
| `ERROR: operator does not exist: jsonb = integer` | Type mismatch in JSONB comparison | Cast JSON value: `(attributes->>'count')::integer = 5` |

---

## Detection Commands Reference

```sql
-- Unindexed foreign keys
-- (see full query in Anti-Patterns section above)

-- Tables with stale statistics
SELECT tablename, last_analyze, n_live_tup
FROM pg_stat_user_tables
WHERE last_analyze < NOW() - INTERVAL '7 days'
ORDER BY n_live_tup DESC;

-- Largest tables by size
SELECT relname, pg_size_pretty(pg_total_relation_size(oid))
FROM pg_class WHERE relkind = 'r'
ORDER BY pg_total_relation_size(oid) DESC LIMIT 20;

-- Slow queries (requires pg_stat_statements extension)
SELECT query, mean_exec_time, calls, total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC LIMIT 20;
```

---

## See Also

- `sql.md` — Cross-database SQL patterns, N+1 queries, migration patterns
- `performance.md` — Index selection, connection pooling, query optimization strategies
