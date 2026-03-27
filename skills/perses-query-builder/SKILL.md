---
name: perses-query-builder
user-invocable: false
description: |
  Build PromQL, LogQL, TraceQL queries for Perses panels. Validate query syntax,
  suggest optimizations, handle variable templating with Perses interpolation formats.
  Integrates with prometheus-grafana-engineer for deep PromQL expertise. Use for
  "perses query", "promql perses", "logql perses", "perses panel query". Do NOT use
  for datasource configuration (use perses-datasource-manage).
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
  - Agent
agent: perses-dashboard-engineer
version: 2.0.0
routing:
  triggers:
    - "build PromQL"
    - "Perses query"
    - "LogQL query"
  category: perses
---

# Perses Query Builder

Build and optimize queries for Perses dashboard panels.

## Overview

This skill constructs, validates, and optimizes queries embedded in Perses panel definitions. It handles PromQL (Prometheus), LogQL (Loki), and TraceQL (Tempo) with correct variable interpolation and datasource binding. The workflow progresses through three phases: identifying query requirements, building the query with proper templating, and optimizing for performance and correctness.

---

## Instructions

### Phase 1: IDENTIFY

**Goal**: Determine query type, datasource, and variable context.

**Blockers**: Do not proceed if any of these are unresolved (because Perses requires them for runtime resolution and query validation):

1. **Datasource unknown** — The target datasource name and kind have not been confirmed. Perses resolves datasources at runtime using the `kind` and `name` pair; queries cannot be validated without this.
2. **Variable definitions missing** — Query references `$var` but no matching variable exists in the dashboard spec. Variables must be defined in the dashboard before queries can reference them.
3. **Query type ambiguous** — Cannot determine whether PromQL (metrics), LogQL (logs), or TraceQL (traces) is needed from the user request. Each query type maps to a specific datasource kind.
4. **Metric name unverified** — The metric name referenced does not exist in the target Prometheus/Loki/Tempo instance and the user has not confirmed it. Skip metric validation if the user explicitly says the metric exists or is intentional.

**Steps**:

1. **Query type**: Identify which query language is needed:
   - PrometheusTimeSeriesQuery (PromQL) — for metrics, counters, histograms
   - TempoTraceQuery (TraceQL) — for distributed traces
   - LokiLogQuery (LogQL) — for log streams
2. **Datasource**: Confirm the datasource `name` and `kind` from the dashboard or project context (because Perses cannot resolve datasources by name alone at runtime)
3. **Variables**: Identify which dashboard variables the query should reference and check their `allowMultiple` setting (because this determines which interpolation format to use)

**Gate**: Query type, datasource, and variable context confirmed. Proceed to Phase 2.

### Phase 2: BUILD

**Goal**: Construct the query with proper variable templating and datasource binding.

**Constraints applied during building**:

- **Always use Perses variable syntax** `$var` or `${var:format}` (not hardcoded label values) because dashboard variables enable query reusability across environments
- **Include both `kind` and `name` in the datasource spec** because Perses resolves datasources by kind+name pair at runtime and will fail silently if `kind` is omitted
- **Use the correct interpolation format for the operator context** — specifically, use `${var:regex}` for `=~` matchers and `${var:csv}` or `${var:pipe}` for equality matchers with multi-select variables, because bare `$var` with regex operators only interpolates the first selected value
- **Never use `${var:regex}` with `=` (equality) matchers** because regex format with equality causes silent mismatches; regex format is only for `=~`
- **Default to PrometheusTimeSeriesQuery** if query type is not explicitly specified
- **Use `$__rate_interval` for `rate()` and `increase()`** when the platform provides it, otherwise set intervals >= 4x the scrape interval, because shorter intervals produce empty results

**Example**:

```yaml
queries:
  - kind: TimeSeriesQuery
    spec:
      plugin:
        kind: PrometheusTimeSeriesQuery
        spec:
          query: "rate(http_requests_total{job=\"$job\", instance=~\"${instance:regex}\"}[$__rate_interval])"
          datasource:
            kind: PrometheusDatasource
            name: prometheus
```

**Variable interpolation reference**:

| Format | Output | Use With |
|---|---|---|
| `${var:regex}` | `val1\|val2\|val3` | `=~` matchers |
| `${var:csv}` | `val1,val2,val3` | API params, `in()` |
| `${var:pipe}` | `val1\|val2\|val3` | Custom pipe-delimited contexts |
| `${var:json}` | `["val1","val2"]` | JSON payloads |
| `${var:doublequote}` | `"val1","val2"` | Quoted lists |
| `${var:singlequote}` | `'val1','val2'` | Quoted lists |
| `${var:glob}` | `{val1,val2}` | Glob patterns |
| `${var:lucene}` | `("val1" OR "val2")` | Lucene queries |
| `${var:raw}` | `val1` (first only) | Single-value forced |
| `${var:values}` | `val1+val2` | URL-encoded params |
| `${var:singlevariablevalue}` | `val1` | Force single value |

