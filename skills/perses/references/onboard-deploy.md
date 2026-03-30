# Onboard and Deploy

## Perses Onboard

First-time Perses setup and Claude Code integration pipeline.

### Overview

This is a 4-phase onboarding pipeline for new Perses users, guiding them from zero to a working Perses setup with Claude Code MCP integration. Scope: server discovery/deployment, MCP connection, initial project setup, and end-to-end validation. Out of scope: dashboard creation (use dashboard sub-domain), complex auth (use deploy section below), and plugin development (use plugin sub-domain).

### Phase 1: DISCOVER

**Goal**: Find or deploy a Perses server.

**Step 1: Check for existing Perses** (because we should reuse running instances before deploying)

```bash
# Check if percli is installed
which percli 2>/dev/null

# Check if already logged in
percli whoami 2>/dev/null

# Check common ports
curl -s http://localhost:8080/api/v1/health 2>/dev/null
```

**Step 2: Determine path** (because different scenarios require different actions)

| Scenario | Action |
|----------|--------|
| percli is logged in | Skip to Phase 2: CONNECT |
| Perses is running locally | Login with percli, proceed to Phase 2 |
| No Perses found, user has URL | Login to provided URL |
| No Perses found, no URL | Offer: (a) deploy locally with Docker, (b) use demo.perses.dev |

**Step 3: Deploy if needed** (route to deploy section for complex deployments; use simple Docker for quick local setup only)

For quick local setup:
```bash
docker run --name perses -d -p 127.0.0.1:8080:8080 persesdev/perses
```

**Step 4: Login**
```bash
percli login http://localhost:8080
# For demo: percli login https://demo.perses.dev
```

**Gate**: Perses server accessible, percli authenticated. Proceed to Phase 2.

### Phase 2: CONNECT

**Goal**: Set up Claude Code MCP integration (so Claude Code can manipulate Perses resources directly).

**Step 1: Check for Perses MCP server**

```bash
which perses-mcp-server 2>/dev/null
```

**Step 2: Install if needed** (because MCP server is a separate binary from Perses itself)

Guide user to install from https://github.com/perses/mcp-server/releases

**Step 3: Configure MCP server** (because MCP needs explicit credentials and resource scoping)

Create `perses-mcp-config.yaml`:
```yaml
transport: stdio
read_only: false
resources: "dashboard,project,datasource,globaldatasource,variable,globalvariable,plugin"
perses_server:
  url: "http://localhost:8080"
  authorization:
    type: Bearer
    credentials: "<token from percli whoami --show-token>"
```

**Step 4: Register in Claude Code settings** (because Claude Code MCP discovery reads from settings.json)

Add to `~/.claude/settings.json` under `mcpServers`:
```json
{
  "perses": {
    "command": "perses-mcp-server",
    "args": ["--config", "/path/to/perses-mcp-config.yaml"]
  }
}
```

**Step 5: Verify MCP connection** (because we must confirm the binary and socket are working before proceeding)

Use ToolSearch("perses") to check if MCP tools are discoverable. If found, test with `perses_list_projects`.

**Gate**: MCP server configured and responsive. Proceed to Phase 3.

### Phase 3: CONFIGURE

**Goal**: Create initial project and datasources (to establish a working workspace and data connectivity).

**Step 1: Create a project** (because projects provide resource isolation and role-based access control)

```bash
percli apply -f - <<EOF
kind: Project
metadata:
  name: default
spec: {}
EOF
percli project default
```

Or via MCP: `perses_create_project(project="default")`

**Step 2: Add a datasource** (optional; only if user has Prometheus/Tempo/Loki available)

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

**Gate**: Project and datasource configured. Proceed to Phase 4.

### Phase 4: VALIDATE

**Goal**: Verify the full setup works end-to-end.

**Checklist**:
- [ ] `percli whoami` shows authenticated user
- [ ] `percli get project` lists the created project
- [ ] `percli get globaldatasource` lists configured datasources (if any)
- [ ] MCP tools respond (if configured): `perses_list_projects` returns data
- [ ] Perses UI is accessible in browser at the configured URL

**Summary output**:
```
Perses Onboarding Complete:
  Server: http://localhost:8080
  Project: default
  Datasources: prometheus (global, default)
  MCP: configured (25+ tools available)
  CLI: percli authenticated as [authenticated-user]

Next steps:
  - Create a dashboard: /do create perses dashboard
  - Migrate Grafana dashboards: /do migrate grafana to perses
  - Set up Dashboard-as-Code: /do perses dac
```

**Gate**: All checks pass. Onboarding complete.

### Onboard Error Handling

