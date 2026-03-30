---
name: perses-variable-manage
user-invocable: false
description: "Perses variable lifecycle: Text/List variables, chains, interpolation."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
agent: perses-dashboard-engineer
version: 2.0.0
routing:
  triggers:
    - "manage Perses variables"
    - "dashboard variables"
  category: perses
---

# Perses Variable Management

Create and manage variables with chains and interpolation.

## Overview

This skill manages the full lifecycle of Perses variables: creation, configuration, chaining with dependencies, and interpolation across all scopes (global, project, dashboard). Variable chains enable cascading filters where dependent variables only show values filtered by their parent selections — for example, a pod variable that only displays pods matching the selected cluster and namespace.

---

## Instructions

### Phase 1: IDENTIFY

**Goal**: Determine variable type, scope, and dependencies.

**Variable types**:
- **TextVariable**: Static text input — user types a value. Use for free-form filters like custom regex or label values not available via query.
- **ListVariable**: Dynamic dropdown populated by a plugin. Use for most filter/selector use cases.

**Variable plugins** (for ListVariable):

| Plugin Kind | Source | Use Case |
|-------------|--------|----------|
| PrometheusLabelValuesVariable | Label values query | Filter by namespace, pod, job |
| PrometheusPromQLVariable | PromQL query results | Dynamic values from expressions |
| StaticListVariable | Hardcoded list | Fixed options (env, region) |
| DatasourceVariable | Available datasources | Switch between datasource instances |

**Variable scopes**:

| Scope | Resource Kind | Use Case |
|-------|---------------|----------|
| Global | GlobalVariable | Shared filters across all projects and dashboards |
| Project | Variable (in project) | Shared filters across dashboards within a project |
| Dashboard | variables[] in dashboard spec | Dashboard-specific filters |

**Interpolation formats** (`${var:format}`):

| Format | Output Example | Use Case |
|--------|---------------|----------|
| csv | `a,b,c` | Multi-value in most contexts |
| json | `["a","b","c"]` | JSON-compatible contexts |
| regex | `a\|b\|c` | Prometheus label matchers with `=~` |
| pipe | `a\|b\|c` | Pipe-delimited lists |
| glob | `{a,b,c}` | Glob-style matching |
| lucene | `("a" OR "b" OR "c")` | Loki/Elasticsearch queries |
| values | `a+b+c` | URL query parameter encoding |
| singlevariablevalue | Single value | Extracts one value from multi-select |
| doublequote | `"a","b","c"` | Quoted CSV |
| singlequote | `'a','b','c'` | Single-quoted CSV |
| raw | `a` (first only) | Single value extraction |

**Key constraint on variable chains**: Variables must be ordered so dependencies come first because Perses evaluates variables in array order. A variable referencing `$cluster` must appear after the cluster variable definition. This is a strict sequencing requirement — if the parent variable appears after the child, the child will resolve `$cluster` as empty on first load, returning unfiltered results.

**Gate**: Variable type, plugin, scope, and dependencies identified. Proceed to Phase 2.

### Phase 2: CREATE

**Goal**: Create the variable resource(s).

**Single variable** (global scope):
```bash
percli apply -f - <<EOF
kind: GlobalVariable
metadata:
  name: namespace
spec:
  kind: ListVariable
  spec:
    name: namespace
    display:
      name: Namespace
      hidden: false
    allowAllValue: true
    allowMultiple: true
    plugin:
      kind: PrometheusLabelValuesVariable
      spec:
        labelName: namespace
        datasource:
          kind: PrometheusDatasource
          name: prometheus
EOF
```

**Via MCP** (project scope):
```
perses_create_project_variable(
  project="my-project",
  name="namespace",
  kind="ListVariable",
  plugin_kind="PrometheusLabelValuesVariable",
  plugin_spec={"labelName": "namespace", "datasource": {"kind": "PrometheusDatasource", "name": "prometheus"}},
  allow_multiple=true,
  allow_all_value=true
)
```

**Variable chain** (dashboard scope — cluster -> namespace -> pod):

When building chains, order variables with dependencies first. Each subsequent variable uses matchers that reference the previous variables using the exact syntax shown below. Always include the `datasource` field — Perses will not infer it and the variable will fail to resolve if omitted. Use explicit interpolation formats in consuming queries (regex for Prometheus `=~` matchers, csv for other contexts) to ensure multi-value substitution works correctly.

```yaml
variables:
  - kind: ListVariable
    spec:
      name: cluster
      display:
        name: Cluster
      allowAllValue: false
      allowMultiple: false
      plugin:
        kind: PrometheusLabelValuesVariable
        spec:
          labelName: cluster
          datasource:
            kind: PrometheusDatasource
            name: prometheus
  - kind: ListVariable
    spec:
      name: namespace
      display:
        name: Namespace
      allowAllValue: true
      allowMultiple: true
      plugin:
        kind: PrometheusLabelValuesVariable
        spec:
          labelName: namespace
          datasource:
            kind: PrometheusDatasource
            name: prometheus
          matchers:
            - "cluster=\"$cluster\""
  - kind: ListVariable
    spec:
      name: pod
      display:
        name: Pod
      allowAllValue: true
      allowMultiple: true
      plugin:
        kind: PrometheusLabelValuesVariable
        spec:
          labelName: pod
          datasource:
            kind: PrometheusDatasource
            name: prometheus
          matchers:
            - "cluster=\"$cluster\""
            - "namespace=\"$namespace\""
```

**Default behaviors** (applied unless overridden):
- Default to ListVariable with PrometheusLabelValuesVariable plugin for query-driven filtering
- Create variables at dashboard scope unless otherwise specified
- Enable `allowMultiple` and `allowAllValue` by default for filter variables (allows users to select all or no specific values)

