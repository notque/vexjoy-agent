# Query Understanding Reference

Deep reference for intent classification, entity extraction, query expansion, spelling correction, and query relaxation. Loaded by QUERY mode.

---

## Intent Classification Taxonomy

Classify every query before constructing the search request. Intent determines field selection, boosting strategy, and result presentation.

### Core Intent Types

| Intent | User Goal | Query Characteristics | Strategy |
|--------|-----------|----------------------|----------|
| **Navigational** | Find a specific known item | Short, contains proper nouns, product names, URLs | Title/name exact match, URL match, high precision |
| **Informational** | Learn about a topic | Question words, "how to", longer phrases | Full-text body search, snippet extraction, diversified results |
| **Transactional** | Take an action (buy, download, sign up) | Action verbs, product terms, pricing keywords | Product fields, availability, CTA matching |
| **Faceted** | Filter by attributes | Attribute-value pairs ("red shoes size 10") | Parse attributes into filters, text remainder into query |
| **Exploratory** | Browse/discover a topic area | Vague terms, broad categories | Related terms, faceted navigation, "did you mean" suggestions |
| **Exact** | Find an exact phrase or identifier | Quoted strings, codes, IDs, error messages | Exact match, no stemming, keyword fields |

### Intent Detection Signals

| Signal | Detection Method | Maps To |
|--------|-----------------|---------|
| Quoted strings | Regex: `"[^"]+"` | Exact intent — use match_phrase |
| Question words | Starts with who/what/when/where/why/how | Informational intent |
| Product identifiers | Regex: SKU patterns, model numbers | Navigational intent |
| Attribute patterns | `color:red`, `size:10`, compound adjective+noun | Faceted intent |
| Action verbs | buy, download, install, configure, fix | Transactional intent |
| Single word / broad term | Short query, no qualifiers | Exploratory intent |

---

## Entity Extraction

Extract structured entities from the query to apply as filters, boosts, or routing decisions.

### Entity Types for Search

| Entity Type | Examples | Extraction Method | Usage |
|------------|---------|-------------------|-------|
| Product names | "MacBook Pro", "OpenSearch" | Dictionary matching, NER | Navigate to product page, boost product fields |
| Categories | "shoes", "documentation", "APIs" | Taxonomy lookup | Category filter or boost |
| Attributes | "red", "large", "v2.x" | Attribute vocabulary matching | Structured filters |
| People | "John Smith", "author:jane" | Name patterns, prefix syntax | Author/creator filter |
| Dates/Ranges | "last week", "2024", "before March" | Date parsing | Date range filter |
| Locations | "San Francisco", "us-east-1" | Geo dictionary, region patterns | Geo filter or boost |
| Error codes | "HTTP 503", "NullPointerException" | Regex patterns | Exact match in error fields |
| Versions | "v2.3", "ES 8.x", "Python 3.11" | Semver regex | Version filter |

### Dictionary-Based Extraction

Maintain domain dictionaries for your search corpus:

```
# products.dict
opensearch -> product:OpenSearch
elasticsearch -> product:Elasticsearch
es -> product:Elasticsearch
solr -> product:Solr
vespa -> product:Vespa

# categories.dict
tutorial -> category:tutorials
guide -> category:guides
api reference -> category:api-docs
troubleshoot* -> category:troubleshooting
```

**Dictionary maintenance**: Dictionaries drift. Review monthly against actual query logs. Add terms that users search for but the dictionary misses. Remove terms that cause false positive extractions.

---

## Query Expansion

Expand the original query to improve recall without sacrificing precision.

### Synonym Expansion

| Strategy | How | When | Risk |
|----------|-----|------|------|
| **Index-time synonyms** | Synonyms applied during indexing (analyzer filter) | Synonyms are stable, full reindex acceptable | Cannot update without reindex. Over-expansion. |
| **Query-time synonyms** | Synonyms applied at search time (search_analyzer) | Synonyms change frequently, cannot reindex | Performance cost per query. |
| **Explicit synonyms** | `k8s => kubernetes`, `js => javascript` | Known abbreviations, brand names | Maintain the list manually or mine from logs |
| **Equivalent synonyms** | `notebook, laptop` | Interchangeable terms | Can cause precision loss on ambiguous terms |
| **One-way expansion** | `js => javascript` (but not reverse) | Abbreviations should expand, full terms should not contract | Need directional synonym rules |

### Synonym Configuration Example

```json
// OpenSearch 2.x — synonym filter
{
  "settings": {
    "analysis": {
      "filter": {
        "domain_synonyms": {
          "type": "synonym_graph",
          "synonyms": [
            "k8s, kubernetes",
            "js => javascript",
            "es => elasticsearch",
            "ml, machine learning",
            "db, database",
            "auth, authentication, authn",
            "authz => authorization"
          ]
        }
      },
      "analyzer": {
        "search_with_synonyms": {
          "tokenizer": "standard",
          "filter": ["lowercase", "domain_synonyms", "stemmer"]
        }
      }
    }
  }
}
```

**Synonym ordering**: Apply synonyms before stemming. `js => javascript` then stem `javascript` -> `javascript`. Reversing the order produces incorrect expansions.

### Embedding-Based Expansion

When the synonym dictionary does not cover a term, use embedding similarity to find expansion candidates.

| Approach | How | When |
|----------|-----|------|
| Nearest neighbors | Find top-k similar terms by embedding distance | Rare terms not in synonym dictionary |
| Query embedding | Embed the full query, find similar queries from logs | Query reformulation |
| Contextual expansion | Use the query context to disambiguate expansion | Polysemous terms ("java" = language or island?) |

**Threshold**: similarity > 0.85 for automatic expansion, 0.7–0.85 for "did you mean" suggestions. Below 0.7, skip — the expansion is likely noise.

