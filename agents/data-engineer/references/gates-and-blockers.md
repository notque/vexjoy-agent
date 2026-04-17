# Data Engineer Gates and Blockers

Hard gate patterns, verification STOP blocks, point-of-failure constraints, recommendation format, blocker criteria, and death loop prevention. Loaded when designing or reviewing pipelines.

## Hard Gate Patterns

Before designing or writing pipeline code, check for these patterns. If found:
1. STOP - Pause execution
2. REPORT - Flag to user
3. FIX - Correct before continuing

| Pattern | Why Blocked | Correct Alternative |
|---------|---------------|---------------------|
| `INSERT INTO target SELECT ... FROM source` without deduplication | Creates duplicates on every re-run; broken recovery | `MERGE INTO` or `INSERT ... ON CONFLICT DO UPDATE` or partition overwrite |
| Fact table without explicit grain statement | Wrong grain = wrong numbers for every downstream consumer | State "one row per ___" before adding any columns |
| Pipeline loading data without any quality check | Bad data propagates to dashboards, reports, ML models | Add schema validation + null key checks as minimum gate |
| `SELECT *` in pipeline transforms | Breaks when source schema changes; loads unnecessary data | Select only needed columns explicitly |
| Hardcoded dates in pipeline logic | Can't backfill, can't test, can't recover | Use parameterized dates (`{{ ds }}` in Airflow, `var()` in dbt) |
| dbt model without at least one test | Untested transforms silently produce wrong data | Add `unique`, `not_null` on primary key at minimum |

### Detection
```sql
-- Find INSERT without MERGE pattern (review pipeline SQL)
-- Look for: INSERT INTO ... SELECT without ON CONFLICT or MERGE
-- This requires manual review of pipeline definitions

-- Find SELECT * in dbt models
-- grep -rn "SELECT \*" models/ --include="*.sql"

-- Find models without tests
-- dbt ls --resource-type test | wc -l vs dbt ls --resource-type model | wc -l
```

### Exceptions
- `INSERT INTO` is acceptable for append-only event logs where the source guarantees exactly-once delivery and the table is partitioned by date with partition overwrite on re-run
- `SELECT *` is acceptable in staging models that explicitly mirror source tables 1:1 (but the staging model itself should have schema tests)

## Verification STOP Blocks

After designing a dimensional model or pipeline architecture, STOP and ask: "Have I validated this design against the existing schema and source system reality? Dimensional modeling without validation against actual source data is speculation."

After recommending a performance optimization (partitioning, clustering, materialized views, incremental processing), STOP and ask: "Am I providing before/after metrics, or can I explain why measurement is impossible here? Unmeasured optimization is guesswork."

After modifying a pipeline that feeds downstream consumers, STOP and ask: "Have I checked for breaking changes in dependent pipelines, dashboards, reports, and ML models? A grain change or column rename cascades everywhere."

## Constraints at Point of Failure

Before any destructive pipeline operation (DROP TABLE, TRUNCATE, partition deletion, full-refresh of a large table): confirm the operation is reversible or that backups/snapshots exist. Irreversible data loss in a warehouse propagates to every downstream consumer.

Before applying pipeline changes to production: validate SQL syntax and DAG structure in a staging environment first. A syntax error in a production pipeline causes failed runs and data gaps that compound daily.

## Recommendation Format

Each pipeline or model recommendation must include:
- **Component**: Table, model, DAG, or pipeline step being changed
- **Current state**: What exists now (or "new" if creating)
- **Proposed state**: What the change produces
- **Risk level**: Low / Medium / High with brief justification

## Blocker Criteria

STOP and ask the user (get explicit confirmation) when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Batch vs. streaming unclear | Architecture-level decision with 10x complexity difference | "Do you need real-time (<1 min latency) or is daily/hourly batch sufficient?" |
| Warehouse platform not chosen | Platform-specific SQL, partitioning, and optimization differ significantly | "Which warehouse: BigQuery, Snowflake, Redshift, DuckDB, or something else?" |
| SCD type for a dimension | Affects schema design, surrogate key strategy, and query patterns permanently | "Do you need historical tracking for [dimension]? Full history (Type 2) or current only (Type 1)?" |
| Fact table grain ambiguous | Wrong grain means wrong numbers in every report | "What does one row represent: one order, one order line item, one daily snapshot?" |
| Source system ownership unclear | Affects data contract design and schema evolution strategy | "Who owns the source schema? Can we establish a data contract for change notification?" |
| Orchestrator not chosen | DAG syntax, operator selection, and deployment differ by tool | "Which orchestrator: Airflow, Prefect, Dagster, or dbt Cloud scheduled jobs?" |

### Always Confirm Before Acting On
- Fact table grain (one row per ___)
- SCD type for dimensions (Type 1 vs 2 vs 3)
- Batch vs. streaming architecture
- Warehouse platform selection
- Source system ownership and data contracts
- Orchestrator choice

## Death Loop Prevention

### Retry Limits
- Maximum 3 attempts for any pipeline design iteration
- If data model doesn't converge after 3 revisions, stop and re-examine requirements with user

### Recovery Protocol
1. **Detection**: Repeated redesigns of the same fact/dimension table, or cycling between SCD types
2. **Intervention**: Go back to requirements -- the grain or SCD choice is likely ambiguous
3. **Prevention**: Always resolve blocker criteria before starting design
