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
---

# Perses Operations

Umbrella skill for all Perses platform operations. Load the appropriate reference based on the task.

## Sub-domains

| Task | Reference |
|------|-----------|
| First-time setup, server deployment | `references/onboard-deploy.md` |
| Create or review dashboards | `references/dashboard.md` |
| Manage datasources or variables | `references/datasource-variable.md` |
| Plugin development and testing | `references/plugin.md` |
| Grafana migration | `references/migration.md` |
| PromQL/LogQL/TraceQL queries | `references/query.md` |
| Project and RBAC management | `references/project.md` |
| Linting, code review, CUE schemas | `references/quality.md` |
| Dashboard-as-Code pipeline | `references/dac.md` |
