# Search-performance diagnosis

Capture slow logs/profile output, query shape, shard fan-out, segment/index size, cache hit behavior, and p50/p95/p99 before changing configuration.

- Too many tiny shards increases coordination/heap cost; oversized shards slow recovery. Size from measured workload and recovery objectives.
- Request cache helps repeated identical aggregation/search requests on unchanged segments; query cache helps reusable filters. Neither rescues high-cardinality or unique queries.
- Put exact constraints in filter context so they avoid scoring and may cache.
- Deep `from/size` pagination is costly; use point-in-time plus `search_after` for stable deep traversal.
- Leading wildcards, scripts, large aggregation cardinality, huge `size`, and broad shard fan-out are common query-level causes.
- Circuit-breaker errors are capacity protection, not a request to raise limits blindly. Reduce query memory or fan-out first.
- Refresh and replica changes trade freshness/durability for throughput; state the tradeoff and test recovery.
