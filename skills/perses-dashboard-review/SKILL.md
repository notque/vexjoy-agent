---
name: perses-dashboard-review
user-invocable: false
description: |
  Review existing Perses dashboards for quality: fetch via MCP or API, analyze panel
  layout, query efficiency, variable usage, datasource configuration. Generate
  improvement report. Optional --fix mode. 4-phase pipeline: FETCH, ANALYZE, REPORT, FIX.
  Use for "review perses dashboard", "audit dashboard", "perses dashboard quality".
  Do NOT use for creating new dashboards (use perses-dashboard-create).
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

# Perses Dashboard Review

Analyze and improve existing Perses dashboards through structured review of layout, queries, variables, and datasource configuration.

## Operator Context

This skill operates as a non-destructive auditor of Perses dashboards, fetching definitions via MCP tools or percli CLI, then systematically analyzing them against quality criteria.

### Hardcoded Behaviors (Always Apply)
- **Non-destructive by default** -- never modify dashboards without explicit `--fix` flag or user confirmation
- **MCP-first retrieval** -- attempt `perses_get_dashboard_by_name` before falling back to percli CLI
- **Structured findings** -- every finding must have a severity (critical, warning, info) and a concrete recommendation
- **Full-scope analysis** -- check all five review areas (layout, queries, variables, datasources, metadata) on every review
- **Preserve dashboard identity** -- never change dashboard name, project assignment, or display metadata unless explicitly requested

### Default Behaviors (ON unless disabled)
- **Severity-sorted output** -- report findings from critical to info
- **Query validation** -- check PromQL/LogQL syntax and common anti-patterns (missing rate intervals, unbounded selectors)
- **Variable chain analysis** -- trace variable dependencies and verify ordering
- **Layout audit** -- flag orphan panels, empty rows, and width overflows

### Optional Behaviors (OFF unless enabled)
- **Fix mode** (`--fix`) -- apply recommended improvements and redeploy
- **Performance scoring** -- assign a numeric quality score (0-100) to the dashboard
- **Cross-dashboard analysis** -- compare variable/datasource usage across multiple dashboards in the same project

## What This Skill CAN Do
- Fetch dashboard definitions via MCP tools or percli CLI
- Analyze panel grid layout for organization and efficiency
- Audit PromQL and LogQL queries for correctness and performance
- Validate variable chains for dependency ordering and circular references
- Check datasource scoping and reachability
- Identify unused panels, missing descriptions, and unclear titles
- Generate a structured findings report with severity levels
- Apply fixes when `--fix` mode is enabled

## What This Skill CANNOT Do
- Create new dashboards from scratch (use `perses-dashboard-create`)
- Develop or modify Perses plugins (use `perses-plugin-create`)
- Deploy or configure Perses server instances (use `perses-deploy`)
- Manage Perses projects, roles, or RBAC configuration

---

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

---

## Anti-Patterns

### Reviewing Only Panel Queries Without Checking Layout
**Wrong**: Jump straight to PromQL/LogQL analysis and ignore how panels are organized.
**Right**: Always start with layout review (Phase 2, Step 1). A dashboard with correct queries but chaotic layout is still a poor dashboard. Check grid positioning, row grouping, collapsible sections, and panel widths before diving into queries.

### Not Checking Variable Dependency Ordering
**Wrong**: Review variables in isolation without tracing which variables feed into others.
**Right**: Build a dependency graph of all variables. Verify that variables are defined in topological order (parents before children). Check that matchers like `$variable_name` reference variables that are already resolved. Variable `sort_order` in `spec.display` affects the rendered dropdown but not dependency resolution -- don't confuse the two.

### Ignoring Datasource Scope Mismatches
**Wrong**: Assume all panels can reach all datasources because they're "in the same Perses instance."
**Right**: Datasources in Perses have explicit scope (global or project-level). A panel referencing a project-scoped datasource from another project will fail silently at render time. Verify that every panel's datasource reference resolves within the dashboard's project scope or is globally available.

### Treating All Findings as Equal Severity
**Wrong**: List every finding as a flat bullet list without distinguishing between broken queries and cosmetic suggestions.
**Right**: Assign severity levels. Critical = dashboard is broken or produces wrong data. Warning = dashboard works but has performance or usability issues. Info = cosmetic or best-practice suggestions.

---

## Anti-Rationalization

| Rationalization | Reality | Required Action |
|-----------------|---------|-----------------|
| "The queries look correct to me" | Visual inspection misses rate interval mismatches, label collisions, and unbounded selectors | **Parse and validate each query against known anti-patterns** |
| "Variable ordering doesn't matter" | Perses evaluates variables top-to-bottom; misordered dependencies cause empty dropdowns | **Build the dependency graph and verify topological order** |
| "Only a few panels -- quick scan is enough" | Small dashboards still have datasource scoping, variable chains, and layout issues | **Run the full 4-phase pipeline regardless of dashboard size** |
| "The dashboard renders fine so it must be correct" | Rendering without errors does not mean queries return correct data or layout is optimal | **Analyze query semantics and layout structure, not just render success** |

---

## FORBIDDEN Patterns

