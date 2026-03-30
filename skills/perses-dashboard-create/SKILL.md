---
name: perses-dashboard-create
user-invocable: false
description: "Guided Perses dashboard creation: requirements, CUE/JSON, validate, deploy."
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
agent: perses-engineer
version: 2.0.0
routing:
  triggers:
    - "create Perses dashboard"
    - "new dashboard"
  category: perses
---

# Perses Dashboard Create

Guided workflow for creating Perses dashboards from requirements through validation and deployment.

## Overview

This workflow guides you through four phases: gathering requirements, generating a dashboard definition, validating it, and deploying to Perses. The skill applies sensible defaults at each phase to minimize configuration while remaining flexible for advanced scenarios.

**Key workflow principle**: Requirements → Definition → Validation → Deployment. Never skip validation, even for simple dashboards, because percli lint catches structural errors early.

## Instructions

### Phase 1: GATHER Requirements

Understand what the dashboard should display.

1. **Identify metrics/data**: What should the dashboard show? (CPU, memory, request rates, traces, logs)
2. **Identify datasource**: Which backend? (Prometheus, Tempo, Loki, Pyroscope, ClickHouse, VictoriaLogs). Defaults to Prometheus unless a datasource type is explicitly specified because Prometheus is the most common monitoring backend.
3. **Identify project**: Which Perses project does this belong to? Always ask — if the project does not exist, create it first before proceeding, because dashboards cannot exist without a project.
4. **Identify layout**: How many panels? How should they be organized? Defaults to Grid layout with collapsible rows using a 12-column width because this layout accommodates responsive rendering and flexible panel sizing.
5. **Identify variables**: What filters should be available? (cluster, namespace, pod, job, instance). Automatically add job, instance, and namespace variables when query patterns suggest common labels, because these are the most frequently queried labels in monitoring scenarios.

**Application of defaults**: When the user provides minimal information, apply these defaults to reduce friction:
- **Output format**: CUE definition by default because CUE provides strong type checking and modularity. Switch to JSON, YAML, or Go SDK only when explicitly requested.
- **Datasource**: Prometheus (default) unless another type is specified
- **Variables**: job, instance (minimum set for filtering)
- **Layout**: Grid with collapsible rows, 12-column width
- **Panels**: TimeSeriesChart for time series, StatChart for single values, Table for lists

**Optional modes** (activate only when explicitly requested to keep the primary path simple):
- **Go SDK output**: Generate Go SDK code instead of CUE
- **Ephemeral mode**: Create EphemeralDashboard with TTL for preview/CI use
- **Bulk creation**: Generate multiple dashboards from a specification

**Gate**: Requirements gathered. Proceed to Phase 2.

### Phase 2: GENERATE Definition

Create the dashboard definition.

**Step 1: Check for Perses MCP tools**

Use MCP tools as the primary interface because they provide direct API integration and better error context. Fall back to percli CLI only when MCP is unavailable.

```
Use ToolSearch("perses") to discover available MCP tools.
If perses_list_projects is available, use it to verify the target project exists.
If not, use percli get project to check.
```

**Step 2: Generate dashboard definition**

Generate a CUE definition by default, because CUE provides strong validation and modularity over JSON. Only use plugin kinds from the official set below — no invented or third-party kinds, because the Perses API only recognizes these standard plugins.

The structure follows:

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

Always validate before deploying — never skip this phase even for simple dashboards, because percli lint catches structural errors that prevent deployment and schema mismatches early.

```bash
percli lint -f <file>
# OR with online validation against running server:
percli lint -f <file> --online
```

If validation fails, fix the issues and re-validate.

**Gate**: Validation passes. Proceed to Phase 4.

### Phase 4: DEPLOY

Deploy the dashboard to Perses.

**Option A: MCP tools** (preferred — use when available because MCP provides better error handling and atomicity)
Use `perses_create_dashboard` MCP tool to create the dashboard directly.

**Option B: percli CLI** (fallback when MCP is unavailable)
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

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `percli lint` fails with unknown plugin kind | Used a plugin kind not in the official set | Replace with one of the 16 panel or 4 variable plugin kinds listed in Phase 2 |
| Project does not exist | Dashboard targets a non-existent project | Create the project first with `percli apply` or `perses_create_project` MCP tool |
| MCP tool not found | Perses MCP server not connected | Fall back to percli CLI commands |
| `percli apply` auth error | Missing or expired credentials | Run `percli login` or check `~/.perses/config.yaml` |
| Online lint fails but offline passes | Server-side schema stricter than local | Fix the server-reported issues — online validation is authoritative |

## References

- Perses dashboard spec: https://perses.dev/docs/api/dashboard/
- percli CLI: https://perses.dev/docs/tooling/percli/
- Plugin catalog: https://perses.dev/docs/plugins/
- Dashboard-as-Code: https://perses.dev/docs/tooling/dac/
- Variable interpolation: https://perses.dev/docs/user-guides/variables/
