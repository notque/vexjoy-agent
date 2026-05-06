# LLM Failure Modes in Search Engineering

Where LLMs systematically fail at search engineering tasks. Loaded across all modes as a guardrail reference.

---

## Why This File Exists

LLMs generate plausible-looking search configurations, query DSL, and relevance advice that passes a casual read but fails in production. Search engineering is particularly vulnerable because: query DSL is complex JSON with strict validation, platform versions have diverged significantly, and "improve relevance" sounds correct while being completely non-actionable.

This reference catalogs specific failure modes, their signatures, and defenses.

---

## Failure Mode 1: Hallucinated Query DSL

### What Happens

The LLM generates query DSL that looks syntactically correct but uses non-existent parameters, deprecated features, or impossible combinations. The JSON is well-formed, so it passes a visual check. It fails at runtime with a parse exception.

### Signatures

| Signal | Example |
|--------|---------|
| Non-existent parameters | `"match": { "field": { "query": "x", "boost_mode": "multiply" } }` — `boost_mode` is a `function_score` parameter, not a `match` parameter |
| Mixed platform syntax | Using Elasticsearch `knn` section syntax in an OpenSearch query |
| Invented query types | `"semantic_match"` — does not exist in any platform |
| Wrong nesting | `function_score` inside `bool.filter` (function_score is a top-level wrapper) |
| Deprecated structure | Type-level mappings (`_doc`), `_optimize` endpoint, `common` query |

### Defenses

| Defense | Implementation |
|---------|---------------|
| State platform + version | Begin every query generation with "Platform: OpenSearch 2.x" or "Elasticsearch 8.x" |
| Validate against docs | Check each query clause against the official API documentation for the stated version |
| Test before recommending | Run the query against a test cluster or provide the validation command |
| Annotate uncertainty | If uncertain whether a parameter exists in the target version, say so explicitly |
| Prefer simple constructs | `match`, `term`, `bool`, `range` are stable across versions. Exotic queries drift. |

---

## Failure Mode 2: Version Confusion

### What Happens

The LLM mixes features from different platform versions or confuses Elasticsearch with OpenSearch. After the fork (ES 7.10), these platforms diverged significantly on security, ML, alerting, and vector search APIs.

### Key Divergence Points

| Feature | Elasticsearch 8.x | OpenSearch 2.x |
|---------|-------------------|----------------|
| Security | On by default, built-in | Security plugin (separate) |
| Vector search | `knn` query type, `dense_vector` field | `knn_vector` field, k-NN plugin, different query syntax |
| ML | Elastic ML (proprietary) | ML Commons (open source, different API) |
| Alerting | Watcher / Kibana alerting | Alerting plugin (different API) |
| SQL | `_sql` endpoint | SQL plugin (different endpoint) |
| ILM / ISM | Index Lifecycle Management (ILM) | Index State Management (ISM) — different policy format |
| Aggregation pipeline | `pipeline` agg | Same syntax but some agg types differ |
| License | Elastic License 2.0 / AGPL | Apache 2.0 |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Confirm platform before generating | Ask: "Which platform and version?" before writing any config or query |
| Label all code blocks | `// OpenSearch 2.x` or `// Elasticsearch 8.14` on every code block |
| Check fork point | Features added after ES 7.10 are likely ES-only. Verify OpenSearch equivalents separately. |
| Separate mental models | OpenSearch 2.x security ≠ ES 8.x security. Different APIs, different defaults. |

---

## Failure Mode 3: Generic Relevance Advice

### What Happens

The LLM provides advice that sounds expert but is too vague to implement. "Boost important fields" does not help without knowing which fields, by how much, and measured against what baseline.

### Signatures

