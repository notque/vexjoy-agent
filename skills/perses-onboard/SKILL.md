---
name: perses-onboard
user-invocable: false
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
routing:
  triggers:
    - "onboard Perses"
    - "first-time Perses setup"
  category: perses
---

# Perses Onboard

First-time Perses setup and Claude Code integration pipeline.

## Overview

This is a 4-phase onboarding pipeline for new Perses users, guiding them from zero to a working Perses setup with Claude Code MCP integration. Scope: server discovery/deployment, MCP connection, initial project setup, and end-to-end validation. Out of scope: dashboard creation (use perses-dashboard-create), complex auth (use perses-deploy), and plugin development (use perses-plugin-create).

## Instructions

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

**Step 3: Deploy if needed** (route to perses-deploy skill for complex deployments; use simple Docker for quick local setup only)

For quick local setup:
```bash
docker run --name perses -d -p 127.0.0.1:8080:8080 persesdev/perses
```

**Step 4: Login**
```bash
percli login http://localhost:8080
# For demo: percli login https://demo.perses.dev
```

**Gate**: Perses server accessible, percli authenticated. Proceed to Phase 2 (because we cannot configure MCP until authentication is established).

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

**Gate**: MCP server configured and responsive. Proceed to Phase 3 (because project creation is easier via MCP than CLI).

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

Or via MCP (because MCP tools are available after Phase 2): `perses_create_project(project="default")`

**Step 2: Add a datasource** (optional; only if user has Prometheus/Tempo/Loki available, because dashboards without datasources cannot render metrics)

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

**Gate**: Project and datasource configured. Proceed to Phase 4 (because we now have resources to validate).

### Phase 4: VALIDATE

**Goal**: Verify the full setup works end-to-end (because we cannot declare success without proof that all components are connected and functional).

**Checklist** (because each item validates a different integration layer):
- [ ] `percli whoami` shows authenticated user (validates CLI auth)
- [ ] `percli get project` lists the created project (validates project creation)
- [ ] `percli get globaldatasource` lists configured datasources (if any; validates datasource setup)
- [ ] MCP tools respond (if configured): `perses_list_projects` returns data (validates MCP socket and credentials)
- [ ] Perses UI is accessible in browser at the configured URL (validates HTTP connectivity)

**Summary output** (because users need clear next-step guidance and confirmation of what was set up):
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

**Gate**: All checks pass. Onboarding complete (because all prerequisites for dashboard creation and day-2 operations are now in place).

## Error Handling

**percli not installed**: Route user to [Perses installation docs](https://doc.perses.dev/latest/installation/installation/). Provide direct percli binary link for their OS.

**Perses server not responding**: Verify the configured URL is correct and the server is running. If using Docker, check `docker ps`. If using deployed server, verify network connectivity and firewall rules.

**MCP server binary not found**: Guide user to [MCP releases](https://github.com/perses/mcp-server/releases). Ensure the binary is in PATH or provide full path in settings.json.

**MCP connection fails after registration**: Verify perses-mcp-config.yaml syntax (YAML indentation matters). Check that the bearer token from `percli whoami --show-token` is still valid (tokens may expire). Restart Claude Code harness to reload settings.json.

**MCP tools not discoverable in Claude Code**: This indicates settings.json registration failed. Verify the file is syntactically correct JSON and the perses-mcp-server command exists at the specified path. Check Claude Code logs for socket errors.

**Project creation fails with permissions error**: Verify user has admin role on the Perses server. Check `percli whoami` output for role information.

**Datasource URL unreachable from Perses**: This is expected if the datasource (Prometheus/Loki/Tempo) is on a different network. Perses server needs network access to the datasource URL for proxying to work. For local dev, ensure services are on the same Docker network.

## References

- [Perses Documentation](https://doc.perses.dev/)
- [percli Installation and Usage](https://doc.perses.dev/latest/cli/installation/)
- [Perses MCP Server Repository](https://github.com/perses/mcp-server)
- [Claude Code MCP Configuration](https://claude.ai/docs/mcp)
- Companion skills: perses-deploy (production setup), perses-dashboard-create (dashboard building), perses-grafana-migrate (migration)
