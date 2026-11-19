# OpenSearch and Elasticsearch Reference

> **Scope**: Run and tune the search cluster itself: node roles, shard allocation, cluster health, snapshot/restore, rolling upgrades, mappings, analyzers, index templates, ILM, reindexing, aliases, Query DSL and aggregation performance, profiling, caching, Bulk API, ingest pipelines, Logstash, hot-warm-cold tiering, capacity planning.
> **Not here**: search-relevance UX or query-DSL authoring inside an app (`domain` skill); relational indexing and query tuning (`skills/analysis/data/references/database.md`); Kubernetes deployment (`kubernetes-helm.md`); application code and log formatting (`programming` skill). Dashboard design in Kibana is out of scope.

Baselines: shards 20-50 GB, heap 50% of RAM and at most 31 GB, primary plus replica, index templates for consistent mappings, ILM for lifecycle. Priorities: performance (query latency, ingest throughput), reliability (replicas, snapshots), scalability (shard sizing, node scaling), cost (tiering, retention).

## Hard rules

- **Shard size limits**: shards are 20-50 GB; warn outside that range.
- **Replicas**: production indices have at least 1 replica.
- **Heap**: at most 50% of RAM and at most 31 GB (compressed pointers limit).
- **Mapping explosion prevention**: limit field count; use explicit mappings in production.

## Defaults (on unless disabled)

- Use index templates for consistent mappings.
- Monitor cluster health, JVM heap, and query performance.
- Configure automated snapshots for disaster recovery.

## Optional (off unless enabled)

- Machine learning, only for anomaly detection or inference.
- Cross-cluster search, only across clusters.
- Alerting/Watcher, only for automated alerts.
- SQL interface, only when SQL query support is needed.

## Output

- **Before**: requirements, current state (cluster stats, index info), scale (data volume, query load), performance targets (latency, throughput).
- **During**: show mappings, query DSL, cluster API calls, performance metrics.
- **After**: indices configured, queries optimized, cluster healthy, targets met; report query latency (p50, p99), ingest rate (docs/sec), cluster health (green/yellow/red).
- Implementation Schema details: [output-schemas.md](../../../shared-patterns/output-schemas.md).

## Error handling

| Error | Cause | Fix |
|---|---|---|
| Cluster yellow | Unassigned replicas: too few nodes, disk full, allocation disabled | Add nodes, free disk (more than 15% free required), `GET /_cluster/allocation/explain`, re-enable allocation |
| Circuit breaker exception | Query needs too much memory (large aggregation, huge result) | Add filters or shorten the time range, raise breaker limits only for a real need, paginate, use pipeline aggs |
| Mapping explosion | Dynamic mapping creates a field per unique key, uncontrolled nesting | `"dynamic": false`, `flattened` for variable keys, limit nesting depth, set `index.mapping.total_fields.limit` |

## Preferred patterns

- **Size shards 20-50 GB**: consolidate small indices with rollover, use the shrink API. 1000+ shards of 1 GB each cost memory and file descriptors per shard and slow cluster state updates.
- **ILM policies**: hot-warm-cold phases, automatic rollover, deletion after retention. Without them indices grow forever and old data stays on hot nodes.
- **Explicit mappings in production**: `"dynamic": "strict"` rejects unknown fields; `"dynamic": false` ignores them. `"dynamic": true` causes mapping explosion and type conflicts.

## Rationalizations to reject

| Claim | Why it's wrong | Do this |
|---|---|---|
| "Small shards are easier to manage" | Overhead kills performance at scale | Consolidate to 20-50 GB shards |
| "Dev doesn't need replicas" | Dev should match prod | Always configure replicas |
| "Dynamic mapping is flexible" | Mapping explosion, type conflicts | Define explicit mappings |
| "We'll add ILM when storage hurts" | Reactive, causes production fires | ILM from the start |
| "Default heap settings are fine" | Wrong heap causes GC issues | Heap 50% RAM, max 31 GB |

## Hard gates

Before implementing, check for these. If found: stop, report, fix before continuing.

| Pattern | Why blocked | Fix |
|---|---|---|
| Heap above 31 GB | Loses compressed pointers | Heap 31 GB max |
| No replicas in production | Data loss on node failure | At least 1 replica |
| Unbounded dynamic mapping | Mapping explosion | Explicit mapping |
| Shards above 50 GB | Slow queries and recovery | Smaller shards with rollover |
| No snapshot configuration | No disaster recovery | Automated snapshots |

## Verification stops

- After designing or changing a mapping: have I checked it against the existing index and its documents? Mapping changes without that cause reindexing surprises.
- After recommending a performance change (rebalancing, query rewrite, analyzer change): do I give before/after numbers (latency, indexing rate, shard sizes), or say why measurement is impossible?
- After any cluster config change: have I checked apps querying the index, Logstash pipelines writing to it, and Kibana dashboards reading it?

## Before destructive or live changes

- Before deleting or closing an index, changing a live mapping, or shrink/split: confirm it is reversible or snapshots exist. Deleting an index without a snapshot loses data permanently; mapping changes on existing indices are largely irreversible.
- Before changing production cluster settings: check the setting name and value against the docs. An invalid setting can break shard allocation or destabilize nodes.

## Audit stance

When auditing a cluster, assume at least one misconfiguration. Check each before calling it healthy; no alarms is not proof of correct config:

- Shards outside 20-50 GB.
- Indices without ILM growing silently.
- Dynamic mapping on production indices piling up unmapped fields.
- Heap above 31 GB.
- No snapshot configuration.
- Replica count 0 on indices that look healthy until a node fails.

## Recommendation format

Each recommendation names the **component** (index, shard, node, or cluster setting), **current state** (or "new"), **proposed state**, and **risk level** (Low, Medium, High) with a short reason.

## Blockers

Resolve routine issues from repository evidence and existing authorization. When sure, decide, record the assumption, and continue; ask Jev when genuinely unsure.

| Situation | Why stop | Ask |
|---|---|---|
| Data volume unknown | Can't size the cluster | "Expected data volume and growth rate?" |
| Query patterns unclear | Can't design indices | "Full-text, aggregations, or filters?" |
| Retention unknown | Can't configure ILM | "Retain data 7d, 30d, or 90d?" |
| Node count unclear | Can't plan capacity | "How many nodes, with what CPU, RAM, disk?" |

Decide explicitly first: data volume, retention period, query patterns, high-availability needs (replica count).

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| Query DSL performance, filter vs query context, aggregations, profiling | [opensearch-elasticsearch/query-optimization.md](opensearch-elasticsearch/query-optimization.md) | Query tuning patterns |
| Mapping design, ILM policies, dynamic mapping, reindexing | [opensearch-elasticsearch/index-management.md](opensearch-elasticsearch/index-management.md) | Index lifecycle and mappings |
| Cluster health, shard allocation, JVM heap, rolling upgrades, snapshots | [opensearch-elasticsearch/cluster-operations.md](opensearch-elasticsearch/cluster-operations.md) | Cluster operations |