| Signal | Example |
|--------|---------|
| No concrete values | "Adjust your BM25 parameters for better relevance" — what values? |
| No measurement | "Add a freshness boost" — how to verify it helped? |
| Undefined terms | "Improve your relevance pipeline" — what specific component? |
| Contradictory advice | "Use BM25 for precision" + "Use vector search for precision" in the same response |
| Missing tradeoffs | "Add synonym expansion" — without noting the precision cost |
| One-size-fits-all | "Set k1=1.2, b=0.75" — these are defaults, not tuning |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Require specifics | Every tuning recommendation includes: parameter name, value, field, expected effect |
| Require measurement | Every change has a before/after metric comparison plan |
| Require context | What content type? What query patterns? What current metrics? |
| Surface tradeoffs | Every optimization has a cost. Name it: precision vs recall, latency vs quality, complexity vs maintainability. |
| Ban "improve relevance" as advice | This is like saying "make it better." Specify what aspect of relevance and how to measure improvement. |

---

## Failure Mode 4: Vector Search as Default Recommendation

### What Happens

The LLM recommends vector search / embeddings as the solution to every search problem. Vector search is powerful but adds significant complexity: embedding model selection, vector storage, approximate nearest neighbor trade-offs, hybrid retrieval fusion, and model retraining.

### When BM25 Solves the Problem

| Scenario | BM25 Sufficient? | Why |
|----------|-----------------|-----|
| Keyword-rich queries ("NullPointerException auth service") | Yes | Exact term matching is what the user wants |
| Known-item search ("OpenSearch documentation") | Yes | Navigational intent, title/URL matching |
| Faceted search ("red shoes size 10") | Yes | Structured filters + text, no semantic gap |
| Log search | Yes | Exact patterns, no semantic interpretation needed |
| Well-maintained synonym dictionaries | Often yes | Synonyms bridge the vocabulary gap BM25 misses |

### When Vector Search Adds Value

| Scenario | Why BM25 Falls Short |
|----------|---------------------|
| Conceptual queries ("how to handle errors gracefully") | Vocabulary gap — user's words differ from document terms |
| Cross-language search | BM25 is language-bound, embeddings can be multilingual |
| Image/multimodal search | No text to match on |
| Semantic similarity for recommendations | "More like this" needs semantic understanding |
| Very short queries against long documents | BM25 struggles with single-word queries on long docs |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Start with BM25 | Tune BM25 + analyzers + synonyms first. Measure the gap. |
| Justify the complexity | Vector search adds: embedding model, index overhead, fusion logic, model maintenance |
| Hybrid, not replacement | Vector search complements BM25. It rarely replaces it entirely. |
| Measure the delta | A/B test hybrid vs BM25-only. Quantify the relevance gain against the complexity cost. |

---

## Failure Mode 5: Ignoring Measurement

### What Happens

The LLM suggests relevance changes without establishing a measurement framework. Without baselines and metrics, there is no way to know whether a change helped, hurt, or had no effect.

### Signatures

| Signal | Example |
|--------|---------|
| No baseline request | "Add this boost" without asking for current metrics |
| Assumed improvement | "This will improve results" without specifying how to verify |
| Subjective evaluation | "Try some queries and see if it looks better" |
| Multiple simultaneous changes | "Update BM25 params, add boosts, and change the analyzer" — which one helped? |
| No regression check | Change improves one query class, silently breaks another |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Baseline first | Capture nDCG@10, P@5, MRR before any change |
| One variable at a time | Change one thing, measure, then change the next |
| Regression check | Evaluate across all query classes, not just the target class |
| Statistical significance | With <200 queries, a 0.02 nDCG change is noise |
| Track the history | Maintain a changelog of what was changed, when, and what the metric impact was |

---

## Failure Mode 6: Deprecated Feature Suggestions

### What Happens

The LLM suggests features that have been removed or deprecated in the target platform version. Training data includes old blog posts, Stack Overflow answers, and documentation from earlier versions.

### Common Deprecated Features

