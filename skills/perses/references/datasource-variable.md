# Datasource and Variable Management

## Datasource Management

Create, update, and manage datasources across scopes. Use Perses MCP tools when available; fall back to percli CLI.

### Phase 1: IDENTIFY

**Goal**: Determine datasource type, scope, and connection details.

Confirm the backend URL is reachable and the datasource type is one of the 6 supported plugin kinds before proceeding.

**Supported types** (exact casing required -- case-sensitive Go type identifiers):

| Plugin Kind | Backend | Common Endpoints |
|-------------|---------|-----------------|
| PrometheusDatasource | Prometheus | `/api/v1/.*` |
| TempoDatasource | Tempo | `/api/traces/.*`, `/api/search` |
| LokiDatasource | Loki | `/loki/api/v1/.*` |
| PyroscopeDatasource | Pyroscope | `/pyroscope/.*` |
| ClickHouseDatasource | ClickHouse | N/A (direct connection) |
| VictoriaLogsDatasource | VictoriaLogs | `/select/.*` |

**Scopes** (priority order, highest first): Dashboard > Project > Global

- **Global**: Organization-wide defaults. Default scope unless user specifies a project.
- **Project**: Team-specific overrides. `metadata.name` must match global name exactly for override.
- **Dashboard**: One-off configurations. Reserve for true one-off test configs only.

Set `default: true` on exactly one datasource per plugin kind per scope.

**Gate**: Type, scope, and connection URL identified. Proceed to Phase 2.

### Phase 2: CREATE

**Goal**: Create the datasource resource.

Every HTTP proxy datasource **must** include `allowedEndpoints` with both `endpointPattern` and explicit `method` entries. Configure both GET and POST for most backends.

Keep secrets out of datasource YAML in version control. For non-local deployments, use container/service names instead of `localhost`.

**Via MCP** (preferred):
```
perses_create_global_datasource(name="prometheus", type="PrometheusDatasource", url="http://prometheus:9090")
```

**Via percli** (GlobalDatasource):
```bash
percli apply -f - <<EOF
kind: GlobalDatasource
metadata:
  name: prometheus
spec:
  default: true
  plugin:
    kind: PrometheusDatasource
    spec:
      proxy:
        kind: HTTPProxy
        spec:
          url: http://prometheus:9090
          allowedEndpoints:
            - endpointPattern: /api/v1/.*
              method: POST
            - endpointPattern: /api/v1/.*
              method: GET
EOF
```

**Via percli** (Project-scoped):
```bash
percli apply -f - <<EOF
kind: Datasource
metadata:
  name: prometheus
  project: <project-name>
spec:
  default: true
  plugin:
    kind: PrometheusDatasource
    spec:
      proxy:
        kind: HTTPProxy
        spec:
          url: http://prometheus:9090
          allowedEndpoints:
            - endpointPattern: /api/v1/.*
              method: POST
            - endpointPattern: /api/v1/.*
              method: GET
EOF
```

**Gate**: Datasource created. Proceed to Phase 3.

### Phase 3: VERIFY

**Goal**: Confirm the datasource exists and is accessible.

Creation success only means the API accepted the definition. Always test with a real query.

```bash
percli get globaldatasource
percli get datasource --project <project>
percli describe globaldatasource <name>

# Test proxy connectivity -- the real validation
curl -s http://localhost:8080/proxy/globaldatasources/<name>/api/v1/query?query=up
curl -s http://localhost:8080/proxy/projects/<project>/datasources/<name>/api/v1/query?query=up
```

Or via MCP:
```
perses_list_global_datasources()
perses_list_datasources(project="<project>")
```

**Gate**: Datasource listed, proxy query returns non-error response. Task complete.

### Datasource Error Handling

| Symptom | Cause | Solution |
|---------|-------|----------|
| **403 Access Denied** | `allowedEndpoints` not configured or method mismatch | Add endpoint patterns with both GET and POST |
| **conflict/already exists** | GlobalDatasource name already taken | Use update instead, or delete first |
| **invalid plugin kind** | Wrong casing | Use exact: `PrometheusDatasource`, `TempoDatasource`, etc. |
| **502/504** | Backend URL unreachable from Perses | Use `host.docker.internal` or service DNS name |
| **TLS handshake error** | Self-signed cert | Configure CA in trust store |
| **Override not working** | Project datasource name doesn't match global | Ensure exact same `metadata.name` |

