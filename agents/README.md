# Agents

Agents are domain experts — specialized Claude Code sub-agents with deep knowledge of a specific language, framework, or discipline. They are invoked by the `/do` router or directly via the `Agent` tool.

Each agent is defined in `agents/*.md` with YAML frontmatter specifying model, version, routing triggers, and paired skills.

---

## Language Engineers

| Agent | Description |
|-------|-------------|
| `golang-general-engineer` | Go development: features, debugging, code review, performance. Modern Go 1.26+ patterns |
| `golang-general-engineer-compact` | Compact Go development for tight context budgets. Modern Go 1.26+ patterns |
| `python-general-engineer` | Python development: features, debugging, code review, performance. Modern Python 3.12+ patterns |
| `typescript-frontend-engineer` | TypeScript frontend architecture: type-safe components, state management, build optimization |
| `typescript-debugging-engineer` | TypeScript debugging: race conditions, async/await issues, type errors, runtime exceptions |
| `kotlin-general-engineer` | Kotlin development: features, coroutines, debugging, code quality, multiplatform |
| `swift-general-engineer` | Swift development: iOS, macOS, server-side Swift, SwiftUI, concurrency, testing |
| `php-general-engineer` | PHP development: features, debugging, code quality, security, modern PHP 8.x patterns |
| `nodejs-api-engineer` | Node.js backend API development: REST endpoints, authentication, file uploads, webhooks, middleware, database integration |

---

## Frontend & UI

| Agent | Description |
|-------|-------------|
| `ui-design-engineer` | UI/UX design: design systems, responsive layouts, accessibility, animations |
| `react-portfolio-engineer` | React portfolio/gallery sites for creatives: React 18+, Next.js App Router, image optimization |
| `nextjs-ecommerce-engineer` | Next.js e-commerce: shopping cart, Stripe payments, product catalogs, order management, checkout flows |
| `performance-optimization-engineer` | Web performance optimization: Core Web Vitals, rendering, bundle analysis, monitoring |

---

## Infrastructure & DevOps

| Agent | Description |
|-------|-------------|
| `kubernetes-helm-engineer` | Kubernetes and Helm: deployments, troubleshooting, cloud-native infrastructure |
| `ansible-automation-engineer` | Ansible automation: playbooks, roles, collections, Molecule testing, Vault security |
| `prometheus-grafana-engineer` | Prometheus and Grafana: monitoring, alerting, dashboard design, PromQL optimization |
| `opensearch-elasticsearch-engineer` | OpenSearch/Elasticsearch: cluster management, performance tuning, index optimization |
| `rabbitmq-messaging-engineer` | RabbitMQ: message queue architecture, clustering, high-availability, routing patterns |

---

## Data & Storage

| Agent | Description |
|-------|-------------|
| `data-engineer` | Data pipelines, ETL/ELT, warehouse design, dimensional modeling, stream processing |
| `database-engineer` | Database design, optimization, query performance, migrations, indexing strategies |
| `sqlite-peewee-engineer` | SQLite with Peewee ORM: model definition, query optimization, migrations, transactions |

---

## Perses (Observability Platform)

| Agent | Description |
|-------|-------------|
| `perses-engineer` | Perses observability platform: dashboards, plugins, operator, core development |

---

## SAP / OpenStack

| Agent | Description |
|-------|-------------|
| `python-openstack-engineer` | OpenStack Python development: Nova, Neutron, Cinder, Oslo libraries, WSGI middleware |

---

## MCP & Tooling

| Agent | Description |
|-------|-------------|
| `mcp-local-docs-engineer` | MCP server development for local documentation access in TypeScript/Node.js and Go |

---

## Research & Coordination

| Agent | Description |
|-------|-------------|
| `research-coordinator-engineer` | Research coordination: systematic investigation, multi-source analysis, synthesis |
| `research-subagent-executor` | Research subagent execution: OODA-loop investigation, intelligence gathering, source evaluation |
| `project-coordinator-engineer` | Multi-agent project coordination: task breakdown, dependency management, progress tracking |

---

## Toolkit Engineering

| Agent | Description |
|-------|-------------|
| `hook-development-engineer` | Python hook development for Claude Code event-driven system and learning database |
| `pipeline-orchestrator-engineer` | Pipeline orchestration: scaffold multi-component workflows, fan-out/fan-in patterns |
| `system-upgrade-engineer` | Systematic toolkit upgrades: adapt agents, skills, hooks when Claude Code ships updates |
| `toolkit-governance-engineer` | Toolkit governance: edit skills, update routing tables, manage ADR lifecycle, enforce standards |

---

## Content & Writing

| Agent | Description |
|-------|-------------|
| `technical-documentation-engineer` | Technical documentation: API docs, system architecture, runbooks, enterprise standards |
| `technical-journalist-writer` | Technical journalism: explainers, opinion pieces, analysis articles, long-form content |
| `github-profile-rules-engineer` | Extract coding conventions and style rules from GitHub user profiles via API |

---

## Testing

| Agent | Description |
|-------|-------------|
| `testing-automation-engineer` | Testing automation: Vitest, Playwright, React Testing Library, CI/CD pipeline integration |

---

## Reviewers

Four umbrella agents covering all review dimensions via reference files loaded on demand. Each umbrella replaces multiple individual reviewer agents from the previous architecture.

| Agent | Description |
|-------|-------------|
| `reviewer-code` | Code quality review across 10 dimensions: conventions, naming, dead code, performance, types, tests, comments, config safety |
| `reviewer-system` | System-level review: security, concurrency, errors, observability, APIs, migrations, dependencies, docs |
| `reviewer-domain` | Domain-specific review: ADR compliance, business logic, SAP CC structural, pragmatic builder |
| `reviewer-perspectives` | Multi-perspective review: newcomer, senior, pedant, contrarian, user advocate, meta-process |

Each umbrella agent loads the appropriate reference file based on the review focus. For example, `reviewer-system` loads its security reference when the task involves OWASP or authentication, and its concurrency reference when the task involves race conditions or goroutine leaks.
