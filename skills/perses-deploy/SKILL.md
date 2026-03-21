---
name: perses-deploy
user-invocable: false
description: |
  Deploy Perses server: Docker Compose for local dev, Helm chart for K8s, or binary
  for bare metal. Configure database (file/SQL), auth (native/OIDC/OAuth), plugins,
  provisioning folders, and frontend settings. Use when user wants to deploy, install,
  set up, or configure a Perses server instance. Use for "deploy perses", "install
  perses", "perses setup", "perses server", "run perses". Do NOT use for dashboard
  creation (use perses-dashboard-create) or plugin development (use perses-plugin-create).
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
---

# Perses Deploy

Deploy and configure Perses server instances across different environments.

## Operator Context

This skill operates as a deployment guide for Perses server instances, covering local development, Kubernetes, and bare metal deployments.

### Hardcoded Behaviors (Always Apply)
- **Never expose admin credentials** in plain text — use environment variables or secrets
- **Always configure auth** for non-local deployments — at minimum enable native auth
- **Validate connectivity** after deployment — check `/api/v1/projects` endpoint responds

### Default Behaviors (ON unless disabled)
- **Local dev default**: Docker with file-based storage if deployment target not specified
- **Plugin loading**: Configure official plugins from perses/plugins repository
- **Health check**: Verify Perses is running and API is accessible after deployment

### Optional Behaviors (OFF unless enabled)
- **Production hardening**: TLS, OIDC auth, SQL database, resource limits
- **Kubernetes operator**: Deploy via perses-operator CRDs instead of Helm
- **MCP server setup**: Install and configure perses-mcp-server alongside Perses

## What This Skill CAN Do
- Deploy Perses via Docker, Helm, binary, or K8s operator
- Configure server settings: database, auth, plugins, provisioning, frontend
- Set up MCP server integration for Claude Code
- Verify deployment health and connectivity

## What This Skill CANNOT Do
- Create or manage dashboards (use perses-dashboard-create)
- Develop plugins (use perses-plugin-create)
- Manage Kubernetes clusters (use kubernetes-helm-engineer)

---

## Instructions

### Phase 1: ASSESS Environment

**Goal**: Determine deployment target and requirements.

1. **Deployment target**: Docker (local dev), Helm (Kubernetes), Binary (bare metal), or Operator (K8s CRDs)
2. **Storage backend**: File-based (default, no external DB needed) or SQL (MySQL)
3. **Authentication**: None (local dev), Native (username/password), OIDC, OAuth, or K8s ServiceAccount
4. **Plugin requirements**: Official plugins only, or custom plugins too?
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

**Goal**: Configure server settings.

**Server configuration** (config.yaml):

```yaml
# Database
database:
  file:
    folder: "/perses/data"
    extension: "yaml"

# Security
security:
  readonly: false
  enable_auth: true
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

# Plugins
plugin:
  archive_path: "plugins-archive"
  path: "plugins"

# Provisioning (auto-load resources from folders)
provisioning:
  folders:
    - "/perses/provisioning"

# Frontend
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
# Check API is responding
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

**Optional: Set up MCP server**

```bash
# Install perses-mcp-server from releases
# Create config
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

**Gate**: Deployment verified, connectivity confirmed. Task complete.
