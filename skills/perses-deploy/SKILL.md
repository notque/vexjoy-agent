---
name: perses-deploy
user-invocable: false
description: "Deploy Perses server: Docker Compose, Helm, or binary installation."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
  - WebFetch
  - WebSearch
version: 2.0.0
routing:
  triggers:
    - "deploy Perses"
    - "Perses server setup"
  category: perses
---

# Perses Deploy

Deploy and configure Perses server instances across different environments.

## Overview

This skill guides you through deploying Perses server instances (local development, Kubernetes, bare metal) and configuring them with databases, authentication, plugins, and provisioning folders. **Route to other skills for dashboard creation (use perses-dashboard-create) or plugin development (use perses-plugin-create).**

By default, local dev deployments use Docker with file-based storage when no target is specified. Health checks verify the API is accessible after deployment. Plugin loading configures official plugins from the perses/plugins repository.

---

## Instructions

### Phase 1: ASSESS Environment

**Goal**: Determine deployment target and requirements.

1. **Deployment target**: Choose Docker (local dev), Helm (Kubernetes), Binary (bare metal), or Operator (K8s CRDs)
   - Defaults to Docker with file-based storage when no target is specified
2. **Storage backend**: File-based (default, no external DB needed) or SQL (MySQL)
3. **Authentication**: None (local dev), Native (username/password), OIDC, OAuth, or K8s ServiceAccount
   - For non-local deployments, enable at minimum native auth because public API access requires credentials
4. **Plugin requirements**: Official plugins only, or custom plugins too?
   - Perses will auto-configure official plugins from perses/plugins repository by default
5. **MCP integration**: Should we also set up the Perses MCP server for Claude Code?

**Gate**: Environment assessed. Proceed to Phase 2.

### Phase 2: DEPLOY

**Goal**: Deploy Perses server.

#### Option A: Docker (Local Development)

```bash
# Simplest — single container with defaults
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
# Install via Homebrew
brew install perses/tap/perses
brew install perses/tap/percli

# Or download from GitHub releases
# Run with config
perses --config=./config.yaml
```

#### Option D: Kubernetes Operator

```bash
helm repo add perses https://perses.github.io/helm-charts
helm install perses-operator perses/perses-operator \
  --namespace perses-system --create-namespace

# Then create a Perses CR
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

**Goal**: Configure server settings to control database, auth, plugins, and provisioning.

**Server configuration** (config.yaml):

```yaml
# Database
database:
  file:
    folder: "/perses/data"
    extension: "yaml"

# Security — ALWAYS configure auth for non-local deployments (minimum native auth)
security:
  readonly: false
  enable_auth: true
  # Use 32-byte AES-256 key — always use env vars or secrets for sensitive values, use env var or secrets
  encryption_key: "<32-byte-AES-256-key>"
  authentication:
    access_token_ttl: "15m"
    refresh_token_ttl: "24h"
    providers:
      enable_native: true
      # oidc:
      #   - slug_id: github
      #     name: "GitHub"
      #     client_id: "<client-id>"
      #     client_secret: "<client-secret>"
      #     issuer: "https://github.com"
      #     redirect_uri: "https://perses.example.com/api/auth/providers/oidc/github/callback"

# Plugins — auto-configures official plugins by default
plugin:
  archive_path: "plugins-archive"
  path: "plugins"

# Provisioning — auto-load resources from folders for GitOps-style management
provisioning:
  folders:
    - "/perses/provisioning"

# Frontend
frontend:
  time_range:
    disable_custom: false
```

**Environment variables** override config with `PERSES_` prefix (because env vars keep credentials out of git):
- `PERSES_DATABASE_FILE_FOLDER=/perses/data`
- `PERSES_SECURITY_ENABLE_AUTH=true`
- `PERSES_SECURITY_ENCRYPTION_KEY=<key>` (use this instead of embedding in config.yaml)

**Gate**: Configuration applied. Proceed to Phase 4.

### Phase 4: VALIDATE

**Goal**: Verify deployment is healthy and all APIs are accessible.

Always validate connectivity by checking the `/api/v1/projects` endpoint responds because this confirms auth, routing, and database connectivity work correctly:

```bash
# Check API is responding — HARDCODED requirement
curl -s http://localhost:8080/api/v1/projects | head

# Install percli and login
percli login http://localhost:8080 --username admin --password <password>
percli whoami

# Create a test project
percli apply -f - <<EOF
kind: Project
metadata:
  name: test
spec: {}
EOF

# Verify
percli get project
```

**Optional: Set up MCP server for Claude Code integration**

If you want Claude Code to interact with Perses dashboards and resources, install and configure the Perses MCP server:

```bash
# Install perses-mcp-server from releases
# Create config — keep credentials out of plain text
cat > perses-mcp-config.yaml <<EOF
transport: stdio
read_only: false
perses_server:
  url: "http://localhost:8080"
  native_auth:
    login: "admin"
    password: "<password>"
EOF

# Add to Claude Code settings.json
# mcpServers.perses.command = "perses-mcp-server"
# mcpServers.perses.args = ["--config", "/path/to/perses-mcp-config.yaml"]
```

**Gate**: Deployment verified, connectivity confirmed, health check passed. Task complete.

---

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused` on `curl http://localhost:8080/api/v1/projects` | Perses container/process not running | Check `docker ps` or process status; restart with deployment command |
| `401 Unauthorized` from API | Auth required but credentials not provided | Set `PERSES_SECURITY_ENABLE_AUTH=false` for local dev, or use `percli login` |
| `Port 8080 already in use` | Another process on host port 8080 | Use `-p 127.0.0.1:9090:8080` to map to 9090, or kill the conflicting process |
| `percli login: invalid credentials` | Admin password mismatch | Check config for actual password, or reset via environment variable override |
| `Plugin archive not found` | Plugin path in config doesn't exist | Create directory or update `plugin.archive_path` to valid location |
| Helm install fails with "namespace not found" | K8s namespace doesn't exist | Create with `kubectl create namespace perses` or use Helm `--create-namespace` |

---

## References

- **Perses GitHub**: https://github.com/perses/perses
- **Helm Charts**: https://github.com/perses/helm-charts
- **Documentation**: https://doc.perses.dev
- **CLI (percli)**: https://github.com/perses/perses/releases (percli binary)
- **MCP Server**: https://github.com/perses/perses-mcp-server
