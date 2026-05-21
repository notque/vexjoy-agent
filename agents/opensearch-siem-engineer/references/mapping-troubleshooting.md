---
description: Field alias bootstrap behavior, chained findings index flood pattern and fix, alias-vs-text conflict diagnosis, type coercion errors, missing path errors, with concrete API commands
---

# OpenSearch SIEM Mapping Troubleshooting

> **Scope**: Mapping failures specific to Security Analytics detectors and alerting. General index management (ILM, reindexing) is in opensearch-elasticsearch-engineer's index-management.md.
> **Version range**: OpenSearch 2.x Security Analytics plugin
> **Generated**: 2026-05-22

---

## Known Failure Mode 1: Chained Findings Index Flood

**Production bug**: Observed in SAP Cloud Infrastructure. `chained_findings` monitors create a new query index on every run and delete it after. At high schedule frequency, this floods the cluster index count.

### Detection

```bash
# Check index count trend
GET /_cat/indices?v&h=index,creation.date.string,status | grep "chained_findings"

# Count chained_findings query indices
GET /_cat/indices?v | grep -c "chained_findings_queries"

# Check monitor type
GET /_plugins/_alerting/monitors?size=50 | python3 -c "
import json, sys
data = json.load(sys.stdin)
for m in data.get('monitors', []):
    if m.get('monitor_type') == 'query_level_monitor':
        print(f'CHAINED: {m[\"name\"]}')
"
```

**Symptom**: Index count grows by 1 per monitor run; indices named `chained_findings_queries_{uuid}` appear and disappear. At high frequency (1-min schedule), can generate 23k+ index create/delete operations per hour.

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
# Note: set {"mappings": {"auto-map-new-fields": false}} in production
# (OpenSearch mapping control parameter: prevents unintended field creation)
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

**Root cause**: The Security Analytics plugin's chained findings implementation creates a new backing index for each evaluation to hold intermediate query results. With no TTL or reuse, each run adds a new index permanently (or until manual cleanup). Static indices are not the default. they must be configured explicitly.

---

## Known Failure Mode 2: Field Alias Bootstrap Conflict

**Production bug**: Security Analytics field alias bootstrap is destructive. When a detector is created targeting a shared datastream, the bootstrap process writes field aliases that can conflict with existing alias mappings from previous detector runs.

### Detection

```bash
# Check existing aliases on the target index
GET /keystone-logs-*/_mapping | python3 -c "
import json, sys
data = json.load(sys.stdin)
for idx, mapping in data.items():
    props = mapping.get('mappings', {}).get('properties', {})
    for field, fdef in props.items():
        if fdef.get('type') == 'alias':
            print(f'{idx}: {field} -> {fdef.get(\"path\")}')
"

# Check for alias conflicts
GET /keystone-logs-*/_mapping/field/source.ip

# Attempt to add alias (will fail if conflict exists)
PUT /keystone-logs-*/_mapping
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
PUT /siem-detection-keystone
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
# Note: set {"mappings": {"auto-map-new-fields": false}} in production
}

# 2. Create reindex pipeline to copy relevant fields from ingestion index
PUT /_ingest/pipeline/siem-detection-keystone-copy
{
  "processors": [
    { "set": { "field": "siem_processed", "value": true } }
  ]
}

# 3. Update detector to use detection-owned index
POST /_plugins/_security_analytics/detectors/{detector_id}
{
  ...
  "inputs": [{ "detector_input": { "indices": ["siem-detection-keystone"] }}]
}
```

### Fix Option B: Reindex to Clean Index

When the shared datastream already has conflicting aliases and cannot be changed.

```bash
# 1. Create new clean index
PUT /keystone-logs-clean-v2
{ ...explicit mapping without alias conflicts... }

# 2. Reindex (async)
POST _reindex?wait_for_completion=false
{
  "source": { "index": "keystone-logs-*" },
  "dest": { "index": "keystone-logs-clean-v2" }
}

# 3. Monitor reindex progress
GET _tasks/{task_id}

# 4. Verify no failures
# In task response: "failures" array must be empty

# 5. Atomic alias swap
POST _aliases
{
  "actions": [
    { "remove": { "index": "keystone-logs-*", "alias": "keystone-logs" } },
    { "add": { "index": "keystone-logs-clean-v2", "alias": "keystone-logs" } }
  ]
}
```

