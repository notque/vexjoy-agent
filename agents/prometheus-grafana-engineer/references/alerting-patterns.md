# Alerting Patterns Reference

> **Scope**: SLO-based alerting, multi-window burn rate, Alertmanager configuration
> **Version range**: Prometheus 2.0+ / Alertmanager 0.20+
> **Generated**: 2026-04-09 — verify burn rate math against your SLO targets

---

## SLO Burn Rate — Core Math

A burn rate of N means you're consuming error budget N× faster than allowed.

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

The `0.001` is the error threshold for 99.9% SLO (1 - 0.999). For 99.5% SLO, use `0.005`.

---

## Correct Patterns

### Alertmanager Inhibition Rules

Suppress lower-severity alerts when a higher-severity alert fires for the same service:

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

---

### Alert Grouping by Team

```yaml
# alertmanager.yml
route:
  group_by: [alertname, job, severity]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: default

  routes:
    - match:
        team: platform
      receiver: platform-slack
      group_by: [alertname, cluster]

    - match:
        severity: critical
      receiver: pagerduty
      continue: true
```

Without `group_by`, Alertmanager sends one notification per alert — 50+ Slack messages during an incident. Grouping collapses related alerts into one message.

---

## Pattern Catalog
<!-- no-pair-required: section header only -->

### Use Multi-Window Burn Rate Alerts

**Detection**:
```bash
grep -rn 'burn_rate\|burnrate\|error_rate.*ratio' --include="*.yml" -A 5 | grep -v 'and'
rg 'alert.*[Bb]urn' --type yaml -A 8 | grep -v 'and\s*$'
```

**Signal**: Single-window burn rate alert (misses slow burns over hours).

**Preferred action**: Require both a long window (trend) and short window (ongoing):
```yaml
- alert: SLOBurnRate
  expr: |
    job:error_rate:ratio1h > (14.4 * 0.001)
    and
    job:error_rate:ratio5m > (14.4 * 0.001)
  for: 2m
```

---

### Validate Alertmanager Config with amtool Before Applying

**Detection**:
```bash
grep -rn 'amtool' --include="Makefile" --include="*.sh" --include="*.yml"
```
<!-- no-pair-required: partial section — positive counterpart follows in next block -->

A YAML syntax error in `alertmanager.yml` causes Alertmanager to reject the config silently. No error surfaces until alerts fail to route.

**Preferred action**:
```bash
amtool check-config alertmanager.yml
amtool config routes test --config.file=alertmanager.yml \
  severity=critical job=api team=platform
```

---

### Include Runbook Annotations on Every Alert

**Detection**:
```bash
grep -rn '^\s*- alert:' --include="*.yml" -A 15 | grep -B 10 'severity: critical' | grep -v 'runbook'
rg 'alert:' --type yaml -A 12 | grep -B8 'severity: critical' | grep -v runbook_url
```

**Preferred action**:
```yaml
annotations:
  summary: "DB connections exhausted on {{ $labels.instance }}"
  description: "Connection pool at {{ $value }}/100."
  runbook_url: "https://wiki.example.com/runbooks/db-connection-pool"
  dashboard_url: "https://grafana.example.com/d/db-overview?var-instance={{ $labels.instance }}"
```

---

### Route Alerts by Severity and Team

**Detection**:
```bash
grep -n 'receiver:' alertmanager.yml | wc -l
grep -c 'routes:' alertmanager.yml
```
<!-- no-pair-required: partial section — positive counterpart follows in next block -->

**Preferred action**:
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
| Alert flapping | No `for:` clause or too short | Add `for: 5m` minimum for non-critical |
| Alertmanager silently stops routing | YAML syntax error | Run `amtool check-config` before applying |
| No alerts during incident | Inhibition too broad | Narrow `equal:` labels in inhibit_rules |
| PagerDuty dedup not working | Missing `source_matchers` | Add `equal: [alertname, job]` |
| Alerts fire during deployment | `absent()` with short `for:` | Increase `for:` to 10m+ |
| Burn rate alert never fires | Wrong error threshold | 99.9% SLO → threshold = `0.001`, not `0.01` |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| Alertmanager 0.20 | `source_matchers` / `target_matchers` syntax | Old `source_match` deprecated in 0.22 |
| Alertmanager 0.22 | `matchers` field for routes | `match:` still works but `matchers:` preferred |
| Alertmanager 0.25 | `time_intervals` replaces mute_time_intervals key | Key rename causes silent ignore on upgrade |
| Prometheus 2.28 | `for` clause resets on state change | Alerts that briefly resolve restart `for:` timer |

---

## Detection Commands Reference

```bash
# Find alerts missing for: clause
grep -rn '^\s*- alert:' --include="*.yml" -A 8 | grep -B 5 'expr:' | grep -v 'for:'

# Find single-window burn rate alerts
grep -rn 'burn_rate\|error_rate.*ratio' --include="*.yml" -A 6 | grep -v '^\s*and\s'

# Find alerts without runbook annotations
grep -rn 'severity: critical' --include="*.yml" -B 10 | grep -v runbook_url

# Validate Alertmanager config
amtool check-config /etc/alertmanager/alertmanager.yml

# Test alert routing
amtool config routes test severity=critical job=api
```

---

## See Also

- `promql-patterns.md` — PromQL query correctness, rate/irate pitfalls
- `cardinality-management.md` — Label cardinality detection and reduction
