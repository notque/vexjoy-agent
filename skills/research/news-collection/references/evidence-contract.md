# Evidence Contract

The five-fact contract every collected item carries, and the JSON artifact
schema. This file is the only normative definition of the artifact — consumers
and the DELIVER phase both read it from here.

## The five facts

| Fact | Type | Missing value handling |
|------|------|------------------------|
| `title` | string | Record as empty string only if the page truly has none; note in `evidence_notes` |
| `url` | string | Required — an item with no URL is unverifiable and stays out of the artifact |
| `outlet` | string | Derive from domain when no masthead is found; note the derivation |
| `author` | string or null | `null` when no byline exists; note where you looked |
| `published_at` | ISO 8601 string or null | Extracted from article metadata, never guessed. `null` when absent; lower `confidence`, disclose in `evidence_notes` |

Every fact is extracted from the source (meta tags, JSON-LD, byline,
sitemap, feed entry) and its origin recorded in `evidence_notes`. Extraction
beats inference because a plausible-looking guess is indistinguishable from a
fact downstream.

## Confidence scale

| Value | Meaning |
|-------|---------|
| `high` | All five facts extracted from explicit metadata |
| `medium` | One fact derived (e.g., outlet from domain) or weakly sourced |
| `low` | `published_at` is null, or two or more facts derived/missing |

## Item schema

```json
{
  "id": "string — stable within this run",
  "title": "string",
  "url": "string",
  "outlet": "string",
  "author": "string | null",
  "published_at": "ISO 8601 string | null",
  "confidence": "high | medium | low",
  "evidence_notes": "string — where each fact came from; disclosed unknowns",
  "verdict": "keep | monitor_only | reject",
  "reason_code": "string — from coarse-filter.md",
  "freshness": "fresh | stale | unclear | null (null for reject items, unchecked)",
  "first_public_estimate": "ISO 8601 string | null",
  "freshness_sources": "integer — independent sources backing the freshness verdict",
  "duplicates_of": "string id | null — canonical item this consolidates into"
}
```

## Artifact schema

```json
{
  "schema_version": "1.0",
  "topic": "string",
  "collected_at": "ISO 8601 string",
  "counts": {
    "collected": 0,
    "keep": 0,
    "monitor_only": 0,
    "reject": 0,
    "unclear_freshness": 0,
    "duplicates_consolidated": 0
  },
  "items": []
}
```

Conservation rule: `collected == keep + monitor_only + reject`. Every item
appears in `items` with its verdict — rejected and unclear items included —
so a consumer can audit the triage, not just read the survivors.
`schema_version` lets consumers detect format changes instead of breaking
silently.
