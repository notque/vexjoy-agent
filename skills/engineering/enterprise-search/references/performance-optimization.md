# Performance Optimization Reference

Deep reference for query optimization, caching strategies, shard sizing, pagination, circuit breakers, and slow query diagnosis. Loaded by PERFORMANCE mode.

---

## Query Optimization Patterns

### Expensive Query Identification

| Query Pattern | Why Expensive | Mitigation |
|--------------|--------------|------------|
| Leading wildcard (`*search`) | Cannot use inverted index, scans all terms | Use `reverse` token filter + prefix query. Or use ngram sub-field. |
| Deep regex | Scans term dictionary | Restrict regex complexity. Use `keyword` field with `wildcard` type. |
| Large `terms` query (1000+ terms) | Each term is a lookup | Use `terms` lookup from an index. Or pre-filter with a `bool` filter. |
| Unbounded aggregations | Bucket explosion | Set `size` on `terms` agg. Use `composite` agg for paginated aggregation. |
| Nested queries | Per-document join cost | Denormalize where possible. Use `has_child`/`has_parent` only when nesting is truly needed. |
| Script scoring | Evaluated per document | Cache computed values as indexed fields. Use `rank_feature` for common patterns. |
| Deep pagination (from + size > 10000) | Coordinator collects from * size * shards | Use `search_after` or `point in time` + `search_after`. |
| Highlight on large fields | Re-analyzes text or reads term vectors | Use `term_vector: with_positions_offsets` at index time. |
| `match_all` with sort | Touches every shard, returns everything | Add a filter. Even broad filters improve performance. |

### Bool Query Optimization

The `filter` context skips scoring and uses bitset caching. Structure queries to maximize filter usage:

```json
// OpenSearch 2.x — optimized bool structure
{
  "query": {
    "bool": {
      "must": [
        { "match": { "body": "kubernetes deployment" } }
      ],
      "filter": [
        { "term": { "status": "published" } },
        { "range": { "date": { "gte": "2024-01-01" } } },
        { "terms": { "category": ["tutorial", "guide"] } }
      ],
      "should": [
        { "match_phrase": { "title": "kubernetes deployment" } }
      ],
      "minimum_should_match": 0
    }
  }
}
```

**Optimization rules**:
- Hard constraints (status, date range, access control) go in `filter` — cached, no scoring
- Text relevance goes in `must` — scored, drives ranking
- Soft boosts go in `should` — scored, additive, optional
- Put the most selective filter first — Lucene evaluates filters in order of selectivity when possible, but explicit ordering helps readability and debugging

### Profile API for Query Diagnosis

```json
// OpenSearch 2.x — profile a slow query
{
  "profile": true,
  "query": {
    "match": { "body": "kubernetes" }
  }
}
```

**Reading profile output**:

| Field | What It Tells You |
|-------|-------------------|
| `time_in_nanos` | Total time for this query component |
| `breakdown.build_scorer` | Time building scorer (high = complex scoring) |
| `breakdown.advance` | Time iterating posting list (high = low selectivity) |
| `breakdown.next_doc` | Time advancing to next matching doc |
| `breakdown.score` | Time computing score (high = expensive scoring) |
| `collector.reason` | Why results were collected (top_docs, aggregation, etc.) |

---

## Caching Strategies

### Cache Types (OpenSearch/Elasticsearch)

| Cache | What It Caches | Scope | Invalidation | When It Helps |
|-------|---------------|-------|-------------|---------------|
| **Node query cache** | Filter clause results (bitsets) | Node-level | Segment merge/change | Repeated filters (status, category, access control) |
| **Shard request cache** | Entire search response per shard | Shard-level | Index refresh | Repeated identical queries (aggregation dashboards) |
| **Field data cache** | Field values for aggregation/sorting | Node-level | Index change | Sorting/aggregating on text fields (use doc_values instead) |
| **OS page cache** | Index segments in memory | OS-level | LRU | All queries. Most important cache. |

### Cache Optimization

| Strategy | How | Impact |
|----------|-----|--------|
| Use `filter` context | Filters are cached in the query cache | Reduces scoring overhead for repeated constraints |
| Round timestamps | `"gte": "2024-01-01"` caches. `"gte": "now-1h"` generates unique cache keys. | Round to nearest hour/day for time-range filters |
| Use doc_values | Pre-computed columnar storage for sort/aggregation | Eliminates field data cache overhead |
| Preference routing | `_preference=custom_string` routes to same shard | Improves cache hit rate at cost of uneven load |
| Pre-warm queries | Search on index open/refresh with known query patterns | Warm caches after restart or reindex |

### Timestamp Rounding for Cache Hits