**Gate**: Variables created without errors. Proceed to Phase 3.

### Phase 3: VERIFY

**Goal**: Confirm variables exist and chains resolve correctly.

```bash
# List variables in project
percli get variable --project <project>

# List global variables
percli get globalvariable

# Describe specific variable
percli describe variable <name> --project <project>
```

Or via MCP:
```
perses_list_variables(project="<project>")
perses_list_global_variables()
```

Verify chain behavior by checking that dependent variables correctly filter when parent values change (requires UI or API query testing).

**Gate**: Variables listed and chain dependencies confirmed. Task complete.

---

## Error Handling

| Cause | Symptom | Solution |
|-------|---------|----------|
| Variable chain break: dependent variable defined before its parent in the array | Child variable shows all values instead of filtering by parent selection; Perses evaluates variables in array order, so the parent has no value yet when the child resolves | Reorder the variables array so parents appear before children — cluster before namespace before pod. Each variable can only reference variables that appear earlier in the array |
| Wrong interpolation format: using `${var:csv}` where `${var:regex}` is needed | Prometheus query with `=~` matcher fails with parse error or matches nothing — `label=~"a,b,c"` is not valid regex, must be `label=~"a\|b\|c"` | Use `${var:regex}` for any Prometheus `=~` or `!~` label matchers. Reserve `${var:csv}` for contexts that accept comma-separated lists |
| PrometheusLabelValuesVariable returns empty dropdown | Variable renders with no selectable options despite metrics existing in Prometheus | Check: (1) `labelName` matches exact Prometheus label name (case-sensitive), (2) `matchers` filters are not too restrictive or referencing nonexistent parent variables, (3) datasource name matches a configured PrometheusDatasource, (4) Prometheus is reachable from Perses server |
| MCP `perses_create_project_variable` fails | Error returned from MCP tool call — variable not created | Check: (1) variable name does not already exist in the project (names must be unique per scope), (2) the target project exists (create it first with `perses_create_project`), (3) plugin kind is spelled correctly (e.g., `PrometheusLabelValuesVariable` not `PrometheusLabelValues`) |
| Matcher syntax error in child variable | Child variable returns empty results or Perses logs show query parse errors | Matchers must be exact PromQL label matcher syntax: `"label=\"$var\""` with escaped inner quotes. Missing escapes or wrong quote nesting breaks the matcher silently |

### Blockers

Stop and resolve before proceeding past each phase gate if any of these conditions exist:

**Phase 1 Blockers**:
- Variable dependency chain is circular (A -> B -> A) — restructure the chain
- Requested label does not exist in the target Prometheus — verify with `curl -s http://<prometheus>/api/v1/labels`
- No datasource of the required type is configured in the target project or globally

**Phase 2 Blockers**:
- `percli apply` or MCP tool returns an error — fix before proceeding
- Variable name conflicts with an existing variable at the same scope
- Matchers reference a parent variable that does not exist or is misspelled

**Phase 3 Blockers**:
- Variable list command does not show the created variable — creation failed silently
- Variable chain produces unfiltered results when parent is selected — dependency order or matcher syntax is wrong
- Variable dropdown is empty — plugin configuration, datasource, or label name is incorrect

### Anti-Rationalization Guards

These shortcuts seem reasonable but cause real failures:

- **"The variable order doesn't matter, they all resolve eventually"**: Perses evaluates variables strictly in array order, not by dependency graph. A child variable that appears before its parent will resolve against an empty parent value on first load, silently producing wrong results.
- **"I'll just use `$var` without a format — Perses will figure it out"**: Bare `$var` uses the default format which may not match the query context. For Prometheus `=~` matchers this silently produces wrong results. Always specify the interpolation format explicitly when the variable is multi-select.
- **"The variable works in the UI so the interpolation must be correct"**: It may work with a single selection but break with multiple selections. Always test with multiple values selected to verify the interpolation format produces valid query syntax.
- **"I'll create the variable and fix the chain order later"**: Variables that appear to work in isolation will return wrong results when chaining is broken, and the bug is subtle — dashboards show data, just unfiltered data. Get the dependency order right before creating any variables.

### Required Patterns

Ensure all configurations follow these requirements:

- **Always** order child variables after their parents in the variables array — this silently breaks filtering
- **Always** use `${var:regex}` for Prometheus `=~` or `!~` matchers — use `${var:regex}` instead
- **Always** use PrometheusLabelValuesVariable or PrometheusPromQLVariable for dynamic label values — use PrometheusLabelValuesVariable or PrometheusPromQLVariable instead
- **Always** verify all consuming queries use an appropriate multi-value interpolation format before enabling `allowMultiple: true` that all consuming queries use an appropriate multi-value interpolation format
- **Always** include the `datasource` field in Prometheus variable plugins — Perses will not infer it and the variable will fail to resolve

---

## References

| Resource | URL | Use For |
|----------|-----|---------|
| Perses Variable Documentation | https://perses.dev/docs/user-guides/variables/ | Variable types, scopes, and configuration |
| Perses Variable Spec (Go types) | https://github.com/perses/perses/tree/main/pkg/model/api/v1/variable | Authoritative field definitions for variable specs |
| Perses Plugin List | https://github.com/perses/plugins | Available variable plugins and their spec schemas |
| Perses MCP Server | https://github.com/perses/perses-mcp-server | MCP tool reference for variable CRUD operations |
| Interpolation Formats Source | https://github.com/perses/perses/tree/main/internal/api/variable | Implementation of all interpolation format handlers |
| percli CLI Reference | https://perses.dev/docs/user-guides/percli/ | CLI commands for variable management |
