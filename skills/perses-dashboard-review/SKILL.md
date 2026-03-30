---
name: perses-dashboard-review
user-invocable: false
description: "Review Perses dashboards: panel layout, query efficiency, variables."
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
    - "review Perses dashboard"
    - "dashboard quality"
  category: perses
---

# Perses Dashboard Review

Analyze and improve existing Perses dashboards through structured review of layout, queries, variables, and datasource configuration.

## Overview

This is a non-destructive review skill that audits dashboard quality without modification unless explicitly requested. The skill runs a 4-phase pipeline (FETCH, ANALYZE, REPORT, FIX) to identify layout issues, query inefficiencies, variable chain problems, and datasource scoping mismatches. Use this skill to review existing dashboards for quality improvements. Do NOT use this skill to create new dashboards—use perses-dashboard-create instead.

## Instructions

### Phase 1: FETCH

**Goal**: Retrieve the current dashboard definition from the live server.

1. Always fetch the live definition via MCP or API first, because a dashboard that "looks fine" locally may differ from what is deployed.
   - Attempt MCP retrieval first (ensures freshest server-side state):
     ```
     perses_get_dashboard_by_name(project=<project>, dashboard=<name>)
     ```
   - If MCP is unavailable, fall back to percli CLI:
     ```bash
     percli describe dashboard <name> --project <project> -ojson
     ```
   - If both fail, ask the user to provide the dashboard JSON directly.

2. Parse and validate the JSON structure. The review MUST NOT proceed past this phase if:
   - Dashboard definition cannot be retrieved (MCP + percli both fail, no JSON provided)
   - Dashboard JSON is malformed and fails structural validation (required fields: `kind: Dashboard`, `metadata.name`, `spec.panels`, `spec.layouts`, `spec.variables`, `spec.datasources`)
   - Project does not exist or user lacks read permissions

### Phase 2: ANALYZE

**Goal**: Systematically audit all five dashboard components. Run all five analysis steps on every review regardless of dashboard size, because small dashboards still have datasource scoping, variable chains, and layout issues that skipping would miss.

#### Step 1: Layout Review

Start here before touching queries (a dashboard with correct queries but chaotic layout is still a poor dashboard):

- Verify grid layout uses 24-column system correctly — panels exceeding width 24 are a critical blocker
- Check for collapsible rows with logical grouping
- Identify orphan panels (defined in `spec.panels` but absent from `spec.layouts`)
- Flag empty rows or sections with no panels

#### Step 2: Query Analysis

Parse and validate each query against known anti-patterns (visual inspection misses rate interval mismatches, label collisions, and unbounded selectors):

- Parse each panel's query (PromQL, LogQL, TraceQL, or SQL depending on plugin)
- Check for common anti-patterns:
  - Missing `$__rate_interval` or hardcoded rate intervals
  - Unbounded label selectors (e.g., `{__name__=~".+"}`)
  - `rate()` without appropriate range vector
  - Recording rule candidates (complex expressions used in multiple panels)
- Verify query references to variables use correct interpolation format (`$variable` or `${variable}`)
- Queries failing syntactic validation (malformed PromQL/LogQL) are critical blockers and halt analysis

#### Step 3: Variable Chain Analysis

Build the full dependency graph rather than reviewing variables in isolation, because Perses evaluates variables top-to-bottom and misordered dependencies cause empty dropdowns at render time:

- Build dependency graph from variable definitions
- Verify topological ordering (parent variables defined before children)
- Check for circular dependencies (critical blocker that prevents dashboard rendering)
- Validate `matchers` reference existing variables
- Check interpolation formats are appropriate for the context: `csv`, `regex`, `json`, `pipe`, `glob`, `lucene`, etc.
- Confirm `spec.display.name` and `spec.display.description` are set for user-facing variables
- Note: `sort_order` in `spec.display` affects the rendered dropdown order but not dependency resolution—do not confuse them

#### Step 4: Datasource Scoping

Datasources in Perses have explicit scope (global or project-level). A panel referencing a project-scoped datasource from another project will fail silently at render time, so assume nothing about datasource reach:

- Map each panel to its datasource reference
- Verify datasource scope (global vs. project-level) matches the dashboard's project
- Check for datasources referenced but not defined in the dashboard's `spec.datasources` (critical blocker)
- Flag proxy configuration issues if datasource URLs are internal-only
- Never change datasource assignments during review—only report scope mismatches

#### Step 5: Metadata and Usability

