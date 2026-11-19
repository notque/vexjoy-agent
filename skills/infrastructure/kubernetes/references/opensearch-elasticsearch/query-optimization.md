---
description: Query DSL patterns, aggregation optimization, caching strategies, and search profiling for performance tuning
---

# OpenSearch/Elasticsearch Query Optimization

> **Scope**: Query DSL performance patterns, filter vs query context, aggregation tuning, and profile API usage. Covers OpenSearch 2.x and Elasticsearch 8.x (compatible APIs).
> **Version range**: OpenSearch 2.0+ / Elasticsearch 8.0+
> **Generated**: 2026-04-08

---

## Overview

Query performance in OpenSearch/Elasticsearch fails in three predictable ways: using query context where filter context is appropriate (query context scores and doesn't cache), returning all fields when only a subset is needed (network and memory overhead), and running large aggregations without sampling (cardinality explosions block query threads). The profile API pinpoints which part of a query is slow; without it, optimization is guesswork.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| Filter context (`filter: []`) | All versions | Exact matches, ranges, term filters | Full-text relevance scoring needed |
| `_source: ['field1', 'field2']` | All versions | Partial document retrieval | Mapping has stored fields separately |
| `request_cache: true` | All versions | Aggregation queries, date-histogram | Frequently-changing data |
| Profile API (`"profile": true`) | All versions | Diagnosing slow queries | Production traffic (25% overhead) |
| `track_total_hits: false` | ES 7.0+/OS 1.0+ | Pagination beyond 10k hits | When exact count is required |
| Async search | ES 7.7+/OS 1.0+ | Aggregations > 10 seconds | Real-time user-facing queries |

---

## Correct Patterns

### Filter vs Query Context

Use `filter` for non-scoring conditions — filter results are cached and reused across requests.

```json
{
  "query": {
    "bool": {
      "must": [
        {
          "match": {
            "title": "kubernetes deployment"
          }
        }
      ],
      "filter": [
        { "term": { "status": "published" } },
        { "range": { "published_at": { "gte": "2024-01-01" } } },
        { "terms": { "tags": ["kubernetes", "devops"] } }
      ]
    }
  }
}
```

**Why**: `filter` context is cached in the filter cache. `must` (query context) recalculates relevance scores on every request. Status checks, date ranges, and term filters have no relevance to scoring — they belong in `filter`.

---

### Source Filtering for Large Documents

```json
{
  "query": { "match": { "content": "deployment strategy" } },
  "_source": {
    "includes": ["title", "summary", "author", "published_at"],
    "excludes": ["content", "raw_html", "embedding_vector"]
  },
  "size": 20
}
```

**Why**: `content` fields of 50KB+ per document mean a 20-hit response could return 1MB+ over the wire. Excluding large fields reduces network transfer by 90%+ for content-heavy indices.

---

### Aggregation Cardinality Limits

```json
{
  "aggs": {
    "by_category": {
      "terms": {
        "field": "category.keyword",
        "size": 20,
        "shard_size": 100,
        "min_doc_count": 5
      }
    },
    "user_count": {
      "cardinality": {
        "field": "user_id",
        "precision_threshold": 1000
      }
    }
  }
}
```

**Why**: `size: 0` or missing `size` defaults to 10. Missing `shard_size` means each shard returns `size` results — set `shard_size` to 5x `size` for accuracy. `cardinality` with high `precision_threshold` uses more memory — tune to accuracy needs.

---

### Profile API for Diagnosis

```json
{
  "profile": true,
  "query": {
    "bool": {
      "should": [
        { "match": { "title": "kubernetes" } },
        { "match": { "content": "kubernetes" } }
      ]
    }
  }
}
```

Interpret the response:
```json
{
  "profile": {
    "shards": [{
      "searches": [{
        "query": [{
          "type": "BooleanQuery",
          "time_in_nanos": 450000,
          "breakdown": {
            "score": 120000,
            "build_scorer": 330000
          }
        }]
      }]
    }]
  }
}
```

**Why**: `build_scorer` dominates? The query is computing relevance scores for many documents — add filters to reduce candidate set. `score` dominates? Complex scoring function — consider a simpler similarity model.

---

## Pattern Catalog

### Use Prefix or N-gram Search Instead of Leading Wildcards
**Detection**:
```bash
# Find wildcard queries with leading wildcard
grep -rn '"wildcard"' --include="*.json" queries/
# Also check application code
rg '"wildcard"' --type json queries/
grep -rn 'wildcard.*\*.*value\|value.*\*.*wild' --include="*.py" --include="*.ts" --include="*.go" src/
```

**Signal**:
```json
{
  "query": {
    "wildcard": {
      "username": {
        "value": "*smith*"
      }
    }
  }
}
```

**Why this matters**: Leading wildcards (`*smith`) force a full index scan — every term in the inverted index must be checked. On a 10M document index with 500K unique usernames, this scans 500K terms per shard. Query latency jumps from ~5ms to 5+ seconds. Trailing wildcards (`smith*`) can use the index efficiently.

**Preferred action**: Use `match_phrase_prefix` for prefix searches or `n-gram` tokenization for infix searches. For substring search, configure `edge_ngram` analyzer at index time.

```json
{
  "query": {
    "match_phrase_prefix": {
      "username": "smith"
    }
  }
}
```

---

### Use search_after for Deep Pagination
**Detection**:
```bash
grep -rn '"from"' --include="*.json" queries/ | grep -v '"from": [0-9]$\|"from": [1-9][0-9]$'
# Find large from values
rg '"from":\s*[0-9]{4,}' --type json
```

**Signal**:
```json
{
  "from": 10000,
  "size": 20,
  "query": { "match_all": {} }
}
```

**Why this matters**: `from: 10000` fetches 10,020 documents per shard, discards 10,000, returns 20. On a 5-shard index: 50,100 documents fetched, 50,080 discarded. Memory and CPU scale linearly with `from` value. Default limit is `index.max_result_window: 10000` — exceeding it throws an exception.

**Preferred action**: Use search_after for deep pagination:
```json
{
  "size": 20,
  "sort": [{ "published_at": "desc" }, { "_id": "asc" }],
  "search_after": ["2024-03-15T10:00:00", "doc_id_from_last_result"]
}
```

**Version note**: `search_after` requires a consistent sort with a tiebreaker (e.g., `_id`). Added in ES 5.0/OS all versions.

---

### Set Explicit Size on Terms Aggregations
**Detection**:
```bash
# Find terms aggregations without explicit size
grep -rn '"terms"' --include="*.json" queries/ -A5 | grep -v '"size"'
rg '"terms"' --type json queries/ -A5 | grep -B3 '"field"' | grep -v size
```

**Signal**:
```json
{
  "aggs": {
    "all_users": {
      "terms": {
        "field": "user_id.keyword"
        // No size — defaults to 10, but 100K users exist
      }
    }
  }
}
```

**Why this matters**: Default `size: 10` returns only the top 10 buckets, which is often wrong but doesn't cause performance issues. The real danger is `size: 0` (some clients send this meaning "all") — OpenSearch interprets 0 as default (10). Some versions also accept very large sizes that materialize all buckets in memory, causing heap pressure on the coordinating node.

**Preferred action**: Always set explicit `size`. For cardinality estimates, use `cardinality` aggregation instead of `terms`.

---

### Precompute Scores at Index Time
**Detection**:
```bash
grep -rn '"script"' --include="*.json" queries/
# Painless scripts in frequently-used queries
grep -rn 'script_score\|script_fields\|scripted_metric' --include="*.json" queries/
```

**Signal**:
```json
{
  "query": {
    "script_score": {
      "query": { "match_all": {} },
      "script": {
        "source": "Math.log(1 + doc['view_count'].value) * params.boost",
        "params": { "boost": 1.5 }
      }
    }
  }
}
```

**Why this matters**: Painless scripts run JVM-compiled code per document. On a 1M document index with `match_all`, this executes 1M script invocations per query, per shard. Compiled script cache is limited — frequent cache misses add compilation overhead.

**Preferred action**: Precompute scores at index time using `rank_features` field type or store the computed value as a regular numeric field.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Result window is too large, from + size must be <= 10000` | Deep pagination exceeds `max_result_window` | Use `search_after` for pagination beyond 10k |
| `Circuit breaking exception: [parent] Data too large` | Aggregation exceeds circuit breaker | Reduce aggregation `size`, add filters to reduce candidate set |
| `all shards failed ... No living connections` | Coordinating node can't reach data nodes | Check cluster health; `GET /_cluster/health` |
| `search_phase_execution_exception` | Query parsing error or field type mismatch | Check field mapping; don't `term` query on `text` fields |
| `Fielddata is disabled on text fields` | Aggregating on `text` field without `keyword` sub-field | Add `.keyword` sub-field to mapping |
| `type_missing_exception` | Querying field that doesn't exist in mapping | Check `GET /index/_mapping` |
| Slow query despite filter context | Filter cache cold (first request after restart) | Warm-up queries or pre-populate filter cache |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| ES 7.0 / OS 1.0 | `track_total_hits: false` option added | Speeds up count queries; use when exact total not needed |
| ES 7.7 / OS 1.0 | Async search API added | Long-running aggregations can run in background |
| ES 8.0 | `_type` removed from queries | Remove type from all query DSL |
| OS 2.4 | Concurrent segment search (experimental) | Parallelizes search across segments within a shard |
| OS 2.9 | `star_tree` index for pre-aggregated metrics | Eliminates aggregation cost for known metric queries |

---

## Detection Commands Reference

```bash
# Leading wildcard queries
grep -rn '"wildcard"' --include="*.json" queries/ -A5 | grep '"value".*\*'

# Deep pagination
rg '"from":\s*[0-9]{3,}' --type json queries/

# Missing aggregation size
grep -rn '"terms"' --include="*.json" queries/ -A5 | grep -L '"size"'

# Script queries in production code
grep -rn '"script"' --include="*.json" queries/

# text field aggregation (should use .keyword)
grep -rn '"terms".*"field"' --include="*.json" queries/ | grep -v '\.keyword'
```

---

## See Also

- `index-management.md` — Mapping design and analyzer configuration
- `cluster-operations.md` — Shard allocation, capacity planning, ILM
