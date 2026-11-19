# Data Pipeline SQL Reference

> **Scope**: Idempotent pipeline SQL — MERGE, partition overwrite, deduplication, incremental processing
> **Version range**: SQL:2003+ / PostgreSQL 15+ / BigQuery / Snowflake / Redshift

Three failure modes: duplicates on re-run, silent schema drift (SELECT *), incorrect grain aggregation. Every query must answer "same result if run twice?" MERGE and partition overwrite are the primary idempotency tools.

## Pattern Table: Idempotency Approaches

| Pattern | Works In | Use When | Limitation |
|---------|----------|----------|------------|
| `MERGE INTO` (SQL:2003) | PostgreSQL 15+, Snowflake, BigQuery | Natural key exists for upsert | Complex syntax, can't batch-delete |
| `INSERT ... ON CONFLICT DO UPDATE` | PostgreSQL 9.5+ | Simpler upsert syntax in Postgres | PostgreSQL-only |
| Partition overwrite | BigQuery, Snowflake, Spark | Date-partitioned tables, full partition re-run | Requires partitioned tables |
| `DELETE + INSERT` in transaction | All databases | Small datasets, no upsert key | Performance: DELETE is a full scan |
| `ROW_NUMBER()` deduplication | All databases | Post-load deduplication, no natural key | Needs staging table |

---

## Correct Patterns

### MERGE for Idempotent Upsert (PostgreSQL 15+ / Snowflake / BigQuery)

```sql
-- PostgreSQL 15+ MERGE syntax
MERGE INTO dim_customer AS target
USING staging_customer AS source
  ON target.customer_id = source.customer_id
WHEN MATCHED AND (
    target.email != source.email OR
    target.segment != source.segment
  ) THEN
  UPDATE SET
    email = source.email,
    segment = source.segment,
    updated_at = NOW()
WHEN NOT MATCHED THEN
  INSERT (customer_id, email, segment, created_at, updated_at)
  VALUES (source.customer_id, source.email, source.segment, NOW(), NOW());
```

Safe to re-run: updates only on value change, inserts new, untouches unchanged.

---

### INSERT ... ON CONFLICT for PostgreSQL Upsert

```sql
-- PostgreSQL 9.5+: cleaner syntax for simple upserts
INSERT INTO dim_customer (customer_id, email, segment, updated_at)
SELECT customer_id, email, segment, NOW()
FROM staging_customer

ON CONFLICT (customer_id) DO UPDATE SET
  email = EXCLUDED.email,
  segment = EXCLUDED.segment,
  updated_at = EXCLUDED.updated_at

-- For SCD Type 2: don't update on conflict, insert new version instead
-- (requires separate MERGE or procedure)
```

**Why**: `EXCLUDED` refers to the row that would have been inserted. More readable than MERGE for simple cases.

---

### Partition Overwrite (BigQuery / Snowflake)

```sql
-- BigQuery: partition overwrite for date-partitioned tables
-- Run for a specific date range -- overwrites exactly those partitions
INSERT OVERWRITE INTO fact_orders
PARTITION (event_date)
SELECT
  order_id,
  customer_id,
  amount,
  DATE(created_at) AS event_date
FROM raw.orders
WHERE DATE(created_at) BETWEEN @start_date AND @end_date;

-- Snowflake equivalent with COPY INTO + overwrite
COPY INTO fact_orders
FROM @stage/orders_{{ ds }}.parquet
FILE_FORMAT = (TYPE = 'PARQUET')
PURGE = FALSE
FORCE = TRUE;  -- Overwrite existing
```

**Why**: Instead of tracking which rows changed, overwrite the entire partition. Idempotent by definition: re-running for the same date range produces the same partition contents.

---

### ROW_NUMBER Deduplication for Staging

```sql
-- Deduplicate before loading into fact table
-- Use when source delivers duplicates or pipeline can re-deliver records
WITH deduped AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY order_id              -- natural key
      ORDER BY _extracted_at DESC        -- keep most recent
    ) AS rn
  FROM staging.raw_orders
)
INSERT INTO fact_orders (order_id, customer_id, amount, created_at)
SELECT order_id, customer_id, amount, created_at
FROM deduped
WHERE rn = 1;
```

**Why**: `ROW_NUMBER()` with the natural key as PARTITION BY and a recency ordering as ORDER BY keeps exactly one row per entity. More robust than DISTINCT (handles partial duplicates where some fields differ).

---

### Incremental Processing Pattern (dbt)

```sql
-- models/fact_orders.sql
{{
  config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge'
  )
}}

SELECT
  order_id,
  customer_id,
  SUM(line_item_amount) AS total_amount,
  COUNT(*) AS line_item_count,
  MIN(created_at) AS order_created_at
FROM {{ source('raw', 'order_line_items') }}

{% if is_incremental() %}
  WHERE created_at > (SELECT MAX(order_created_at) FROM {{ this }})
{% endif %}

GROUP BY order_id, customer_id
```

