# Data Engineer Gates and Blockers

## Hard Gate Patterns

If found: STOP, REPORT, FIX before continuing.

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

- After dimensional model/pipeline design: "Validated against existing schema and source reality?"
- After performance optimization: "Providing before/after metrics?"
- After modifying pipeline with downstream consumers: "Checked for breaking changes in dependent pipelines/dashboards/models?"

## Constraints at Point of Failure

Before destructive operations (DROP, TRUNCATE, partition deletion, full-refresh): confirm reversibility or backups. Irreversible warehouse data loss cascades everywhere.

Before production pipeline changes: validate in staging first.

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

## Death Loop Prevention

Max 3 attempts per pipeline design iteration. If not converging, re-examine requirements.

1. **Detection**: Repeated redesigns or cycling between SCD types
2. **Intervention**: Return to requirements -- grain or SCD choice is ambiguous
3. **Prevention**: Resolve blocker criteria before starting design
