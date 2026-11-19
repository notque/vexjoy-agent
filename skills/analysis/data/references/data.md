# Data Engineering Reference

> **Scope**: OLAP pipeline design, ETL/ELT orchestration (Airflow, Prefect, Dagster, dbt), dimensional modeling (star, snowflake, data vault, SCD), data quality, stream processing (Kafka, Spark, Flink), warehouse and lake storage (BigQuery, Redshift, Parquet, Delta Lake, Iceberg), lineage.
> **Not here**: OLTP schema and query tuning (`database.md`); embedded SQLite and Peewee (`sqlite-peewee.md`); RabbitMQ or AMQP topology, clustering, and HA (`skills/infrastructure/kubernetes/references/rabbitmq-messaging.md`); data analysis (this skill, Mode A). This reference complements `database.md`, which owns OLTP concerns.

Full expertise list, default and optional behaviors, scope limits, and output format: [data/expertise.md](data/expertise.md). Load it when scoping or designing a pipeline.

## Hard rules

- **Prevent over-engineering**: build what is asked, not a platform. Use streaming only when batch is not enough. Use real-time CDC only when daily snapshots fall short. Three simple DAGs beat one "universal" pipeline framework.
- **Idempotency required**: every pipeline step is safe to re-run. Use MERGE/upsert, partition overwrite, or deduplication. A pipeline that creates duplicates on re-run is broken. Failures are inevitable; the only question is whether recovery is automatic or manual.
- **Grain first**: state every fact table's grain ("one row per ___") before designing columns. Wrong grain means wrong numbers, and wrong numbers undermine every decision built on them.
- **Quality gates before load**: validate schema and check null key columns before loading target tables. Bad data in a warehouse reaches every dashboard, report, and ML model downstream; catching it at the gate is far cheaper than fixing it later.

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| Expertise, default/optional behaviors, scope limits, output format | [data/expertise.md](data/expertise.md) | Scoping and output contract |
| Pipeline error catalog (deadlocks, late data, schema drift, SCD mismatch, duplicates) | [data/error-catalog.md](data/error-catalog.md) | Error to fix mappings |
| Pipeline preferred patterns, detection signals, domain rationalizations | [data/preferred-patterns.md](data/preferred-patterns.md) | Patterns with grep detection |
| Pipeline hard gates, STOP blocks, blocker criteria, death loop prevention | [data/gates-and-blockers.md](data/gates-and-blockers.md) | Gates and when to stop |
| MERGE, INSERT ON CONFLICT, partition overwrite, deduplication, incremental SQL | [data/sql.md](data/sql.md) | Idempotent SQL patterns |
| dbt tests, Great Expectations, source freshness, row count reconciliation | [data/testing.md](data/testing.md) | Pipeline testing |
| Partitioning, clustering, materialized views, incremental processing, warehouse cost | [data/performance.md](data/performance.md) | Warehouse performance |

Implementation Schema details: [output-schemas.md](../../../shared-patterns/output-schemas.md).
