---
description: SIGMA rule authoring, OpenSearch DSL translation, MITRE ATT&CK mapping, detector creation API, field normalization patterns, false positive suppression
---

# OpenSearch SIEM Detection Engineering

> **Scope**: Detection authoring, SIGMA-to-DSL translation, MITRE mapping, field normalization for OpenSearch Security Analytics. Does not cover incident escalation (see incident-escalation.md) or mapping failures (see mapping-troubleshooting.md).
> **Version range**: OpenSearch 2.x Security Analytics plugin
> **Generated**: 2026-05-22

---

## MITRE ATT&CK Quick Reference

| Tactic | ID Range | Common Techniques for Cloud Identity |
|--------|----------|--------------------------------------|
| Reconnaissance | TA0043 | T1595 (Active Scan), T1596 (Search Open Datasets) |
| Initial Access | TA0001 | T1078 (Valid Accounts), T1190 (Exploit Public App) |
| Credential Access | TA0006 | T1110 (Brute Force), T1110.001 (Password Guessing), T1110.003 (Password Spray), T1110.004 (Credential Stuffing), T1528 (Steal App Access Token) |
| Lateral Movement | TA0008 | T1550 (Use Alternate Auth Material), T1550.001 (App Access Token) |
| Privilege Escalation | TA0004 | T1078.004 (Cloud Accounts), T1548 (Abuse Elevation Control) |
| Defense Evasion | TA0005 | T1578 (Modify Cloud Compute Infra), T1070 (Indicator Removal) |
| Exfiltration | TA0010 | T1537 (Transfer Data to Cloud Account), T1530 (Data from Cloud Storage) |

**Keystone/OpenStack specific**: T1110.003 (password spray on `/v3/auth/tokens`), T1528 (application credential abuse), T1078.004 (cloud account takeover via token replay).

---

## SIGMA Rule Structure

```yaml
title: Keystone Password Spray
id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
status: experimental
description: Multiple failed authentication attempts from a single source against different user accounts
author: SOC
date: 2026-05-22
logsource:
  category: authentication
  product: openstack
detection:
  selection:
    event.outcome: failure
    url.path|contains: '/v3/auth/tokens'
  condition: selection | count(user.name) by source.ip > 5
falsepositives:
  - Misconfigured service accounts
  - Load balancer health checks
level: high
tags:
  - attack.credential_access
  - attack.t1110.003
```

---

## SIGMA to OpenSearch DSL Translation

### Rule-based detection (simple filter)

```json
POST /_plugins/_security_analytics/detectors
{
  "type": "detector",
  "detector_type": "OTHERS_APPLICATION",
  "name": "keystone-auth-failure",
  "enabled": true,
  "schedule": { "period": { "interval": 5, "unit": "MINUTES" } },
  "inputs": [{
    "detector_input": {
      "description": "Keystone authentication failures",
      "indices": ["keystone-logs-*"],
      "queries": [{
        "id": "keystone-auth-fail-q1",
        "name": "auth_failure_query",
        "query": "event.outcome:failure AND url.path:*v3*auth*tokens*",
        "tags": ["attack.credential_access", "attack.t1110"]
      }]
    }
  }],
  "triggers": [{
    "detector_trigger": {
      "name": "High Failure Rate",
      "severity": "3",
      "types": ["rules"],
      "sev_levels": ["high", "critical"],
      "tags": ["attack.t1110"]
    }
  }]
}
```

### Threshold-based detection (aggregation)

```json
POST /_plugins/_alerting/monitors
{
  "type": "monitor",
  "monitor_type": "bucket_level_monitor",
  "name": "keystone-password-spray",
  "enabled": true,
  "schedule": { "period": { "interval": 5, "unit": "MINUTES" } },
  "inputs": [{
    "search": {
      "indices": ["keystone-logs-*"],
      "query": {
        "size": 0,
        "query": {
          "bool": {
            "filter": [
              { "term": { "event.outcome": "failure" } },
              { "wildcard": { "url.path": "*v3*auth*tokens*" } },
              { "range": { "@timestamp": { "gte": "now-5m" } } }
            ]
          }
        },
        "aggs": {
          "source_ips": {
            "terms": { "field": "source.ip", "size": 100 },
            "aggs": {
              "unique_users": {
                "cardinality": { "field": "user.name" }
              }
            }
          }
        }
      }
    }
  }],
  "triggers": [{
    "bucket_level_trigger": {
      "name": "spray_threshold",
      "severity": "2",
      "condition": {
        "buckets_path": { "unique_users": "unique_users" },
        "parent_bucket_path": "source_ips",
        "script": {
          "source": "params.unique_users >= 5",
          "lang": "painless"
        }
      },
      "actions": []
    }
  }]
}
```

---

## Detector Creation API

### Create Security Analytics detector

```bash
POST /_plugins/_security_analytics/detectors
```

### List existing detectors

```bash
GET /_plugins/_security_analytics/detectors/_search
{
  "query": { "match_all": {} }
}
```

### Get detector findings

```bash
GET /_plugins/_security_analytics/findings/_search?detector_id={id}&startIndex=0&size=20
```

### Enable/disable detector

```bash
POST /_plugins/_security_analytics/detectors/{id}/_start
POST /_plugins/_security_analytics/detectors/{id}/_stop
```

### List custom rules

```bash
GET /_plugins/_security_analytics/rules/_search?pre_packaged=false
{
  "query": { "match_all": {} }
}
```