**percli not installed**: Route user to [Perses installation docs](https://doc.perses.dev/latest/installation/installation/).

**Perses server not responding**: Verify the configured URL and server status. If using Docker, check `docker ps`.

**MCP server binary not found**: Guide user to [MCP releases](https://github.com/perses/mcp-server/releases).

**MCP connection fails after registration**: Verify perses-mcp-config.yaml syntax. Check bearer token validity. Restart Claude Code harness.

**MCP tools not discoverable**: Verify settings.json is syntactically correct JSON and perses-mcp-server command exists.

**Project creation fails with permissions error**: Verify user has admin role. Check `percli whoami` output.

**Datasource URL unreachable from Perses**: Perses server needs network access to the datasource URL. For local dev, ensure services are on the same Docker network.

---

## Perses Deploy

Deploy and configure Perses server instances across different environments.

### Overview

This section guides deploying Perses server instances (local development, Kubernetes, bare metal) and configuring them with databases, authentication, plugins, and provisioning folders.

By default, local dev deployments use Docker with file-based storage when no target is specified.

### Phase 1: ASSESS Environment

**Goal**: Determine deployment target and requirements.

1. **Deployment target**: Docker (local dev), Helm (Kubernetes), Binary (bare metal), or Operator (K8s CRDs)
2. **Storage backend**: File-based (default) or SQL (MySQL)
3. **Authentication**: None (local dev), Native, OIDC, OAuth, or K8s ServiceAccount
4. **Plugin requirements**: Official plugins only, or custom plugins too?
5. **MCP integration**: Should we also set up the Perses MCP server?

**Gate**: Environment assessed. Proceed to Phase 2.

### Phase 2: DEPLOY

**Goal**: Deploy Perses server.

#### Option A: Docker (Local Development)

```bash
docker run --name perses -d -p 127.0.0.1:8080:8080 persesdev/perses

# With custom config
docker run --name perses -d -p 127.0.0.1:8080:8080 \
  -v /path/to/config.yaml:/etc/perses/config.yaml \
  -v /path/to/data:/perses/data \
  persesdev/perses --config=/etc/perses/config.yaml
```

#### Option B: Helm (Kubernetes)

```bash
helm repo add perses https://perses.github.io/helm-charts
helm repo update
helm install perses perses/perses \
  --namespace perses --create-namespace \
  --set config.database.file.folder=/perses/data \
  --set config.security.enable_auth=true
```

#### Option C: Binary (Bare Metal)

```bash
brew install perses/tap/perses
brew install perses/tap/percli
perses --config=./config.yaml
```

#### Option D: Kubernetes Operator

```bash
helm repo add perses https://perses.github.io/helm-charts
helm install perses-operator perses/perses-operator \
  --namespace perses-system --create-namespace

cat <<EOF | kubectl apply -f -
apiVersion: perses.dev/v1alpha2
kind: Perses
metadata:
  name: perses
  namespace: perses
spec:
  config:
    database:
      file:
        folder: '/perses'
        extension: 'yaml'
  containerPort: 8080
EOF
```

**Gate**: Perses server deployed. Proceed to Phase 3.

### Phase 3: CONFIGURE

**Goal**: Configure server settings.

**Server configuration** (config.yaml):

```yaml
database:
  file:
    folder: "/perses/data"
    extension: "yaml"

security:
  readonly: false
  enable_auth: true
  encryption_key: "<32-byte-AES-256-key>"
  authentication:
    access_token_ttl: "15m"
    refresh_token_ttl: "24h"
    providers:
      enable_native: true

plugin:
  archive_path: "plugins-archive"
  path: "plugins"

provisioning:
  folders:
    - "/perses/provisioning"

frontend:
  time_range:
    disable_custom: false
```

**Environment variables** override config with `PERSES_` prefix:
- `PERSES_DATABASE_FILE_FOLDER=/perses/data`
- `PERSES_SECURITY_ENABLE_AUTH=true`
- `PERSES_SECURITY_ENCRYPTION_KEY=<key>`

**Gate**: Configuration applied. Proceed to Phase 4.

### Phase 4: VALIDATE

**Goal**: Verify deployment is healthy.

```bash
curl -s http://localhost:8080/api/v1/projects | head
percli login http://localhost:8080 --username admin --password <password>
percli whoami
percli apply -f - <<EOF
kind: Project
metadata:
  name: test
spec: {}
EOF
percli get project
```

**Gate**: Deployment verified. Task complete.

### Deploy Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused` | Perses not running | Check `docker ps` or process status |
| `401 Unauthorized` | Auth required but no credentials | Set `PERSES_SECURITY_ENABLE_AUTH=false` for local dev, or use `percli login` |
| `Port 8080 already in use` | Port conflict | Use `-p 127.0.0.1:9090:8080` or kill conflicting process |
| `percli login: invalid credentials` | Password mismatch | Check config or reset via env var |
| `Plugin archive not found` | Plugin path doesn't exist | Create directory or update config |
| Helm install fails | K8s namespace doesn't exist | Use `--create-namespace` |

---

## References

- [Perses Documentation](https://doc.perses.dev/)
- [percli Installation](https://doc.perses.dev/latest/cli/installation/)
- [Perses MCP Server](https://github.com/perses/mcp-server)
- [Perses GitHub](https://github.com/perses/perses)
- [Helm Charts](https://github.com/perses/helm-charts)
- [Claude Code MCP Configuration](https://claude.ai/docs/mcp)
