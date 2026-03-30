# Query Builder

Build and optimize queries for Perses dashboard panels.

## Overview

Construct, validate, and optimize queries embedded in Perses panel definitions. Handles PromQL (Prometheus), LogQL (Loki), and TraceQL (Tempo) with correct variable interpolation and datasource binding.

## Phase 1: IDENTIFY

**Goal**: Determine query type, datasource, and variable context.

**Blockers** (do not proceed if unresolved):

1. **Datasource unknown** -- Perses resolves datasources at runtime using `kind` and `name` pair
2. **Variable definitions missing** -- Query references `$var` with no matching variable
3. **Query type ambiguous** -- Cannot determine PromQL vs LogQL vs TraceQL
4. **Metric name unverified** -- Metric doesn't exist and user hasn't confirmed

**Steps**:

1. **Query type**:
   - PrometheusTimeSeriesQuery (PromQL) -- metrics, counters, histograms
   - TempoTraceQuery (TraceQL) -- distributed traces
   - LokiLogQuery (LogQL) -- log streams
2. **Datasource**: Confirm `name` and `kind` from dashboard or project context
3. **Variables**: Identify referenced variables and check `allowMultiple` setting

**Gate**: Query type, datasource, and variable context confirmed.

## Phase 2: BUILD

**Goal**: Construct the query with proper variable templating and datasource binding.

**Constraints**:
- Always use Perses variable syntax `$var` or `${var:format}`
- Include both `kind` and `name` in datasource spec
- Use `${var:regex}` for `=~` matchers, `${var:csv}` or `${var:pipe}` for equality
- Never use `${var:regex}` with `=` (equality) matchers
- Default to PrometheusTimeSeriesQuery if unspecified
- Use `$__rate_interval` for `rate()` and `increase()`

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
| `${var:pipe}` | `val1\|val2\|val3` | Pipe-delimited contexts |
| `${var:json}` | `["val1","val2"]` | JSON payloads |
| `${var:doublequote}` | `"val1","val2"` | Quoted lists |
| `${var:singlequote}` | `'val1','val2'` | Quoted lists |
| `${var:glob}` | `{val1,val2}` | Glob patterns |
| `${var:lucene}` | `("val1" OR "val2")` | Lucene queries |
| `${var:raw}` | `val1` (first only) | Single-value forced |
| `${var:values}` | `val1+val2` | URL-encoded params |
| `${var:singlevariablevalue}` | `val1` | Force single value |

**Gate**: Query built with correct interpolation and datasource.

## Phase 3: OPTIMIZE

**Goal**: Review for performance and correctness.

1. **Label narrowing** -- at least one selective matcher (job, namespace)
2. **Rate intervals** -- aligned with scrape interval or `$__rate_interval`
3. **Recording rule candidates** -- flag expensive patterns (histogram_quantile, multi-level aggregations)
4. **Variable format audit** -- correct format for each operator context
5. **Plugin-datasource alignment** -- query kind matches datasource kind

**Gate**: Query optimized and validated. Task complete.

## Error Handling

### PromQL Syntax Errors
Fix: add missing closing brackets, use valid RE2 regex, use correct function names.

### Variable Interpolation Format Mismatch
Fix: `${var:regex}` for `=~`, `${var:csv}` for `=` with multi-select, `${var:json}` for JSON params.

### Datasource Kind Mismatch
Fix: `PrometheusTimeSeriesQuery` -> `PrometheusDatasource`, `TempoTraceQuery` -> `TempoDatasource`, `LokiLogQuery` -> `LokiDatasource`.

### High-Cardinality Warnings
Fix: add label matchers, wrap counters in `rate()`/`increase()`, consider recording rules.

## References

- [Perses Variable Interpolation](https://perses.dev/docs/user-guides/variables/)
- [Perses Panel Queries](https://perses.dev/docs/user-guides/panels/)
- [PromQL Docs](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Perses Datasource Config](https://perses.dev/docs/user-guides/datasources/)
- [Recording Rules Best Practices](https://prometheus.io/docs/practices/rules/)
