# Worker Capability Map Reference

> **Scope**: Task-to-reference routing for coordinated workers; capabilities and boundaries per domain.

Every worker is a fresh `general-purpose` agent (Agent tool `subagent_type: "general-purpose"`). The domain lives in a skill reference, not in an agent. Start each worker prompt with two instructions: call the Skill tool with the row's skill, then `Read ~/.claude/skills/<skill>/references/<file> and follow it; load every file its Reference Loading Table matches.`

---

## Primary Routing Table

| Task Type | Skill | Reference to load | Avoid |
|-----------|-------|-------------------|-------|
| Go source code | `programming` | `references/golang-general.md` | a worker with no reference |
| TypeScript backend API | `programming` | `references/nodejs-api.md` (runtime bugs: `references/typescript-debugging.md`) | frontend reference |
| TypeScript frontend/React | `frontend` | `references/typescript-frontend.md` | backend reference |
| Python scripts/data | `programming` | `references/python-general.md` (OpenStack: `references/python-openstack.md`) | a worker with no reference |
| Database schema/migrations | `data` | `references/database.md` | application references |
| Kubernetes/Helm | `kubernetes` | `references/kubernetes-helm.md` | `references/ansible-automation.md` |
| Ansible playbooks | `kubernetes` | `references/ansible-automation.md` | `references/kubernetes-helm.md` |
| OpenSearch/Elasticsearch | `kubernetes` | `references/opensearch-elasticsearch.md` | `data` references |
| Prometheus/Grafana | `kubernetes` | `references/prometheus-grafana.md` | — |
| Swift iOS/macOS | `programming` | `references/swift-general.md` | — |
| Kotlin Android/JVM | `programming` | `references/kotlin-general.md` | — |
| PHP backend | `programming` | `references/php-general.md` | — |
| React Native / Expo | `frontend` | `references/react-native.md` | `references/typescript-frontend.md` |
| Code review | `review` | `references/reviewer-code.md` (fallback `references/reviewer-system.md`) | — |
| Security audit | `review` | `references/reviewer-system.md` | — |
| Performance | `frontend` | `references/performance-optimization.md` | — |
| Documentation | `writing` | `references/technical-documentation.md` | — |

`security` is a skill: call it with the Skill tool for a standalone scan of git changes.

Verify the reference exists before dispatch: `ls ~/.claude/skills/{skill}/references/{file}`

---

## Domain Scope Boundaries

**Go worker** (`programming`, `golang-general.md`): CAN modify `.go` files, run `go build/test/vet`, add packages, fix linting. CANNOT modify non-Go files, make architectural decisions, run migrations.

**Node API worker** (`programming`, `nodejs-api.md`): CAN do REST endpoints, middleware, auth, webhooks, DB integration. CANNOT do frontend components, native code, infrastructure.

**Database worker** (`data`, `database.md`): CAN do schema design, migrations, indexes, query optimization. CANNOT do application code. **Mandatory sequencing**: the database worker ALWAYS runs before application workers on schema changes.

**Performance worker** (`frontend`, `performance-optimization.md`): CAN do Core Web Vitals, bundle analysis, rendering optimization, profiling. CANNOT fix unrelated logic bugs.

---

## Compound Task Routing

### API + Frontend Feature
```
1. database worker (data/database.md) → schema migration
2. Node API worker → endpoint (parallel with 3 if no shared types)
3. frontend worker (frontend/typescript-frontend.md) → UI
4. code review worker (review/reviewer-code.md) → full-stack review
```

### Go Service Performance
```
1. performance worker (frontend/performance-optimization.md) → profile, identify hotspot (read-only)
2. Go worker (programming/golang-general.md) → fix
3. Go worker → benchmark validation
```

### Infrastructure + Application
```
1. Helm worker (kubernetes/kubernetes-helm.md) → Helm chart (parallel with 2 if isolated)
2. Ansible worker (kubernetes/ansible-automation.md) → provisioning
3. Application worker → smoke test
```

---

## Preferred Patterns

### Name the Reference in Every Dispatch
**Signal**: A `general-purpose` worker dispatched for Go errors with no skill or reference in its prompt.
**Fix**: Look up the task type in the routing table; put the Skill call and reference read line first in the prompt.

### Match Reference to Language Domain
**Signal**: TypeScript backend work sent with the frontend reference.
**Fix**: Check imports — `express`/`@nestjs`/`fastify` → Node API worker. `react`/`next` → frontend worker.

```bash
rg "import.*express|import.*@nestjs" --files-with-matches src/  # → backend
rg "import.*react|import.*next" --files-with-matches src/       # → frontend
```

### Route Schema Changes to the Database Worker
**Signal**: Asking the Node API worker to add a column.
**Fix**: Database worker first for the migration, then the application worker for ORM models.

---

## Worker Selection Decision Tree

```
.go files? → programming + golang-general.md
TypeScript backend/API? → programming + nodejs-api.md
TypeScript frontend/React? → frontend + typescript-frontend.md
Database schema? → data + database.md (first, before app workers)
K8s/containers? → kubernetes + kubernetes-helm.md
VM provisioning? → kubernetes + ansible-automation.md
Performance? → frontend + performance-optimization.md
Code review? → review + reviewer-code.md
Otherwise? → find the skill whose references match → general-purpose with that skill
```
