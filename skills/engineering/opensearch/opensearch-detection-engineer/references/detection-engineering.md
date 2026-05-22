---
description: SIGMA rule authoring, OpenSearch DSL translation, MITRE ATT&CK mapping, detector creation API, field normalization patterns, false positive suppression
---

# Detection Engineering

Authoring detection rules for OpenSearch Security Analytics: SIGMA format, DSL translation, MITRE mapping, anomaly detector setup, correlation rules, FP suppression. Vendor-neutral methodology with OpenSearch API specifics.

> **Scope**: Detection authoring and translation patterns. Incident escalation lives in `incident-escalation.md`. Detector failure modes live in `detection-safety-patterns.md`.
> **Version range**: OpenSearch 2.x Security Analytics plugin

---

## MITRE ATT&CK Quick Reference

Every detection includes technique ID + tactic + kill chain phase. Tactic alone is insufficient.

| Tactic | ID | Common Techniques (Cloud / Identity Focus) |
|--------|-----|-------------------------------------------|
| Reconnaissance | TA0043 | T1595 (Active Scan), T1596 (Search Open Datasets) |
| Initial Access | TA0001 | T1078 (Valid Accounts), T1190 (Exploit Public App) |
| Credential Access | TA0006 | T1110 (Brute Force), T1110.001 (Password Guessing), T1110.003 (Password Spray), T1110.004 (Credential Stuffing), T1528 (Steal App Access Token) |
| Lateral Movement | TA0008 | T1550 (Use Alternate Auth Material), T1550.001 (App Access Token), T1021 (Remote Services) |
| Privilege Escalation | TA0004 | T1078.004 (Cloud Accounts), T1548 (Abuse Elevation Control) |
| Defense Evasion | TA0005 | T1578 (Modify Cloud Compute Infra), T1070 (Indicator Removal) |
| Exfiltration | TA0010 | T1537 (Transfer Data to Cloud Account), T1530 (Data from Cloud Storage) |

---

## SIGMA Rule Structure

Author detections in SIGMA first (vendor-neutral), then translate to OpenSearch DSL.

