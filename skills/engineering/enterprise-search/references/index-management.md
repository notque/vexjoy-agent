# Index Management Reference

Deep reference for schema design, analyzer chains, mapping optimization, reindex strategies, alias management, and ILM policies. Loaded by INDEX mode.

---

## Schema Design by Use Case

### Field Type Selection

| Data | Field Type | Searchable | Aggregatable | Sortable | Notes |
|------|-----------|------------|-------------|----------|-------|
| Full-text content | `text` | Yes | No (use `.keyword` sub-field) | No | Analyzed, tokenized |
| Identifiers, enums | `keyword` | Exact only | Yes | Yes | Not analyzed, max 256 chars default |
| Both search + aggregate | `text` + `keyword` sub-field | Yes (text), exact (keyword) | Yes (keyword) | Yes (keyword) | Most common pattern for string fields |
| Numbers | `integer`, `long`, `float`, `double` | Range queries | Yes | Yes | Choose smallest type that fits |
| Dates | `date` | Range queries | Yes | Yes | Specify format explicitly |
| Booleans | `boolean` | Filter | Yes | Yes | |
| Geo coordinates | `geo_point` | Geo queries | Geo agg | Geo sort | lat/lon pair |
| Nested objects | `nested` | Independent scoring | Nested agg | No | Cross-field correlation preserved |
| Flattened objects | `flattened` | Exact only | Limited | No | Dynamic keys, low overhead |
| Dense vectors | `knn_vector` (OpenSearch) / `dense_vector` (ES) | kNN search | No | No | Embedding storage |
| Rank features | `rank_feature` | rank_feature query | No | No | Numeric signals for scoring only |

### Schema Patterns by Domain

#### E-Commerce Product Search

```json
// OpenSearch 2.x
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "product_analyzer",
        "fields": { "keyword": { "type": "keyword" } }
      },
      "description": { "type": "text", "analyzer": "product_analyzer" },
      "brand": {
        "type": "text",
        "fields": { "keyword": { "type": "keyword" } }
      },
      "categories": { "type": "keyword" },
      "price": { "type": "scaled_float", "scaling_factor": 100 },
      "in_stock": { "type": "boolean" },
      "rating": { "type": "half_float" },
      "review_count": { "type": "integer" },
      "sku": { "type": "keyword" },
      "attributes": {
        "type": "nested",
        "properties": {
          "name": { "type": "keyword" },
          "value": { "type": "keyword" }
        }
      },
      "created_at": { "type": "date", "format": "strict_date_optional_time" },
      "popularity_score": { "type": "rank_feature" }
    }
  }
}
```

**Key decisions**:
- `nested` for attributes: preserves color:red + size:10 correlation (prevents "red size-5" matching "red" + "size 10")
- `rank_feature` for popularity: optimized for scoring, not storage
- `scaled_float` for price: efficient storage, avoids floating-point issues

#### Document/Knowledge Base Search

```json
// OpenSearch 2.x
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "document_analyzer",
        "fields": { "keyword": { "type": "keyword" }, "suggest": { "type": "completion" } }
      },
      "body": { "type": "text", "analyzer": "document_analyzer", "term_vector": "with_positions_offsets" },
      "author": { "type": "keyword" },
      "tags": { "type": "keyword" },
      "path": { "type": "keyword" },
      "last_modified": { "type": "date" },
      "content_type": { "type": "keyword" },
      "access_groups": { "type": "keyword" },
      "embedding": { "type": "knn_vector", "dimension": 768, "method": { "name": "hnsw", "space_type": "cosinesimil", "engine": "nmslib" } }
    }
  }
}
```

**Key decisions**:
- `term_vector` on body: enables highlighting without re-analysis at query time
- `completion` sub-field on title: powers type-ahead suggest
- `knn_vector` for embedding: hybrid search (BM25 + semantic)
- `access_groups` for document-level security filtering

#### Log/Event Search

```json
// OpenSearch 2.x
{
  "mappings": {
    "properties": {
      "@timestamp": { "type": "date" },
      "message": { "type": "text" },
      "level": { "type": "keyword" },
      "service": { "type": "keyword" },
      "host": { "type": "keyword" },
      "trace_id": { "type": "keyword" },
      "span_id": { "type": "keyword" },
      "status_code": { "type": "short" },
      "duration_ms": { "type": "integer" },
      "labels": { "type": "flattened" }
    }
  }
}
```

**Key decisions**:
- `flattened` for labels: handles dynamic key-value pairs without mapping explosion
- `short` for status_code: smallest type that fits
- No sub-fields on message: logs rarely need both text search and exact match

---

## Analyzer Chain Design

An analyzer = char_filters -> tokenizer -> token_filters. Each component transforms text in sequence.

### Component Reference