**Why `PUT _mapping` cannot fix this**: The field alias bootstrap writes a mapping entry of type `alias`. Once an index has a field mapped as `alias`, it cannot be changed to any other type. not even to another `alias` pointing to a different path. The only resolution is reindex.

---

## Failure Mode 3: Alias-vs-Text Conflict

Alias fields and text fields cannot coexist at the same path.

### Detection

```bash
# Check field type
GET /keystone-logs-*/_mapping/field/source.ip

# Response showing conflict:
# { "keystone-logs-000001": { "mappings": { "source.ip": { "mapping": { "source.ip": { "type": "text" } } } } } }
# Expected: "type": "alias" or "type": "ip"
```

**Error when creating detector**: `Validation Failed: ... field [source.ip] of type [alias] cannot be used in aggregations`

### Diagnosis Table

| Symptom | Type | Fix |
|---------|------|-----|
| Field is `text` where `keyword` or `ip` expected | Type mismatch | Reindex with corrected mapping |
| Field is `alias` where `text` expected | Alias-vs-text conflict | Reindex; alias cannot be removed via PUT _mapping |
| Field path resolves to `null` | Missing nested path | Check parent object exists in mapping |
| Aggregation on `text` field throws exception | Missing `keyword` sub-field | Add `.keyword` sub-field; cannot be added without reindex if data exists |
| `ip` field stores non-IP string | Type coercion failure | Add `ignore_malformed: true` or fix ingestion pipeline |

### Fix: Type Coercion on IP Field

```bash
# Diagnose malformed IP values
POST /keystone-logs-*/_search
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

# Fix mapping to tolerate malformed IPs temporarily
PUT /keystone-logs-clean-v2/_mapping
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
GET /keystone-logs-*/_mapping/field/attributes.user.name

# Empty response means path is not explicitly mapped
# Verify data exists at this path
POST /keystone-logs-*/_search
{
  "query": { "exists": { "field": "attributes.user.name" } },
  "size": 1
}
```

### Fix

```bash
PUT /keystone-logs-*/_mapping
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

Note: This only works on indices without existing conflicting mappings at `attributes`. If `attributes` is already mapped as `flattened` or `object` with auto-mapping disabled, the PUT will fail.

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Diagnosis Command | Fix |
|----------------|------------|-------------------|-----|
| `chained_findings_queries_*` indices accumulating | Chained findings monitor creates index per run | `GET _cat/indices | grep chained_findings` | Use static query index |
| Detector stuck in FAILED state after creation | Field alias bootstrap conflict on shared datastream | `GET index/_mapping | python3 ...` (check alias type) | Detection-owned index or reindex |
| `Cannot update to alias mapping` on PUT _mapping | Existing non-alias mapping at field path | `GET index/_mapping/field/{name}` | Reindex to clean index |
| `mapper_parsing_exception` on indexing | Type mismatch (IP field receiving hostname string) | Query `ignore_malformed` docs | Add `ignore_malformed: true`; fix upstream |
| Aggregation exception on `text` field | Missing `keyword` sub-field | `GET index/_mapping/field/{name}` | Add `.keyword` sub-field; reindex if data exists |
| `field_not_found` in Security Analytics rule | Field absent from index mapping | `GET index/_mapping` | Add field to mapping or adjust rule |
| Index count grows without bound | Chained findings index flood | `GET _cat/indices | wc -l` (trend) | Static query index; see above |

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

# Verify a field type before creating a detector rule
GET /keystone-logs-*/_mapping/field/source.ip,user.name,event.outcome

# Check for chained findings monitor configuration
GET /_plugins/_alerting/monitors/_search
{
  "query": {
    "match": { "monitor.monitor_type": "query_level_monitor" }
  }
}

# Validate reindex had no failures
GET _tasks/{task_id}
# Check: response.task.status.failures == 0
```

---

## See Also

- `detection-engineering.md`: Detector creation API, SIGMA translation, field normalization
- `incident-escalation.md`: Escalation content requirements, KPIs
