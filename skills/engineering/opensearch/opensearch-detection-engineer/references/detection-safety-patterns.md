---
description: OpenSearch Security Analytics failure modes — chained findings index flood, field alias bootstrap conflicts, alias-vs-text conflicts, type coercion, missing nested paths, with concrete API diagnosis and fix commands
---

# Detection Safety Patterns

OpenSearch-specific failure modes that block or destabilize detector creation. Production-observed bugs with concrete diagnosis commands and remediation paths.

> **Scope**: Mapping failures and runtime safety patterns specific to Security Analytics detectors and alerting. General index management (ILM, reindexing) lives in `opensearch-elasticsearch-engineer`.
> **Version range**: OpenSearch 2.x Security Analytics plugin

---

## Failure Mode 1: Chained Findings Index Flood

`chained_findings` monitors create a new query index on every run and delete it after. At high schedule frequency, this floods cluster index count.

### Detection

```bash
# Check index count trend
GET /_cat/indices?v&h=index,creation.date.string,status | grep "chained_findings"

# Count chained_findings query indices
GET /_cat/indices?v | grep -c "chained_findings_queries"

# Identify chained-findings-style monitors
GET /_plugins/_alerting/monitors?size=50 | python3 -c "
import json, sys
data = json.load(sys.stdin)
for m in data.get('monitors', []):
    if m.get('monitor_type') == 'query_level_monitor':
        print(f'CHAINED: {m[\"name\"]}')
"
```

**Symptom**: Index count grows by 1 per monitor run; indices named `chained_findings_queries_{uuid}` appear and disappear. At a 1-minute schedule, this can generate 23k+ index create/delete operations per hour.

### Fix: Static Query Indices

Replace per-run query index creation with a static, reused index.

```bash
# 1. Create static query index with explicit mapping
PUT /siem-chained-findings-queries
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 1
  },
  "mappings": {
    "properties": {
      "@timestamp": { "type": "date" },
      "finding_id": { "type": "keyword" },
      "detector_id": { "type": "keyword" },
      "queries": { "type": "object" }
    }
  }
# In production: also disable dynamic mapping ("auto-map-new-fields": false)
# to prevent unintended field creation under load
}

# 2. Update chained findings monitor to use static index
PUT /_plugins/_alerting/monitors/{monitor_id}
{
  ...existing monitor config...,
  "inputs": [{
    "search": {
      "indices": ["siem-chained-findings-queries"],
      ...
    }
  }]
}

# 3. Verify: index count stabilizes
GET /_cat/count/siem-chained-findings-queries?v
```

**Root cause**: The Security Analytics plugin's chained findings implementation creates a new backing index for each evaluation to hold intermediate query results. With no TTL or reuse, each run adds a new index permanently (or until manual cleanup). Static indices are not the default — configure them explicitly.

---

## Failure Mode 2: Field Alias Bootstrap Conflict

Security Analytics field alias bootstrap is destructive. When a detector is created targeting a shared datastream, the bootstrap process writes field aliases that can conflict with existing alias mappings from previous detector runs.

### Detection

```bash
# Check existing aliases on the target index
GET /auth-logs-*/_mapping | python3 -c "
import json, sys
data = json.load(sys.stdin)
for idx, mapping in data.items():
    props = mapping.get('mappings', {}).get('properties', {})
    for field, fdef in props.items():
        if fdef.get('type') == 'alias':
            print(f'{idx}: {field} -> {fdef.get(\"path\")}')
"

# Check for alias conflicts on a specific field
GET /auth-logs-*/_mapping/field/source.ip

# Attempt to add an alias (fails with a conflict if one exists)
PUT /auth-logs-*/_mapping
{
  "properties": {
    "src_ip_alias": {
      "type": "alias",
      "path": "source.ip"
    }
  }
}
```

**Error message**: `mapper_parsing_exception: failed to parse mapping [_doc]: Cannot update to alias mapping, a non-alias mapping exists at [field_name]`

### Fix Option A: Detection-Owned Index (Preferred)

Create a dedicated index for the detector. Security Analytics bootstraps aliases on this index without conflicting with the ingestion datastream.

```bash
# 1. Create detection-owned index with explicit mapping
PUT /siem-detection-auth
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 1,
    "index.lifecycle.name": "siem-short-retention"
  },
  "mappings": {
    "properties": {
      "@timestamp": { "type": "date" },
      "source.ip": { "type": "ip" },
      "user.name": { "type": "keyword" },
      "event.outcome": { "type": "keyword" },
      "url.path": { "type": "keyword" },
      "http.response.status_code": { "type": "integer" }
    }
  }
# In production: also disable dynamic mapping
}

# 2. Create reindex pipeline copying relevant fields from the ingestion index
PUT /_ingest/pipeline/siem-detection-auth-copy
{
  "processors": [
    { "set": { "field": "siem_processed", "value": true } }
  ]
}

# 3. Update detector to use detection-owned index
POST /_plugins/_security_analytics/detectors/{detector_id}
{
  ...
  "inputs": [{ "detector_input": { "indices": ["siem-detection-auth"] }}]
}
```

### Fix Option B: Reindex to Clean Index

Use when the shared datastream already has conflicting aliases and cannot be changed in place.

```bash
# 1. Create new clean index
PUT /auth-logs-clean-v2
{ ...explicit mapping without alias conflicts... }

# 2. Reindex (async)
POST _reindex?wait_for_completion=false
{
  "source": { "index": "auth-logs-*" },
  "dest": { "index": "auth-logs-clean-v2" }
}

# 3. Monitor reindex progress
GET _tasks/{task_id}

# 4. Verify no failures (response.task.status.failures must be empty)

# 5. Atomic alias swap
POST _aliases
{
  "actions": [
    { "remove": { "index": "auth-logs-*", "alias": "auth-logs" } },
    { "add": { "index": "auth-logs-clean-v2", "alias": "auth-logs" } }
  ]
}
```

