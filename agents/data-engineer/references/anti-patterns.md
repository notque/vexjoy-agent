# Data Engineer Anti-Patterns and Rationalizations

Common data engineering mistakes and their corrections, plus domain-specific rationalizations. Loaded when reviewing pipeline designs or pushing back on shortcuts.

## Preferred Patterns

Common data engineering mistakes and their corrections.

### ❌ Non-Idempotent Pipeline Steps
**What it looks like**: Using `INSERT INTO` without deduplication, appending to tables on every run without checking for existing data.
**Why wrong**: Re-runs create duplicate records, inflating metrics. Recovery from failures requires manual intervention to delete duplicates before re-running.
**Do instead**: Use `MERGE`/`INSERT ... ON CONFLICT`, partition overwrite, or deduplication with windowed `ROW_NUMBER()`. Test by running the pipeline twice and verifying identical output.

### ❌ Fact Table Without Defined Grain
**What it looks like**: Creating a fact table and adding columns without first stating "one row represents ___."
**Why wrong**: Ambiguous grain leads to double-counting in aggregations, inconsistent metrics across reports, and dimensions that don't join cleanly.
**Do instead**: State grain explicitly before any column design: "one row per order line item per day." If stakeholders disagree on grain, that is a blocker -- resolve it before building.

### ❌ Testing Transforms in Production
**What it looks like**: Running new or modified dbt models directly against the production warehouse without staging environment validation.
**Why wrong**: Bad transforms corrupt production data, break downstream dashboards, and erode trust in the data platform.
**Do instead**: Run transforms in a staging/dev environment first. Use dbt's `--target dev` to test against a non-production dataset. Add schema and data tests that must pass before promotion.

### ❌ Monolithic Pipeline DAG
**What it looks like**: A single Airflow DAG with 50+ tasks covering extraction, transformation, loading, and quality checks for multiple data domains.
**Why wrong**: A single task failure blocks everything. Impossible to debug. Can't backfill one domain without re-running all. Deployment changes affect the entire pipeline.
**Do instead**: Decompose into independent sub-DAGs per data domain with clear contracts. Use dataset-triggered DAGs (Airflow 2.4+) or Dagster assets for cross-pipeline dependencies.

### ❌ Hardcoded Business Logic in SQL
**What it looks like**: Revenue calculation formula duplicated across 5 different dbt models with slight variations.
**Why wrong**: Logic drift -- different reports show different numbers for the "same" metric. Fixing a bug requires finding and updating every copy.
**Do instead**: Centralize business logic in dbt macros or a shared transformation layer. Define metrics once, reference everywhere.

### ❌ No Backfill Strategy
**What it looks like**: Pipeline only processes "today's data" with no way to reprocess historical date ranges.
**Why wrong**: When bugs are found, corrections require manual intervention. Schema changes that affect historical data can't be applied retroactively.
**Do instead**: Parameterize pipelines with date ranges from day one. Use `{{ ds }}` in Airflow, `var()` in dbt. Test backfill by running for a historical date range before going to production.

## Domain-Specific Rationalizations

See [shared-patterns/anti-rationalization-core.md](../../skills/shared-patterns/anti-rationalization-core.md) for universal patterns.

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "We'll add data quality checks later" | Bad data compounds daily -- every day without checks is a day of potentially corrupt data in the warehouse | Add at minimum: null key checks, schema validation, freshness assertion before first production load |
| "INSERT is fine, we'll deduplicate downstream" | Deduplication downstream is fragile and often forgotten. Every consumer must now handle duplicates | Use MERGE/upsert at the source. Idempotency is a pipeline responsibility, not a consumer responsibility |
| "The grain is obvious" | Obvious to you is ambiguous to the next engineer. Unstated grain leads to metric disagreements | State the grain explicitly in model documentation: "one row per ___" |
| "Daily batch is too slow, we need streaming" | Streaming adds 10x complexity (Kafka, exactly-once, windowing, state management). Most analytics don't need sub-minute freshness | Prove the latency requirement first. If hourly or daily batch works, use it |
| "SCD Type 2 for everything" | Type 2 adds surrogate keys, effective dates, and current flags to every dimension. Most dimensions don't need full history | Choose SCD type per dimension based on actual reporting needs. Type 1 is correct when history is irrelevant |
| "One big DAG keeps things simple" | A 50-task DAG is not simple -- it's a single point of failure with hidden dependencies | Decompose by data domain. Independent pipelines with clear contracts are actually simpler |
| "We can figure out lineage later" | Without lineage, you can't answer "what breaks if this source changes?" -- and someone will ask | Document source -> transform -> target for every pipeline at build time |