```json
// BAD — unique cache key every second
{ "range": { "date": { "gte": "now-24h" } } }

// BETTER — cache key changes hourly
{ "range": { "date": { "gte": "now-24h/h" } } }

// BEST for daily reports — cache key changes daily
{ "range": { "date": { "gte": "now-1d/d" } } }
```

The `/h` and `/d` suffixes round to the hour/day boundary, making the cache key stable for that period.

---

## Shard Sizing

### Sizing Guidelines

| Factor | Guideline | Reasoning |
|--------|-----------|-----------|
| Shard size | 10–50 GB per shard | <10 GB: overhead dominates. >50 GB: recovery/rebalance takes too long. |
| Shards per node | < 20 shards per GB of heap | Each shard consumes memory for metadata, segment files, caches |
| Max shards per index | Divide total data size by target shard size | |
| Minimum shards | 1 for <50 GB, scale linearly | Start with 1 shard for small indices |
| Write throughput | 1 shard handles ~10K docs/sec (depends on doc size) | Scale write shards to match ingest rate |

### Shard Count Formula

```
number_of_shards = ceil(expected_data_GB / target_shard_size_GB)

Example: 200 GB of data, 30 GB target shard size
→ ceil(200 / 30) = 7 shards
```

### Over-Sharding Symptoms

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| Cluster state > 500 MB | Too many indices/shards | Merge small indices, use rollover with larger periods |
| Search latency high despite low data volume | Scatter-gather overhead across too many shards | Reduce shard count, shrink API |
| Master node instability | Cluster state updates overwhelm master | Reduce total shard count cluster-wide |
| Memory pressure on data nodes | Too many open segments | Reduce shards, force_merge old indices |

### Shard Allocation Awareness

```json
// OpenSearch 2.x — zone-aware allocation
{
  "cluster.routing.allocation.awareness.attributes": "zone",
  "cluster.routing.allocation.awareness.force.zone.values": "zone-a,zone-b,zone-c"
}
```

Ensures replicas are placed in different availability zones for fault tolerance.

---

## Pagination

### Pagination Methods

| Method | Max Depth | Consistency | Use Case |
|--------|-----------|-------------|----------|
| `from` + `size` | 10,000 (default limit) | Snapshot | UI pagination, small result sets |
| `search_after` | Unlimited | Snapshot (with PIT) | Deep pagination, infinite scroll |
| `scroll` | Unlimited | Frozen snapshot | Batch processing, export (deprecated for search) |
| `point_in_time` + `search_after` | Unlimited | Frozen snapshot | Deep pagination with consistency |

### search_after Pattern

```json
// OpenSearch 2.x — page 1
POST /products/_search
{
  "size": 20,
  "query": { "match": { "title": "shoes" } },
  "sort": [
    { "_score": "desc" },
    { "_id": "asc" }
  ]
}

// Page 2: use sort values from last result of page 1
POST /products/_search
{
  "size": 20,
  "query": { "match": { "title": "shoes" } },
  "sort": [
    { "_score": "desc" },
    { "_id": "asc" }
  ],
  "search_after": [0.87, "product_4521"]
}
```

**Tiebreaker**: Always include a unique field (`_id` or `_shard_doc`) as the last sort criterion. Without a tiebreaker, documents with equal scores may be skipped or duplicated across pages.

### Point in Time for Consistent Pagination

```json
// Step 1: Create PIT
POST /products/_search/point_in_time?keep_alive=5m

// Step 2: Search with PIT
POST /_search
{
  "pit": { "id": "PIT_ID", "keep_alive": "5m" },
  "size": 20,
  "query": { "match": { "title": "shoes" } },
  "sort": [{ "_score": "desc" }, { "_shard_doc": "asc" }]
}
```

---

## Circuit Breakers

### Default Circuit Breakers

| Breaker | Default Limit | What It Protects |
|---------|--------------|------------------|
| `indices.breaker.total.limit` | 95% of heap | Total memory across all breakers |
| `indices.breaker.request.limit` | 60% of heap | Per-request data structures (aggregations, sorting) |
| `indices.breaker.fielddata.limit` | 40% of heap | Field data cache |
| `network.breaker.inflight_requests.limit` | 100% of heap | In-flight network requests |

### Tripped Breaker Diagnosis

| Breaker | Common Cause | Remediation |
|---------|-------------|-------------|
| Request breaker | Large aggregation (high cardinality terms agg) | Reduce agg size, use composite agg, increase heap |
| Field data breaker | Sorting/aggregating on analyzed text field | Use `keyword` sub-field or `doc_values` |
| Parent breaker | Combined memory pressure | Reduce concurrent queries, increase heap, add nodes |