**Why**: `is_incremental()` macro makes the query context-aware: full refresh on first run, incremental on subsequent runs. `unique_key` triggers MERGE behavior, preventing duplicates on overlapping date ranges.

---

## Pattern Catalog

### Use MERGE or ON CONFLICT for Idempotent Inserts
**Detection**:
```sql
-- Review pipeline SQL for INSERT without ON CONFLICT or MERGE
-- Search for raw INSERT INTO ... SELECT patterns
```

```bash
# Find INSERT without ON CONFLICT or MERGE in SQL files
grep -rn "INSERT INTO" pipelines/ dbt/ sql/ --include="*.sql" \
  | grep -v "ON CONFLICT\|MERGE\|INSERT OVERWRITE\|IGNORE INTO"

rg 'INSERT INTO \w+ SELECT' --type sql | grep -v "ON CONFLICT"
```

**Signal**:
```sql
-- BROKEN: Creates duplicates on every pipeline re-run
INSERT INTO fact_orders (order_id, amount, created_at)
SELECT order_id, SUM(amount), created_at
FROM staging_orders
GROUP BY order_id, created_at;
```

**Why**: Re-runs add duplicates. Aggregations double-count. Recovery requires manual partition deletion.

**Fix**: Use MERGE or INSERT ON CONFLICT.

---

### Use Explicit Column Lists in Pipeline SQL
**Detection**:
```bash
grep -rn "SELECT \*" models/ pipelines/ sql/ --include="*.sql"
rg 'SELECT \*' --type sql
```

**Signal**:
```sql
-- Staging model that passes through everything
SELECT * FROM raw.orders
```

**Why**: Schema additions pass downstream, breaking models or leaking PII.

**Fix**:
```sql
-- Explicit column selection — schema changes are opt-in
SELECT
  order_id,
  customer_id,
  status,
  total_amount,
  created_at,
  updated_at
FROM raw.orders
```

**Exception**: `SELECT *` is acceptable in staging models that mirror source 1:1 AND have schema tests to catch unexpected columns.

---

### Parameterize All Date Values in Pipeline SQL
**Detection**:
```bash
# Find hardcoded date literals in SQL pipeline files
grep -rn "WHERE.*[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}" pipelines/ sql/ --include="*.sql" \
  | grep -v "-- example\|-- comment"

rg "'\d{4}-\d{2}-\d{2}'" --type sql | grep -v "#"
```

**Signal**:
```sql
-- Can't backfill, can't test, breaks next day
INSERT INTO fact_orders
SELECT * FROM staging_orders
WHERE DATE(created_at) = '2026-04-04'  -- hardcoded!
```

**Why**: Only runs for one date. Backfill requires manual edits. CI breaks when date passes.

**Fix**:
```sql
-- Parameterized (Airflow Jinja templating)
WHERE DATE(created_at) = '{{ ds }}'

-- dbt variable
WHERE DATE(created_at) = '{{ var("run_date") }}'

-- Parameterized (Python/SQL with bind variables)
WHERE DATE(created_at) = %(run_date)s
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `duplicate key value violates unique constraint` | Re-run of INSERT without ON CONFLICT | Switch to `INSERT ... ON CONFLICT DO UPDATE` or MERGE |
| `column "x" of relation does not exist` | SELECT * picked up a column that was renamed downstream | Replace SELECT * with explicit column list |
| `division by zero in aggregate` | Fact table has duplicate rows inflating denominator | Add deduplication step before aggregation |
| `Query exceeded resource limits` | Full table scan on large unpartitioned table | Add partition filter; verify partition pruning with EXPLAIN |
| `No partition found for value` | Partition-overwrite targets partition that doesn't exist | Create partition first or use `CREATE IF NOT EXISTS` |

---

## Detection Commands Reference

```bash
# Non-idempotent INSERT patterns
grep -rn "INSERT INTO" --include="*.sql" \
  | grep -v "ON CONFLICT\|MERGE INTO\|INSERT OVERWRITE"

# SELECT * in pipeline SQL
grep -rn "SELECT \*" --include="*.sql"

# Hardcoded date literals
grep -rn "'\d{4}-\d{2}-\d{2}'" --include="*.sql"

# dbt models without tests (schema.yml check)
dbt ls --resource-type model | sort > /tmp/models.txt
dbt ls --resource-type test | sed 's/test\.//' | sort > /tmp/tested.txt
comm -23 /tmp/models.txt /tmp/tested.txt  # Models with no tests
```

---

## See Also

- `testing.md` — dbt tests, Great Expectations, data quality gate patterns
- `performance.md` — Partitioning, clustering, and query optimization for warehouses
