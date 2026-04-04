# SQL Patterns Reference

> **Scope**: Cross-database SQL anti-patterns, N+1 detection, migration safety, and query correctness
> **Version range**: Standard SQL / PostgreSQL 14+ / MySQL 8.0+
> **Generated**: 2026-04-04 — syntax notes for PostgreSQL vs MySQL where they differ

---

## Overview

SQL bugs are silent: wrong queries don't raise errors, they return wrong data that propagates to reports and APIs. The most common SQL failures are N+1 patterns (100 queries where 1 would do), NULL comparison mistakes (`col = NULL` always returns false), and implicit type coercion in WHERE clauses that prevent index use. Detection requires EXPLAIN plans and slow query logs, not code review alone.

---

## Pattern Table: NULL Handling

| Pattern | SQL Behavior | Use When |
|---------|-------------|----------|
| `col = NULL` | Always FALSE (never matches) | Never use this |
| `col IS NULL` | Correct null check | Checking for absent values |
| `col IS NOT NULL` | Correct non-null check | Filtering out absent values |
| `COALESCE(col, default)` | Returns first non-null | Substituting defaults for nulls |
| `NULLIF(col, val)` | Returns NULL when col = val | Converting sentinels to NULL |
| `COUNT(col)` | Counts non-null values only | Column-level counts (vs `COUNT(*)`) |
| `col = ANY(ARRAY[...])` | NULL-safe for IN lists | Replacing large IN lists |

---

## Correct Patterns

### Solving N+1 with a Single JOIN

```sql
-- N+1 pattern: application executes 1 query to get orders, then 1 per order to get user
-- 1000 orders = 1001 queries

-- Wrong pattern (from ORM or manual loop):
SELECT * FROM orders WHERE status = 'pending';
-- Then for each order:
SELECT * FROM users WHERE id = ?;  -- executed 1000 times

-- Fix: Single JOIN retrieves all needed data
SELECT
  o.id AS order_id,
  o.status,
  o.total_amount,
  u.name AS customer_name,
  u.email AS customer_email
FROM orders o
JOIN users u ON o.user_id = u.id
WHERE o.status = 'pending';
```

**Why**: 1001 round-trips to the database at 1ms each = 1 second of latency. 1 JOIN query = 5ms. The performance difference scales with result set size.

---

### Safe NULL Comparisons

```sql
-- Checking for NULL: IS NULL, not = NULL
-- Wrong: never matches any row
SELECT * FROM users WHERE deleted_at = NULL;

-- Correct
SELECT * FROM users WHERE deleted_at IS NULL;

-- Combining null and value checks
SELECT * FROM users
WHERE deleted_at IS NULL          -- Active users
   OR deleted_at > NOW() - INTERVAL '30 days';  -- Deleted within 30 days

-- NULL in aggregate: COUNT(*) vs COUNT(col)
SELECT
  COUNT(*) AS total_rows,              -- Counts all rows including NULLs
  COUNT(email) AS rows_with_email,     -- Counts only non-NULL email rows
  COUNT(DISTINCT email) AS unique_emails
FROM users;
```

---

### Zero-Downtime Migration Pattern

For production tables that can't be taken offline:

```sql
-- Phase 1: Add nullable column (fast, no lock on data)
ALTER TABLE orders ADD COLUMN processed_at TIMESTAMPTZ;
-- Deploy: application writes processed_at for new orders

-- Phase 2: Backfill existing rows in batches (no long lock)
UPDATE orders SET processed_at = created_at
WHERE processed_at IS NULL
  AND id BETWEEN 1 AND 100000;  -- Process in batches to avoid long locks

-- Repeat for remaining batches with increasing ID ranges
-- Schedule during low-traffic windows, pause if replication lag increases

-- Phase 3: Add NOT NULL constraint (requires all rows populated)
-- PostgreSQL 14+: validates without full table scan if using NOT VALID first
ALTER TABLE orders
  ADD CONSTRAINT orders_processed_at_not_null
  CHECK (processed_at IS NOT NULL) NOT VALID;

ALTER TABLE orders VALIDATE CONSTRAINT orders_processed_at_not_null;
-- Validate acquires ShareLock, not ExclusiveLock — concurrent reads allowed

-- Phase 4: Convert to NOT NULL column (after constraint validated)
ALTER TABLE orders ALTER COLUMN processed_at SET NOT NULL;
```

