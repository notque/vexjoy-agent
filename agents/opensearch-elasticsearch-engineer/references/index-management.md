---
name: OpenSearch/Elasticsearch Index Management
description: Mapping design, ILM policies, index templates, and reindexing strategies with anti-pattern detection
---

# OpenSearch/Elasticsearch Index Management

> **Scope**: Index mapping, analyzer configuration, ILM policies, index templates, and reindexing. Covers OpenSearch 2.x and Elasticsearch 8.x. Does not cover cluster-level shard allocation (see cluster-operations.md).
> **Version range**: OpenSearch 2.0+ / Elasticsearch 8.0+
> **Generated**: 2026-04-08

---

## Overview

Index management failures are slow-moving disasters: dynamic mapping enables today, then causes mapping explosion in 3 months. ILM not configured today means manual deletion during a storage emergency. Mapping design is largely irreversible on live indices — reindexing 100GB of data takes hours. Get it right at creation time.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `"dynamic": "strict"` | All versions | Production indices with known schema | Exploratory/dev indices |
| `"dynamic": false` | All versions | Log indices with variable fields | Need to query dynamic fields |
| `keyword` sub-field on `text` | All versions | Need both full-text and aggregation | Field is never aggregated |
| `flattened` field type | ES 7.3+/OS 1.0+ | JSON objects with unknown keys | Need to score individual sub-fields |
| Index aliases | All versions | Zero-downtime reindexing | Direct index name in application code |
| Rollover API | All versions | Time-series data, log ingestion | Static content indices |

---

## Correct Patterns

### Explicit Mapping with Strict Dynamic

Define all fields at creation time; reject unknown fields.

```json
PUT /articles
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "index.mapping.total_fields.limit": 200
  },
  "mappings": {
    "dynamic": "strict",
    "_source": { "enabled": true },
    "properties": {
      "title": {
        "type": "text",
        "fields": {
          "keyword": { "type": "keyword", "ignore_above": 256 }
        },
        "analyzer": "english"
      },
      "content": { "type": "text", "analyzer": "english" },
      "author_id": { "type": "keyword" },
      "published_at": { "type": "date", "format": "strict_date_time" },
      "tags": { "type": "keyword" },
      "view_count": { "type": "long" },
      "metadata": {
        "type": "object",
        "dynamic": false
      }
    }
  }
}
```

**Why**: `"dynamic": "strict"` rejects documents with unknown fields (returns a 400 error). This prevents the gradual accumulation of unknown field mappings that causes `index.mapping.total_fields.limit` to be reached silently.

---

### ILM Policy for Log Indices

```json
PUT _ilm/policy/logs-policy
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_size": "30gb",
            "max_age": "1d",
            "max_docs": 10000000
          },
          "set_priority": { "priority": 100 }
        }
      },
      "warm": {
        "min_age": "3d",
        "actions": {
          "forcemerge": { "max_num_segments": 1 },
          "shrink": { "number_of_shards": 1 },
          "set_priority": { "priority": 50 }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "set_priority": { "priority": 0 },
          "freeze": {}
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}
```

**Why**: Hot phase: active writes, high-priority. Warm phase: force-merge reduces segment count (read optimization), shrink consolidates shards from hot to 1 (saves file descriptors). Cold phase: frozen indices move to object storage. Delete: automatic cleanup.

---

### Zero-Downtime Reindex with Alias

```bash
# 1. Create new index with updated mapping
PUT /articles-v2
{ ... new mapping ... }

# 2. Reindex from old to new (background)
POST _reindex?wait_for_completion=false
{
  "source": { "index": "articles-v1" },
  "dest": { "index": "articles-v2" }
}

# 3. Monitor progress
GET _tasks?actions=*reindex

# 4. Once complete, atomically swap alias
POST _aliases
{
  "actions": [
    { "remove": { "index": "articles-v1", "alias": "articles" } },
    { "add": { "index": "articles-v2", "alias": "articles" } }
  ]
}

# 5. Verify alias points to new index
GET articles/_alias
```

**Why**: Application code always queries `articles` alias — never the versioned index name. Alias swap is atomic: no gap between removing old and adding new. Clients see no downtime.

---

### Index Template for Consistent Mapping

```json
PUT _index_template/logs-template
{
  "index_patterns": ["logs-*"],
  "priority": 100,
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 1,
      "index.lifecycle.name": "logs-policy",
      "index.lifecycle.rollover_alias": "logs"
    },
    "mappings": {
      "dynamic": false,
      "properties": {
        "@timestamp": { "type": "date" },
        "level": { "type": "keyword" },
        "service": { "type": "keyword" },
        "message": { "type": "text" },
        "trace_id": { "type": "keyword" }
      }
    }
  },
  "data_stream": {}
}
```

**Why**: Template applies automatically to new indices matching the pattern. Without a template, each rollover creates an index with default settings — no ILM policy, no explicit mapping.

---

## Anti-Pattern Catalog

### ❌ Mapping Explosion from Dynamic Mapping

**Detection**:
```bash
# Check current field count on an index
curl -s "$ES_HOST/your-index/_mapping" | python3 -c "
import json, sys
mapping = json.load(sys.stdin)
idx = list(mapping.keys())[0]
props = mapping[idx]['mappings'].get('properties', {})
print(f'Top-level field count: {len(props)}')
"

# Check all indices for field counts
GET /_cat/indices?v&h=index,docs.count
GET /your-index/_mapping | jq '.[] | .mappings.properties | keys | length'
```

