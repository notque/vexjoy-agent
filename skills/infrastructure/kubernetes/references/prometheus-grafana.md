# Prometheus and Grafana Reference

> **Scope**: Prometheus scrape configs, service discovery, relabeling, recording rules, federation, remote storage; Grafana panels, variables, data sources; Alertmanager routing, inhibition, notifications; SLI/SLO and multi-window burn-rate alerts; PromQL performance and cardinality; ServiceMonitor and operator deployment; RED/USE metrics.
> **Not here**: business or product metrics analysis (`data` skill); Perses (`perses.md`); deploying the monitoring stack through manifests or Helm (`kubernetes-helm.md`); instrumenting application code (`programming` skill). Log aggregation (ELK, Loki) and APM tools (New Relic, Datadog, Dynatrace) are out of scope.

Principles: monitor SLIs (error rate, latency, throughput), alert on user impact rather than cause, keep labels low-cardinality, use recording rules for expensive queries, template dashboards. Priorities: actionability (every alert has a remediation), signal-to-noise, performance, usability.

## Hard rules

- **Low-cardinality labels**: labels hold only bounded values (endpoints, status codes, methods). Keep user IDs, request IDs, and timestamps out.
- **SLO-based alerting**: tie alerts to SLIs/SLOs, not arbitrary thresholds.
- **Recording rules for expensive queries**: frequently used complex queries become recording rules.
- **Retention awareness**: set retention from storage and query patterns.

## Defaults (on unless disabled)

- Dashboards include RED metrics (rate, errors, duration).
- Use Grafana variables so dashboards work across services and environments.
- Alert annotations carry runbook links, dashboard links, and query results.
- Test every PromQL query before it goes into a dashboard or alert.

## Optional (off unless enabled)

- Tracing correlation (Jaeger, Tempo), only when integrating tracing.
- Long-term storage (Thanos, Cortex, Mimir), only when extended retention is needed.
- Federation, only across several Prometheus instances.
- Custom exporters, only for systems without native Prometheus support.

## Output

- **Before**: requirements, metrics available, SLIs/SLOs, cardinality check.
- **During**: show PromQL, Prometheus/Grafana config YAML, dashboard JSON or screenshots, alert rules.
- **After**: dashboards, alerts, recording rules, retention configured; validation shows queries run efficiently, cardinality within limits, alerts fire as expected.
- Implementation Schema details: [output-schemas.md](../../../shared-patterns/output-schemas.md).

## Error handling

| Error | Cause | Fix |
|---|---|---|
| High cardinality | Unbounded labels (user_id, request_id, timestamp) create millions of series | Drop labels with relabeling, aggregate with recording rules, use histogram buckets instead of exact values, limit values with `label_replace` |
| Query timeout or OOM | Query scans too much data (long range, high cardinality, heavy aggregation) | Shorten the range, add label filters, use recording rules, raise memory limits, add `topk()` |
| Missing metrics | Scrape failing (target down, wrong port, missing auth, discovery miss) | Check the Prometheus targets page, match service/pod labels to the ServiceMonitor selector, check network, `curl` the metrics endpoint, add auth |

## Preferred patterns

- **Alert on SLO violations, not symptoms**: signal "Disk 80% full", "CPU 90%". These may not affect users and cause fatigue. Use "Error rate >0.1% for 5m", "Latency p99 >500ms for 10m".
- **Bounded label values**: signal `http_requests{user_id="12345"}`. Use `http_requests{endpoint="/api/users"}` and aggregate by meaningful dimensions only.
- **Recording rules for expensive queries**: signal complex aggregations in every panel, alerts timing out. Pre-compute `sum(rate(http_requests[5m])) by (service, status)`.

## Rationalizations to reject

| Claim | Why it's wrong | Do this |
|---|---|---|
| "Alert on everything to be safe" | Alert fatigue, ignored alerts | Alert only on SLO violations |
| "Prometheus handles high cardinality" | Eventually OOM, query failures | Limit labels to bounded values |
| "We'll optimize queries later" | Dashboards are slow now | Recording rules for expensive queries |
| "Resource alerts are important" | Resource use is not user impact | Alert on user-impacting SLIs |
| "More retention is always better" | Storage cost, query performance | Set retention from actual needs |

## Hard gates

Before implementing monitoring, check for these. If found: stop, report, fix before continuing.

| Pattern | Why blocked | Fix |
|---|---|---|
| Unbounded label values (user_id, request_id) | Cardinality explosion, OOM | Bounded labels (endpoint, status, method) |
| Alerts without runbooks | Not actionable | Runbook annotation with remediation steps |
| No retention limits | Disk fills, cost grows | `--storage.tsdb.retention.time=30d` |
| Complex queries without recording rules | Slow dashboards, alert delays | Recording rules for frequent queries |
| Symptom alerts (CPU, disk) | Fatigue, unclear action | Alert on error rate and latency SLOs |

## Verification stops

- After designing alert or recording rules: have I checked them against metrics that exist in Prometheus? Rules on missing metrics fail silently.
- After recommending cardinality or query changes: do I give before/after numbers (series count, query time), or say why measurement is impossible?
- After changing scrape configs, retention, or Alertmanager routing: have I checked dashboards that use these metrics, alert routes other teams rely on, and recording rules on affected targets?

## Before destructive or live changes

- Before changing retention or deleting metric data: check the impact on dashboards and alerts. Lower retention silently breaks long-range dashboards and historical analysis.
- Before changing Alertmanager routing: validate the YAML and test the tree with `amtool config routes test`. A broken alerting config means no alerts fire, which is worse than too many.

## Audit stance

When auditing a deployment, assume at least one misconfiguration. Check each before calling it healthy; an alert system that fails silently is worse than none:

- Alert rules on metrics no longer scraped.
- High-cardinality labels growing toward OOM.
- Recording rules that duplicate other recording rules.
- Dashboard queries scanning far more data than needed.
- Alertmanager routes that swallow alerts through wrong matchers.
- Retention too high for the disk.

## Recommendation format

Each recommendation names the **component** (dashboard, alert rule, recording rule, or scrape config), **current state** (or "new"), **proposed state**, and **risk level** (Low, Medium, High) with a short reason.

## Blockers

Resolve routine issues from repository evidence and existing authorization. When sure, decide, record the assumption, and continue; ask Jev when genuinely unsure.

| Situation | Why stop | Ask |
|---|---|---|
| SLIs/SLOs undefined | No meaningful alerts | "What are your SLIs (error rate, latency) and SLO targets?" |
| Cardinality limits unclear | Explosion risk | "Maximum number of time series expected?" |
| Retention unknown | Storage planning | "Retain metrics for 15d, 30d, or 90d?" |
| Notification channels unknown | Can't route alerts | "Send alerts to Slack, PagerDuty, or email?" |

Decide explicitly first: SLI/SLO definitions, retention periods, alert severity levels, notification channels.

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| Writing or debugging PromQL: `rate()`, `irate()`, `histogram_quantile()`, recording rules, subqueries | [prometheus-grafana/promql-patterns.md](prometheus-grafana/promql-patterns.md) | PromQL patterns and pitfalls |
| SLO alerts, burn-rate alerts, Alertmanager routing, inhibition rules, runbook annotations | [prometheus-grafana/alerting-patterns.md](prometheus-grafana/alerting-patterns.md) | Alert design and routing |
| High cardinality, OOM, label explosion, `relabel_configs`, `metric_relabel_configs`, TSDB analysis | [prometheus-grafana/cardinality-management.md](prometheus-grafana/cardinality-management.md) | Cardinality detection and reduction |
