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
---

# Perses Query Builder

Build and optimize queries for Perses dashboard panels.

## Operator Context

This skill constructs, validates, and optimizes queries embedded in Perses panel definitions. It handles PromQL (Prometheus), LogQL (Loki), and TraceQL (Tempo) with correct variable interpolation and datasource binding.

### Hardcoded Behaviors (Always Apply)
- **Variable-aware**: Always use Perses variable syntax `$var` or `${var:format}` — never hardcode label values that should come from variables
- **Datasource-scoped**: Every query MUST reference its datasource by both `kind` and `name` fields
- **Interpolation-correct**: Use `${var:regex}` for `=~` matchers, `${var:csv}` or `${var:pipe}` for multi-select labels — never use bare `$var` with regex operators
- **Rate interval alignment**: Use `$__rate_interval` when the platform provides it; otherwise set rate intervals >= 4x the scrape interval

### Default Behaviors (ON unless disabled)
- **PromQL default**: Default to PrometheusTimeSeriesQuery if query type not specified
- **Optimization suggestions**: Flag recording rule candidates for expensive aggregations over high-cardinality metrics
- **Label matcher validation**: Warn when queries lack a narrowing label matcher (e.g., selecting all series for a metric)
- **Multi-value detection**: When a variable is marked `allowMultiple`, automatically apply the correct interpolation format

### Optional Behaviors (OFF unless enabled)
- **Recording rule generation**: Produce `recording_rules.yaml` for identified candidates
- **TraceQL exemplar linking**: Add exemplar query alongside PromQL for trace correlation
- **Query explain mode**: Annotate each query clause with comments explaining what it selects

## What This Skill CAN Do
- Build PromQL, LogQL, and TraceQL queries for Perses panel specs
- Apply correct Perses variable interpolation formats (`${var:regex}`, `${var:csv}`, etc.)
- Validate query syntax and flag common PromQL/LogQL/TraceQL errors
- Suggest query optimizations (recording rules, label narrowing, rate intervals)
- Wire queries to the correct datasource kind and name

## What This Skill CANNOT Do
- Create or configure datasources (use perses-datasource-manage)
- Build full dashboards or panel layouts (use perses-dashboard-create)
- Deploy Perses server instances (use perses-deploy)
- Develop custom Perses plugins (use perses-plugin-create)

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

## Anti-Patterns

### Hardcoding Label Values
**Wrong**: `http_requests_total{namespace="production"}` in a panel query.
**Right**: `http_requests_total{namespace="$namespace"}` using a dashboard variable.
**Why**: Hardcoded values break reusability across environments and defeat the purpose of dashboard variables.

### Bare `$var` with Multi-Value or Regex
**Wrong**: `http_requests_total{pod=~"$pod"}` when `pod` is a multi-select variable.
**Right**: `http_requests_total{pod=~"${pod:regex}"}`.
**Why**: Without `:regex` format, multi-select values are not joined with `|` — the query matches only the first selected value or produces a syntax error.

### Missing Datasource Spec in Query
**Wrong**: Omitting the `datasource` block or specifying only `name` without `kind`.
**Right**:
```yaml
datasource:
  kind: PrometheusDatasource
  name: prometheus
```
**Why**: Perses needs both `kind` and `name` to resolve the datasource. Omitting `kind` causes runtime resolution failures.

### Using `rate()` Without Meaningful Interval
**Wrong**: `rate(http_requests_total{job="api"}[1s])`.
**Right**: `rate(http_requests_total{job="api"}[$__rate_interval])` or `[5m]` aligned with scrape interval.
**Why**: Intervals shorter than the scrape interval produce empty results; `$__rate_interval` auto-adapts.

---

## Anti-Rationalization

| Rationalization | Reality | Required Action |
|---|---|---|
| "Bare `$var` works fine for single-select" | Variables can be changed to multi-select later, breaking the query | **Always use explicit format when combined with `=~`** |
| "Datasource kind is obvious from context" | Perses resolves datasources by kind+name pair at runtime | **Always specify both `kind` and `name`** |
| "This query is simple enough to skip validation" | Simple queries with typos still fail silently | **Validate every query against syntax rules** |
| "Recording rules are premature optimization" | `histogram_quantile` over thousands of series will time out in production | **Flag recording rule candidates for expensive aggregations** |

---

## FORBIDDEN Patterns

- **NEVER** use `${var:regex}` with `=` (equality) matchers — regex format with `=` causes silent mismatches
- **NEVER** omit `kind` from the datasource reference — Perses cannot resolve by name alone
- **NEVER** mix query plugin types within a single panel query list (e.g., PromQL and TraceQL in the same `queries[]` array)
- **NEVER** use Grafana-style `$__interval` or `${__rate_interval}` — Perses uses `$__rate_interval` (no braces, double underscores)
- **NEVER** assume a variable supports multi-select — check the variable definition's `allowMultiple` field

---

## Blocker Criteria

Do NOT proceed past the BUILD phase if any of these are true:

1. **Datasource unknown**: The target datasource name and kind have not been confirmed — query cannot be validated
2. **Variable definitions missing**: Query references `$var` but no matching variable exists in the dashboard spec
3. **Query type ambiguous**: Cannot determine whether PromQL, LogQL, or TraceQL is needed from user request
4. **Metric name unverified**: The metric name referenced does not exist in the target Prometheus/Loki/Tempo instance and the user has not confirmed it

---

## Instructions

### Phase 1: IDENTIFY

**Goal**: Determine query type, datasource, and variable context.

1. **Query type**: Identify which query language is needed:
   - PrometheusTimeSeriesQuery (PromQL) — metrics, counters, histograms
   - TempoTraceQuery (TraceQL) — distributed traces
   - LokiLogQuery (LogQL) — log streams
2. **Datasource**: Confirm the datasource `name` and `kind` from the dashboard or project context
3. **Variables**: Identify which dashboard variables the query should reference and their `allowMultiple` setting

**Gate**: Query type, datasource, and variable context confirmed. Proceed to Phase 2.

### Phase 2: BUILD

**Goal**: Construct the query with proper variable templating and datasource binding.

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

1. **Label narrowing**: Ensure at least one selective label matcher is present (e.g., `job`, `namespace`)
2. **Rate intervals**: Confirm `rate()`/`increase()` intervals align with scrape interval or use `$__rate_interval`
3. **Recording rule candidates**: Flag `histogram_quantile()` over high-cardinality metrics, multi-level `sum(rate(...))` aggregations, or any query aggregating over > 1000 estimated series
4. **Variable format audit**: Verify every `$var` reference uses the correct interpolation format for its operator context
5. **Datasource alignment**: Confirm query plugin kind matches datasource kind

**Gate**: Query optimized and validated. Task complete.

---

## References

- [Perses Variable Interpolation](https://perses.dev/docs/user-guides/variables/) — Official docs on variable formats
- [Perses Panel Queries](https://perses.dev/docs/user-guides/panels/) — Query spec structure
- [PromQL Docs](https://prometheus.io/docs/prometheus/latest/querying/basics/) — PromQL syntax reference
- [Perses Datasource Config](https://perses.dev/docs/user-guides/datasources/) — Datasource kind/name binding
- [Recording Rules Best Practices](https://prometheus.io/docs/practices/rules/) — When to create recording rules
