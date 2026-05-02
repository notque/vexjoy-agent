---
description: Cluster health, shard allocation, capacity planning, rolling upgrades, and snapshot/restore operations
---

# OpenSearch/Elasticsearch Cluster Operations

> **Scope**: Cluster health management, shard allocation debugging, node roles, JVM heap tuning, rolling upgrades, and snapshot configuration. OpenSearch 2.x and Elasticsearch 8.x.
> **Version range**: OpenSearch 2.0+ / Elasticsearch 8.0+
> **Generated**: 2026-04-08

---

## Overview

Misconfigured heap or shard counts are silent until load spikes. Yellow is tolerable; red is data loss risk. DELETE index, live mapping updates, and shrink are irreversible without snapshots.

---

## Pattern Table

| Pattern | Version | Use When | Prefer Another Pattern When |
|---------|---------|----------|------------|
| `cluster.routing.allocation.enable: all` | All versions | After maintenance window | Never set to `none` and forget |
| `indices.recovery.max_bytes_per_sec` | All versions | Limiting recovery bandwidth | Default is unlimited (saturates network) |
| Hot-warm-cold node roles | OS 2.0+ / ES 7.0+ | Mixed workload (active + archive data) | Single-tier small clusters |
| Cross-cluster replication | OS 1.1+ / ES 6.5+ | DR, geographic distribution | Simple single-cluster HA |
| Snapshot before destructive ops | Always | Before DELETE, reindex, mapping update | Never skip |

---

## Correct Patterns

### Diagnosing Yellow/Red Cluster Status

Start with allocation explain before guessing.

```bash
# Step 1: Overall health
GET /_cluster/health?pretty

# Step 2: Identify unassigned shards
GET /_cat/shards?v&h=index,shard,prirep,state,unassigned.reason&s=state:desc

# Step 3: Get authoritative explanation for unassigned shard
GET /_cluster/allocation/explain
{
  "index": "your-index",
  "shard": 0,
  "primary": false
}

# Step 4: Check disk thresholds (common cause)
GET /_cluster/settings?include_defaults=true&filter_path=*.cluster.routing.allocation.disk*

# Common fix for disk threshold exceeded:
PUT /_cluster/settings
{
  "transient": {
    "cluster.routing.allocation.disk.watermark.low": "85%",
    "cluster.routing.allocation.disk.watermark.high": "90%",
    "cluster.routing.allocation.disk.watermark.flood_stage": "95%"
  }
}
```

**Why**: `allocation/explain` tells exactly why a shard won't assign. Guessing without this leads to misdiagnosis.

---

### JVM Heap Configuration

```bash
# In jvm.options (or opensearch.yml for OS 2.12+):
# Set to 50% of available RAM, never exceed 31GB
-Xms16g
-Xmx16g

# Verify heap in use
GET /_nodes/stats?filter_path=nodes.*.jvm.mem

# Monitor GC pressure
GET /_nodes/stats?filter_path=nodes.*.jvm.gc.collectors.*.collection_time_in_millis
# GC time > 25% of wall clock = heap pressure
```

**Why**: JVM uses compressed OOPs below ~31GB. Above that, pointer size doubles, effective capacity drops 30%. Set max 31g; verify with `GET /_nodes`.

---

### Rolling Upgrade Procedure

```bash
# 1. Disable shard allocation before each node
PUT /_cluster/settings
{
  "transient": {
    "cluster.routing.allocation.enable": "primaries"
  }
}

# 2. Flush syncronized (ES 7.6+ / OS: not needed — handled by upgrade)
POST /_flush

# 3. Stop node, upgrade, start node
systemctl stop opensearch
# ... upgrade package ...
systemctl start opensearch

# 4. Wait for node to rejoin
GET /_cat/nodes?v

# 5. Re-enable allocation
PUT /_cluster/settings
{
  "transient": {
    "cluster.routing.allocation.enable": null
  }
}

# 6. Wait for green before upgrading next node
GET /_cluster/health?wait_for_status=green&timeout=300s

# 7. Repeat for each node
```

**Why**: Prevents shard recovery storms. Without this, cluster recovers replicas to other nodes then cancels when the node returns.

---

### Snapshot Configuration

```bash
# Register S3 snapshot repository
PUT /_snapshot/backups
{
  "type": "s3",
  "settings": {
    "bucket": "es-snapshots-prod",
    "region": "us-east-1",
    "base_path": "snapshots",
    "compress": true,
    "chunk_size": "1gb",
    "server_side_encryption": true
  }
}

# Create snapshot policy (automated)
PUT /_slm/policy/nightly-snapshots
{
  "schedule": "0 30 1 * * ?",
  "name": "<nightly-snap-{now/d}>",
  "repository": "backups",
  "config": {
    "indices": ["*"],
    "ignore_unavailable": false,
    "include_global_state": true
  },
  "retention": {
    "expire_after": "30d",
    "min_count": 5,
    "max_count": 50
  }
}

# Verify latest snapshot
GET /_snapshot/backups/_all?pretty&s=start_time:desc
```

**Why**: `include_global_state: true` captures templates, ILM policies, cluster settings. Without it, full restore requires manual config recreation.

---

## Pattern Catalog

### Keep JVM Heap at or Below 31GB
**Detection**:
```bash
# Check current heap for all nodes
GET /_nodes?filter_path=nodes.*.jvm.mem.heap_max_in_bytes
# Convert bytes to GB and flag if > 31GB
curl -s "$ES_HOST/_nodes/stats/jvm" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for nid, n in data['nodes'].items():
    heap_gb = n['jvm']['mem']['heap_max_in_bytes'] / (1024**3)
    flag = ' *** ABOVE 31GB ***' if heap_gb > 31 else ''
    print(f\"{n['name']}: {heap_gb:.1f}GB{flag}\")
"
```