**Why `PUT _mapping` cannot fix this**: The field alias bootstrap writes a mapping entry of type `alias`. Once an index has a field mapped as `alias`, it cannot be changed to any other type — not even to another `alias` pointing to a different path. Reindex is the only resolution path.

---

## Failure Mode 3: Alias-vs-Text Conflict

Alias fields and text fields cannot coexist at the same path.

### Detection

```bash
# Check field type
GET /auth-logs-*/_mapping/field/source.ip

# Response showing conflict:
# { "auth-logs-000001": { "mappings": { "source.ip": { "mapping": { "source.ip": { "type": "text" } } } } } }
# Expected: "type": "alias" or "type": "ip"
```

**Error when creating detector**: `Validation Failed: ... field [source.ip] of type [alias] cannot be used in aggregations`

### Diagnosis Table

| Symptom | Type | Fix |
|---------|------|-----|
| Field is `text` where `keyword` or `ip` expected | Type mismatch | Reindex with corrected mapping |
| Field is `alias` where `text` expected | Alias-vs-text conflict | Reindex; alias cannot be removed via `PUT _mapping` |
| Field path resolves to `null` | Missing nested path | Check parent object exists in mapping |
| Aggregation on `text` field throws exception | Missing `keyword` sub-field | Add `.keyword` sub-field; reindex if data exists |
| `ip` field stores non-IP string | Type coercion failure | Add `ignore_malformed: true` or fix ingestion pipeline |

### Fix: Type Coercion on IP Field

```bash
# Diagnose malformed IP values
POST /auth-logs-*/_search
{
  "query": {
    "bool": {
      "must_not": [
        { "exists": { "field": "source.ip" } }
      ],
      "filter": [
        { "exists": { "field": "REMOTE_ADDR" } }
      ]
    }
  },
  "size": 10,
  "_source": ["REMOTE_ADDR"]
}

# Tolerate malformed IPs temporarily
PUT /auth-logs-clean-v2/_mapping
{
  "properties": {
    "source.ip": {
      "type": "ip",
      "ignore_malformed": true
    }
  }
}
```

---

## Failure Mode 4: Missing Path in Nested Object

Security Analytics rules referencing nested paths (e.g., `attributes.user.name`) fail when the parent object is unmapped.

### Detection

```bash
# Check if path resolves in mapping
GET /auth-logs-*/_mapping/field/attributes.user.name

# Empty response means path is not explicitly mapped
# Verify data exists at this path
POST /auth-logs-*/_search
{
  "query": { "exists": { "field": "attributes.user.name" } },
  "size": 1
}
```

### Fix

```bash
PUT /auth-logs-*/_mapping
{
  "properties": {
    "attributes": {
      "properties": {
        "user": {
          "properties": {
            "name": { "type": "keyword" }
          }
        }
      }
    }
  }
}
```

This succeeds only on indices without conflicting mappings at `attributes`. If `attributes` is already mapped as `flattened` or `object` with dynamic mapping disabled, the PUT will fail. Reindex is the resolution.

---

## Error → Fix Mapping

| Error / Symptom | Root Cause | Diagnosis Command | Fix |
|-----------------|------------|-------------------|-----|
| `chained_findings_queries_*` indices accumulating | Chained findings monitor creates index per run | `GET _cat/indices \| grep chained_findings` | Use static query index |
| Detector stuck in FAILED state after creation | Field alias bootstrap conflict on shared datastream | `GET {index}/_mapping \| python3 ...` (check alias type) | Detection-owned index or reindex |
| `Cannot update to alias mapping` on `PUT _mapping` | Existing non-alias mapping at field path | `GET {index}/_mapping/field/{name}` | Reindex to clean index |
| `mapper_parsing_exception` on indexing | Type mismatch (IP field receiving hostname string) | Query `ignore_malformed` docs | Add `ignore_malformed: true`; fix upstream |
| Aggregation exception on `text` field | Missing `keyword` sub-field | `GET {index}/_mapping/field/{name}` | Add `.keyword` sub-field; reindex if data exists |
| `field_not_found` in Security Analytics rule | Field absent from index mapping | `GET {index}/_mapping` | Add field to mapping or adjust rule |
| Index count grows without bound | Chained findings index flood | `GET _cat/indices \| wc -l` (trend) | Static query index (see above) |

---

## Detection Commands Reference

```bash
# Check index count (run repeatedly to detect growth)
GET /_cat/indices?v&s=creation.date:desc | head -20

# Find all alias-type fields across SIEM indices
curl -s "$OS_HOST/siem-*/_mapping" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for idx, m in data.items():
    for field, fdef in m.get('mappings', {}).get('properties', {}).items():
        if fdef.get('type') == 'alias':
            print(f'{idx}: {field} -> {fdef.get(\"path\")}')
"

# Verify field types before creating a detector rule
GET /auth-logs-*/_mapping/field/source.ip,user.name,event.outcome

# Check for chained-findings-style monitor configuration
GET /_plugins/_alerting/monitors/_search
{
  "query": {
    "match": { "monitor.monitor_type": "query_level_monitor" }
  }
}

# Validate reindex had no failures
GET _tasks/{task_id}
# Confirm: response.task.status.failures == 0
```

---

## See Also

- `detection-engineering.md`: Detector creation API, SIGMA translation, field normalization
- `incident-escalation.md`: Escalation content requirements, KPIs