**Gate**: Query built with correct interpolation and datasource. Proceed to Phase 3.

### Phase 3: OPTIMIZE

**Goal**: Review the query for performance and correctness.

**Constraints validated during optimization**:

- **Validate label narrowing** — ensure at least one selective label matcher is present (e.g., `job`, `namespace`) because queries without label matchers select all series for a metric and can overwhelm Prometheus
- **Confirm rate intervals** — verify `rate()`/`increase()` intervals align with scrape interval or use `$__rate_interval`, because intervals shorter than scrape interval produce empty results
- **Flag recording rule candidates** — identify expensive patterns like `histogram_quantile()` over high-cardinality metrics, multi-level `sum(rate(...))` aggregations, or queries aggregating over > 1000 estimated series, because these will time out in production
- **Audit variable formats** — verify every `$var` reference uses the correct interpolation format for its operator context (regex format for `=~`, CSV/pipe for `=`), because mismatches produce wrong results
- **Align plugin and datasource kinds** — confirm query plugin kind matches datasource kind (e.g., `PrometheusTimeSeriesQuery` with `PrometheusDatasource`, not `TempoDatasource`), because mismatches cause "unsupported query type" errors at runtime

**Steps**:

1. Check that at least one selective label matcher narrows the selection
2. Verify rate intervals are appropriately tuned
3. Identify expensive aggregations that should become recording rules
4. Validate each variable uses the correct format for its context
5. Confirm datasource kind aligns with query plugin kind

**Gate**: Query optimized and validated. Task complete.

---

## Error Handling

### PromQL Syntax Errors
**Symptom**: Query fails validation — missing closing bracket, invalid function name, bad label matcher syntax.
**Detection**: Look for unbalanced `()`, `{}`, `[]`; unknown function names; `=~` with unescaped special chars.
**Resolution**: Fix the syntax. Common fixes:
- Add missing closing `}` or `)`
- Replace `=~` value with a valid RE2 regex (no lookaheads)
- Use correct function name (e.g., `rate()` not `Rate()`, `histogram_quantile()` not `histogram_percentile()`)

### Variable Interpolation Format Mismatch
**Symptom**: Dashboard renders wrong results or query errors when multi-value variable is selected.
**Detection**: `$var` or `${var}` used with `=~` matcher; `${var:csv}` used with `=~` (needs regex format).
**Resolution**:
- For `=~` matchers: use `${var:regex}` (produces `val1|val2|val3`)
- For `=` with multi-select: use `${var:csv}` or `${var:pipe}` depending on downstream expectation
- For JSON API params: use `${var:json}`

### Datasource Kind Mismatch
**Symptom**: Query silently returns no data or errors at runtime with "unsupported query type".
**Detection**: Query plugin `kind` does not match datasource `kind` (e.g., `PrometheusTimeSeriesQuery` referencing a `TempoDatasource`).
**Resolution**: Align the query plugin kind with the datasource kind:
- `PrometheusTimeSeriesQuery` → `PrometheusDatasource`
- `TempoTraceQuery` → `TempoDatasource`
- `LokiLogQuery` → `LokiDatasource`

### High-Cardinality Query Warnings
**Symptom**: Query is slow, times out, or overwhelms Prometheus.
**Detection**: No label matchers narrowing selection; `rate()` missing or with no interval; aggregation over unbounded label set.
**Resolution**:
- Add label matchers to reduce selected series (at minimum `job` or `namespace`)
- Wrap counters in `rate()` or `increase()` with an appropriate interval
- Consider a recording rule for expensive `histogram_quantile()` or multi-level aggregations

---

## References

- [Perses Variable Interpolation](https://perses.dev/docs/user-guides/variables/) — Official docs on variable formats
- [Perses Panel Queries](https://perses.dev/docs/user-guides/panels/) — Query spec structure
- [PromQL Docs](https://prometheus.io/docs/prometheus/latest/querying/basics/) — PromQL syntax reference
- [Perses Datasource Config](https://perses.dev/docs/user-guides/datasources/) — Datasource kind/name binding
- [Recording Rules Best Practices](https://prometheus.io/docs/practices/rules/) — When to create recording rules
