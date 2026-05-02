# Cardinality Management Reference

> **Scope**: Label cardinality detection, TSDB analysis, relabeling to prevent OOM
> **Version range**: Prometheus 2.0+ (TSDB analysis: 2.23+)
> **Generated**: 2026-04-09 — cardinality budgets depend on Prometheus memory allocation

---

## Cardinality Budget Reference

| Memory Available | Safe Series Count | Warning | Critical |
|------------------|-------------------|---------|----------|
| 4 GB | ~1M series | 800K | 1.2M |
| 8 GB | ~2M series | 1.6M | 2.4M |
| 16 GB | ~4M series | 3.2M | 4.8M |
| 32 GB | ~8M series | 6.4M | 9.6M |

Rule of thumb: ~4KB per active time series for index + chunks.

---

## Detection Commands

### Immediate Cardinality Check

```bash
# Total active series count
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

# TSDB analysis (2.23+)
promtool tsdb analyze /path/to/prometheus-data

# Via PromQL
topk(20, count by (__name__)({__name__=~".+"}))
```

---

## Pattern Catalog
<!-- no-pair-required: section header only -->

### Use Bounded Labels Only

**Detection**:
```bash
grep -rn 'user_id\|request_id\|session_id\|trace_id\|transaction_id' \
  --include="*.go" --include="*.py" --include="*.js" | grep -i 'label\|metric\|prometheus'

rg 'WithLabelValues|labels\.Set|prometheus\.Labels' --type go -A 3 | \
  grep -i 'user\|request_id\|session\|trace'

# Check actual cardinality in PromQL
count by (user_id) (http_requests_total)
```

**Signal**: `user_id` as label — 100K users × 50 endpoints × 5 status codes = 25M series = 100GB memory.

**Preferred action**:
```go
httpRequests.With(prometheus.Labels{
    "endpoint": endpoint,   // bounded: known set of routes
    "status":  statusCode,  // bounded: 2xx/3xx/4xx/5xx
    "method":  r.Method,    // bounded: GET/POST/PUT/DELETE
}).Inc()
// Track per-user analytics in a separate system (Kafka, ClickHouse)
```

---

### Add Relabeling Drop Rules for Internal Metrics

**Detection**:
```bash
grep -n 'action: drop\|action: keep' prometheus.yml
curl -s 'http://localhost:9090/api/v1/targets' | \
  python3 -c "import json,sys; d=json.load(sys.stdin); [print(t['labels']) for t in d['data']['activeTargets'][:5]]"
```
<!-- no-pair-required: partial section — positive counterpart follows in next block -->

Without `relabel_configs`, all K8s pod labels become Prometheus dimensions. A git commit hash label creates unique series per deployment.

**Preferred action**:
```yaml
scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        target_label: app
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
      - regex: __meta_kubernetes_.*
        action: labeldrop
      - source_labels: [app]
        regex: .+
        action: keep
```

---

### Exclude High-Cardinality Labels from Recording Rules

**Detection**:
```bash
grep -A 5 'record:' prometheus-rules.yml | grep 'by (' | grep -i 'user\|request_id\|pod_name'
rg 'record:' --type yaml -A 5 | grep 'by\s*\(' | grep -v 'service\|job\|namespace\|status'
```

**Preferred action**:
```yaml
- record: job:http_requests:rate5m
  expr: sum(rate(http_requests_total[5m])) by (job, status, method)
  # user_id intentionally excluded
```

---

### Add a Cardinality Alert

**Detection**:
```bash
grep -rn 'tsdb_head_series\|cardinality' --include="*.yml"
```

**Preferred action**:
```yaml
- alert: PrometheusHighCardinality
  expr: prometheus_tsdb_head_series > 1500000
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Prometheus series count high: {{ $value | humanize }}"
    description: "Run 'promtool tsdb analyze' to identify top contributors."
    runbook_url: "https://wiki.example.com/runbooks/prometheus-high-cardinality"

- alert: PrometheusCardinalityCritical
  expr: prometheus_tsdb_head_series > 3000000
  for: 5m
  labels:
    severity: critical
```

---

## Cardinality Reduction Playbook

```bash
# Step 1: Identify top contributors
promtool tsdb analyze /var/lib/prometheus --limit 20

# Step 2: Check which labels drive cardinality
count by (label_name) (
  {__name__="suspect_metric_name"}
)

# Step 3: Find label with highest unique values
topk(5, count by (user_id) (suspect_metric_name))

# Step 4: Add metric_relabel_config to drop after scraping
scrape_configs:
  - job_name: 'api'
    metric_relabel_configs:
      - source_labels: [__name__, user_id]
        regex: 'http_requests_total;.+'
        action: labeldrop
```

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| Prometheus OOM | Series count exceeds memory | `promtool tsdb analyze`, drop/aggregate high-cardinality labels |
| Queries timeout | Too many series scanned | Recording rules, reduce cardinality, more specific selectors |
| Scrape duration > interval | Target exposes too many metrics | `metric_relabel_configs` to drop unused metrics |
| `err="out of order"` | Clock skew | Sync NTP, check `timestamp()` in exposition |
| `many-to-many matching` | Join without enough `on()` labels | Add explicit `on()` or `ignoring()` |
| Memory grows despite stable series | Old series not GC'd | Check `--storage.tsdb.retention.time` |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| 2.23 | `promtool tsdb analyze` added | First-class cardinality analysis |
| 2.39 | Native histograms (stable) | Fixed cardinality regardless of bucket count |
| 2.43 | `--storage.tsdb.head-chunks-write-queue-size` | Tune write queue for high-ingest |
| 2.45 | `--query.max-samples` default changed | Queries >50M samples fail by default |

---

## Detection Commands Reference

```bash
# Current series count
curl -sg 'http://localhost:9090/api/v1/query?query=prometheus_tsdb_head_series' | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['result'][0]['value'][1])"

# TSDB cardinality report (2.23+)
promtool tsdb analyze /var/lib/prometheus

# Top metrics by series count (PromQL)
topk(20, count by (__name__)({__name__=~".+"}))

# Check for unbounded labels in code
grep -rn 'user_id\|request_id\|session_id' --include="*.go" | grep -i 'label\|prometheus'

# Verify relabeling drops
grep -n 'action: drop\|action: keep\|labeldrop' prometheus.yml
```

---

## See Also

- `promql-patterns.md` — Query patterns that scale as cardinality grows
- `alerting-patterns.md` — Alerting on cardinality (PrometheusHighCardinality alert template)
