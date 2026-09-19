# Relevance Tuning Reference

Deep reference for BM25 tuning, learned ranking, boost strategies, function scoring, and field weighting. Loaded by RELEVANCE mode.

---

## BM25 Parameter Tuning

BM25 has two parameters that control term frequency saturation (k1) and document length normalization (b). Default values (k1=1.2, b=0.75) are a reasonable starting point. Tuning them for your content type yields measurable gains.

### Parameter Behavior

| Parameter | Controls | Low Value Effect | High Value Effect |
|-----------|----------|-----------------|-------------------|
| **k1** | Term frequency saturation | Quickly saturates (one mention ≈ many mentions) | More mentions = more relevant, linear-ish |
| **b** | Length normalization | Length barely matters | Long documents penalized heavily |

### Tuning Recipes by Content Type

| Content Type | k1 | b | Rationale |
|-------------|-----|-----|-----------|
| Product titles / short text | 0.3–0.6 | 0.1–0.3 | Short fields. One mention is sufficient. Length variation is noise. |
| Product descriptions | 1.0–1.4 | 0.5–0.7 | Medium text. Repetition somewhat informative. Moderate length normalization. |
| Long-form articles / docs | 1.2–2.0 | 0.75–0.9 | Long text. Repetition matters. Strong length normalization prevents long-doc bias. |
| Log messages | 0.5–0.8 | 0.0–0.2 | Structured, consistent length. Minimal normalization needed. |
| Code / technical content | 0.8–1.2 | 0.3–0.5 | Term frequency informative but saturates. Length varies by file, partial normalization. |
| User reviews / comments | 1.0–1.5 | 0.6–0.8 | Variable length, repetition can indicate emphasis. Normalize for length. |

### How to Tune

1. Start with defaults (k1=1.2, b=0.75)
2. Run evaluation on judgment set, capture nDCG@10
3. Sweep k1 in [0.2, 0.5, 0.8, 1.2, 1.6, 2.0] with b fixed
4. Fix best k1, sweep b in [0.0, 0.25, 0.5, 0.75, 1.0]
5. Fine-tune around the best pair in smaller increments
6. Validate on held-out query set to confirm generalization

### Per-Field BM25 (OpenSearch/Elasticsearch)

```json
// OpenSearch 2.x — per-field similarity override
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "similarity": "title_bm25"
      },
      "body": {
        "type": "text",
        "similarity": "body_bm25"
      }
    }
  },
  "settings": {
    "index": {
      "similarity": {
        "title_bm25": {
          "type": "BM25",
          "k1": 0.5,
          "b": 0.2
        },
        "body_bm25": {
          "type": "BM25",
          "k1": 1.4,
          "b": 0.8
        }
      }
    }
  }
}
```

---

## Field Boosting Strategies

### Multi-Match with Field Weights

```json
// OpenSearch 2.x
{
  "query": {
    "multi_match": {
      "query": "kubernetes deployment",
      "type": "cross_fields",
      "fields": ["title^3", "summary^2", "body^1", "tags^2.5"],
      "tie_breaker": 0.3
    }
  }
}
```

### Multi-Match Types and When to Use Each

| Type | Behavior | Best For |
|------|----------|----------|
| `best_fields` | Score from best-matching field | Queries where one field should dominate |
| `most_fields` | Sum scores across fields | Same content analyzed differently (stemmed + exact) |
| `cross_fields` | Treats fields as one big field | Person names, addresses split across fields |
| `phrase` | Phrase match per field, take best | Exact phrase importance |
| `phrase_prefix` | Phrase prefix per field | Autocomplete / type-ahead |

### Boost Value Calibration

Boost values are relative multipliers. Start with these ranges, then measure:

| Field Role | Boost Range | Example |
|-----------|-------------|---------|
| Primary identifier (title, name) | 2.0–5.0 | `title^3` |
| Secondary text (summary, description) | 1.5–2.5 | `summary^2` |
| Body / content | 1.0 (baseline) | `body^1` |
| Structured metadata (tags, categories) | 1.5–3.0 | `tags^2.5` |
| Weak signals (comments, metadata) | 0.5–1.0 | `comments^0.5` |