- **NEVER** modify a dashboard without `--fix` mode or explicit user confirmation
- **NEVER** delete panels, variables, or datasources during review -- only flag them as findings
- **NEVER** skip the FETCH phase and work from stale or assumed dashboard state
- **NEVER** report on dashboard quality without actually retrieving the current definition
- **NEVER** auto-fix circular variable dependencies without user approval
- **NEVER** change datasource assignments -- only report scope mismatches

---

## Blocker Criteria

The review **MUST NOT** proceed past the FETCH phase if:
- Dashboard definition cannot be retrieved (MCP + percli both fail, no JSON provided)
- Dashboard JSON is malformed and fails structural validation
- Project does not exist or user lacks read permissions

The review **MUST** flag as critical blockers:
- Circular variable dependency chains
- Panels referencing non-existent datasources
- Queries that fail syntactic validation (malformed PromQL/LogQL)
- Grid layout with panels exceeding the 24-column width limit

---

## Instructions

### Phase 1: FETCH

**Goal**: Retrieve the current dashboard definition.

1. Attempt MCP retrieval:
   ```
   perses_get_dashboard_by_name(project=<project>, dashboard=<name>)
   ```
2. If MCP unavailable, fall back to percli:
   ```bash
   percli describe dashboard <name> --project <project> -ojson
   ```
3. If both fail, ask the user to provide the dashboard JSON directly.
4. Parse and validate the JSON structure (`kind: Dashboard`, `metadata.name`, `spec.panels`, `spec.layouts`, `spec.variables`, `spec.datasources`).

**Gate**: Dashboard definition retrieved and structurally valid. Proceed to Phase 2.

### Phase 2: ANALYZE

**Goal**: Systematically audit all dashboard components.

#### Step 1: Layout Review
- Verify grid layout uses 24-column system correctly (no panel exceeds width 24)
- Check for collapsible rows with logical grouping
- Identify orphan panels (defined in `spec.panels` but absent from `spec.layouts`)
- Flag empty rows or sections with no panels

#### Step 2: Query Analysis
- Parse each panel's query (PromQL, LogQL, TraceQL, or SQL depending on plugin)
- Check for common anti-patterns:
  - Missing `$__rate_interval` or hardcoded rate intervals
  - Unbounded label selectors (e.g., `{__name__=~".+"}`)
  - `rate()` without appropriate range vector
  - Recording rule candidates (complex expressions used in multiple panels)
- Verify query references to variables use correct interpolation format (`$variable` or `${variable}`)

#### Step 3: Variable Chain Analysis
- Build dependency graph from variable definitions
- Verify topological ordering (parent variables defined before children)
- Check for circular dependencies
- Validate `matchers` reference existing variables
- Check interpolation formats are appropriate for the context: `csv`, `regex`, `json`, `pipe`, `glob`, `lucene`, etc.
- Confirm `spec.display.name` and `spec.display.description` are set for user-facing variables

#### Step 4: Datasource Scoping
- Map each panel to its datasource reference
- Verify datasource scope (global vs. project-level) matches the dashboard's project
- Check for datasources referenced but not defined in the dashboard's `spec.datasources`
- Flag proxy configuration issues if datasource URLs are internal-only

#### Step 5: Metadata and Usability
- Check for missing panel titles or descriptions
- Verify dashboard-level `spec.display` has a meaningful name
- Flag panels with identical titles (confusing for users)
- Check `spec.duration` (default time range) is set appropriately

**Gate**: All five analysis steps completed. Proceed to Phase 3.

### Phase 3: REPORT

**Goal**: Generate a structured findings report.

Output format:
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

**Gate**: Report generated with all findings categorized. If `--fix` not requested, task complete.

### Phase 4: FIX (optional, requires --fix)

**Goal**: Apply recommended improvements.

1. Present the list of proposed fixes to the user for confirmation
2. Apply approved fixes to the dashboard JSON
3. Deploy the updated dashboard:
   ```
   perses_update_dashboard(project=<project>, dashboard=<name>, body=<updated_json>)
   # OR
   percli apply -f <updated_dashboard.json> --project <project>
   ```
4. Re-run Phase 2 ANALYZE on the updated dashboard to verify fixes resolved the findings

**Gate**: Fixes applied and verified. Task complete.

---

## References

- **Perses Dashboard Spec**: Dashboard JSON structure, panel plugins, layout system
- **27 Official Plugins**: TimeSeriesChart, GaugeChart, StatChart, MarkdownPanel, ScatterChart, BarChart, StatusHistoryChart, TextVariable, ListVariable, LabelNamesVariable, LabelValuesVariable, PrometheusLabelNamesVariable, PrometheusLabelValuesVariable, PrometheusPromQLVariable, StaticListVariable, PrometheusTimeSeriesQuery, PrometheusDatasource, HTTPProxy, TempoDatasource, TempoTraceQuery, LogsPanel, LokiDatasource, LokiLogsQuery, SQLDatasource, SQLQuery, and more
- **Variable Interpolation Formats**: csv, regex, json, pipe, glob, lucene (applied via `spec.display.format`)
- **MCP Tools**: `perses_get_dashboard_by_name`, `perses_list_dashboards`, `perses_update_dashboard`
- **percli CLI**: `percli describe dashboard`, `percli get dashboard`, `percli apply`
- **Grid Layout**: 24-column system with collapsible row support
