# Dashboard Create and Review

## Dashboard Create

Guided workflow for creating Perses dashboards from requirements through validation and deployment.

### Overview

This workflow guides you through four phases: gathering requirements, generating a dashboard definition, validating it, and deploying to Perses. Sensible defaults minimize configuration while remaining flexible for advanced scenarios.

**Key workflow principle**: Requirements -> Definition -> Validation -> Deployment. Never skip validation, even for simple dashboards, because percli lint catches structural errors early.

### Phase 1: GATHER Requirements

1. **Identify metrics/data**: What should the dashboard show? (CPU, memory, request rates, traces, logs)
2. **Identify datasource**: Which backend? Defaults to Prometheus unless explicitly specified.
3. **Identify project**: Which Perses project? Always ask -- dashboards cannot exist without a project.
4. **Identify layout**: How many panels? Defaults to Grid layout with collapsible rows, 12-column width.
5. **Identify variables**: What filters? Automatically add job, instance, namespace when query patterns suggest common labels.

**Defaults** when user provides minimal information:
- **Output format**: CUE definition (strong type checking and modularity). Switch to JSON, YAML, or Go SDK only when explicitly requested.
- **Datasource**: Prometheus
- **Variables**: job, instance (minimum set)
- **Layout**: Grid with collapsible rows, 12-column width
- **Panels**: TimeSeriesChart for time series, StatChart for single values, Table for lists

**Optional modes** (activate only when explicitly requested):
- **Go SDK output**: Generate Go SDK code instead of CUE
- **Ephemeral mode**: Create EphemeralDashboard with TTL for preview/CI use
- **Bulk creation**: Generate multiple dashboards from a specification

**Gate**: Requirements gathered. Proceed to Phase 2.

### Phase 2: GENERATE Definition

**Step 1: Check for Perses MCP tools**

Use MCP tools as the primary interface. Fall back to percli CLI only when MCP is unavailable.

**Step 2: Generate dashboard definition**

Generate a CUE definition by default. Only use plugin kinds from the official set -- no invented or third-party kinds.

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

Always validate before deploying -- never skip this phase.

```bash
percli lint -f <file>
# OR with online validation:
percli lint -f <file> --online
```

If validation fails, fix issues and re-validate.

**Gate**: Validation passes. Proceed to Phase 4.

### Phase 4: DEPLOY

**Option A: MCP tools** (preferred)
Use `perses_create_dashboard` MCP tool.

**Option B: percli CLI** (fallback)
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
```

**Gate**: Dashboard deployed and verified. Task complete.

### Create Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `percli lint` fails with unknown plugin kind | Used a non-official plugin kind | Replace with one of the 16 panel or 4 variable plugin kinds |
| Project does not exist | Dashboard targets non-existent project | Create project first |
| MCP tool not found | Perses MCP server not connected | Fall back to percli CLI |
| `percli apply` auth error | Missing or expired credentials | Run `percli login` |
| Online lint fails but offline passes | Server-side schema stricter | Fix server-reported issues -- online is authoritative |

---

## Dashboard Review

Analyze and improve existing Perses dashboards through structured review of layout, queries, variables, and datasource configuration.

### Overview

Non-destructive review that audits dashboard quality without modification unless explicitly requested. 4-phase pipeline: FETCH, ANALYZE, REPORT, FIX.

### Phase 1: FETCH

**Goal**: Retrieve the current dashboard definition.

1. Fetch via MCP first:
   ```
   perses_get_dashboard_by_name(project=<project>, dashboard=<name>)
   ```
2. Fall back to percli CLI:
   ```bash
   percli describe dashboard <name> --project <project> -ojson
   ```
3. If both fail, ask the user for dashboard JSON directly.

The review MUST NOT proceed if dashboard cannot be retrieved or JSON is malformed.

### Phase 2: ANALYZE

Run all five analysis steps on every review regardless of dashboard size.

#### Step 1: Layout Review
- Verify grid layout uses 24-column system correctly
- Check for collapsible rows with logical grouping
- Identify orphan panels (defined but absent from layouts)
- Flag empty rows

#### Step 2: Query Analysis
- Parse each panel's query (PromQL, LogQL, TraceQL, SQL)
- Check for anti-patterns: missing `$__rate_interval`, unbounded selectors, `rate()` without range vector, recording rule candidates
- Verify variable interpolation format correctness

#### Step 3: Variable Chain Analysis
- Build dependency graph
- Verify topological ordering (parents before children)
- Check for circular dependencies (critical blocker)
- Validate matchers reference existing variables
- Check interpolation formats

#### Step 4: Datasource Scoping
- Map each panel to its datasource reference
- Verify datasource scope matches dashboard's project
- Check for missing datasource references (critical blocker)
- Never change datasource assignments during review

#### Step 5: Metadata and Usability
- Check for missing panel titles or descriptions
- Verify dashboard-level display name
- Flag duplicate panel titles
- Check default time range

**Gate**: All five steps completed. Proceed to Phase 3.

### Phase 3: REPORT

Assign severity by impact:
- **Critical**: Dashboard is broken or produces wrong data
- **Warning**: Performance or usability issues
- **Info**: Cosmetic or best-practice suggestions

```
## Dashboard Review: <name> (project: <project>)

### Critical Findings
- [CRITICAL] <description> -- <recommendation>

### Warnings
- [WARNING] <description> -- <recommendation>

### Info
- [INFO] <description> -- <recommendation>

### Summary
- Panels reviewed: N
- Variables reviewed: N
- Datasources reviewed: N
- Critical: N | Warnings: N | Info: N
```

**Gate**: Report generated. If no `--fix` flag, task complete.

### Phase 4: FIX (optional, requires --fix flag)

OFF by default. Never modify without `--fix` or explicit user confirmation.

1. Present proposed fixes for user confirmation
2. Apply approved fixes
3. Deploy updated dashboard
4. Re-run Phase 2 ANALYZE to verify fixes

**Gate**: Fixes applied and verified. Task complete.

### Review Error Handling

**MCP Tools Not Available**: Fall back to percli CLI or ask user for dashboard JSON.

**Dashboard Not Found**: List available dashboards and confirm names with user.

**Variable Chain Circular Dependency**: Flag as critical. Map the full cycle. Never auto-fix without user confirmation.

**Malformed Dashboard JSON**: Report structural error and halt analysis.

---

## References

- [Perses Dashboard Spec](https://perses.dev/docs/api/dashboard/)
- [percli CLI](https://perses.dev/docs/tooling/percli/)
- [Plugin Catalog](https://perses.dev/docs/plugins/)
- [Dashboard-as-Code](https://perses.dev/docs/tooling/dac/)
- [Variable Interpolation](https://perses.dev/docs/user-guides/variables/)