**Why**: `ALTER TABLE ... ALTER COLUMN ... SET NOT NULL` without prior constraint validation requires a full table scan with ExclusiveLock, blocking all writes. The NOT VALID → VALIDATE approach does the check incrementally, only holding a ShareLock during validation.

---

### Pagination with Keyset Instead of OFFSET

```sql
-- OFFSET pagination: gets slower as page number increases
-- Page 1000 of 20 = scan 20,000 rows then discard 19,980
SELECT * FROM orders
ORDER BY created_at DESC
LIMIT 20 OFFSET 19980;  -- 20s on 10M row table

-- Keyset pagination: always O(1) regardless of depth
-- First page
SELECT id, created_at, amount
FROM orders
ORDER BY created_at DESC, id DESC
LIMIT 20;

-- Next page: pass last_created_at and last_id from previous page
SELECT id, created_at, amount
FROM orders
WHERE (created_at, id) < ($last_created_at, $last_id)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

**Why**: OFFSET scans all rows up to the offset. Page 1000 is 1000× slower than page 1. Keyset pagination uses the index to jump directly to the right position — always the same speed regardless of page depth.

**Version note**: Composite comparison `(col1, col2) < (val1, val2)` is standard SQL and supported in PostgreSQL and MySQL 8.0+.

---

## Anti-Pattern Catalog

### ❌ SELECT * in Application Queries

**Detection**:
```bash
# Find SELECT * in application SQL strings
grep -rn "SELECT \*\|select \*" src/ --include="*.py" --include="*.go" \
  --include="*.ts" --include="*.js" --include="*.rb"

# Find in ORM query builders
grep -rn "\.find_all\(\|\.all()\|fetchAll()" src/ --include="*.py" --include="*.rb"
```

**What it looks like**:
```python
# Python example
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

**Why wrong**: Retrieves all columns including large TEXT/BLOB fields even when only `name` and `email` are needed. Breaks when schema adds columns (new columns appear in API responses). Prevents index-only scans (which need only indexed columns).

**Fix**:
```python
cursor.execute(
    "SELECT id, name, email, created_at FROM users WHERE id = %s",
    (user_id,)
)
```

---

### ❌ Implicit Type Conversion in WHERE Clause

**Detection**:
```bash
# Find potential type mismatch comparisons in SQL strings
# (column is VARCHAR/TEXT but compared to integer, or vice versa)
grep -rn "WHERE.*id.*=.*'\|WHERE.*_id.*=.*'" src/ --include="*.py" --include="*.go"

# PostgreSQL: check pg_stat_statements for full seq scans that shouldn't be
SELECT query, rows, shared_blks_read
FROM pg_stat_statements
WHERE shared_blks_read > 10000
ORDER BY shared_blks_read DESC;
```

**What it looks like**:
```sql
-- users.id is BIGINT, but query passes a string
SELECT * FROM users WHERE id = '12345';

-- MySQL: silently converts, but prevents index use
-- PostgreSQL: may work or throw type mismatch error depending on context
```

**Why wrong**: In MySQL, comparing an integer column to a string `'12345'` coerces the string to integer for comparison but may or may not use the index depending on the column type. PostgreSQL is stricter and often throws an error, but implicit casts in some cases bypass indexes.

**Fix**: Pass the correct type from the application:
```python
# Python: pass integer, not string
cursor.execute("SELECT * FROM users WHERE id = %s", (int(user_id),))
```

---

### ❌ Unparameterized Queries (SQL Injection Risk)