---

## Spelling Correction

### Correction Strategies

| Strategy | How | Best For |
|----------|-----|----------|
| **Did you mean** | Suggest correction, do not auto-apply | Ambiguous corrections, low confidence |
| **Auto-correct** | Silently correct and search | High-confidence corrections, common misspellings |
| **Search both** | Search original AND corrected query, merge results | Maximize recall, user may have meant what they typed |

### Implementation Approaches

| Approach | Mechanism | Pros | Cons |
|----------|-----------|------|------|
| Index-based suggest | `_suggest` API with term/phrase suggesters | Uses your actual corpus vocabulary | Limited to indexed terms |
| Fuzzy matching | `fuzziness: "AUTO"` on match queries | Zero configuration | Performance cost, false positives |
| Custom dictionary | Pre-built correction dictionary from query logs | High precision for your domain | Maintenance overhead |
| Phonetic matching | `phonetic` token filter (soundex, metaphone) | Catches homophones | Language-specific, false positives |

### Fuzzy Query Configuration

```json
// OpenSearch 2.x — fuzzy match with controlled edit distance
{
  "query": {
    "match": {
      "title": {
        "query": "kuberntes",
        "fuzziness": "AUTO",
        "prefix_length": 2,
        "max_expansions": 50
      }
    }
  }
}
```

**fuzziness: AUTO** behavior:
- 0–2 characters: exact match only
- 3–5 characters: 1 edit allowed
- 6+ characters: 2 edits allowed

**prefix_length**: Characters that must match exactly at the start. Set to 2+ to avoid "cat" matching "bat". Higher values = faster but stricter.

---

## Query Relaxation

When initial queries return too few results, systematically relax constraints to broaden the search.

### Relaxation Hierarchy

Apply in order, stopping when result count is sufficient:

| Step | Action | Example |
|------|--------|---------|
| 1 | Remove date/time filters | `after:2024-01-01` -> no date filter |
| 2 | Remove location/source filters | `in:engineering` -> all sources |
| 3 | Reduce `minimum_should_match` | `100%` -> `75%` -> `50%` |
| 4 | Broaden specific terms | `"PostgreSQL migration"` -> `"database migration"` |
| 5 | Drop least important query terms | `kubernetes pod scheduling failure` -> `kubernetes pod failure` |
| 6 | Apply stemming if not already | `configurations` -> `configur*` |
| 7 | Add synonyms/expansions | `kubernetes` -> `kubernetes OR k8s OR container orchestration` |
| 8 | Fuzzy matching | `fuzziness: AUTO` on remaining terms |

### minimum_should_match Patterns

```json
// OpenSearch 2.x — adaptive minimum_should_match
{
  "query": {
    "bool": {
      "should": [
        { "match": { "body": "distributed" } },
        { "match": { "body": "search" } },
        { "match": { "body": "engine" } },
        { "match": { "body": "architecture" } }
      ],
      "minimum_should_match": "75%"
    }
  }
}
```

| Value | Meaning | When |
|-------|---------|------|
| `100%` or `all` | All terms must match | High-precision mode, short queries |
| `75%` | 3 of 4 terms (rounds down) | Default for informational queries |
| `2<75%` | First 2 required, 75% of remainder | Long queries where core terms matter |
| `1` | At least one term | Maximum recall, use with re-ranking |

---

## Query Transformation Examples

Real-world query rewrites showing the full pipeline:

| User Query | Intent | Entities | Expansion | Final Query |
|-----------|--------|----------|-----------|-------------|
| `kuberntes deploy error` | Informational | product:Kubernetes | spelling: kubernetes, synonym: k8s | `(kubernetes OR k8s) AND deploy* AND error` with body boost |
| `"NullPointerException" in auth service` | Exact + Navigational | error:NPE, service:auth | None (exact match) | `phrase_match("NullPointerException") AND service:auth*` |
| `how to configure opensearch dashboards` | Informational | product:OpenSearch Dashboards | synonym: kibana (for ES users) | Multi-match on title^3, body^1 for "configure opensearch dashboards" |
| `red shoes size 10 under $50` | Faceted | color:red, size:10, price:<50 | None | Filters: color=red, size=10, price<=50. Text: "shoes" |
| `john's PR from last week` | Navigational | person:john, time:last_week | None | Author:john*, date:last_7d, type:pull_request |

---

## Query Pipeline Architecture

```
User Query
    ↓
[1. Tokenize + Normalize]  — lowercase, unicode normalization
    ↓
[2. Spell Check]           — correct obvious misspellings
    ↓
[3. Entity Extract]        — pull out structured entities (people, dates, products)
    ↓
[4. Intent Classify]       — determine query type
    ↓
[5. Synonym Expand]        — add equivalent terms
    ↓
[6. Query Construct]       — build platform-specific query DSL
    ↓
[7. Boost/Filter Apply]    — intent-specific field weights and filters
    ↓
Platform Query
```

Each step is independently testable. Log the query at each stage for debugging relevance issues.

---

## Common Pitfalls and Positive Alternatives

| Pitfall | What to Do Instead |
|---------|-------------------|
| Applying synonyms bidirectionally when only one direction is correct | Use directional synonyms: `js => javascript` keeps precision. |
| Auto-correcting queries without showing the user | Use "did you mean" for ambiguous corrections. Auto-correct only when confidence is very high. |
| Expanding every query with embeddings | Reserve embedding expansion for tail queries with zero results. Head queries have enough signal. |
| Treating all query terms as equally important | Use IDF or query-term weights. Rare terms carry more information than common ones. |
| Building query understanding without logging | Log every stage of the query pipeline. Debugging without query logs is guesswork. |
