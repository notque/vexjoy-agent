# PromQL Patterns Reference

> **Scope**: PromQL query correctness, common expression mistakes, and recording rule design
> **Version range**: Prometheus 2.0+ (most patterns apply to all 2.x)
> **Generated**: 2026-04-09 — verify against current Prometheus release notes

---

## Overview

PromQL is a functional query language where small mistakes produce silently wrong results rather than errors. The most common failure mode is using `rate()` or `increase()` incorrectly — queries return numbers that look plausible but are mathematically wrong. Detection requires knowing what correct output looks like, not just that the query runs.

---

## Pattern Table

| Function | Version | Use When | Avoid When |
|----------|---------|----------|------------|
| `rate()` | 2.0+ | Sustained per-second rate over a window | Short windows (< 4x scrape interval) |
| `irate()` | 2.0+ | Instantaneous rate for spike detection | Alerting rules (too spiky, flaps) |
| `increase()` | 2.0+ | Total count increase over a window | Comparing across different window sizes |
| `histogram_quantile()` | 2.0+ | Latency percentiles from histograms | Summary metrics (different type) |
| `absent()` | 2.0+ | Alert when a metric stops being scraped | Checking if a value is zero (use `== 0`) |
| `subquery` `[5m:1m]` | 2.3+ | Range query over instant vector function | Ad-hoc use — always create recording rule |

---

## Correct Patterns

### rate() Window Sizing

Use a window at least 4x the scrape interval. For a 15s scrape interval, minimum window is `1m`.

```promql
# Correct — 5m window with 15s scrape interval
rate(http_requests_total[5m])

# Correct — 1m minimum window for 15s scrape
rate(http_requests_total[1m])
```

**Why**: `rate()` requires at least 2 samples in the window to compute a slope. With a 15s scrape interval and a 15s window, you often get only 1 sample, returning no data or stale results.

---

### histogram_quantile() with le Label

Always aggregate over the `le` label when using `histogram_quantile()`:

```promql
# Correct — aggregate over le bucket boundaries
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)
)

# Correct — single service with explicit le
histogram_quantile(0.95,
  rate(http_request_duration_seconds_bucket{service="api"}[5m])
)
```

**Why**: Omitting `le` in the aggregation collapses all buckets together, producing meaningless quantile values. The `le` label defines the bucket boundaries that `histogram_quantile()` uses for interpolation.

---

### Recording Rules for Alert Expressions

Pre-compute expensive aggregations as recording rules named by convention `level:metric:ops`:

```yaml
# recording_rules.yml
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

**Why**: Alert expressions evaluated every 15-30s against raw counters scan all samples in the window repeatedly. Recording rules pre-aggregate, reducing evaluation from O(N×samples) to O(1).

---

## Anti-Pattern Catalog

### ❌ Using irate() in Alert Rules

**Detection**:
```bash
grep -rn 'irate(' --include="*.yml" --include="*.yaml"
rg 'irate\(' --type yaml
```

**What it looks like**:
```yaml
# alert_rules.yml
- alert: HighErrorRate
  expr: irate(http_requests_total{status=~"5.."}[5m]) > 0.01
```

**Why wrong**: `irate()` uses only the last two samples, making it extremely sensitive to single-scrape spikes. Alert rules evaluated every 30s will flap on transient spikes, generating spurious notifications. Production alert fatigue follows.

**Fix**:
```yaml
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
  for: 5m  # also add a for: clause to require sustained violation
```

---

### ❌ Missing `for:` Clause on Latency Alerts

**Detection**:
```bash
grep -B5 'latency\|duration\|p99\|p95\|quantile' --include="*.yml" --include="*.yaml" -rn | grep -v 'for:'
rg 'alert:.*[Ll]atency' --type yaml -A 10 | grep -v 'for:'
```

**What it looks like**:
```yaml
- alert: HighLatency
  expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 0.5
  # No for: clause!
```

**Why wrong**: Without `for:`, a single evaluation above the threshold fires the alert immediately. Network hiccups, deployment restarts, or pod scheduling create transient spikes that produce immediate pages. The signal-to-noise ratio degrades fast.

**Fix**:
```yaml
- alert: HighLatency
  expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 0.5
  for: 5m  # must sustain for 5 minutes before firing
  labels:
    severity: warning
