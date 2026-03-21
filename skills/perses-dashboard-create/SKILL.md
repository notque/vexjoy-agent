---
name: perses-dashboard-create
user-invocable: false
description: |
  Guided Perses dashboard creation: gather requirements (metrics, datasource, layout),
  generate CUE definition or JSON spec, validate with percli lint, deploy with percli
  apply or MCP perses_create_dashboard. Use when user wants to create a new Perses
  dashboard, build a monitoring dashboard, or generate dashboard definitions. Use for
  "create perses dashboard", "new dashboard", "perses new dashboard", "build dashboard".
  Do NOT use for Grafana migration (use perses-grafana-migrate) or plugin development
  (use perses-plugin-create).
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
  - Agent
  - WebFetch
  - WebSearch
agent: perses-dashboard-engineer
version: 2.0.0
---

# Perses Dashboard Create

Guided workflow for creating Perses dashboards with validation and deployment.

## Operator Context

This skill operates as a guided workflow for Perses dashboard creation, from requirements gathering through validation and deployment.

### Hardcoded Behaviors (Always Apply)
- **Validate before deploy**: Always run `percli lint` on generated dashboard definitions before applying
- **MCP-first**: Use Perses MCP tools when available, percli CLI as fallback
- **Scope-aware**: Ask which project the dashboard belongs to. Create the project first if it doesn't exist
- **Plugin-aware**: Only use panel/query/variable plugin kinds from the official 27 plugins

### Default Behaviors (ON unless disabled)
- **CUE output**: Generate CUE definitions by default (can switch to JSON/YAML if requested)
- **Prometheus datasource**: Default to Prometheus datasource if no datasource type specified
- **Grid layout**: Use Grid layout with collapsible rows by default
- **Variable templating**: Add common variables (job, instance, namespace) based on query patterns

### Optional Behaviors (OFF unless enabled)
- **Go SDK output**: Generate Go SDK code instead of CUE
- **Ephemeral mode**: Create EphemeralDashboard with TTL for preview/CI
- **Bulk creation**: Generate multiple dashboards from a specification

## What This Skill CAN Do
- Create complete dashboard definitions in CUE, Go, JSON, or YAML format
- Configure datasources (Prometheus, Tempo, Loki, Pyroscope, ClickHouse, VictoriaLogs)
- Set up variables with proper chains and interpolation formats
- Validate definitions with percli lint
- Deploy to Perses via percli apply or MCP tools
- Generate CI/CD config for Dashboard-as-Code workflows

## What This Skill CANNOT Do
- Migrate Grafana dashboards (use perses-grafana-migrate)
- Create custom panel plugins (use perses-plugin-create)
- Deploy/configure Perses server itself (use perses-deploy)

---

## Instructions

### Phase 1: GATHER Requirements

**Goal**: Understand what the dashboard should display.

1. **Identify metrics/data**: What should the dashboard show? (CPU, memory, request rates, traces, logs)
2. **Identify datasource**: Which backend? (Prometheus, Tempo, Loki, Pyroscope, ClickHouse, VictoriaLogs)
3. **Identify project**: Which Perses project does this belong to?
4. **Identify layout**: How many panels? How should they be organized?
5. **Identify variables**: What filters should be available? (cluster, namespace, pod, job, instance)

If the user provides minimal info, make reasonable defaults:
- Default datasource: Prometheus
- Default variables: job, instance
- Default layout: Grid with collapsible rows, 12-column width
- Default panels: TimeSeriesChart for time series, StatChart for single values, Table for lists

**Gate**: Requirements gathered. Proceed to Phase 2.

### Phase 2: GENERATE Definition

**Goal**: Create the dashboard definition.

**Step 1: Check for Perses MCP tools**
```
Use ToolSearch("perses") to discover available MCP tools.
If perses_list_projects is available, use it to verify the target project exists.
If not, use percli get project to check.
```

**Step 2: Generate dashboard definition**

Generate a CUE definition by default. The structure follows:

```yaml
kind: Dashboard
metadata:
  name: <dashboard-name>
  project: <project-name>
spec:
  display:
    name: <Display Name>
    description: <description>
  duration: 1h
  refreshInterval: 30s
  datasources:
    <name>:
      default: true
      plugin:
        kind: PrometheusDatasource
        spec:
          proxy:
            kind: HTTPProxy
            spec:
              url: <prometheus-url>
  variables:
    - kind: ListVariable
      spec:
        name: <var-name>
        display:
          name: <display-name>
        plugin:
          kind: PrometheusLabelValuesVariable
          spec:
            labelName: <label>
            datasource:
              kind: PrometheusDatasource
              name: <ds-name>
  panels:
    <panel-id>:
      kind: Panel
      spec:
        display:
          name: <Panel Title>
        plugin:
          kind: TimeSeriesChart
          spec: {}
        queries:
          - kind: TimeSeriesQuery
            spec:
              plugin:
                kind: PrometheusTimeSeriesQuery
                spec:
                  query: <promql-query>
  layouts:
    - kind: Grid
      spec:
        display:
          title: <Row Title>
          collapse:
            open: true
        items:
          - x: 0
            "y": 0
            width: 12
            height: 6
            content:
              "$ref": "#/spec/panels/<panel-id>"
```

**Available panel plugin kinds**: TimeSeriesChart, BarChart, GaugeChart, HeatmapChart, HistogramChart, PieChart, ScatterChart, StatChart, StatusHistoryChart, FlameChart, Table, TimeSeriesTable, LogsTable, TraceTable, Markdown, TracingGanttChart

**Available variable plugin kinds**: PrometheusLabelValuesVariable, PrometheusPromQLVariable, StaticListVariable, DatasourceVariable

**Variable interpolation formats**: `$var` or `${var:format}` where format is one of: csv, json, regex, pipe, glob, lucene, values, singlevariablevalue, doublequote, singlequote, raw

**Gate**: Definition generated. Proceed to Phase 3.

### Phase 3: VALIDATE

**Goal**: Ensure the dashboard definition is valid.

Run validation:
```bash
percli lint -f <file>
# OR with online validation against running server:
percli lint -f <file> --online
```

If validation fails, fix the issues and re-validate.

**Gate**: Validation passes. Proceed to Phase 4.

### Phase 4: DEPLOY

**Goal**: Deploy the dashboard to Perses.

**Option A: MCP tools** (preferred if available)
Use `perses_create_dashboard` MCP tool to create the dashboard directly.

**Option B: percli CLI**
```bash
percli apply -f <file>
```

**Option C: Dashboard-as-Code** (if DaC workflow is requested)
```bash
percli dac build -f <file> -ojson
percli apply -f built/<dashboard>.json
```

Verify deployment:
```bash
percli describe dashboard <name> --project <project>
# OR via MCP:
perses_get_dashboard_by_name(project=<project>, dashboard=<name>)
```

**Gate**: Dashboard deployed and verified. Task complete.
