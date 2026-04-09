# Alerting Patterns Reference

> **Scope**: SLO-based alerting, multi-window burn rate, and Alertmanager configuration patterns
> **Version range**: Prometheus 2.0+ / Alertmanager 0.20+
> **Generated**: 2026-04-09 — verify burn rate math against your SLO targets

---

## Overview

SLO-based alerting is the production standard for actionable alerts. The primary failure mode is alerting on symptoms (CPU, disk, memory) that have no direct user impact, or using single-window burn rate that misses both slow and fast burns. Google's SRE book multi-window burn rate pattern detects 99% of SLO violations with low false-positive rate.

---

## SLO Burn Rate — Core Math

A burn rate of N means you're consuming your error budget N× faster than allowed.

| Burn Rate | Time to Exhaust Budget | Severity | Window |
|-----------|----------------------|----------|--------|
| 14.4× | 1 hour | Critical / Page | short: 1h, long: 5m |
| 6× | 2.5 hours | Critical / Page | short: 6h, long: 30m |
| 3× | 5 days | Warning / Ticket | short: 1d, long: 2h |
| 1× | 30 days | No alert needed | — |

**Standard multi-window SLO alert (99.9% SLO, 30-day window)**:

```yaml
groups:
  - name: slo_burn_rate
    rules:
      # Page immediately — exhausts budget in 1 hour
      - alert: SLOBurnRateCritical
        expr: |
          (
            job:slo_error_rate:ratio1h{job="api"} > (14.4 * 0.001)
            and
            job:slo_error_rate:ratio5m{job="api"} > (14.4 * 0.001)
          )
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "SLO burn rate critical: {{ $labels.job }}"
          description: "Error budget exhausted in < 1h at current rate"
          runbook_url: "https://wiki.example.com/runbooks/slo-burn-rate"

      # Ticket — exhausts budget in 2.5 hours
      - alert: SLOBurnRateHigh
        expr: |
          (
            job:slo_error_rate:ratio6h{job="api"} > (6 * 0.001)
            and
            job:slo_error_rate:ratio30m{job="api"} > (6 * 0.001)
          )
        for: 15m
        labels:
          severity: warning
```

The `0.001` is the error threshold for a 99.9% SLO (1 - 0.999). For 99.5% SLO, use `0.005`.

---

## Correct Patterns

### Alertmanager Inhibition Rules

Use inhibition to suppress lower-severity alerts when a higher-severity alert fires for the same service:

```yaml
# alertmanager.yml
inhibit_rules:
  - source_match:
      severity: critical
    target_match:
      severity: warning
    equal:
      - job
      - instance
```

**Why**: Without inhibition, a database outage fires both `DBDown (critical)` and `SlowQueries (warning)` for the same instance. On-call gets paged twice and must mentally correlate. Inhibition auto-suppresses the warning when the critical is active.

---

### Alert Grouping by Team

Group alerts before routing to team channels:

```yaml
# alertmanager.yml
route:
  group_by: [alertname, job, severity]
  group_wait: 30s      # wait 30s to batch alerts in same group
  group_interval: 5m   # send new alerts in existing group every 5m
  repeat_interval: 4h  # re-notify if still firing after 4h
  receiver: default

  routes:
    - match:
        team: platform
      receiver: platform-slack
      group_by: [alertname, cluster]

    - match:
        severity: critical
      receiver: pagerduty
      continue: true    # continue to check other routes too
```

**Why**: Without `group_by`, Alertmanager sends one notification per alert, generating 50+ Slack messages during an incident. Grouping collapses a K8s node failure (5+ firing alerts per pod) into one actionable message.

---

## Anti-Pattern Catalog

### ❌ Single-Window Burn Rate Alert

**Detection**:
```bash
grep -rn 'burn_rate\|burnrate\|error_rate.*ratio' --include="*.yml" -A 5 | grep -v 'and'
rg 'alert.*[Bb]urn' --type yaml -A 8 | grep -v 'and\s*$'
```

**What it looks like**:
```yaml
- alert: SLOBurnRate
  expr: job:error_rate:ratio5m > 0.01
  # Single window — misses slow burns over hours
```

**Why wrong**: A single 5-minute window catches fast burns (many errors quickly) but misses slow burns (few errors sustained over hours) that also exhaust the error budget. 30% of budget-exhausting incidents are slow burns invisible to single-window alerting.

