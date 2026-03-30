---
name: perses-datasource-manage
user-invocable: false
description: "Perses datasource lifecycle: create, update, delete across scopes."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
agent: perses-engineer
version: 2.0.0
routing:
  triggers:
    - "manage datasource"
    - "Perses datasource"
  category: perses
---

# Perses Datasource Management

Create, update, and manage datasources across scopes. Use Perses MCP tools when available; fall back to percli CLI when MCP is not connected.

## Instructions

### Phase 1: IDENTIFY

**Goal**: Determine datasource type, scope, and connection details.

Before proceeding, confirm the backend URL is reachable and the datasource type is one of the 6 supported plugin kinds. If either is unknown or unresolvable, stop and ask the user because a datasource cannot function without a valid backend, and Perses does not support arbitrary plugins without custom development.

**Supported types** (use exact casing because these are case-sensitive Go type identifiers; `prometheusdatasource` or `prometheus` will fail with an unhelpful "invalid plugin kind" error):

| Plugin Kind | Backend | Common Endpoints |
|-------------|---------|-----------------|
| PrometheusDatasource | Prometheus | `/api/v1/.*` |
| TempoDatasource | Tempo | `/api/traces/.*`, `/api/search` |
| LokiDatasource | Loki | `/loki/api/v1/.*` |
| PyroscopeDatasource | Pyroscope | `/pyroscope/.*` |
| ClickHouseDatasource | ClickHouse | N/A (direct connection) |
| VictoriaLogsDatasource | VictoriaLogs | `/select/.*` |

If the user requests a plugin kind not installed on the Perses server, verify available plugins before attempting creation.

**Scopes** (priority order, highest first): Dashboard > Project > Global

A dashboard-scoped datasource overrides a project-scoped one of the same name, which overrides a global one. Choose scope deliberately at creation time because moving from global to project later requires deleting the global datasource and recreating it as project-scoped — a disruptive migration. Ask: "Does every project need this, or just one team?"

- **Global**: Organization-wide defaults. Default to this scope unless the user specifies a project. Place team-specific backends at project scope because it pollutes the namespace and makes per-team access control impossible.
- **Project**: Team-specific overrides. Use when a datasource serves more than one dashboard but not the entire organization. The project datasource `metadata.name` must match the global datasource name exactly for override to work (names are case-sensitive).
- **Dashboard**: One-off configurations embedded in the dashboard spec. Reserve for true one-off test configurations only because dashboard-scoped config is duplicated in every dashboard that needs it and cannot be shared.

Set the first datasource of each plugin kind as `default: true` so dashboard panels auto-discover it. Set `default: true` on exactly one datasource per plugin kind per scope because behavior with multiple defaults is undefined and varies between Perses versions.

**Gate**: Type, scope, and connection URL identified. Proceed to Phase 2.

### Phase 2: CREATE

**Goal**: Create the datasource resource.

Every HTTP proxy datasource **must** include `allowedEndpoints` with both `endpointPattern` and explicit `method` entries. Without them, the proxy returns 403 on all queries with no useful error message. Always use explicit method entries or omit the `method` field because the Perses proxy requires explicit method matching. Configure both GET and POST for most backends because Prometheus `/api/v1/query_range` and `/api/v1/labels` use POST for large payloads, and Loki/Tempo also mix methods.

Keep secrets out of (passwords, tokens) in datasource YAML committed to version control — use Perses native auth or external secret management.

For non-local deployments, use container/service names instead of `localhost`. In Docker, use the container network name or `host.docker.internal`. In Kubernetes, use the service DNS name (e.g., `http://prometheus.monitoring.svc:9090`). `localhost` refers to the container itself and will break.

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

**Via percli** (Project-scoped Datasource):
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

**Gate**: Datasource created without errors. Proceed to Phase 3.

### Phase 3: VERIFY

**Goal**: Confirm the datasource exists and is accessible.

Creation succeeding only means the API accepted the resource definition. It does not validate that the backend URL is reachable or that allowedEndpoints are correct. Always test with a real query.

```bash
# Global datasources
percli get globaldatasource

# Project datasources
percli get datasource --project <project>

# Describe specific datasource
percli describe globaldatasource <name>

# Test proxy connectivity (global) -- this is the real validation
curl -s http://localhost:8080/proxy/globaldatasources/<name>/api/v1/query?query=up

# Test proxy connectivity (project-scoped)
curl -s http://localhost:8080/proxy/projects/<project>/datasources/<name>/api/v1/query?query=up
```

Or via MCP:
```
perses_list_global_datasources()
perses_list_datasources(project="<project>")
```

If the proxy test returns persistent 5xx errors, this indicates infrastructure issues beyond datasource configuration — stop and escalate to the user.

Before deleting any global datasource, check which projects and dashboards reference it by running `percli get datasource --project <project>` across all projects. If it is used by multiple projects, confirm the blast radius with the user before proceeding.

**Gate**: Datasource listed, configuration confirmed, and proxy query returns a non-error response. Task complete.

---

## Error Handling

| Symptom | Cause | Solution |
|---------|-------|----------|
| Datasource proxy returns **403 Access Denied** | `allowedEndpoints` not configured, or the HTTP method in the endpoint pattern does not match the request method (e.g., only GET defined but query uses POST) | Add the missing endpoint patterns to `spec.plugin.spec.proxy.spec.allowedEndpoints`. Prometheus needs both GET and POST for `/api/v1/.*`. Tempo needs GET for `/api/traces/.*` and POST for `/api/search` |
| MCP tool `perses_create_global_datasource` fails with **conflict/already exists** | A GlobalDatasource with that name already exists | Use `perses_update_global_datasource` instead, or delete the existing one first with `percli delete globaldatasource <name>`. To check: `perses_list_global_datasources()` |
| MCP tool fails with **invalid plugin kind** | The `type` parameter does not match a registered plugin kind exactly | Use the exact casing: `PrometheusDatasource`, `TempoDatasource`, `LokiDatasource`, `PyroscopeDatasource`, `ClickHouseDatasource`, `VictoriaLogsDatasource`. These are case-sensitive |
| Datasource connectivity test fails (proxy returns **502/504**) | Backend URL is unreachable from the Perses server. The server cannot connect to the datasource backend at the configured URL | Verify the backend URL is reachable from the Perses server's network context. For Docker, use `host.docker.internal` or the container network name instead of `localhost`. For K8s, use the service DNS name (e.g., `http://prometheus.monitoring.svc:9090`) |
| Proxy returns **TLS handshake error** | Backend uses HTTPS but Perses cannot verify the certificate (self-signed or missing CA) | For self-signed certs, configure the CA in the Perses server's trust store or set the `PERSES_DATASOURCE_SKIP_TLS_VERIFY` environment variable if available. Prefer fixing the cert chain over disabling verification |
| Project datasource does **not override** global datasource | The project datasource `metadata.name` does not match the global datasource name exactly. Override only works when names are identical | Ensure the project-scoped `Datasource` has the exact same `metadata.name` as the `GlobalDatasource` it should override. Names are case-sensitive |

---

## References

| Resource | URL |
|----------|-----|
| Perses datasource documentation | https://perses.dev/docs/user-guides/datasources/ |
| Perses HTTP proxy configuration | https://perses.dev/docs/user-guides/datasources/#http-proxy |
| Perses API: GlobalDatasource | https://perses.dev/docs/api/datasource/ |
| Perses MCP server (datasource tools) | https://github.com/perses/perses-mcp-server |
| percli reference | https://perses.dev/docs/user-guides/percli/ |
| Perses GitHub repository | https://github.com/perses/perses |