```

---

### ❌ Querying Summaries with histogram_quantile()

**Detection**:
```bash
grep -rn 'histogram_quantile.*_summary\|histogram_quantile.*quantile=' --include="*.yml"
rg 'histogram_quantile' --type yaml -A 3 | grep 'quantile='
```

**What it looks like**:
```promql
# Wrong — using histogram_quantile on a summary type metric
histogram_quantile(0.99, rate(rpc_duration_seconds{quantile="0.99"}[5m]))
```

**Why wrong**: Summary metrics expose pre-computed quantiles (via the `quantile` label) that cannot be re-aggregated. Passing them to `histogram_quantile()` produces nonsense — the function expects `le` bucket labels, not pre-computed quantile values. The query may not error but will silently return wrong numbers.

**Fix**: Use the pre-computed quantile label directly:
```promql
# Correct for summary metrics
rpc_duration_seconds{quantile="0.99", job="grpc-server"}
```

Version note: This confusion is extremely common when migrating from libraries that default to summary type. Check metric type with `{__name__="metric_name"}` metadata query.

---

### ❌ Using `increase()` Across Different Windows for Comparison

**Detection**:
```bash
grep -rn 'increase(' --include="*.yml" --include="*.yaml" | grep -v 'record:'
```

**What it looks like**:
```promql
# Wrong — comparing increase over different windows
increase(http_requests_total[1h]) > increase(http_requests_total[24h]) * 0.1
```

**Why wrong**: `increase()` results are not comparable across different window sizes without normalization. This expression always evaluates false since 1h increase is always < 24h × 0.1 for any reasonable traffic. Use `rate()` for comparisons.

**Fix**:
```promql
# Correct — compare rates
rate(http_requests_total[1h]) > rate(http_requests_total[24h]) * 1.5
```

---

### ❌ Absent Alert Without Sufficient For Clause

**Detection**:
```bash
grep -rn 'absent(' --include="*.yml" --include="*.yaml" -A 5 | grep -v 'for:\s*[5-9][0-9]\|for:\s*[1-9][0-9][0-9]'
```

**What it looks like**:
```yaml
- alert: MetricMissing
  expr: absent(up{job="api"})
  for: 1m  # too short — scrape gaps cause false positives
```

**Why wrong**: Scrape targets can have momentary gaps during pod restarts, rolling deployments, or network blips. A 1-minute `for:` fires during normal K8s pod recycling. This produces alert storms during every deployment.

**Fix**:
```yaml
- alert: MetricMissing
  expr: absent(up{job="api"})
  for: 10m  # tolerate pod restarts and rolling updates
  labels:
    severity: warning
```

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| Query returns no data but metric exists | Window too short (< 2 scrape intervals) | Increase window to 4× scrape interval |
| `histogram_quantile` returns `NaN` | No samples in bucket or all buckets equal | Check if metric is a histogram type, verify le labels exist |
| Alert flaps every 30-60 seconds | Using `irate()` or missing `for:` clause | Switch to `rate()`, add `for: 5m` |
| Recording rule shows `many-to-many` error | Aggregation labels don't match join keys | Add explicit `by()` clause with matching labels on both sides |
| `increase()` shows non-integer values | Counter reset mid-window (pod restart) | Expected behavior — `increase()` handles resets but result is fractional |
| `rate()` returns 0 after counter reset | Window too short to span the reset | Extend window or use `resets()` to detect reset count |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| 2.3 | Subquery syntax added (`[5m:1m]`) | Can run instant functions over ranges — expensive, always use recording rules |
| 2.7 | `absent_over_time()` added | Better than `absent()` for intermittent metrics with irregular scrape |
| 2.14 | Native histograms (experimental) | Different aggregation — `histogram_quantile()` syntax changes for native type |
| 2.40 | Native histograms stable | `histogram_quantile()` on native histograms uses `{}` not `le` buckets |
| 2.45 | `limit_ratio()` added | Rate limiting for query evaluation — useful for expensive federation queries |

---

## Detection Commands Reference

```bash
# Find irate() in alert rules (should use rate() instead)
grep -rn 'irate(' --include="*.yml" --include="*.yaml"

# Find alerts missing for: clause
grep -rn '^\s*- alert:' --include="*.yml" -A 10 | grep -B5 'expr:' | grep -v 'for:'

# Find histogram_quantile on summary metrics (has quantile= label)
rg 'histogram_quantile' --type yaml -A 5 | grep 'quantile='

# Find recording rules that don't follow level:metric:ops naming
grep -rn '^\s*record:' --include="*.yml" | grep -v 'record: [a-z_]*:[a-z_]*:[a-z_]*'

# Find absent() with short for: clause (< 5 minutes)
grep -A 5 'absent(' --include="*.yml" -rn | grep 'for:\s*[1-4]m'
```

---

## See Also

- `alerting-patterns.md` — SLO burn rate alerts, multi-window patterns, Alertmanager routing
- `cardinality-management.md` — Label cardinality detection, relabeling rules, TSDB analysis
