# Agent Capability Map Reference

> **Scope**: Routing table for task types to specialized agents; what each agent can and cannot do.
> **Version range**: Toolkit v2+ agent roster as of 2026-04
> **Generated**: 2026-04-09 — verify agent list against `agents/` directory before dispatching

---

## Overview

The coordinator's primary routing decision is which agent to dispatch for a given task. Wrong routing means either: (1) an under-specialized agent producing lower quality output, or (2) an agent receiving work outside its capability and failing (using up one of the 3 attempts). Route correctly the first time.

---

## Primary Routing Table

| Task Type | Primary Agent | Fallback Agent | Do NOT Use |
|-----------|--------------|----------------|------------|
| Go source code changes | `golang-general-engineer` | `golang-general-engineer-compact` | general-purpose |
| TypeScript backend API | `nodejs-api-engineer` | `typescript-frontend-engineer` | general-purpose |
| TypeScript frontend/React | `typescript-frontend-engineer` | — | nodejs-api-engineer |
| Python scripts/data | `python-general-engineer` | `python-openstack-engineer` | general-purpose |
| Database schema/migrations | `database-engineer` | — | application agents |
| Kubernetes/Helm | `kubernetes-helm-engineer` | — | ansible-automation-engineer |
| Ansible playbooks | `ansible-automation-engineer` | — | kubernetes-helm-engineer |
| OpenSearch/Elasticsearch | `opensearch-elasticsearch-engineer` | — | database-engineer |
| Prometheus/Grafana dashboards | `prometheus-grafana-engineer` | — | — |
| Swift iOS/macOS | `swift-general-engineer` | — | — |
| Kotlin Android/JVM | `kotlin-general-engineer` | — | — |
| PHP backend | `php-general-engineer` | — | — |
| React Native / Expo | `react-native-engineer` | — | typescript-frontend-engineer |
| Code review (any language) | `reviewer-code-playbook` | `reviewer-system-playbook` | — |
| Security audit | `security-threat-model` | — | — |
| Performance optimization | `performance-optimization-engineer` | — | — |
| Documentation writing | `technical-documentation-engineer-playbook` | — | — |
| Multi-agent coordination | `project-coordinator-engineer` (self) | — | — |

**Detection** — verify agent exists before dispatching:
```
ls ~/.claude/agents/ | grep {agent-name}
```

---

## Agent Scope Boundaries

### golang-general-engineer

**Can**: Modify `.go` files, run `go build`, `go test`, `go vet`, add packages, fix linting.
**Cannot**: Modify non-Go files, make architectural decisions, run migrations.
**Signals needing this agent**: `.go` compile errors, `golangci-lint` failures, goroutine leaks.

```
# Dispatch signal detection
rg "\.go$" --files-with-matches | head -5  # Go files present
rg "go build.*failed|cannot use|undefined:" build.log  # Compile errors
```

---

### nodejs-api-engineer

**Can**: REST endpoints, middleware, auth (JWT/OAuth), file uploads, webhooks, DB integration.
**Cannot**: Frontend components, Swift/Kotlin native code, infrastructure provisioning.
**Signals**: `app.get/post/put/delete`, Express/Fastify routes, `prisma`, `typeorm`.

```
rg "(app|router)\.(get|post|put|delete|patch)\(" src/  # Route definitions
rg "import.*express|import.*fastify" src/  # Framework detection
```

---

### database-engineer

**Can**: Schema design, migrations, index strategy, query optimization, replication.
**Cannot**: Application code changes, ORM model generation (route to language agent after schema).
**Signals**: Slow queries, schema changes requested, missing indexes, N+1 query patterns.

**Mandatory sequencing**: Database agent ALWAYS before application agents when schema changes.

---

### performance-optimization-engineer

**Can**: Core Web Vitals, bundle analysis, rendering optimization, profiling.
**Cannot**: Fix application logic bugs unrelated to performance.
**Signals**: LCP > 2.5s, bundle > 500KB, render blocking resources, memory leaks.

---

## Compound Task Routing

Some tasks require multiple agents in sequence. Common patterns:

### API + Frontend Feature

```
Step 1: database-engineer → schema migration
Step 2: nodejs-api-engineer → new endpoint (parallel with Step 3 if no shared types)
Step 3: typescript-frontend-engineer → UI consuming endpoint
Step 4: reviewer-code-playbook → full-stack review
```

### Go Service Performance Issue

```
Step 1: performance-optimization-engineer → profile, identify hotspot (read-only)
Step 2: golang-general-engineer → fix based on profiling report
Step 3: golang-general-engineer → benchmark validation (go test -bench=.)
```

### Infrastructure + Application Deployment

```
Step 1: kubernetes-helm-engineer → Helm chart / deployment config
Step 2: ansible-automation-engineer → provisioning playbooks (parallel with Step 1 if isolated)
Step 3: Application agent → smoke test against deployed environment
```

---

## Routing Anti-Patterns

### ❌ General-Purpose Agent for Specialized Work

**What it looks like**: Dispatching `Agent({ subagent_type: undefined })` for Go compilation errors.

**Why wrong**: General-purpose agent lacks Go-specific pattern libraries, anti-pattern catalog, idiomatic corrections. Produces functional-but-non-idiomatic code that causes rework.

**Fix**: Always specify `subagent_type` for language/infrastructure work.

---

### ❌ Wrong Language Agent

**What it looks like**: Sending TypeScript backend work to `typescript-frontend-engineer`.

**Why wrong**: Frontend agent optimizes for bundle size, React patterns, CSR/SSR — not REST APIs, database connection pooling, or request middleware.

**Detection**:
```
rg "import.*express|import.*@nestjs" --files-with-matches src/
# → backend work → nodejs-api-engineer
rg "import.*react|import.*next" --files-with-matches src/
# → frontend work → typescript-frontend-engineer
```

---

### ❌ Application Agent Doing Schema Work

**What it looks like**: Asking `nodejs-api-engineer` to add a database column.

**Why wrong**: Application agent will add the column in the ORM model but not create the migration, causing runtime errors on deploy.

**Fix**: Schema changes always go to `database-engineer` first. Application agents pick up the committed migration.

---

## Agent Selection Decision Tree

```
Task involves .go files?
  → golang-general-engineer

Task involves TypeScript?
  → Backend/API? → nodejs-api-engineer
  → Frontend/React? → typescript-frontend-engineer

Task involves database schema?
  → database-engineer (first, before application agents)

Task involves infrastructure?
  → Kubernetes/containers? → kubernetes-helm-engineer
  → VM provisioning? → ansible-automation-engineer

Task involves performance profiling?
  → performance-optimization-engineer

Task involves code review?
  → reviewer-code-playbook

Otherwise?
  → Check agents/ directory for domain match
  → general-purpose only as last resort
```
