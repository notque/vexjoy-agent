---
name: perses-onboard
user-invocable: true
description: |
  First-time Perses setup pipeline: discover or deploy server, configure MCP connection,
  create initial project, add datasources, and verify connectivity. 4-phase pipeline:
  DISCOVER, CONNECT, CONFIGURE, VALIDATE. Use when setting up Perses for the first time,
  connecting Claude Code to an existing Perses instance, or onboarding a new team to Perses.
  Use for "perses onboard", "setup perses", "connect to perses", "perses getting started".
  Do NOT use for dashboard creation (use perses-dashboard-create) or server deployment
  details (use perses-deploy).
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
  - Agent
  - WebFetch
  - WebSearch
agent: perses-dashboard-engineer
version: 2.0.0
---

# Perses Onboard

First-time Perses setup and Claude Code integration pipeline.

## Operator Context

This skill operates as an onboarding pipeline for new Perses users, guiding them from zero to a working Perses setup with Claude Code MCP integration.

### Hardcoded Behaviors (Always Apply)
- **Check before deploy**: Always check if Perses is already running before offering to deploy
- **MCP setup**: Always offer to configure the Perses MCP server for Claude Code integration
- **Verify each phase**: Don't proceed to next phase until current phase passes validation

### Default Behaviors (ON unless disabled)
- **Interactive**: Ask for confirmation at each phase gate
- **Local-first**: Default to Docker deployment if no server URL provided
- **Demo datasource**: Offer to connect to demo.perses.dev for exploration

### Optional Behaviors (OFF unless enabled)
- **Production mode**: Configure auth, TLS, SQL database
- **Team onboarding**: Create multiple projects and RBAC roles

## What This Skill CAN Do
- Discover existing Perses instances or deploy new ones
- Configure Claude Code MCP integration
- Create initial projects and datasources
- Verify end-to-end connectivity

## What This Skill CANNOT Do
- Create dashboards (use perses-dashboard-create after onboarding)
- Configure complex auth (use perses-deploy for production setups)
- Develop plugins (use perses-plugin-create)

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Find or deploy a Perses server.

**Step 1: Check for existing Perses**

```bash
# Check if percli is installed
which percli 2>/dev/null

# Check if already logged in
percli whoami 2>/dev/null

# Check common ports
curl -s http://localhost:8080/api/v1/health 2>/dev/null
```

**Step 2: Determine path**

| Scenario | Action |
|----------|--------|
| percli is logged in | Skip to Phase 2: CONNECT |
| Perses is running locally | Login with percli, proceed to Phase 2 |
| No Perses found, user has URL | Login to provided URL |
| No Perses found, no URL | Offer: (a) deploy locally with Docker, (b) use demo.perses.dev |

**Step 3: Deploy if needed** (route to perses-deploy skill)

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

**Goal**: Set up Claude Code MCP integration.

**Step 1: Check for Perses MCP server**

```bash
which perses-mcp-server 2>/dev/null
```

**Step 2: Install if needed**

Guide user to install from https://github.com/perses/mcp-server/releases

**Step 3: Configure MCP server**

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

**Step 4: Register in Claude Code settings**

Add to `~/.claude/settings.json` under `mcpServers`:
```json
{
  "perses": {
    "command": "perses-mcp-server",
    "args": ["--config", "/path/to/perses-mcp-config.yaml"]
  }
}
```

**Step 5: Verify MCP connection**

Use ToolSearch("perses") to check if MCP tools are discoverable. If found, test with `perses_list_projects`.

**Gate**: MCP server configured and responsive. Proceed to Phase 3.

### Phase 3: CONFIGURE

**Goal**: Create initial project and datasources.

**Step 1: Create a project**

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

**Step 2: Add a datasource** (if user has Prometheus/Tempo/Loki available)

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
  CLI: percli authenticated as <user>

Next steps:
  - Create a dashboard: /do create perses dashboard
  - Migrate Grafana dashboards: /do migrate grafana to perses
  - Set up Dashboard-as-Code: /do perses dac
```

**Gate**: All checks pass. Onboarding complete.