Boost values above 5 rarely help and often indicate a structural problem. If you need title^10, consider whether a `bool` query with `should` clauses gives better control.

---

## Function Scoring

Use function_score when relevance depends on non-textual signals: popularity, freshness, authority, geographic proximity.

### Decay Functions for Freshness

```json
// OpenSearch 2.x — exponential decay on date
{
  "query": {
    "function_score": {
      "query": { "match": { "body": "kubernetes" } },
      "functions": [
        {
          "exp": {
            "publish_date": {
              "origin": "now",
              "scale": "30d",
              "offset": "7d",
              "decay": 0.5
            }
          }
        }
      ],
      "boost_mode": "multiply",
      "score_mode": "multiply"
    }
  }
}
```

### Decay Parameter Guide

| Parameter | Meaning | Tuning Guidance |
|-----------|---------|----------------|
| `origin` | "Ideal" value (usually `now` for dates) | Set to the optimal value for scoring |
| `scale` | Distance from origin where score = `decay` | Content shelf life: 7d for news, 90d for docs, 365d for reference |
| `offset` | No decay within this range | Grace period: 0 for time-sensitive, 7-30d for general |
| `decay` | Score at `scale` distance (0-1) | 0.5 is standard. Lower = steeper drop. |

### Decay Function Types

| Function | Curve | When |
|----------|-------|------|
| `exp` | Exponential | Strong freshness signal, news/social |
| `linear` | Linear | Steady decline, general content |
| `gauss` | Bell curve | Optimal range (geographic distance, price) |

### Field Value Factor for Popularity

```json
// OpenSearch 2.x — log-dampened popularity boost
{
  "query": {
    "function_score": {
      "query": { "match": { "body": "search tutorial" } },
      "functions": [
        {
          "field_value_factor": {
            "field": "view_count",
            "factor": 1.2,
            "modifier": "log1p",
            "missing": 1
          }
        }
      ],
      "boost_mode": "sum"
    }
  }
}
```

### Modifier Selection

| Modifier | Formula | When |
|----------|---------|------|
| `none` | value * factor | Linear boost. Use for small, bounded values. |
| `log1p` | log(1 + value * factor) | Dampened. Prevents runaway from high values. Most common. |
| `log2p` | log(2 + value * factor) | Slightly more dampened than log1p |
| `sqrt` | sqrt(value * factor) | Moderate dampening |
| `square` | (value * factor)^2 | Amplifies differences. Use with caution. |
| `reciprocal` | 1 / (value * factor) | Inverse. Lower values score higher. |

### boost_mode vs score_mode

| Setting | Controls | Options |
|---------|----------|---------|
| `score_mode` | How multiple functions combine | `multiply`, `sum`, `avg`, `first`, `max`, `min` |
| `boost_mode` | How function result combines with query score | `multiply`, `replace`, `sum`, `avg`, `max`, `min` |

**Common patterns**:
- `score_mode: multiply` + `boost_mode: multiply` — functions modulate text relevance
- `score_mode: sum` + `boost_mode: sum` — functions add independent signals
- `boost_mode: replace` — ignore text score, rank by function output only

---

## Learned Ranking (LTR)

When BM25 + hand-tuned boosts plateau, learned ranking (Learning to Rank) trains a model on relevance judgments to combine features optimally.

### Feature Engineering

Features that make LTR models effective:

| Feature Category | Examples | Implementation |
|-----------------|----------|----------------|
| Text relevance | BM25 score per field, TF-IDF, match count | Query-dependent, from search engine |
| Query features | Query length, query type, has quotes, has filters | Query-dependent, computed at query time |
| Document features | Document length, age, popularity, authority score | Query-independent, indexed as fields |
| Interaction features | Click-through rate, dwell time, bounce rate | Query-document pair, from click logs |
| Freshness | Days since publish, days since update | Query-independent |
| Coverage | Fraction of query terms matched | Query-dependent |
| Exact match | Title exact match, URL path match | Query-dependent, binary features |