---

## Slow Query Diagnosis

### Enable Slow Query Logging

```json
// OpenSearch 2.x — dynamic setting
PUT /products/_settings
{
  "index.search.slowlog.threshold.query.warn": "5s",
  "index.search.slowlog.threshold.query.info": "2s",
  "index.search.slowlog.threshold.query.debug": "1s",
  "index.search.slowlog.threshold.fetch.warn": "1s",
  "index.search.slowlog.threshold.fetch.info": "500ms"
}
```

### Slow Query Investigation Checklist

| Check | How | What to Look For |
|-------|-----|-----------------|
| Query complexity | Profile API | Deep nesting, expensive clauses, script scoring |
| Shard count | `GET /_cat/shards/products` | Over-sharded index |
| Segment count | `GET /_cat/segments/products` | Too many segments (needs force_merge) |
| Field data usage | `GET /_nodes/stats/indices/fielddata` | High field data = sorting on wrong field type |
| Cache hit rate | `GET /_nodes/stats/indices/query_cache` | Low hit rate = filters not cacheable |
| GC pauses | Node stats, GC logs | Long GC pauses cause query spikes |
| Hot threads | `GET /_nodes/hot_threads` | Shows what threads are doing during slow periods |
| Disk I/O | OS monitoring | Page cache thrashing = not enough memory for data |

### Common Slow Query Patterns and Fixes

| Pattern | Typical Latency | Fix |
|---------|----------------|-----|
| Leading wildcard on large field | 5-30s | Reverse token filter, ngram sub-field |
| `terms` with 10K+ values | 2-10s | Terms lookup, pre-filter, redesign data model |
| Deep pagination (from: 50000) | 5-60s | Switch to search_after |
| High-cardinality terms agg | 2-20s | Set explicit size, use composite agg, pre-aggregate |
| Regex on text field | 5-60s | Keyword sub-field with wildcard type |
| Script score touching all docs | 2-30s | Pre-compute and index as field, use rank_feature |
| match_all on large index | 1-10s | Add at least one filter to narrow candidates |
| Nested query on deeply nested docs | 2-15s | Denormalize, flatten structure |

---

## Bulk Indexing Optimization

| Setting | Default | During Bulk Ingest | Restore After |
|---------|---------|-------------------|---------------|
| `refresh_interval` | `1s` | `-1` (disable) | `1s` or `5s` |
| `number_of_replicas` | 1-2 | `0` | Original value |
| `translog.durability` | `request` | `async` | `request` |
| `translog.flush_threshold_size` | `512mb` | `1gb` | `512mb` |
| Bulk batch size | — | 5-15 MB per batch | — |

### Bulk Request Sizing

| Document Size | Recommended Batch | Docs per Batch |
|--------------|-------------------|----------------|
| < 1 KB | 5-10 MB | 5,000-10,000 |
| 1-10 KB | 5-15 MB | 1,000-5,000 |
| 10-100 KB | 5-15 MB | 100-500 |
| > 100 KB | 5-15 MB | 50-100 |

Target 5-15 MB per bulk request. Larger batches increase memory pressure. Smaller batches increase HTTP overhead.

---

## Refresh Interval Tuning

| Use Case | Refresh Interval | Tradeoff |
|----------|-----------------|----------|
| Real-time search | `1s` (default) | Higher indexing overhead, freshest results |
| Near-real-time | `5s`–`30s` | Good balance for most use cases |
| Batch / analytics | `60s`–`120s` | Higher throughput, stale results acceptable |
| Bulk ingest | `-1` (disable) | Maximum throughput, no search until manual refresh |

**Per-index setting**: Set refresh interval per index based on its use case. Search indices need faster refresh than analytics indices.

---

## Common Pitfalls and Positive Alternatives

| Pitfall | What to Do Instead |
|---------|-------------------|
| Adding nodes to fix slow queries | Profile the query first. Most slow queries are caused by query pattern, not cluster size. |
| Using `from: 10000, size: 20` for deep pagination | Use `search_after` with a PIT. Deep `from` requires coordinator to fetch and discard `from * shards` results. |
| Setting `number_of_shards` to match node count | Size shards by data volume (10-50 GB each). Node count is for replicas and capacity. |
| Sorting on `text` fields | Sort on `keyword` sub-field or `doc_values`-enabled field. Text field sorting loads field data into heap. |
| Disabling caching to "ensure fresh results" | Use appropriate refresh intervals instead. Caching is critical for performance. |
| Tuning JVM heap without data | Profile actual memory usage patterns. Start at 50% of available RAM (max 30-31 GB for compressed oops). |
