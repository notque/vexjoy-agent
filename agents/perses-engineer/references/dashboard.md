# Perses Dashboard Reference

> **Scope**: Dashboard-as-Code (DaC) patterns, Go/CUE SDK usage, percli CLI, variables, panels, and datasource wiring. Does not cover operator CRDs or plugin development.
> **Version range**: Perses v0.47+ (CRD v1alpha2, Go SDK v0.47+)
> **Generated**: 2026-05-09 — verify against https://github.com/perses/perses/releases

---

## Overview

Perses dashboards are defined as JSON/YAML documents validated against CUE schemas. Dashboard-as-Code (DaC) lets you generate these documents programmatically using the Go SDK or CUE, avoiding hand-edited JSON drift. The most common failure mode is referencing a datasource name or variable name that doesn't match the project's registered datasources — Perses fails silently on missing refs.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| Go SDK (`go/sdk`) | `v0.47+` | Generating dashboards from code | The dashboard is one-off or manually curated |
| CUE schemas | all | Validating dashboard JSON | You need Go type safety across multiple dashboards |
| `percli apply -f` | all | Pushing dashboards to a live server | Dry-runs — use `--dry-run` flag |
| `percli export` | all | Pulling existing dashboards to DaC | Initial migration from UI-created dashboards |
| `percli migrate` | `v0.40+` | Converting Grafana dashboards | Only Grafana JSON v8+ is supported |

---

## Dashboard-as-Code: Go SDK

### Minimal working dashboard

```go
import (
    "github.com/perses/perses/go/sdk/dashboard"
    "github.com/perses/perses/go/sdk/panel/timeseries"
    listvar "github.com/perses/perses/go/sdk/variable/listvar"
    prometheustarget "github.com/perses/perses/go/sdk/prometheus/query"
)

builder, err := dashboard.New("My Dashboard",
    dashboard.ProjectName("my-project"),
    dashboard.Duration("1h"),
    dashboard.RefreshInterval("30s"),
    dashboard.AddVariable(
        listvar.New("namespace",
            listvar.DisplayName("Namespace"),
            listvar.CapturingRegexp("(.+)"),
            listvar.AllowAllValue(true),
            listvar.AllowMultiple(false),
        ),
    ),
    dashboard.AddPanelGroup("Overview",
        dashboard.AddPanel("Requests/sec",
            timeseries.New("Requests/sec",
                timeseries.WithPrometheusTarget(
                    `rate(http_requests_total{namespace="$namespace"}[5m])`,
                    prometheustarget.Legend("{{handler}}"),
                ),
            ),
        ),
    ),
)
```

**Why**: The SDK enforces schema at compile time. Mistyped field names are caught before `percli apply` runs.

---

### Variable types

```go
// Text variable — free-form input
textvar.New("cluster",
    textvar.DisplayName("Cluster"),
    textvar.Value("prod"),  // default value
)

// List variable — query-driven options
listvar.New("namespace",
    listvar.PrometheusLabelValuesQuery("namespace", "kube_pod_info"),
    listvar.AllowAllValue(true),
    listvar.AllowMultiple(true),
    listvar.Sort(listvar.AlphabeticalAsc),
)

// Constant variable — fixed value, often hidden
constantvar.New("datasource",
    constantvar.Value("PrometheusDemo"),
    constantvar.Hide(true),
)
```

**Why**: List variables using `AllowMultiple(true)` must use `=~` (regex match) in PromQL, not `=`. Mixing `=` with a multi-value variable silently uses only the first selected value.

---

### Panel types and imports

| Panel | Import path suffix | Key option |
|-------|-------------|-----------|
| TimeSeriesChart | `panel/timeseries` | `.WithPrometheusTarget()` |
| GaugeChart | `panel/gauge` | `.Thresholds()` |
| StatChart | `panel/stat` | `.Format()`, `.Sparkline()` |
| BarChart | `panel/barchart` | `.XAxis()` |
| Markdown | `panel/markdown` | `.Text()` |
| ScatterChart | `panel/scatterchart` | `.WithPrometheusTarget()` |
| Table | `panel/table` | `.ColumnSettings()` |

---

## Pattern Catalog: Detection and Fixes

### Hardcoded datasource name (breaks across projects)

**Detection**:
```bash
grep -rn '"default"' --include="*.go" | grep -i datasource
grep -rn 'datasource.*"prometheus"' --include="*.cue"
rg 'datasourceName.*"[A-Za-z]+"' --type go
```

**Signal**:
```go
// Hardcoded datasource name — breaks when deployed to a project
// that registered the datasource under a different name
timeseries.WithPrometheusTarget(
    "up",
    prometheustarget.Datasource("default"),  // "default" may not exist
)
```

**Why it matters**: Datasource names are scoped to a project. A dashboard deployed to project `team-a` expecting `"default"` fails if that project registered the datasource as `"prometheus-prod"`. The panel renders empty with no error in the UI.