---

## Field Normalization: OTel Semantic Conventions

Keystone/WSGI logs ingested via Fluentd use `attributes.*` prefix for non-standard fields.

| Raw Keystone Field | OTel Mapped Field | Type |
|--------------------|-------------------|------|
| `REMOTE_ADDR` | `source.ip` | `ip` |
| `HTTP_USER_AGENT` | `user_agent.original` | `text` |
| `REQUEST_METHOD` | `http.request.method` | `keyword` |
| `PATH_INFO` | `url.path` | `keyword` |
| `HTTP_X_AUTH_TOKEN` | `attributes.token_id` | `keyword` |
| `wsgi.user_id` | `user.id` | `keyword` |
| `wsgi.project_id` | `cloud.account.id` | `keyword` |
| HTTP response status | `http.response.status_code` | `integer` |

**Cardinality check before adding field to aggregation:**

```bash
POST /keystone-logs-*/_search
{
  "size": 0,
  "aggs": {
    "field_cardinality": {
      "cardinality": { "field": "source.ip" }
    }
  }
}
```

High-cardinality fields (>100k unique values) in aggregation `terms` buckets cause heap pressure. Use `filter` + `cardinality` instead of `terms` for high-cardinality keys.

---

## Detection Methodology Selection

| Scenario | Methodology | Why |
|----------|-------------|-----|
| Known bad pattern (e.g., specific URL path abuse) | Rule-based | Low latency, deterministic, low FP |
| Abnormal rate (e.g., 50 failed logins in 5 min) | Threshold-based | Tunable, fast, explainable |
| Subtle behavioral shift (e.g., time-of-day anomaly) | Anomaly-based | Catches slow-burn attacks; higher FP rate |
| Multi-source correlation (auth + network + IAM) | Correlation rule | Required for lateral movement detection |

---

## Anomaly Detector Setup

```bash
POST /_plugins/_anomaly_detection/detectors
{
  "name": "keystone-auth-anomaly",
  "description": "Anomalous authentication volume per source IP",
  "time_field": "@timestamp",
  "indices": ["keystone-logs-*"],
  "feature_attributes": [{
    "feature_name": "failed_auth_count",
    "feature_enabled": true,
    "aggregation_query": {
      "failed_auths": {
        "filter": { "term": { "event.outcome": "failure" } }
      }
    }
  }],
  "detection_interval": { "period": { "interval": 5, "unit": "Minutes" } },
  "window_delay": { "period": { "interval": 1, "unit": "Minutes" } },
  "category_field": ["source.ip"],
  "shingle_size": 8
}
```

**Cold start**: Model requires `shingle_size * 2` intervals (16 intervals = 80 min at 5-min detection interval) before producing results. Run historical analysis first on production rollouts:

```bash
POST /_plugins/_anomaly_detection/detectors/{id}/_start
{
  "start_time": 1700000000000,
  "end_time": 1700086400000
}
```

---

## False Positive Suppression

| Pattern | Suppression Approach | API |
|---------|---------------------|-----|
| Known IP CIDR (internal load balancers, monitoring) | `bool.must_not: [{ "cidr": { "field": "source.ip", "value": "10.0.0.0/8" } }]` | Filter in monitor query |
| Service account prefix (e.g., `svc-*`) | `bool.must_not: [{ "wildcard": { "user.name": "svc-*" } }]` | Filter in monitor query |
| Known-good user-agent (health checks) | `bool.must_not: [{ "match": { "user_agent.original": "healthcheck" } }]` | Filter in monitor query |
| Time-window suppression (maintenance windows) | `range: @timestamp: { gte/lte: ... }` | Add to trigger condition |

**Threshold calibration process:**
1. Run monitor in dry-run mode for 5 business days
2. Export findings: `GET /_plugins/_security_analytics/findings/_search`
3. Label FPs and TPs manually
4. Adjust threshold (e.g., cardinality count) until FP rate <= 10%
5. Document threshold decision in use case lifecycle doc

---

## Correlation Rule Example

```bash
POST /_plugins/_security_analytics/correlation/rules
{
  "name": "auth-then-lateral-movement",
  "correlate": [
    {
      "index": "keystone-logs-*",
      "query": "event.outcome:failure AND url.path:*v3*auth*tokens*",
      "category": "credential_access",
      "tags": ["attack.t1110.003"]
    },
    {
      "index": "network-logs-*",
      "query": "destination.port:(22 OR 3389 OR 5985) AND event.action:connection",
      "category": "lateral_movement",
      "tags": ["attack.t1021"]
    }
  ],
  "time_window": 600
}
```

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `field [X] not found` on detector create | Field absent from index mapping | `GET index/_mapping`; add field or adjust rule |
| Detector in FAILED state after creation | Bootstrap conflict on shared index | See mapping-troubleshooting.md |
| Anomaly detector no results after 2 hours | Cold start not complete | Check shingle_size × detection_interval; run historical mode |
| Monitor trigger never fires | Wrong time range in query | Verify `range.@timestamp.gte` matches monitor schedule |
| High FP rate on threshold monitor | Threshold too low or missing IP allowlist | Add CIDR exclusion filter; recalibrate threshold |

---

## See Also

- `mapping-troubleshooting.md` — Field alias bootstrap conflicts, chained findings index flood
- `incident-escalation.md` — Severity tiers, escalation packages, KPIs
