# Data Engineer Preferred Patterns

Common data engineering patterns and their rationale. Loaded when reviewing pipeline designs or pushing back on shortcuts.

## Preferred Patterns

### Make Every Pipeline Step Idempotent

Use `MERGE`/`INSERT ... ON CONFLICT`, partition overwrite, or deduplication with windowed `ROW_NUMBER()` so that running a pipeline twice produces identical output. Test idempotency explicitly: run the pipeline twice against the same input and verify the row count and checksums match.

**Why this matters**: Non-idempotent steps (plain `INSERT INTO` without deduplication) create duplicate records on every re-run, inflating metrics silently. Recovery from failures requires manual intervention to delete duplicates before re-running -- an error-prone process that erodes trust in the data platform.

**Detection**: `grep -rn 'INSERT INTO' --include="*.sql" | grep -v 'ON CONFLICT\|MERGE\|UPSERT'` finds insert statements without deduplication guards.

---

### Define the Grain Before Designing Columns

State the grain explicitly before any column design: "one row per order line item per day." If stakeholders disagree on grain, that is a requirement blocker -- resolve it before building. Document the grain in the model's YAML description or dbt schema.

**Why this matters**: Ambiguous grain leads to double-counting in aggregations, inconsistent metrics across reports, and dimensions that don't join cleanly. The bug is invisible until two teams produce different numbers for the "same" metric.

**Detection**: `grep -rL 'grain\|one row per' models/ --include="*.yml" --include="*.yaml"` finds dbt model docs that may lack grain definitions.

---

### Validate Transforms in a Staging Environment First

Run transforms in a staging/dev environment before production. Use dbt's `--target dev` to test against a non-production dataset. Add schema tests and data tests (`not_null`, `unique`, `accepted_values`, row count assertions) that must pass before promotion to production.

**Why this matters**: Running new or modified dbt models directly against the production warehouse risks corrupting production data, breaking downstream dashboards, and eroding stakeholder trust in the data platform. A staging validation that takes 10 minutes prevents a production incident that takes 10 hours.

**Detection**: `grep -rn '\-\-target prod' --include="*.sh" --include="*.yml"` finds scripts that may run directly against production without a staging gate.

---

### Decompose Pipeline DAGs by Data Domain

Split monolithic DAGs into independent sub-DAGs, one per data domain, with clear contracts between them. Use dataset-triggered DAGs (Airflow 2.4+) or Dagster assets for cross-pipeline dependencies. Each sub-DAG should be independently backfillable, deployable, and debuggable.

**Why this matters**: A single 50+ task DAG is a single point of failure. One task failure blocks everything downstream, debugging requires tracing through unrelated tasks, backfilling one domain re-runs all domains, and deployment changes affect the entire pipeline.

**Detection**: `grep -c 'task_id' dags/*.py` gives task counts per DAG file. Any DAG with 20+ tasks warrants decomposition review.

---

### Centralize Business Logic in Shared Transformations

Define business calculations (revenue formulas, churn definitions, cohort logic) once in dbt macros or a shared transformation layer. Reference the centralized definition everywhere. Never duplicate formulas across models.

**Why this matters**: Duplicated business logic drifts. When the revenue formula is in 5 models with slight variations, different reports show different numbers for the "same" metric. Fixing a bug requires finding and updating every copy -- and missing one creates a silent inconsistency.

**Detection**: `grep -rn 'revenue\|total_amount\|net_amount' models/ --include="*.sql" | sort | uniq -c | sort -rn` surfaces formulas that may be duplicated across models.

---

### Parameterize Pipelines for Date-Range Backfill From Day One

Design every pipeline to accept start and end dates as parameters. Use `{{ ds }}` in Airflow, `var()` in dbt, or environment variables in scripts. Test backfill by running for a historical date range before the first production deployment.

**Why this matters**: When bugs are discovered, corrections require reprocessing historical data. Without date parameterization, this requires manual intervention, custom one-off scripts, and downtime. Schema changes that affect historical data become impossible to apply retroactively.

**Detection**: `grep -rL 'ds\|execution_date\|date_range\|start_date' dags/ --include="*.py"` finds DAGs that may lack date parameterization.

---

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
