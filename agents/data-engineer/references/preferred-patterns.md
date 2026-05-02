# Data Engineer Preferred Patterns

### Make Every Pipeline Step Idempotent

Use `MERGE`/`INSERT ... ON CONFLICT`, partition overwrite, or `ROW_NUMBER()` deduplication. Test: run twice, verify row count and checksums match.

**Why**: Non-idempotent steps create duplicates on re-run, inflating metrics silently.

**Detection**: `grep -rn 'INSERT INTO' --include="*.sql" | grep -v 'ON CONFLICT\|MERGE\|UPSERT'` finds insert statements without deduplication guards.

---

### Define the Grain Before Designing Columns

State explicitly: "one row per order line item per day." Stakeholder disagreement = requirement blocker. Document in dbt schema YAML.

**Why**: Ambiguous grain = double-counting, inconsistent metrics, dimensions that don't join.

**Detection**: `grep -rL 'grain\|one row per' models/ --include="*.yml" --include="*.yaml"` finds dbt model docs that may lack grain definitions.

---

### Validate Transforms in Staging First

`--target dev` before production. Schema + data tests must pass before promotion.

**Why**: 10 minutes of staging validation prevents 10 hours of production incident.

**Detection**: `grep -rn '\-\-target prod' --include="*.sh" --include="*.yml"` finds scripts that may run directly against production without a staging gate.

---

### Decompose DAGs by Data Domain

One sub-DAG per domain with clear contracts. Dataset-triggered DAGs (Airflow 2.4+) or Dagster assets for cross-pipeline deps. Each independently backfillable.

**Why**: A 50+ task DAG is a single point of failure.

**Detection**: `grep -c 'task_id' dags/*.py` gives task counts per DAG file. Any DAG with 20+ tasks warrants decomposition review.

---

### Centralize Business Logic

Define calculations once in dbt macros. Never duplicate formulas across models.

**Why**: Duplicated logic drifts. Revenue formula in 5 models = different numbers for the "same" metric.

**Detection**: `grep -rn 'revenue\|total_amount\|net_amount' models/ --include="*.sql" | sort | uniq -c | sort -rn` surfaces formulas that may be duplicated across models.

---

### Parameterize for Backfill From Day One

Accept start/end dates as parameters. `{{ ds }}` in Airflow, `var()` in dbt. Test backfill before first production deploy.

**Why**: Bug corrections require reprocessing. Without parameters = manual intervention.

**Detection**: `grep -rL 'ds\|execution_date\|date_range\|start_date' dags/ --include="*.py"` finds DAGs that may lack date parameterization.

---

## Domain-Specific Rationalizations

See [shared-patterns/anti-rationalization-core.md](../../skills/shared-patterns/anti-rationalization-core.md).

| Rationalization | Why Wrong | Action |
|----------------|-----------|--------|
| "Quality checks later" | Bad data compounds daily | Null key checks + schema validation + freshness before first load |
| "INSERT is fine, deduplicate downstream" | Downstream dedup is fragile | MERGE/upsert at source |
| "The grain is obvious" | Ambiguous to next engineer | State "one row per ___" |
| "Need streaming" | 10x complexity | Prove latency requirement first |
| "SCD Type 2 for everything" | Most dimensions don't need history | Choose per dimension |
| "One big DAG" | Single point of failure | Decompose by domain |
| "Lineage later" | Can't answer "what breaks?" | Document at build time |
