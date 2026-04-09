# Cardinality Management Reference

> **Scope**: Label cardinality detection, TSDB analysis, and relabeling to prevent OOM
> **Version range**: Prometheus 2.0+ (TSDB analysis tools: 2.23+)
> **Generated**: 2026-04-09 — cardinality budgets depend on Prometheus memory allocation

---

## Overview

High cardinality is the #1 cause of Prometheus OOM in production. Each unique combination of label values creates one time series. A metric with `{service, endpoint, status, user_id}` and 1,000 users × 100 endpoints × 5 statuses = 500,000 series — from one metric. The failure mode is gradual: query performance degrades first, then OOM kills under query load. Detection must be proactive, not reactive.

---

## Cardinality Budget Reference

| Memory Available | Safe Series Count | Warning Threshold | Critical Threshold |
|------------------|-------------------|-------------------|--------------------|
| 4 GB | ~1M series | 800K | 1.2M |
| 8 GB | ~2M series | 1.6M | 2.4M |
| 16 GB | ~4M series | 3.2M | 4.8M |
| 32 GB | ~8M series | 6.4M | 9.6M |

Rule of thumb: Prometheus uses ~4KB per active time series for index + chunks in memory.

---

## Detection Commands

### Immediate Cardinality Check

```bash
# Total active series count (requires HTTP API access)
curl -s 'http://localhost:9090/api/v1/query?query=prometheus_tsdb_head_series' | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['result'][0]['value'][1])"

# Top 20 metrics by series count
curl -s 'http://localhost:9090/api/v1/label/__name__/values' | \
  python3 -c "
import json, sys, subprocess, re
data = json.load(sys.stdin)
counts = []
for m in data['data'][:50]:  # sample first 50
    r = subprocess.run(['curl','-s', f'http://localhost:9090/api/v1/query?query=count({{__name__=\"{m}\"}} )'],
                       capture_output=True, text=True)
    val = json.loads(r.stdout)
    if val.get('data', {}).get('result'):
        counts.append((m, int(val['data']['result'][0]['value'][1])))
counts.sort(key=lambda x: -x[1])
for m, c in counts[:20]: print(f'{c:>10}  {m}')
"

# Prometheus TSDB analysis (requires promtool, Prometheus 2.23+)
promtool tsdb analyze /path/to/prometheus-data

# Check series count by metric name via PromQL
topk(20, count by (__name__)({__name__=~".+"}))
```

---

## Anti-Pattern Catalog

### ❌ High-Cardinality Labels (user_id, request_id, session_id)

**Detection**:
```bash
# Find instrumentation code with potentially unbounded label values
grep -rn 'user_id\|request_id\|session_id\|trace_id\|transaction_id' \
  --include="*.go" --include="*.py" --include="*.js" | grep -i 'label\|metric\|prometheus'

rg 'WithLabelValues|labels\.Set|prometheus\.Labels' --type go -A 3 | \
  grep -i 'user\|request_id\|session\|trace'

# Check actual cardinality of suspect metrics in PromQL
count by (user_id) (http_requests_total)  # should return 0 results if correctly designed
```

**What it looks like**:
```go
// Go example — unbounded label
httpRequests.With(prometheus.Labels{
    "user_id": userID,      // WRONG: unbounded
    "endpoint": endpoint,
    "status":  strconv.Itoa(statusCode),
}).Inc()
```

**Why wrong**: 100K users × 50 endpoints × 5 status codes = 25M series. Prometheus memory usage becomes `25M × 4KB = 100GB`. Queries against this metric scan all 25M series even with filters, because index lookup is by label, not by value range.

**Fix**:
```go
// Correct — bounded labels only
httpRequests.With(prometheus.Labels{
    "endpoint": endpoint,   // bounded: known set of routes
    "status":  statusCode,  // bounded: 2xx/3xx/4xx/5xx
    "method":  r.Method,    // bounded: GET/POST/PUT/DELETE
}).Inc()
// Track per-user analytics in a separate system (Kafka, ClickHouse)
```

---

### ❌ No Relabeling Drop Rules for Internal Metrics

**Detection**:
```bash
# Check if prometheus.yml has any drop relabeling rules
grep -n 'action: drop\|action: keep' prometheus.yml
# If no results: no cardinality guardrails in scrape config

# Check what labels are coming in from a target
curl -s 'http://localhost:9090/api/v1/targets' | \
  python3 -c "import json,sys; d=json.load(sys.stdin); [print(t['labels']) for t in d['data']['activeTargets'][:5]]"
```

**What it looks like**:
```yaml
# prometheus.yml — no relabeling
scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    # No relabel_configs — ingests all labels from pod annotations
```

**Why wrong**: Kubernetes pods can expose dozens of labels (app, version, helm-release, git-commit, build-time, namespace). Without `relabel_configs`, all of these become Prometheus label dimensions. A git commit hash label creates unique series per deployment, exploding cardinality.

**Fix**:
```yaml
scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      # Keep only the labels you actually need
      - source_labels: [__meta_kubernetes_pod_label_app]
        target_label: app
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
      # Drop all other __meta_ labels (they're huge and mostly unused)
      - regex: __meta_kubernetes_.*
        action: labeldrop
      # Drop pods with no app label (system pods you don't care about)
      - source_labels: [app]
        regex: .+
        action: keep
```

