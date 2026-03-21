---
name: perses-datasource-manage
user-invocable: false
description: |
  Perses datasource lifecycle management: create, update, delete datasources at
  global, project, or dashboard scope. Supports Prometheus, Tempo, Loki, Pyroscope,
  ClickHouse, and VictoriaLogs. Uses MCP tools when available, percli CLI as fallback.
  Use for "perses datasource", "add datasource", "configure prometheus perses",
  "perses data source". Do NOT use for dashboard creation (use perses-dashboard-create).
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
agent: perses-dashboard-engineer
version: 2.0.0
---

# Perses Datasource Management

Create, update, and manage datasources across scopes.

## Operator Context

This skill operates as the lifecycle manager for Perses datasources, handling creation, updates, and deletion across global, project, and dashboard scopes.

### Hardcoded Behaviors (Always Apply)
- **Scope-aware**: Always clarify scope — global (all projects), project, or dashboard — because scope determines resource kind and override priority
- **MCP-first**: Use Perses MCP tools when available, percli as fallback
- **Proxy configuration**: Always configure allowedEndpoints for HTTP proxy datasources — without them, queries will be blocked by the proxy

### Default Behaviors (ON unless disabled)
- **Global scope**: Default to global datasource unless project is specified
- **Default flag**: Set first datasource of each type as default

### Optional Behaviors (OFF unless enabled)
- **Multi-backend**: Configure multiple datasources of the same type with different names
- **Dashboard-scoped**: Embed datasource config directly in dashboard spec

## What This Skill CAN Do
- Create/update/delete datasources at any scope
- Configure HTTP proxy with allowed endpoints
- Manage datasource priority (global vs project vs dashboard)
- Support all 6 datasource types: Prometheus, Tempo, Loki, Pyroscope, ClickHouse, VictoriaLogs

## What This Skill CANNOT Do
- Create the datasource backends themselves (Prometheus, Loki, etc.)
- Manage Perses server configuration (use perses-deploy)
- Create dashboards (use perses-dashboard-create)

---

## Instructions

### Phase 1: IDENTIFY

**Goal**: Determine datasource type, scope, and connection details.

**Supported types**:

| Plugin Kind | Backend | Common Endpoints |
|-------------|---------|-----------------|
| PrometheusDatasource | Prometheus | `/api/v1/.*` |
| TempoDatasource | Tempo | `/api/traces/.*`, `/api/search` |
| LokiDatasource | Loki | `/loki/api/v1/.*` |
| PyroscopeDatasource | Pyroscope | `/pyroscope/.*` |
| ClickHouseDatasource | ClickHouse | N/A (direct connection) |
| VictoriaLogsDatasource | VictoriaLogs | `/select/.*` |

**Scopes** (priority order, highest first): Dashboard > Project > Global

A dashboard-scoped datasource overrides a project-scoped one of the same name, which overrides a global one. Use global for organization-wide defaults, project for team-specific overrides, dashboard for one-off configurations.

**Gate**: Type, scope, and connection URL identified. Proceed to Phase 2.

### Phase 2: CREATE

**Goal**: Create the datasource resource.

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

```bash
# Global datasources
percli get globaldatasource

# Project datasources
percli get datasource --project <project>

# Describe specific datasource
percli describe globaldatasource <name>

# Test proxy connectivity (global)
curl -s http://localhost:8080/proxy/globaldatasources/<name>/api/v1/query?query=up

# Test proxy connectivity (project-scoped)
curl -s http://localhost:8080/proxy/projects/<project>/datasources/<name>/api/v1/query?query=up
```

Or via MCP:
```
perses_list_global_datasources()
perses_list_datasources(project="<project>")
```

**Gate**: Datasource listed and configuration confirmed. Task complete.

---

## Error Handling

| Symptom | Cause | Solution |
|---------|-------|----------|
| Datasource proxy returns **403 Forbidden** | `allowedEndpoints` not configured, or the HTTP method in the endpoint pattern does not match the request method (e.g., only GET defined but query uses POST) | Add the missing endpoint patterns to `spec.plugin.spec.proxy.spec.allowedEndpoints`. Prometheus needs both GET and POST for `/api/v1/.*`. Tempo needs GET for `/api/traces/.*` and POST for `/api/search` |
| MCP tool `perses_create_global_datasource` fails with **conflict/already exists** | A GlobalDatasource with that name already exists | Use `perses_update_global_datasource` instead, or delete the existing one first with `percli delete globaldatasource <name>`. To check: `perses_list_global_datasources()` |
| MCP tool fails with **invalid plugin kind** | The `type` parameter does not match a registered plugin kind exactly | Use the exact casing: `PrometheusDatasource`, `TempoDatasource`, `LokiDatasource`, `PyroscopeDatasource`, `ClickHouseDatasource`, `VictoriaLogsDatasource`. These are case-sensitive |
| Datasource connectivity test fails (proxy returns **502/504**) | Backend URL is unreachable from the Perses server. The server cannot connect to the datasource backend at the configured URL | Verify the backend URL is reachable from the Perses server's network context. For Docker, use `host.docker.internal` or the container network name instead of `localhost`. For K8s, use the service DNS name (e.g., `http://prometheus.monitoring.svc:9090`) |
| Proxy returns **TLS handshake error** | Backend uses HTTPS but Perses cannot verify the certificate (self-signed or missing CA) | For self-signed certs, configure the CA in the Perses server's trust store or set the `PERSES_DATASOURCE_SKIP_TLS_VERIFY` environment variable if available. Prefer fixing the cert chain over disabling verification |
| Project datasource does **not override** global datasource | The project datasource `metadata.name` does not match the global datasource name exactly. Override only works when names are identical | Ensure the project-scoped `Datasource` has the exact same `metadata.name` as the `GlobalDatasource` it should override. Names are case-sensitive |