| Stage | Component | What It Does | When to Use |
|-------|-----------|-------------|-------------|
| **Char Filter** | `html_strip` | Removes HTML tags | Content from web crawlers |
| | `mapping` | Character replacement (`& -> and`) | Normalize special characters |
| | `pattern_replace` | Regex-based replacement | Clean up structured noise (IDs, hashes) |
| **Tokenizer** | `standard` | Unicode-aware word tokenizer | General text (default) |
| | `whitespace` | Split on whitespace only | Preserve special tokens (error codes, identifiers) |
| | `keyword` | No splitting — entire input is one token | When field should not be tokenized |
| | `pattern` | Regex-based splitting | Custom delimiters |
| | `path_hierarchy` | `/a/b/c` -> `/a`, `/a/b`, `/a/b/c` | File paths, URLs, categories |
| **Token Filter** | `lowercase` | Lowercases all tokens | Almost always |
| | `stemmer` | Reduces to word stem | Recall improvement (searching -> search) |
| | `stop` | Removes stop words | Usually skip — modern BM25 handles them well |
| | `synonym_graph` | Expands or maps synonyms | Domain vocabulary |
| | `edge_ngram` | Prefix tokens (`search` -> `s`, `se`, `sea`...) | Autocomplete / type-ahead |
| | `shingle` | Creates token n-grams (`search engine` -> `search engine`) | Phrase-like matching without match_phrase |
| | `word_delimiter_graph` | Splits on case change, delimiters | camelCase, under_score, hyphen-ated |
| | `asciifolding` | Folds unicode to ASCII (`café` -> `cafe`) | Multi-language, accent-insensitive search |
| | `truncate` | Truncate tokens to max length | Prevent oversized tokens |

### Analyzer Recipes

#### Product Search Analyzer

```json
{
  "analysis": {
    "char_filter": {
      "normalize_special": {
        "type": "mapping",
        "mappings": ["& => and", "+ => plus", "# => sharp"]
      }
    },
    "filter": {
      "product_synonyms": {
        "type": "synonym_graph",
        "synonyms_path": "analysis/product_synonyms.txt"
      },
      "product_stemmer": {
        "type": "stemmer",
        "language": "light_english"
      }
    },
    "analyzer": {
      "product_analyzer": {
        "type": "custom",
        "char_filter": ["normalize_special"],
        "tokenizer": "standard",
        "filter": ["lowercase", "asciifolding", "product_synonyms", "product_stemmer"]
      }
    }
  }
}
```

**Light stemming**: Use `light_english` instead of `english` for product search. Aggressive stemming conflates terms that should remain distinct in commerce ("running" vs "run" mean different things for shoes).

#### Autocomplete Analyzer (Index + Search Pair)

```json
{
  "analysis": {
    "analyzer": {
      "autocomplete_index": {
        "type": "custom",
        "tokenizer": "standard",
        "filter": ["lowercase", "autocomplete_edge"]
      },
      "autocomplete_search": {
        "type": "custom",
        "tokenizer": "standard",
        "filter": ["lowercase"]
      }
    },
    "filter": {
      "autocomplete_edge": {
        "type": "edge_ngram",
        "min_gram": 2,
        "max_gram": 15
      }
    }
  }
}
```

**Index/search analyzer split**: Index-time analyzer generates edge ngrams (`kub`, `kube`, `kuber`...). Search-time analyzer uses standard tokenization (the full query term). This way `kube` matches documents with `kubernetes` without generating edge ngrams of the query itself.

---

## Mapping Optimization

### Dynamic Mapping Control

```json
// OpenSearch 2.x — strict dynamic mapping
{
  "mappings": {
    "dynamic": "strict",
    "properties": { }
  }
}
```

| Setting | Behavior | Use When |
|---------|----------|----------|
| `true` (default) | Auto-detect and add new fields | Prototyping only. Mapping explosion risk. |
| `runtime` | New fields as runtime fields | Want flexibility without index bloat |
| `strict` | Reject documents with unmapped fields | Production schemas. Forces explicit mapping. |
| `false` | Store but do not index unknown fields | Preserve data without indexing overhead |

### Mapping Explosion Prevention

Mapping explosion happens when dynamic mapping creates thousands of fields from dynamic data (e.g., user-defined labels, arbitrary JSON).

| Problem | Solution |
|---------|----------|
| Dynamic key-value pairs | Use `flattened` field type |
| Nested objects with variable keys | Map known keys explicitly, set `dynamic: false` for the rest |
| Too many fields total | Set `index.mapping.total_fields.limit` (default 1000). If you need more, reconsider the schema. |
| Deep nesting | Set `index.mapping.depth.limit`. Flatten where possible. |

### Multi-Field Patterns

```json
{
  "title": {
    "type": "text",
    "analyzer": "standard",
    "fields": {
      "keyword": { "type": "keyword", "ignore_above": 256 },
      "exact": { "type": "text", "analyzer": "whitespace" },
      "autocomplete": { "type": "text", "analyzer": "autocomplete_index", "search_analyzer": "autocomplete_search" }
    }
  }
}
```

Use sub-fields when the same data needs different treatment: full-text search on `title`, aggregation on `title.keyword`, autocomplete on `title.autocomplete`.

---

## Reindex Strategies

Schema changes that alter field types, analyzers, or mappings require reindexing. Design for it.

### Zero-Downtime Reindex Pattern