---

### ❌ Recording Rules That Don't Reduce Cardinality

**Detection**:
```bash
# Find recording rules that preserve high-cardinality labels
grep -A 5 'record:' prometheus-rules.yml | grep 'by (' | grep -i 'user\|request_id\|pod_name'
rg 'record:' --type yaml -A 5 | grep 'by\s*\(' | grep -v 'service\|job\|namespace\|status'
```

**What it looks like**:
```yaml
- record: job:http_requests:rate5m
  expr: sum(rate(http_requests_total[5m])) by (job, user_id)
  # Aggregates but still fans out by user_id — doesn't help
```

**Why wrong**: Recording rules are meant to reduce query cost by pre-aggregating. If the `by()` clause includes a high-cardinality label, the recording rule creates as many series as the original metric, with no benefit.

**Fix**:
```yaml
# Drop high-cardinality dimensions in recording rules
- record: job:http_requests:rate5m
  expr: sum(rate(http_requests_total[5m])) by (job, status, method)
  # user_id intentionally excluded — aggregate user metrics in application layer
```

---

### ❌ No Cardinality Alert

**Detection**:
```bash
grep -rn 'tsdb_head_series\|cardinality' --include="*.yml"
# If no results: no proactive cardinality monitoring
```

**What it looks like**: No alert for growing series count — OOM is the first signal.

**Why wrong**: Cardinality growth is gradual. A new deployment adds 50K series per day unnoticed until Prometheus hits memory limits under query load 2 weeks later. By then, the causing deployment is long merged and difficult to identify.

**Fix**:
```yaml
- alert: PrometheusHighCardinality
  expr: prometheus_tsdb_head_series > 1500000
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Prometheus series count high: {{ $value | humanize }}"
    description: "Cardinality approaching memory limits. Run 'promtool tsdb analyze' to identify top contributors."
    runbook_url: "https://wiki.example.com/runbooks/prometheus-high-cardinality"

- alert: PrometheusCardinalityCritical
  expr: prometheus_tsdb_head_series > 3000000
  for: 5m
  labels:
    severity: critical
```

---

## Cardinality Reduction Playbook

When `promtool tsdb analyze` identifies a high-cardinality metric:

```bash
# Step 1: Identify top contributors
promtool tsdb analyze /var/lib/prometheus --limit 20

# Step 2: Check which labels drive cardinality for a specific metric
count by (label_name) (
  {__name__="suspect_metric_name"}
)

# Step 3: Find the label with highest unique values
topk(5, count by (user_id) (suspect_metric_name))

# Step 4: Add a metric_relabel_config to drop the label AFTER scraping
# (metric_relabel_configs apply post-scrape, before storage)
scrape_configs:
  - job_name: 'api'
    metric_relabel_configs:
      - source_labels: [__name__, user_id]
        regex: 'http_requests_total;.+'
        action: labeldrop
        # or use replacement to bucket: user_id → user_tier
```

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| Prometheus OOM killed | Series count exceeds memory budget | Run `promtool tsdb analyze`, drop or aggregate high-cardinality labels |
| Queries timeout on dashboards | Too many series scanned per query | Add recording rules, reduce label cardinality, use more specific label selectors |
| Scrape duration > scrape interval | Target exposes too many metrics or slow `/metrics` | Add `metric_relabel_configs` to drop unused metrics, check target performance |
| `err="out of order"` in Prometheus logs | Clock skew between scrape target and Prometheus | Sync NTP on target, check if using `timestamp()` in exposition |
| `many-to-many matching not allowed` | Join between two high-cardinality metrics without enough `on()` labels | Add explicit `on()` or `ignoring()` labels to the join expression |
| Series count stable but memory grows | Old time series not being garbage collected | Check `--storage.tsdb.retention.time` — default 15d, may need to lower |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| 2.23 | `promtool tsdb analyze` command added | First-class cardinality analysis without external tools |
| 2.39 | Native histograms (stable) | Native histograms have fixed cardinality regardless of bucket count — major cardinality win |
| 2.43 | `--storage.tsdb.head-chunks-write-queue-size` flag | Tune write queue for high-ingest scenarios |
| 2.45 | `--query.max-samples` default changed | Queries that scan >50M samples now fail by default — catches runaway cardinality queries |

---

## Detection Commands Reference

```bash
# Current series count
curl -sg 'http://localhost:9090/api/v1/query?query=prometheus_tsdb_head_series' | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['result'][0]['value'][1])"

# TSDB cardinality report (2.23+)
promtool tsdb analyze /var/lib/prometheus

# Top metrics by series count (PromQL)
topk(20, count by (__name__)({__name__=~".+"}))

# Check for unbounded labels in instrumentation code
grep -rn 'user_id\|request_id\|session_id' --include="*.go" | grep -i 'label\|prometheus'

# Verify relabeling drops are in place
grep -n 'action: drop\|action: keep\|labeldrop' prometheus.yml
```

---

## See Also

- `promql-patterns.md` — Query patterns that scale as cardinality grows
- `alerting-patterns.md` — Alerting on cardinality (PrometheusHighCardinality alert template)