---

## Variable Management

Create and manage variables with chains and interpolation.

### Overview

Full lifecycle of Perses variables: creation, configuration, chaining with dependencies, and interpolation across all scopes (global, project, dashboard).

### Phase 1: IDENTIFY

**Variable types**:
- **TextVariable**: Static text input for free-form filters.
- **ListVariable**: Dynamic dropdown populated by a plugin. Use for most filter use cases.

**Variable plugins** (for ListVariable):

| Plugin Kind | Source | Use Case |
|-------------|--------|----------|
| PrometheusLabelValuesVariable | Label values query | Filter by namespace, pod, job |
| PrometheusPromQLVariable | PromQL query results | Dynamic values from expressions |
| StaticListVariable | Hardcoded list | Fixed options (env, region) |
| DatasourceVariable | Available datasources | Switch between instances |

**Variable scopes**:

| Scope | Resource Kind | Use Case |
|-------|---------------|----------|
| Global | GlobalVariable | Shared across all projects |
| Project | Variable (in project) | Shared within a project |
| Dashboard | variables[] in dashboard spec | Dashboard-specific filters |

**Interpolation formats** (`${var:format}`):

| Format | Output Example | Use Case |
|--------|---------------|----------|
| csv | `a,b,c` | Multi-value in most contexts |
| json | `["a","b","c"]` | JSON-compatible contexts |
| regex | `a\|b\|c` | Prometheus `=~` matchers |
| pipe | `a\|b\|c` | Pipe-delimited lists |
| glob | `{a,b,c}` | Glob-style matching |
| lucene | `("a" OR "b" OR "c")` | Loki/Elasticsearch queries |
| values | `a+b+c` | URL query parameter encoding |
| singlevariablevalue | Single value | Extract one from multi-select |
| doublequote | `"a","b","c"` | Quoted CSV |
| singlequote | `'a','b','c'` | Single-quoted CSV |
| raw | `a` (first only) | Single value extraction |

**Key constraint**: Variables must be ordered with dependencies first. Perses evaluates in array order. A child referencing `$cluster` must appear after the cluster variable definition.

**Gate**: Variable type, plugin, scope, and dependencies identified. Proceed to Phase 2.

### Phase 2: CREATE

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

**Variable chain** (dashboard scope -- cluster -> namespace -> pod):

Order variables with dependencies first. Always include the `datasource` field. Use explicit interpolation formats.

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

**Gate**: Variables created. Proceed to Phase 3.

### Phase 3: VERIFY

```bash
percli get variable --project <project>
percli get globalvariable
percli describe variable <name> --project <project>
```

Or via MCP:
```
perses_list_variables(project="<project>")
perses_list_global_variables()
```

**Gate**: Variables listed and chain dependencies confirmed. Task complete.

### Variable Error Handling

| Cause | Symptom | Solution |
|-------|---------|----------|
| Chain break: child before parent | Child shows all values unfiltered | Reorder: parents before children |
| Wrong format: `${var:csv}` with `=~` | PromQL parse error | Use `${var:regex}` for `=~` matchers |
| Empty dropdown | No selectable options | Check labelName, matchers, datasource name, Prometheus reachability |
| MCP create fails | Variable not created | Check name uniqueness, project existence, plugin kind spelling |
| Matcher syntax error | Empty results | Use exact syntax: `"label=\"$var\""` with escaped quotes |

### Required Patterns

- **Always** order child variables after parents
- **Always** use `${var:regex}` for Prometheus `=~` or `!~` matchers
- **Always** include the `datasource` field in Prometheus variable plugins
- **Always** verify consuming queries use appropriate multi-value format before enabling `allowMultiple`

---

## References

- [Perses Datasource Documentation](https://perses.dev/docs/user-guides/datasources/)
- [Perses HTTP Proxy Configuration](https://perses.dev/docs/user-guides/datasources/#http-proxy)
- [Perses Variable Documentation](https://perses.dev/docs/user-guides/variables/)
- [Perses Variable Spec](https://github.com/perses/perses/tree/main/pkg/model/api/v1/variable)
- [Perses Plugin List](https://github.com/perses/plugins)
- [Perses MCP Server](https://github.com/perses/perses-mcp-server)
- [percli CLI Reference](https://perses.dev/docs/user-guides/percli/)