| Feature | Deprecated In | Replacement |
|---------|--------------|-------------|
| Type mappings (`_type`) | ES 7.0+ | Single type per index, `_doc` default |
| `_optimize` API | ES 2.1+ | `_forcemerge` |
| `common` query | ES 7.0+ | `match` query handles stop words natively |
| `indices.optimize` | ES 2.1+ | `_forcemerge` |
| `filtered` query | ES 5.0+ | `bool` with `filter` clause |
| `or`/`and` queries | ES 5.0+ | `bool` with `should`/`must` |
| String field type | ES 5.0+ | `text` or `keyword` |
| `fielddata: true` for aggregation | Discouraged since ES 5.0 | `keyword` sub-field or `doc_values` |
| `_all` field | ES 6.0+ | `copy_to` or `multi_match` |
| `parent-child` joins | ES 5.6+ | `join` field type |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Check release notes | Verify features against the target version's breaking changes documentation |
| Prefer modern constructs | Use `bool`+`filter` over `filtered`, `text`/`keyword` over `string` |
| Flag uncertainty | "This may be deprecated in your version — verify against the docs" when unsure |
| Test with version info | Include version in test setup to catch compatibility issues |

---

## Failure Mode 7: Over-Engineered Schemas

### What Happens

The LLM creates mappings with 50+ fields, sub-fields for every possible analysis, nested objects where flat structures work, and vector fields "just in case." The resulting schema has high storage overhead, slow indexing, and complex query requirements.

### Schema Complexity Assessment

| Signal | Indicates Over-Engineering |
|--------|---------------------------|
| Fields that no query uses | Schema mirrors data model, not query requirements |
| Every string field has 3+ sub-fields | Speculative analysis chains |
| Nested type where arrays of keywords work | Unnecessary join overhead |
| Vector field with no embedding pipeline | Added "for future use" |
| Custom analyzers that duplicate standard behavior | Reinventing existing analyzers |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Start from queries | List the queries the application runs. Map only the fields those queries need. |
| Add fields when needed | Ship minimal schema, add fields when query requirements emerge |
| Measure index cost | Track index size, indexing speed, segment count as schema grows |
| Question every nested type | "Do I need cross-field correlation?" If not, use keyword arrays. |
| Review sub-fields | Each sub-field has storage and indexing cost. Justify each one against a real query need. |

---

## Failure Mode 8: Cargo-Cult Configuration

### What Happens

The LLM copies cluster configuration from blog posts, conference talks, or generic templates without understanding the specific workload. "Best practices" settings harm performance when applied to the wrong workload.

### Common Cargo-Cult Settings

| Setting | Blog Recommendation | Reality |
|---------|-------------------|---------|
| `number_of_shards: 5` | "Always use 5 shards" | Depends on data volume. 50 MB index with 5 shards is wasteful. |
| `refresh_interval: 30s` | "Set to 30s for performance" | Depends on freshness requirements. Search applications need faster refresh. |
| `index.max_result_window: 100000` | "Increase for deep pagination" | Use `search_after` instead. This setting exists as a safety limit. |
| JVM heap at 31 GB | "Always set to 31 GB" | Depends on workload. Over-allocating heap steals from page cache. |
| `thread_pool.search.size: 100` | "Increase for more throughput" | Excessive threads cause context switching. Default is usually correct. |
| `translog.durability: async` | "Set to async for speed" | Trades data durability for indexing speed. Appropriate only during bulk ingest. |

### Defenses

| Defense | Implementation |
|---------|---------------|
| Justify every setting | "Why this value for this workload?" If you cannot answer, use the default. |
| Benchmark with your data | Test settings against representative data and query patterns |
| Monitor the effect | Change one setting, observe the metrics impact, then decide to keep or revert |
| Understand the tradeoff | Every non-default setting trades something. Name what you are trading away. |
| Defaults are usually good | Platform teams optimize defaults for common workloads. Deviate with evidence, not blog posts. |

---

## Cross-Cutting Defense: The Search Engineering Verification Habit

Before delivering any search engineering recommendation:

1. **Platform check**: Is this valid for the stated platform and version?
2. **Specificity check**: Does this include concrete values, field names, and expected outcomes?
3. **Measurement check**: Is there a plan to measure the impact?
4. **Tradeoff check**: Are costs and tradeoffs explicitly stated?
5. **Complexity check**: Is this the simplest approach that solves the problem?
6. **Regression check**: Could this improve one thing while breaking another?

If any check fails, fix it before delivering. "Improve your relevance" is not a recommendation — it is a wish.
