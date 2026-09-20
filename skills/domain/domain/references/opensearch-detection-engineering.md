# OpenSearch detection engineering

## Local field contract

For OpenStack Keystone normalization use:

| Raw | Detection field | Type |
|---|---|---|
| `REMOTE_ADDR` | `source.ip` | `ip` |
| `HTTP_USER_AGENT` | `user_agent.original` | `text` |
| `REQUEST_METHOD` | `http.request.method` | `keyword` |
| `PATH_INFO` | `url.path` | `keyword` |
| `HTTP_X_AUTH_TOKEN` | `attributes.token_id` | `keyword` |
| `wsgi.user_id` | `user.id` | `keyword` |
| `wsgi.project_id` | `cloud.account.id` | `keyword` |
| response status | `http.response.status_code` | `integer` |

Prove mapping and type before authoring. For aggregations, inspect cardinality first; high-cardinality terms can exhaust memory.

## Rule choices

Use deterministic filters for known signatures, thresholds for abnormal rates, anomaly detection for behavioral shifts, and correlation only when evidence must join sources. SIGMA is the source rule; retain `id`, status, logsource, detection, false positives, level, and ATT&CK tags when translating to OpenSearch DSL.

Security Analytics endpoints are under `_plugins/_security_analytics/detectors`, `findings`, and `rules`. A created detector is not proof of operation: query its state and findings.

An anomaly detector can legitimately be empty during cold start; compare `shingle_size × detection_interval` before diagnosing failure. A monitor that never fires commonly has a query time range inconsistent with its schedule.

Suppress known infrastructure explicitly (CIDRs, service-account prefixes, health-check user agents, maintenance windows), and record each suppression as part of the detection.