**What it looks like**:
```json
{
  "mappings": {
    "dynamic": true,
    "properties": {
      "event_data": {
        "properties": {
          "user_pref_color": { "type": "text" },
          "user_pref_font_size": { "type": "long" },
          "experiment_ab_1234_variant": { "type": "text" },
          "experiment_ab_5678_variant": { "type": "text" }
        }
      }
    }
  }
}
```

**Why wrong**: Each unique key in a JSON blob creates a new field mapping. Experiment names, user preference keys, and event properties grow unbounded. At `index.mapping.total_fields.limit` (default 1000), indexing fails with `limit of total fields [1000] has been exceeded`. Existing data is already corrupted by this point — reindexing required.

**Fix**: Use `"dynamic": false` on nested objects with variable keys, or use the `flattened` field type:
```json
{
  "properties": {
    "event_data": { "type": "flattened" },
    "user_prefs": { "type": "flattened" }
  }
}
```

**Version note**: `flattened` type available since ES 7.3 / OS 1.0.

---

### ❌ Mapping `text` Fields for Exact-Match Queries

**Detection**:
```bash
# Find term queries on text fields (likely mistake)
grep -rn '"term"' --include="*.json" queries/ -A3 | grep -v '\.keyword'
# Check mapping for fields used in term queries
GET /your-index/_mapping
```

**What it looks like**:
```json
{
  "mappings": {
    "properties": {
      "status": { "type": "text" }
    }
  }
}

// Query that silently fails:
{
  "query": { "term": { "status": "active" } }
}
```

**Why wrong**: `text` fields are analyzed — `"active"` is tokenized and lowercased. A `term` query for `"active"` works, but `"Active"` misses. `"IS_ACTIVE"` gets tokenized to `["is", "active"]` — `term` query on `"IS_ACTIVE"` returns nothing. Aggregations on `text` fields throw `Fielddata is disabled on text fields`.

**Fix**: Use `keyword` for exact-match fields (status, IDs, category); use `text` with `.keyword` sub-field when both full-text search and aggregation are needed.

---

### ❌ Ignoring Mapping Before Reindexing

**Detection**:
```bash
# Compare source and destination mappings before reindex
GET /source-index/_mapping
GET /dest-index/_mapping
# Check for type conflicts
```

**What it looks like**:
```bash
# Blindly reindex without checking mapping compatibility
POST _reindex
{
  "source": { "index": "articles-v1" },
  "dest": { "index": "articles-v2" }
}
# Then discover v2 has "date" field mapped as "text" in v1
```

**Why wrong**: If `published_at` is `text` in v1 and `date` in v2, reindex fails on any document where `published_at` doesn't parse as a date. `_reindex` continues by default, silently skipping failed documents. The result is an incomplete index with no clear indication of what was dropped.

**Fix**: Use `"conflicts": "proceed"` only intentionally, and check task results for failures:
```bash
GET _tasks/{taskId}
# Check: "failures" array in response — should be empty
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `limit of total fields [1000] has been exceeded` | Dynamic mapping explosion | Set `"dynamic": false` on variable-key objects; use `flattened` type |
| `Fielddata is disabled on text fields` | Aggregating on `text` field | Add `.keyword` sub-field; update mapping and reindex |
| `mapper_parsing_exception: failed to parse field [date]` | Date format mismatch | Specify `"format"` in date mapping matching your data format |
| `illegal_argument_exception: can't merge a non-object...` | Mapping conflict between versions | Check field types in both indices before reindex |
| `index_not_found_exception` | Alias points to deleted index | Verify alias: `GET alias/_alias`; update to current index |
| `index_closed_exception` | Querying frozen/closed index | Open index: `POST index/_open` or query cold tier differently |
| Reindex missing documents | `"conflicts": "proceed"` skipped failures silently | Check task response for failure count; investigate failed docs |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| ES 7.0 | `_type` removed; single mapping per index | Remove type field from all mapping definitions |
| ES 7.3 / OS 1.0 | `flattened` field type added | Use for variable-key JSON objects instead of dynamic mapping |
| ES 7.9 / OS 1.0 | Data streams added (wraps ILM + rollover) | Prefer data streams for time-series over manual ILM setup |
| ES 8.0 | `freeze` API removed from data tier model | Use searchable snapshots for cold tier instead |
| OS 2.0 | `_tier_preference` routing added | Explicit hot/warm/cold tier routing without custom attributes |

---

## Detection Commands Reference

```bash
# Field count per index
GET /_cat/indices?v
curl "$ES_HOST/index/_mapping" | python3 -c "import json,sys; m=json.load(sys.stdin); print(len(list(m.values())[0]['mappings'].get('properties',{})))"

# Dynamic mapping enabled on production indices
GET /_cat/indices?v | awk '{print $3}' | while read idx; do
  curl -s "$ES_HOST/$idx/_mapping" | python3 -c "import json,sys; m=json.load(sys.stdin); d=[v['mappings'].get('dynamic') for v in m.values()]; print('$idx:', d)"
done

# text fields used in term queries
grep -rn '"term"' queries/ --include="*.json" -A3 | grep -v keyword

# Indices without ILM policy
GET /_all/_settings?filter_path=*.settings.index.lifecycle.name
```

---

## See Also

- `query-optimization.md` — Query DSL performance and profiling
- `cluster-operations.md` — Shard sizing, node roles, capacity planning
