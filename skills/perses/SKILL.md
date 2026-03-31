---
name: perses
version: 2.0.0
description: "Perses platform operations: dashboards, plugins, deployment, migration, and quality."
context: fork
agent: perses-engineer
model: sonnet
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
  - Glob
  - Grep
  - Agent
routing:
  force_route: true
  triggers:
    - "perses"
    - "perses dashboard"
    - "perses plugin"
    - "perses lint"
    - "perses migrate"
    - "percli"
    - "Grafana to Perses"
    - "perses deploy"
    - "perses datasource"
    - "perses variable"
    - "perses project"
    - "perses CUE"
    - "dashboard-as-code"
  category: infrastructure
  pairs_with:
    - "perses-engineer"
    - "prometheus-grafana-engineer"
---

# Perses Operations

Umbrella skill for all Perses platform operations.

## How to Use (MANDATORY)

**You MUST load the matching reference file before starting any Perses work.** The table below routes tasks to domain-specific references containing the actual methodology, commands, and patterns.

1. **Match** the user's task to a sub-domain in the table below
2. **Load** the reference file using `Read` tool on `${CLAUDE_SKILL_DIR}/references/<name>.md`
3. **Follow** the instructions in the loaded reference exactly
4. If the task spans multiple sub-domains, load each relevant reference

**Anti-pattern**: Do NOT attempt Perses operations from general knowledge alone. The reference files contain percli commands, CUE schema patterns, and deployment procedures specific to this toolkit's Perses setup.

## Sub-domains

| Task | Reference | When to Load |
|------|-----------|-------------|
| First-time setup, server deployment | `references/onboard-deploy.md` | New Perses installation or server configuration |
| Create or review dashboards | `references/dashboard.md` | Any dashboard CRUD operation |
| Manage datasources or variables | `references/datasource-variable.md` | Connecting data sources or template variables |
| Plugin development and testing | `references/plugin.md` | Building or testing Perses plugins |
| Grafana migration | `references/migration.md` | Converting Grafana dashboards to Perses |
| PromQL/LogQL/TraceQL queries | `references/query.md` | Writing or debugging queries |
| Project and RBAC management | `references/project.md` | Multi-tenant setup or permissions |
| Linting, code review, CUE schemas | `references/quality.md` | Code quality or CUE schema work |
| Dashboard-as-Code pipeline | `references/dac.md` | GitOps or CI/CD for dashboards |
