# Data Engineer Error Catalog

## DAG Dependency Deadlock
**Cause**: Circular dependencies between pipeline tasks, or upstream tasks that never complete, blocking the entire DAG.
**Solution**: Map the dependency graph explicitly. Break cycles with staging tables or intermediate datasets. Use Airflow's `ExternalTaskSensor` with timeout for cross-DAG dependencies.

## Late-Arriving Data
**Cause**: Events arrive after the processing window closes (common with mobile apps, IoT, distributed systems).
**Solution**: Implement late-arrival handling: add a reprocessing window (e.g., re-run last 3 days daily), use watermarking in streaming, or design a lambda architecture with batch correction layer.

## Schema Evolution Breakage
**Cause**: Source system schema changes without notice -- columns renamed, types changed, new fields added.
**Solution**: Implement data contracts between producer and consumer. Use schema registry for streaming (Confluent Schema Registry). Add schema validation as the first step in every extraction pipeline. Alert on schema drift.

## SCD Type Mismatch
**Cause**: Using SCD Type 1 (overwrite) when historical tracking is needed, or Type 2 (versioned rows) when only current state matters (adding unnecessary complexity).
**Solution**: Analyze reporting requirements before choosing. Type 1 for current-only attributes (e.g., customer email). Type 2 for historically significant attributes (e.g., customer segment, address for regional analysis). Document the choice and rationale per dimension.

## Duplicate Records After Re-run
**Cause**: Pipeline uses INSERT instead of MERGE/upsert, or lacks deduplication logic.
**Solution**: Use MERGE statements, partition overwrite (replace entire partition on re-run), or deduplication with ROW_NUMBER() windowed by natural key ordered by load timestamp. Every pipeline must produce identical results regardless of how many times it runs.