---

## Anti-Patterns

| Anti-Pattern | Why It Fails | Do This Instead |
|--------------|-------------|-----------------|
| Creating all datasources at global scope | Pollutes the namespace, makes per-team access control impossible, and forces every project to see every datasource | Use global scope only for organization-wide defaults. Use project-scoped datasources for team-specific backends |
| Omitting `allowedEndpoints` on HTTP proxy datasources | Queries are blocked silently — the proxy returns 403 with no useful error message in dashboards, making debugging difficult | Always define `allowedEndpoints` with both the `endpointPattern` regex and `method` for every HTTP proxy datasource |
| Not setting `default: true` on the primary datasource | Dashboard panels cannot auto-discover the datasource. Users must manually select it in every panel, and panel YAML must hardcode the datasource name | Set `default: true` on exactly one datasource per plugin kind per scope. If you have multiple Prometheus datasources, designate one as default |
| Using dashboard-scoped datasources when project scope would enable reuse | Dashboard-scoped datasource config is embedded in the dashboard JSON and cannot be shared. Every dashboard that needs it must duplicate the config | Use project-scoped datasources for any datasource used by more than one dashboard. Reserve dashboard scope for true one-off test configurations |
| Hardcoding `localhost` URLs in non-local deployments | Breaks when Perses runs in Docker or Kubernetes because `localhost` refers to the container, not the host | Use container/service names: Docker network names for Compose, K8s service DNS for Helm deployments |

---

## Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|---------------|-----------------|
| "The datasource was created successfully, so it must be working" | Creation succeeding only means the API accepted the resource definition. It does not validate that the backend URL is reachable or that allowedEndpoints are correct | **Test the proxy endpoint** with a real query: `curl` the `/proxy/globaldatasources/<name>/...` path and verify a non-error response |
| "I don't need allowedEndpoints because I'm only doing GET requests" | Prometheus `/api/v1/query_range` and `/api/v1/labels` use POST for large payloads. Loki and Tempo also mix methods. A GET-only config breaks silently on certain queries | **Always configure both GET and POST** for the relevant endpoint patterns unless the datasource documentation explicitly states only one method is used |
| "Global scope is fine — we can always move it later" | Moving from global to project scope requires deleting the global datasource and recreating it as project-scoped. All dashboards referencing it by name will keep working only if the project datasource name matches exactly. This is a disruptive migration | **Choose scope deliberately** at creation time. Ask: "Does every project need this, or just one team?" |
| "The datasource type name is probably case-insensitive" | Plugin kind names are case-sensitive Go type identifiers. `prometheusdatasource` or `prometheus` will fail with an unhelpful "invalid plugin kind" error | **Use exact casing**: `PrometheusDatasource`, `TempoDatasource`, etc. Copy from the supported types table |

---

## FORBIDDEN Patterns

These patterns cause silent failures, data loss, or security issues. Never use them.

- **NEVER** create a datasource without `allowedEndpoints` on HTTP proxy types — results in silent 403 on all queries
- **NEVER** use `method: *` or omit the `method` field in allowedEndpoints — the Perses proxy requires explicit method matching
- **NEVER** set `default: true` on multiple datasources of the same plugin kind at the same scope — behavior is undefined and varies between Perses versions
- **NEVER** embed secrets (passwords, tokens) in datasource YAML committed to version control — use Perses native auth or external secret management
- **NEVER** delete a global datasource without checking which projects and dashboards reference it — use `percli get datasource --project <project>` across all projects first

---

## Blocker Criteria

Stop and escalate to the user if ANY of these conditions are true:

- Backend URL is unknown or unresolvable — cannot create a functional datasource without a reachable backend
- Datasource type is not one of the 6 supported plugin kinds — Perses does not support arbitrary datasource plugins without custom plugin development
- User requests a datasource plugin kind that is not installed on the Perses server — verify available plugins before attempting creation
- Proxy test returns persistent 5xx errors after datasource creation — indicates infrastructure issues beyond datasource configuration
- User wants to delete a global datasource used by multiple projects — requires explicit confirmation of the blast radius

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