```yaml
title: Authentication Password Spray
id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
status: experimental
description: Multiple failed authentication attempts from one source against many users
author: SOC
date: 2026-05-22
logsource:
  category: authentication
  product: {your-auth-product}
detection:
  selection:
    event.outcome: failure
    url.path|contains: '/auth/tokens'
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

## SIGMA → OpenSearch DSL Translation

### Rule-based detection (filter)

```json
POST /_plugins/_security_analytics/detectors
{
  "type": "detector",
  "detector_type": "OTHERS_APPLICATION",
  "name": "auth-failure-detector",
  "enabled": true,
  "schedule": { "period": { "interval": 5, "unit": "MINUTES" } },
  "inputs": [{
    "detector_input": {
      "description": "Authentication failures",
      "indices": ["auth-logs-*"],
      "queries": [{
        "id": "auth-fail-q1",
        "name": "auth_failure_query",
        "query": "event.outcome:failure AND url.path:*auth*tokens*",
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
  "name": "password-spray-monitor",
  "enabled": true,
  "schedule": { "period": { "interval": 5, "unit": "MINUTES" } },
  "inputs": [{
    "search": {
      "indices": ["auth-logs-*"],
      "query": {
        "size": 0,
        "query": {
          "bool": {
            "filter": [
              { "term": { "event.outcome": "failure" } },
              { "wildcard": { "url.path": "*auth*tokens*" } },
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

```bash
# Create Security Analytics detector
POST /_plugins/_security_analytics/detectors

# List existing detectors
GET /_plugins/_security_analytics/detectors/_search
{ "query": { "match_all": {} } }

# Get detector findings
GET /_plugins/_security_analytics/findings/_search?detector_id={id}&startIndex=0&size=20

# Enable / disable detector
POST /_plugins/_security_analytics/detectors/{id}/_start
POST /_plugins/_security_analytics/detectors/{id}/_stop

# List custom rules
GET /_plugins/_security_analytics/rules/_search?pre_packaged=false
{ "query": { "match_all": {} } }
```

---

## Field Normalization (OpenTelemetry Semantic Conventions)

Detection rules reference normalized field names, not raw log fields. Map raw → OTel before authoring rules.

### Example: OpenStack Keystone field mapping

Keystone/WSGI logs ingested through a field-mapping pipeline use `attributes.*` for non-standard fields. Use the same pattern for any authentication source.

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

### Cardinality check before adding to aggregation

```bash
POST /auth-logs-*/_search
{
  "size": 0,
  "aggs": {
    "field_cardinality": {
      "cardinality": { "field": "source.ip" }
    }
  }
}
```

High-cardinality fields (>100k unique values) in `terms` buckets cause heap pressure. Use `filter` + `cardinality` instead of `terms` for high-cardinality keys.

---

## Detection Methodology Selection

| Scenario | Methodology | Why |
|----------|-------------|-----|
| Known bad pattern (specific URL abuse, exact CVE signature) | Rule-based | Low latency, deterministic, low FP |
| Abnormal rate (50 failures / 5 min) | Threshold-based | Tunable, fast, explainable |
| Subtle behavioral shift (time-of-day anomaly) | Anomaly-based | Catches slow-burn attacks; higher FP rate |
| Multi-source correlation (auth + network + IAM) | Correlation rule | Required for lateral movement detection |

---

## Anomaly Detector Setup

```bash
POST /_plugins/_anomaly_detection/detectors
{
  "name": "auth-volume-anomaly",
  "description": "Anomalous authentication volume per source IP",
  "time_field": "@timestamp",
  "indices": ["auth-logs-*"],
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

**Cold start**: Model requires `shingle_size * 2` intervals (16 intervals = 80 min at 5-min detection) before producing results. Run historical analysis first on production rollouts:

```bash
POST /_plugins/_anomaly_detection/detectors/{id}/_start
{
  "start_time": 1700000000000,
  "end_time": 1700086400000
}
```

---

## False Positive Suppression

| Pattern | Suppression Approach | Where |
|---------|---------------------|-------|
| Known IP CIDR (internal LBs, monitoring) | `bool.must_not: [{ "cidr": { "field": "source.ip", "value": "10.0.0.0/8" } }]` | Filter in monitor query |
| Service account prefix (e.g., `svc-*`) | `bool.must_not: [{ "wildcard": { "user.name": "svc-*" } }]` | Filter in monitor query |
| Known-good user-agent (health checks) | `bool.must_not: [{ "match": { "user_agent.original": "healthcheck" } }]` | Filter in monitor query |
| Time-window suppression (maintenance) | `range: @timestamp: { gte/lte: ... }` | Add to trigger condition |

### Threshold calibration process

1. Run monitor in dry-run mode for 5 business days
2. Export findings: `GET /_plugins/_security_analytics/findings/_search`
3. Label TPs and FPs manually
4. Adjust threshold (e.g., cardinality count) until FP rate ≤ 10%
5. Document threshold decision in use case lifecycle doc

---

## Correlation Rule Example

```bash
POST /_plugins/_security_analytics/correlation/rules
{
  "name": "auth-then-lateral-movement",
  "correlate": [
    {
      "index": "auth-logs-*",
      "query": "event.outcome:failure AND url.path:*auth*tokens*",
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

## Example: Detection Authoring Walkthrough (Keystone Password Spray)

End-to-end example — substitute your own auth source for the same flow.

1. **Scope**: T1110.003 (Password Spray), Credential Access tactic, severity High.
2. **Field check**: `GET /keystone-logs-*/_mapping/field/source.ip,user.name,event.outcome,url.path` — confirm types are `ip`, `keyword`, `keyword`, `keyword`.
3. **SIGMA rule**: written as in the SIGMA Rule Structure section above.
4. **Translate** to bucket-level monitor (Threshold methodology).
5. **FP suppression**: exclude internal LB CIDR `10.0.0.0/8` and service-account prefix `svc-*`.
6. **Calibrate**: 5-day dry run, label findings, tune `unique_users >= 5` if FP rate exceeds 10%.
7. **Document**: 6-section use case (see `incident-escalation.md` template).

---

## Error → Fix Mapping

| Error | Root Cause | Fix |
|-------|------------|-----|
| `field [X] not found` on detector create | Field absent from index mapping | `GET {index}/_mapping`; add field or adjust rule |
| Detector in FAILED state after creation | Bootstrap conflict on shared index | See `detection-safety-patterns.md` |
| Anomaly detector no results after 2 hours | Cold start not complete | Check `shingle_size × detection_interval`; run historical mode |
| Monitor trigger never fires | Wrong time range in query | Verify `range.@timestamp.gte` matches monitor schedule |
| High FP rate on threshold monitor | Threshold too low or missing IP allowlist | Add CIDR exclusion filter; recalibrate |

---

## See Also

- `detection-safety-patterns.md`: Field alias bootstrap conflicts, chained findings index flood
- `incident-escalation.md`: Severity tiers, escalation packages, KPIs