**Detection**:
```bash
# Find string interpolation in SQL queries (critical security issue)
grep -rn "f\"SELECT\|f'SELECT\|\"SELECT.*%s.*%\" %\|'SELECT.*format(" \
  src/ --include="*.py"

grep -rn "\"SELECT.*\+.*\|query.*\+.*where" src/ --include="*.go" --include="*.java"
```

**What it looks like**:
```python
# SQL injection vulnerability
user_id = request.args.get('id')
query = f"SELECT * FROM users WHERE id = {user_id}"  # NEVER DO THIS
cursor.execute(query)
```

**Why wrong**: Attacker passes `id=1 OR 1=1` to dump all users, or `id=1; DROP TABLE users` to destroy data. This is OWASP Top 10 #3.

**Fix**:
```python
# Always use parameterized queries
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# SQLAlchemy ORM
user = session.query(User).filter(User.id == user_id).first()
```

---

### ❌ Function on Indexed Column in WHERE Clause

**Detection**:
```bash
# Find function calls wrapping column names in WHERE clauses
grep -rn "WHERE.*DATE(\|WHERE.*LOWER(\|WHERE.*UPPER(\|WHERE.*YEAR(\|WHERE.*MONTH(" \
  src/ --include="*.sql" --include="*.py"
```

**What it looks like**:
```sql
-- B-tree index on created_at is useless here
SELECT * FROM orders WHERE DATE(created_at) = '2026-04-04';

-- B-tree index on email is useless here
SELECT * FROM users WHERE LOWER(email) = 'alice@example.com';
```

**Why wrong**: Applying a function to an indexed column prevents index use. `DATE(created_at)` computes a new value for every row, forcing a full sequential scan. The index stores values of `created_at`, not values of `DATE(created_at)`.

**Fix**:
```sql
-- Date range instead of function (uses index)
SELECT * FROM orders
WHERE created_at >= '2026-04-04'
  AND created_at < '2026-04-05';

-- For case-insensitive email search: expression index
CREATE INDEX idx_users_email_lower ON users (LOWER(email));
SELECT * FROM users WHERE LOWER(email) = 'alice@example.com';
-- OR: store email already lowercased
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `ERROR: operator does not exist: integer = character varying` | Type mismatch in comparison | Cast column or pass correct type: `WHERE id = $1::bigint` |
| `ERROR: syntax error at or near "LIMIT"` | LIMIT without ORDER BY (some databases require ORDER for LIMIT) | Always add `ORDER BY` before `LIMIT` |
| `Lock wait timeout exceeded` | Long-running transaction holding row lock | Use `SELECT ... FOR UPDATE SKIP LOCKED` for job queues; check for long-running transactions |
| `ERROR: column reference "x" is ambiguous` | JOIN with same column name in both tables | Qualify with table alias: `u.id` instead of `id` |
| `ERROR: value too long for type character varying(N)` | Input exceeds column width | Increase column size in migration or truncate input |

---

## Detection Commands Reference

```bash
# PostgreSQL: Find slow queries (requires pg_stat_statements)
psql -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 20;"

# MySQL: Show slow query log
mysql -e "SHOW VARIABLES LIKE 'slow_query_log%';"
mysql -e "SELECT * FROM mysql.slow_log ORDER BY start_time DESC LIMIT 20;"

# Find SELECT * in application code
grep -rn "SELECT \*" src/ --include="*.py" --include="*.go" --include="*.ts"

# Find unparameterized queries (Python f-string SQL)
grep -rn 'f"SELECT\|f'"'"'SELECT' src/ --include="*.py"

# Find function-wrapped indexed columns in WHERE
grep -rn "WHERE.*DATE(\|WHERE.*LOWER(\|WHERE.*UPPER(" --include="*.sql"
```

---

## See Also

- `postgres.md` — PostgreSQL-specific patterns: index types, EXPLAIN analysis, JSONB
- `performance.md` — Index selection, connection pooling, query caching strategies
