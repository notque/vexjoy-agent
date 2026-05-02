# PromQL Patterns Reference

> **Scope**: PromQL query correctness, common mistakes, recording rule design
> **Version range**: Prometheus 2.0+
> **Generated**: 2026-04-09

---

## Pattern Table

| Function | Version | Use When | Avoid When |
|----------|---------|----------|------------|
| `rate()` | 2.0+ | Sustained per-second rate over a window | Short windows (< 4x scrape interval) |
| `irate()` | 2.0+ | Instantaneous rate for spike detection | Alerting rules (too spiky, flaps) |
| `increase()` | 2.0+ | Total count increase over a window | Comparing across different window sizes |
| `histogram_quantile()` | 2.0+ | Latency percentiles from histograms | Summary metrics (different type) |
| `absent()` | 2.0+ | Alert when metric stops being scraped | Checking if value is zero (use `== 0`) |
| `subquery` `[5m:1m]` | 2.3+ | Range query over instant vector function | Ad-hoc use — always create recording rule |

---

## Correct Patterns

### rate() Window Sizing

Use a window at least 4x the scrape interval. For 15s scrape, minimum window is `1m`.

```promql
rate(http_requests_total[5m])
rate(http_requests_total[1m])  # minimum for 15s scrape
```

`rate()` requires at least 2 samples. With 15s scrape and 15s window, you often get 1 sample — no data.

---

### histogram_quantile() with le Label

Always aggregate over `le` when using `histogram_quantile()`:

```promql
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)
)
```

Omitting `le` collapses all buckets, producing meaningless quantile values.

---

### Recording Rules for Alert Expressions

Pre-compute expensive aggregations as `level:metric:ops`:

```yaml
groups:
  - name: slo_rules
    interval: 30s
    rules:
      - record: job:http_requests_total:rate5m
        expr: sum(rate(http_requests_total[5m])) by (job, status)

      - record: job:http_errors_total:rate5m
        expr: sum(rate(http_requests_total{status=~"5.."}[5m])) by (job)

      - record: job:error_rate:ratio5m
        expr: |
          job:http_errors_total:rate5m
          /
          job:http_requests_total:rate5m
```

Recording rules reduce alert evaluation from O(N×samples) to O(1).

---

## Pattern Catalog
<!-- no-pair-required: section header only -->

### Use rate() Instead of irate() in Alert Rules

**Detection**:
```bash
grep -rn 'irate(' --include="*.yml" --include="*.yaml"
rg 'irate\(' --type yaml
```
<!-- no-pair-required: partial section — positive counterpart follows in next block -->

`irate()` uses only the last two samples — extremely sensitive to single-scrape spikes. Alert rules flap on transient spikes.

**Preferred action**:
```yaml
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
  for: 5m
```

---

### Add a `for:` Clause on Latency Alerts

**Detection**:
```bash
grep -B5 'latency\|duration\|p99\|p95\|quantile' --include="*.yml" --include="*.yaml" -rn | grep -v 'for:'
rg 'alert:.*[Ll]atency' --type yaml -A 10 | grep -v 'for:'
```

Without `for:`, a single evaluation above threshold fires immediately. Network hiccups produce immediate pages.

**Preferred action**:
```yaml
- alert: HighLatency
  expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 0.5
  for: 5m
  labels:
    severity: warning
```

---

### Use Pre-Computed Quantile Labels for Summary Metrics

**Detection**:
```bash
grep -rn 'histogram_quantile.*_summary\|histogram_quantile.*quantile=' --include="*.yml"
rg 'histogram_quantile' --type yaml -A 3 | grep 'quantile='
```
<!-- no-pair-required: partial section — positive counterpart follows in next block -->

Summary metrics expose pre-computed quantiles via `quantile` label — cannot be re-aggregated. Passing to `histogram_quantile()` produces nonsense (expects `le` bucket labels).

**Preferred action**:
```promql
rpc_duration_seconds{quantile="0.99", job="grpc-server"}
```

---

### Use rate() for Cross-Window Comparisons

**Detection**:
```bash
grep -rn 'increase(' --include="*.yml" --include="*.yaml" | grep -v 'record:'
```
<!-- no-pair-required: partial section — positive counterpart follows in next block -->

`increase()` results are not comparable across different window sizes without normalization.

**Preferred action**:
```promql
rate(http_requests_total[1h]) > rate(http_requests_total[24h]) * 1.5
```

---

### Use Sufficient for: Clause on Absent Alerts

**Detection**:
```bash
grep -rn 'absent(' --include="*.yml" --include="*.yaml" -A 5 | grep -v 'for:\s*[5-9][0-9]\|for:\s*[1-9][0-9][0-9]'
```

Scrape targets have momentary gaps during pod restarts. A 1-minute `for:` fires during normal K8s pod recycling.

**Preferred action**:
```yaml
- alert: MetricMissing
  expr: absent(up{job="api"})
  for: 10m
  labels:
    severity: warning
```

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| Query returns no data | Window too short (< 2 scrape intervals) | Increase to 4× scrape interval |
| `histogram_quantile` returns `NaN` | No samples or all buckets equal | Verify metric is histogram type, check le labels |
| Alert flaps every 30-60s | `irate()` or missing `for:` | Switch to `rate()`, add `for: 5m` |
| Recording rule `many-to-many` | Aggregation labels don't match join keys | Add explicit `by()` with matching labels |
| `increase()` returns non-integer | Counter reset mid-window | Expected — `increase()` handles resets |
| `rate()` returns 0 after reset | Window too short to span reset | Extend window or use `resets()` |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| 2.3 | Subquery syntax (`[5m:1m]`) | Expensive — always use recording rules |
| 2.7 | `absent_over_time()` | Better than `absent()` for intermittent metrics |
| 2.14 | Native histograms (experimental) | Different aggregation syntax |
| 2.40 | Native histograms stable | `histogram_quantile()` uses `{}` not `le` buckets |
| 2.45 | `limit_ratio()` added | Rate limiting for expensive federation queries |

---

## Detection Commands Reference

```bash
# Find irate() in alert rules
grep -rn 'irate(' --include="*.yml" --include="*.yaml"

# Find alerts missing for: clause
grep -rn '^\s*- alert:' --include="*.yml" -A 10 | grep -B5 'expr:' | grep -v 'for:'

# Find histogram_quantile on summary metrics
rg 'histogram_quantile' --type yaml -A 5 | grep 'quantile='

# Find recording rules not following level:metric:ops naming
grep -rn '^\s*record:' --include="*.yml" | grep -v 'record: [a-z_]*:[a-z_]*:[a-z_]*'

# Find absent() with short for: clause
grep -A 5 'absent(' --include="*.yml" -rn | grep 'for:\s*[1-4]m'
```

---

## See Also

- `alerting-patterns.md` — SLO burn rate, multi-window patterns, Alertmanager routing
- `cardinality-management.md` — Label cardinality detection, relabeling, TSDB analysis