### Feature Store Pattern (OpenSearch LTR Plugin)

```json
// OpenSearch 2.x — feature set definition
{
  "featureset": {
    "name": "product_search_features",
    "features": [
      {
        "name": "title_bm25",
        "params": ["keywords"],
        "template_language": "mustache",
        "template": {
          "match": { "title": "{{keywords}}" }
        }
      },
      {
        "name": "description_bm25",
        "params": ["keywords"],
        "template_language": "mustache",
        "template": {
          "match": { "description": "{{keywords}}" }
        }
      },
      {
        "name": "popularity",
        "params": [],
        "template_language": "mustache",
        "template": {
          "function_score": {
            "functions": [
              { "field_value_factor": { "field": "sales_rank", "modifier": "log1p" } }
            ],
            "query": { "match_all": {} }
          }
        }
      }
    ]
  }
}
```

### Model Selection

| Model | Approach | Pros | Cons |
|-------|----------|------|------|
| LambdaMART (XGBoost) | Gradient-boosted trees optimizing nDCG | Strong accuracy, interpretable features | Requires feature engineering |
| RankNet | Neural pairwise loss | Handles raw features | Needs more data, less interpretable |
| Linear | Weighted feature combination | Simple, fast, explainable | Limited expressiveness |

### LTR Workflow

1. Define feature set covering text, query, document, and interaction signals
2. Collect judgments: 4-point scale (Perfect, Good, Fair, Bad) on query-document pairs
3. Log features for judged pairs using `_ltr/_log` endpoint
4. Train model offline (XGBoost/LambdaMART typical)
5. Upload model to the search platform
6. A/B test against BM25 baseline
7. Monitor feature importance drift over time

### When to Use LTR vs Simpler Approaches

| Signal | Stick with BM25 + Boosts | Move to LTR |
|--------|--------------------------|-------------|
| Query volume | < 10K queries/day | > 10K queries/day (enough click data) |
| Relevance gap | Tuning BM25 params still improving | BM25 plateau — same nDCG regardless of tuning |
| Ranking signals | Text relevance dominates | Multiple non-text signals matter (popularity, freshness, personalization) |
| Judgment availability | < 500 judged queries | > 1000 judged queries with consistent labels |
| Engineering capacity | Limited ML infrastructure | Can maintain feature pipelines and model retraining |

---

## Rescoring

Rescoring applies an expensive second query to the top N results from the initial query. Useful for applying complex scoring without paying the cost on every document.

```json
// OpenSearch 2.x — rescore with phrase proximity
{
  "query": {
    "match": { "body": "distributed search engine" }
  },
  "rescore": {
    "window_size": 100,
    "query": {
      "rescore_query": {
        "match_phrase": {
          "body": {
            "query": "distributed search engine",
            "slop": 2
          }
        }
      },
      "query_weight": 0.7,
      "rescore_query_weight": 1.2
    }
  }
}
```

### Rescore Use Cases

| Use Case | First Pass | Rescore |
|----------|-----------|---------|
| Phrase proximity | match query | match_phrase with slop |
| LTR | BM25 | sltr model |
| Vector similarity | BM25 keyword match | knn on top candidates |
| Complex scripting | Standard query | script_score with expensive logic |

**Window size guideline**: Start with 100–200. Larger windows improve quality but cost latency. Measure the tradeoff for your workload.

---

## Common Pitfalls and Positive Alternatives

| Pitfall | What to Do Instead |
|---------|-------------------|
| Tuning boost values by intuition | Measure nDCG before and after each change. Let metrics guide. |
| Applying the same BM25 params to all fields | Per-field similarity. Short fields and long fields have different saturation curves. |
| Adding popularity boost without dampening | Use `log1p` modifier. Raw popularity scores create runaway effects. |
| Stacking multiple function_score functions | Start with one function, measure, add the next. Interaction effects are unpredictable. |
| Copying relevance config from blog posts | Every corpus has different characteristics. Validate against your data and queries. |
| Boosting a field to 10+ | Restructure the query instead. Extreme boosts mask structural issues. |