**Signal**:
```bash
# jvm.options
-Xms64g
-Xmx64g  # 64GB — loses compressed OOPs
```

**Why this matters**: Above ~31GB, 64-bit pointers increase memory per object. A 64GB heap may hold less effective data than 31GB. GC pauses increase with heap size.

**Preferred action**: Split across two nodes rather than exceed 31GB.

---

### Re-enable Shard Allocation After Maintenance
**Detection**:
```bash
# Check allocation settings — should be 'all' during normal operation
GET /_cluster/settings?filter_path=*.cluster.routing.allocation.enable
# Anything other than 'all' or null is suspect
```

**Signal**:
```bash
# Set during maintenance window, then forgotten
PUT /_cluster/settings
{
  "transient": {
    "cluster.routing.allocation.enable": "none"
  }
}
# Maintenance completes, engineer leaves — setting persists
```

**Why this matters**: With `allocation.enable: none`, no shard assignments occur. New nodes receive nothing. Node failures cause unrecovered replicas. Cluster silently degrades to red.

**Preferred action**: After every maintenance operation, verify allocation is re-enabled:
```bash
PUT /_cluster/settings { "transient": { "cluster.routing.allocation.enable": null } }
GET /_cluster/health?wait_for_status=green&timeout=60s
```

---

### Set Replicas to 1+ on Production Indices
**Detection**:
```bash
# Find indices with number_of_replicas: 0
GET /_cat/indices?v&h=index,rep&s=rep:asc | head -20
# Any index with rep=0 in production is a risk

# Verify via settings
GET /_all/_settings?filter_path=*.settings.index.number_of_replicas
```

**Signal**:
```json
PUT /logs-2024-01
{
  "settings": {
    "number_of_replicas": 0
  }
}
```

**Why this matters**: Node failure + 0 replicas = data loss for all primaries on that node. Cluster goes RED.

**Preferred action**: `number_of_replicas: 1` minimum in production. Dev clusters: set 0 explicitly with comment.

---

### Size Shard Count to Data Volume
**Detection**:
```bash
# Check shard sizes
GET /_cat/shards?v&h=index,shard,prirep,state,store&s=store:desc

# Calculate average shard size per index
GET /_cat/indices?v&h=index,pri,store.size
# Compute: store.size / pri = avg shard size
# Target: 20-50GB per shard
```

**Signal**:
```bash
# New index created with 5 shards for a 500MB dataset
PUT /tiny-index
{
  "settings": { "number_of_shards": 5 }
}
# 5 shards of 100MB each — massive overhead for tiny data
```

**Why this matters**: Each shard has fixed overhead (file descriptors, JVM memory, cluster state). 1000 shards of 1MB = same overhead as 1000 of 50GB, but 100x slower from cross-shard coordination.

**Preferred action**: `number_of_shards: 1` for indices < 5GB. Use rollover for growing indices rather than pre-allocating many shards.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `cluster_block_exception: read-only index block` | Disk flood stage (95%) reached | Free disk space, then: `PUT /index/_settings {"index.blocks.read_only_allow_delete": null}` |
| `no_shard_available_action_exception` | All shards unassigned (cluster RED) | `GET /_cluster/allocation/explain` to diagnose; check disk space and node health |
| `primary shard is not active` | Primary shard lost (node down, no replica) | Restore from snapshot; use `GET /_cat/snapshots` |
| `circuit_breaking_exception: [parent]` | Coordinating node OOM during large operation | Reduce query scope; increase circuit breaker limit or heap |
| `TOO_MANY_REQUESTS/12/disk usage exceeded` | Disk watermark breach | Free disk > 15% or add nodes |
| Node not joining cluster | `cluster.name` mismatch or discovery misconfigured | Check `cluster.name` in `opensearch.yml` matches all nodes |
| `version conflict` on bulk index | Optimistic concurrency violation | Use `retry_on_conflict: 3` in bulk requests |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| OS 2.0 | Node role `data_content`, `data_hot`, `data_warm`, `data_cold` added | Explicit hot-warm-cold tier roles replace custom attributes |
| ES 8.0 | Security enabled by default | HTTP requires TLS; plain HTTP connections fail |
| OS 2.12 | `opensearch.yml` JVM heap options (replacing jvm.options) | Heap config can be in main config file |
| OS 2.4 | Segment replication GA | Replicas receive segment files instead of re-indexing — 30-50% less CPU |

---

## Detection Commands Reference

```bash
# Cluster health and unassigned shards
GET /_cluster/health?pretty
GET /_cat/shards?v&h=index,shard,prirep,state,unassigned.reason&s=state:desc

# JVM heap per node
GET /_nodes/stats?filter_path=nodes.*.jvm.mem.heap_max_in_bytes,nodes.*.name

# Allocation settings
GET /_cluster/settings?filter_path=*.cluster.routing.allocation.enable

# Indices with 0 replicas
GET /_cat/indices?v&h=index,rep | awk '$2 == "0" {print $1}'

# Shard size distribution
GET /_cat/shards?v&h=index,shard,prirep,store&s=store:desc | head -30

# Snapshot status
GET /_snapshot/_all
GET /_slm/policy
```

---

## See Also

- `index-management.md` — Mapping, ILM, and template configuration
- `query-optimization.md` — Query performance tuning