```
1. Create new index (products_v2) with updated mappings
2. Reindex: POST _reindex { "source": {"index": "products_v1"}, "dest": {"index": "products_v2"} }
3. Verify document count: products_v2 count == products_v1 count
4. Switch alias: POST _aliases { "actions": [
     { "remove": { "index": "products_v1", "alias": "products" } },
     { "add": { "index": "products_v2", "alias": "products" } }
   ]}
5. Delete old index when confirmed
```

**Alias**: Applications always query the alias (`products`), not the index directly (`products_v1`). Alias swaps are atomic and zero-downtime.

### Reindex Performance

| Setting | Default | Tuning |
|---------|---------|--------|
| `_reindex` batch size | 1000 | Increase to 5000–10000 for large reindexes |
| `slices` | 1 | Set to `auto` (= number of shards) for parallelism |
| `refresh_interval` | 1s | Set to `-1` during reindex, restore after |
| `number_of_replicas` | N | Set to 0 during reindex, restore after |
| `requests_per_second` | unlimited | Throttle if reindex competes with production traffic |

---

## Alias Management

### Alias Patterns

| Pattern | Use Case | Setup |
|---------|----------|-------|
| **Read alias** | Application reads from `products` | Points to current active index |
| **Write alias** | Application writes to `products-write` | Points to current write target |
| **Filtered alias** | Tenant isolation, subset views | Alias with filter: `"filter": {"term": {"tenant_id": "abc"}}` |
| **Rollover alias** | Time-series data | Auto-creates new index when conditions met |

### Rollover for Time-Series

```json
// OpenSearch 2.x — rollover conditions
POST /logs-write/_rollover
{
  "conditions": {
    "max_age": "7d",
    "max_docs": 10000000,
    "max_primary_shard_size": "50gb"
  }
}
```

---

## Index Lifecycle Management (ILM / ISM)

### Phase Definitions

| Phase | Purpose | Typical Actions |
|-------|---------|----------------|
| **Hot** | Active indexing + querying | Full resources, high refresh rate |
| **Warm** | Query-only, recent data | Reduce replicas, merge segments, move to warm nodes |
| **Cold** | Infrequent access | Freeze index, move to cold storage |
| **Delete** | Data expired | Delete index |

### ISM Policy Example (OpenSearch)

```json
// OpenSearch 2.x — Index State Management policy
{
  "policy": {
    "description": "Log retention: hot 7d, warm 30d, cold 90d, delete 365d",
    "default_state": "hot",
    "states": [
      {
        "name": "hot",
        "actions": [{ "rollover": { "min_doc_count": 5000000, "min_index_age": "7d" } }],
        "transitions": [{ "state_name": "warm", "conditions": { "min_index_age": "7d" } }]
      },
      {
        "name": "warm",
        "actions": [
          { "replica_count": { "number_of_replicas": 1 } },
          { "force_merge": { "max_num_segments": 1 } }
        ],
        "transitions": [{ "state_name": "cold", "conditions": { "min_index_age": "30d" } }]
      },
      {
        "name": "cold",
        "actions": [{ "read_only": {} }],
        "transitions": [{ "state_name": "delete", "conditions": { "min_index_age": "365d" } }]
      },
      {
        "name": "delete",
        "actions": [{ "delete": {} }],
        "transitions": []
      }
    ]
  }
}
```

---

## Index Template Patterns

### Composable Index Templates (OpenSearch 2.x / Elasticsearch 8.x)

```json
// Component template for common settings
PUT _component_template/common_settings
{
  "template": {
    "settings": {
      "number_of_shards": 3,
      "number_of_replicas": 1,
      "refresh_interval": "5s",
      "codec": "best_compression"
    }
  }
}

// Component template for common mappings
PUT _component_template/common_mappings
{
  "template": {
    "mappings": {
      "properties": {
        "@timestamp": { "type": "date" },
        "created_at": { "type": "date" },
        "updated_at": { "type": "date" }
      }
    }
  }
}

// Index template composing components
PUT _index_template/products
{
  "index_patterns": ["products-*"],
  "composed_of": ["common_settings", "common_mappings"],
  "template": {
    "mappings": {
      "properties": {
        "title": { "type": "text" },
        "price": { "type": "scaled_float", "scaling_factor": 100 }
      }
    }
  },
  "priority": 200
}
```

---

## Common Pitfalls and Positive Alternatives

| Pitfall | What to Do Instead |
|---------|-------------------|
| Using `dynamic: true` in production | Set `dynamic: strict`. Map all fields explicitly. Catch schema drift at index time. |
| Applying aggressive stemming to product names | Use `light_english` or no stemming for product/brand names. "Running shoes" and "run shoes" are different queries. |
| Storing everything as `text` | Use `keyword` for identifiers, enums, and structured data. Text analysis has storage and query cost. |
| Querying index names directly from applications | Use aliases. Direct index names couple applications to index lifecycle. |
| Using `standard` analyzer for all text fields | Design analyzers per field role: titles need different analysis than body content, tags need `keyword`, autocomplete needs edge_ngram. |
| Setting shard count without considering data volume | Target 10-50 GB per shard. See performance-optimization.md for shard sizing guidance. |