- Check for missing panel titles or descriptions
- Verify dashboard-level `spec.display` has a meaningful name
- Flag panels with identical titles (confusing for users)
- Check `spec.duration` (default time range) is set appropriately
- Preserve dashboard identity: never change dashboard name, project assignment, or display metadata unless explicitly requested

**Completion Gate**: All five analysis steps completed. Findings collected and categorized. Proceed to Phase 3.

### Phase 3: REPORT

**Goal**: Generate a structured findings report with severity levels and recommendations.

Assign severity by impact:
- **Critical**: Dashboard is broken or produces wrong data
- **Warning**: Dashboard works but has performance or usability issues
- **Info**: Cosmetic or best-practice suggestions

Note: A dashboard that renders without errors is not necessarily correct—analyze query semantics and layout structure, not just render success.

Format findings as:

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

**Completion Gate**: Report generated with all findings categorized. If `--fix` flag not present, task complete.

### Phase 4: FIX (optional, requires --fix flag)

**Goal**: Apply recommended improvements to the dashboard. This phase is OFF by default—never modify a dashboard without `--fix` mode or explicit user confirmation.

1. Present the list of proposed fixes to the user for confirmation
2. Apply approved fixes to the dashboard JSON (never auto-fix circular variable dependencies without user approval)
3. Deploy the updated dashboard via MCP or percli:
   ```
   perses_update_dashboard(project=<project>, dashboard=<name>, body=<updated_json>)
   # OR
   percli apply -f <updated_dashboard.json> --project <project>
   ```
4. Re-run Phase 2 ANALYZE on the updated dashboard to verify fixes resolved the findings

**Completion Gate**: Fixes applied and verified. Task complete.

## Error Handling

### MCP Tools Not Available
**Symptom**: `perses_get_dashboard_by_name` or `perses_list_dashboards` calls fail or are not registered.
**Action**: Fall back to percli CLI. Run `percli describe dashboard <name> --project <project> -ojson`. If percli is also unavailable, ask the user to provide the dashboard JSON directly or check MCP server configuration.

### Dashboard Not Found
**Symptom**: MCP or percli returns 404 or empty result for the dashboard name.
**Action**: List available dashboards with `perses_list_dashboards(project=<project>)` or `percli get dashboard --project <project>`. Confirm the project name and dashboard name with the user. Dashboard names are case-sensitive and use kebab-case by convention.

### Datasource Unreachable
**Symptom**: Datasource referenced in panels returns connection errors, proxy failures, or auth rejections during validation.
**Action**: Log the unreachable datasource as an info-level finding (not a dashboard quality issue). Note which panels are affected. Do not block the review -- continue analyzing query syntax and structure without live validation. Suggest the user verify network/proxy/auth configuration separately.

### Variable Chain Circular Dependency
**Symptom**: Variable A depends on variable B which depends on variable A (directly or transitively).
**Action**: Flag as a **critical** finding. Map the full dependency cycle and include it in the report. In `--fix` mode, propose breaking the cycle by making one variable static or removing the circular matcher. Never auto-fix circular dependencies without user confirmation.

### Malformed Dashboard JSON
**Symptom**: Dashboard definition fails to parse or is missing required fields (`kind`, `metadata`, `spec`).
**Action**: Report the structural error and halt analysis. Do not attempt partial review of a malformed definition -- the results would be unreliable.

## References

- **Perses Dashboard Spec**: Dashboard JSON structure, panel plugins, layout system
- **27 Official Plugins**: TimeSeriesChart, GaugeChart, StatChart, MarkdownPanel, ScatterChart, BarChart, StatusHistoryChart, TextVariable, ListVariable, LabelNamesVariable, LabelValuesVariable, PrometheusLabelNamesVariable, PrometheusLabelValuesVariable, PrometheusPromQLVariable, StaticListVariable, PrometheusTimeSeriesQuery, PrometheusDatasource, HTTPProxy, TempoDatasource, TempoTraceQuery, LogsPanel, LokiDatasource, LokiLogsQuery, SQLDatasource, SQLQuery, and more
- **Variable Interpolation Formats**: csv, regex, json, pipe, glob, lucene (applied via `spec.display.format`)
- **MCP Tools**: `perses_get_dashboard_by_name`, `perses_list_dashboards`, `perses_update_dashboard`
- **percli CLI**: `percli describe dashboard`, `percli get dashboard`, `percli apply`
- **Grid Layout**: 24-column system with collapsible row support