**Preferred action**:
```go
// Use a variable reference for datasource selection
constantvar.New("datasource", constantvar.Value("PrometheusDemo"))
// Then reference it:
prometheustarget.Datasource("$datasource")
```

---

### Multi-value variable with equality operator

**Detection**:
```bash
grep -rn 'AllowMultiple(true)' --include="*.go" -A5 | grep -v '=~'
rg '\$\w+[^~]' --type json | grep -i 'expr\|query'
```

**Signal**:
```go
listvar.New("namespace", listvar.AllowMultiple(true))
// ...then in query:
`kube_pod_info{namespace="$namespace"}`  // = operator, not =~
```

**Why it matters**: When multiple namespaces are selected, `$namespace` expands to `ns1|ns2|ns3`. The `=` operator treats this as a literal string match, always returning no results. The `=~` operator applies regex matching.

**Preferred action**:
```go
`kube_pod_info{namespace=~"$namespace"}`  // regex match for multi-value
```

---

### Missing `dashboard.Duration` / `RefreshInterval`

**Detection**:
```bash
rg 'dashboard\.New\(' --type go -A 10 | grep -c 'Duration\|Refresh'
grep -rn 'dashboard.New(' --include="*.go" -A 8 | grep -v 'Duration'
```

**Signal**:
```go
dashboard.New("My Dashboard",
    dashboard.ProjectName("my-project"),
    // No Duration or RefreshInterval — uses server defaults (may be 6h)
)
```

**Why it matters**: Without explicit duration, the dashboard opens with the server's default time range, which may be 6h or 24h. Users expect the dashboard designer's intended time range.

**Preferred action**:
```go
dashboard.New("My Dashboard",
    dashboard.Duration("1h"),
    dashboard.RefreshInterval("30s"),
)
```

---

### Using `percli apply` without `--project`

**Detection**:
```bash
grep -rn 'percli apply' --include="*.sh" | grep -v '\-\-project\|-p '
grep -rn 'percli apply' Makefile | grep -v '\-\-project\|-p '
```

**Signal**:
```bash
percli apply -f dashboard.json  # applies to project embedded in JSON, may be wrong env
```

**Why it matters**: Without `--project`, percli uses the project name embedded in the dashboard JSON. A dashboard exported from `dev` and re-applied without `--project` silently creates/updates a dashboard in the wrong project in `prod`.

**Preferred action**:
```bash
percli apply -f dashboard.yaml --project my-project --server https://perses.prod
```

---

## percli Command Reference

```bash
# Export dashboard from server to local JSON
percli export dashboard my-dashboard --project my-project --output json > dashboard.json

# Apply (create or update) from file
percli apply -f dashboard.yaml --project my-project

# Dry-run validation without applying
percli apply -f dashboard.yaml --project my-project --dry-run

# Migrate Grafana dashboard JSON to Perses format
percli migrate -f grafana-dashboard.json --output json > perses-dashboard.json

# List all dashboards in a project
percli get dashboard --project my-project

# Delete a dashboard
percli delete dashboard my-dashboard --project my-project
```

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `datasource "X" not found` | Dashboard references a datasource name not registered in project | Register datasource in project or use `$datasource` variable |
| `variable "X" not defined` | Panel query uses `$varname` not declared in dashboard variables | Add variable to `dashboard.AddVariable(...)` |
| Panel shows "No data" (no error) | Multi-value variable used with `=` instead of `=~` | Change PromQL query to use `=~` operator |
| `percli apply: 409 Conflict` | Dashboard already exists and `--force` not set | Add `--force` flag or delete existing first |
| `cue: schema validation failed` | Dashboard JSON doesn't match CUE schema | Run `cue vet` with Perses schemas to find exact field violation |
| `migrate: unsupported panel type` | Grafana panel type has no Perses equivalent | Replace with StatChart or Markdown manually post-migration |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| `v0.47` | `GridLayout` became the only supported layout type | Remove legacy `FlexLayout` references |
| `v0.45` | Go SDK `dashboard.AddPanelGroup` replaced `dashboard.AddRow` | Update DaC code using old API |
| `v0.43` | `percli migrate` added `--keep-unsupported` flag | Grafana dashboards with unsupported panels no longer abort migration |
| `v0.40` | CRD promoted to `v1alpha2` | Update `apiVersion: perses.dev/v1alpha1` to `v1alpha2` in all manifests |

---

## Detection Commands Reference

```bash
# Hardcoded datasource names
grep -rn 'datasourceName.*"[A-Za-z]+"' --include="*.go"

# Multi-value variable without regex match operator
grep -rn 'AllowMultiple(true)' --include="*.go"

# Missing time range in DaC dashboards
rg 'dashboard\.New\(' --type go -A 10 | grep -v 'Duration'

# percli apply without explicit project
grep -rn 'percli apply' --include="*.sh" | grep -v '\-\-project\|-p '
```

---

## See Also

- `plugin.md` — Panel plugin development and CUE schema authoring
- `operator.md` — Kubernetes CRDs for managing dashboards declaratively
- `core.md` — Go backend API and React frontend architecture