**Fix**: Multi-window burn rate — require both a long window (confirming trend) and a short window (confirming it's ongoing):
```yaml
- alert: SLOBurnRate
  expr: |
    job:error_rate:ratio1h > (14.4 * 0.001)
    and
    job:error_rate:ratio5m > (14.4 * 0.001)
  for: 2m
```

---

### ❌ Alertmanager Config Without amtool Validation

**Detection**:
```bash
# Check if amtool is available and used in CI
grep -rn 'amtool' --include="Makefile" --include="*.sh" --include="*.yml"
# If no results: amtool validation is missing from deployment pipeline
```

**What it looks like**:
```bash
# alertmanager.yml applied directly without validation
kubectl apply -f alertmanager-config.yaml
# A YAML syntax error silences ALL alerts
```

**Why wrong**: A single YAML syntax error in `alertmanager.yml` causes Alertmanager to reject the config and continue using the previous valid config — or fail to start. No error surfaces in the UI until alerts fail to route. Silent alert failures are worse than loud ones.

**Fix**:
```bash
# Validate before applying
amtool check-config alertmanager.yml

# Test routing for a specific alert label set
amtool config routes test --config.file=alertmanager.yml \
  severity=critical job=api team=platform

# In CI: add this to pre-commit or CI pipeline
amtool check-config alertmanager.yml && echo "Config valid"
```

---

### ❌ Missing Runbook Annotations

**Detection**:
```bash
grep -rn '^\s*- alert:' --include="*.yml" -A 15 | grep -B 10 'severity: critical' | grep -v 'runbook'
rg 'alert:' --type yaml -A 12 | grep -B8 'severity: critical' | grep -v runbook_url
```

**What it looks like**:
```yaml
- alert: DatabaseConnectionPoolExhausted
  expr: pg_stat_activity_count > 90
  labels:
    severity: critical
  annotations:
    summary: "DB connections exhausted"
    # No runbook_url — on-call must guess remediation at 3am
```

**Why wrong**: Alerts without runbooks produce "now what?" paralysis at incident time. The 3am on-call engineer shouldn't be solving novel problems — they should be executing a known remediation. Missing runbooks convert paging alerts into learning exercises.

**Fix**:
```yaml
annotations:
  summary: "DB connections exhausted on {{ $labels.instance }}"
  description: "Connection pool at {{ $value }}/100. Spike in slow queries or leaked connections."
  runbook_url: "https://wiki.example.com/runbooks/db-connection-pool"
  dashboard_url: "https://grafana.example.com/d/db-overview?var-instance={{ $labels.instance }}"
```

---

### ❌ Routing All Alerts to a Single Receiver

**Detection**:
```bash
grep -n 'receiver:' alertmanager.yml | wc -l
# If only 1-2 unique receivers with no routes: flat routing
grep -c 'routes:' alertmanager.yml
```

**What it looks like**:
```yaml
# alertmanager.yml
route:
  receiver: all-alerts-slack  # everything goes to one channel
receivers:
  - name: all-alerts-slack
    slack_configs:
      - channel: "#alerts"
```

**Why wrong**: Mixing critical pages (database down), warnings (disk at 70%), and informational (deployment complete) into one channel trains teams to ignore the channel. Critical alerts get lost in noise. Mean time to acknowledge increases.

**Fix**: Route by severity and team:
```yaml
route:
  receiver: default
  routes:
    - match: {severity: critical}
      receiver: pagerduty
    - match: {severity: warning, team: platform}
      receiver: platform-slack
    - match: {severity: warning}
      receiver: general-slack
```

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| Alert fires then immediately resolves (flapping) | No `for:` clause or `for:` too short | Add `for: 5m` minimum to all non-critical alerts |
| Alertmanager silently stops routing alerts | YAML syntax error in config — old config still active | Run `amtool check-config` before applying; add to CI |
| No alerts during incident | Inhibition rule too broad — critical silenced warnings AND pages | Narrow `equal:` labels in inhibit_rules to specific instance |
| PagerDuty deduplication not working | Missing `source_matchers` or wrong `equal:` set | Add `equal: [alertname, job]` to inhibit rules |
| Alerts fire during rolling deployment | `absent()` alert with short `for:` | Increase `for:` to 10m+ to tolerate pod restart gaps |
| Burn rate alert never fires | Error threshold wrong for SLO (e.g., using 0.01 for 99.9%) | SLO = 99.9% → threshold = `1 - 0.999 = 0.001`, not `0.01` |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| Alertmanager 0.20 | `inhibit_rules.source_matchers` / `target_matchers` syntax | Old `source_match` / `target_match` deprecated in 0.22 |
| Alertmanager 0.22 | `matchers` field for routes (replaces `match` + `match_re`) | `match:` still works but `matchers:` is preferred |
| Alertmanager 0.25 | `time_intervals` replaces `time_intervals` in mute_time_intervals | Check config if upgrading — key rename causes silent ignore |
| Prometheus 2.28 | `for` clause resets on alert state change | Alerts that briefly resolve then re-fire restart the `for:` timer |

---

## Detection Commands Reference

```bash
# Find alerts missing for: clause
grep -rn '^\s*- alert:' --include="*.yml" -A 8 | grep -B 5 'expr:' | grep -v 'for:'

# Find single-window burn rate alerts (no 'and' multi-window)
grep -rn 'burn_rate\|error_rate.*ratio' --include="*.yml" -A 6 | grep -v '^\s*and\s'

# Find alerts without runbook annotations
grep -rn 'severity: critical' --include="*.yml" -B 10 | grep -v runbook_url

# Validate Alertmanager config syntax
amtool check-config /etc/alertmanager/alertmanager.yml

# Test alert routing for a label set
amtool config routes test severity=critical job=api
```

---

## See Also

- `promql-patterns.md` — PromQL query correctness, rate/irate pitfalls, histogram_quantile usage
- `cardinality-management.md` — Label cardinality detection and reduction before adding alert label dimensions
