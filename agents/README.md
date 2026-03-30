# Agents

Agents are domain experts — specialized Claude Code sub-agents with deep knowledge of a specific language, framework, or discipline. They are invoked by the `/do` router or directly via the `Agent` tool.

Each agent is defined in `agents/*.md` with YAML frontmatter specifying model, version, routing triggers, and paired skills.

---

## Language Engineers

| Agent | Description |
|-------|-------------|
| `golang-general-engineer` | Go development (1.26+): concurrency, testing, interfaces, production-ready code; includes gopls MCP integration |
| `golang-general-engineer-compact` | Focused Go development with tight context budgets; streamlined for targeted implementations |
| `python-general-engineer` | Python development (3.11+): type safety, async, pytest, modern patterns |
| `typescript-frontend-engineer` | TypeScript 5+ frontend: React 19, Zod validation, state management, type-safe component development |
| `typescript-debugging-engineer` | TypeScript debugging specialist: race conditions, async/await, type errors, runtime exceptions |
| `kotlin-general-engineer` | Kotlin 1.9+/2.0: null safety, coroutines, Flow, Ktor, Koin, Kotest/MockK |
| `swift-general-engineer` | Swift 6: iOS/macOS/visionOS, strict concurrency, SwiftUI/UIKit, Keychain, Swift Testing |
| `php-general-engineer` | PHP 8.2+: PSR-12, Laravel/Symfony/Doctrine, PHPStan/Psalm, SAP Commerce Cloud (Hybris) |
| `nodejs-api-engineer` | Node.js backend: RESTful APIs, authentication, file uploads, webhooks, Next.js API routes |

---

## Frontend & UI

| Agent | Description |
|-------|-------------|
| `ui-design-engineer` | UI/UX design systems: Tailwind CSS, Headless UI, ARIA, WCAG 2.1 AA, modern design principles |
| `react-portfolio-engineer` | React portfolio/gallery sites for creative professionals: Next.js App Router, image galleries, lightbox |
| `nextjs-ecommerce-engineer` | Next.js e-commerce: shopping cart, Stripe, Prisma ORM, server components, checkout flows |
| `performance-optimization-engineer` | Web performance: Core Web Vitals, bundle analysis, caching strategies, Next.js optimization |

---

## Infrastructure & DevOps

| Agent | Description |
|-------|-------------|
| `kubernetes-helm-engineer` | Kubernetes and Helm: chart development, cluster operations, container orchestration, production deployments |
| `ansible-automation-engineer` | Ansible: idempotent playbooks, roles, collections, CI/CD integration, Molecule testing, Vault |
| `prometheus-grafana-engineer` | Prometheus and Grafana: metrics collection, alerting, dashboard design, cloud-native observability |
| `opensearch-elasticsearch-engineer` | OpenSearch/Elasticsearch: cluster management, index optimization, query tuning, search infrastructure |
| `rabbitmq-messaging-engineer` | RabbitMQ: message routing patterns, clustering, HA messaging, performance optimization |

---

## Data & Storage

| Agent | Description |
|-------|-------------|
| `data-engineer` | Data pipelines, ETL/ELT, data warehouse design, Airflow, dbt, Kafka, Spark, BigQuery, Snowflake |
| `database-engineer` | Database design and optimization: schema design, indexing, query optimization, PostgreSQL/MySQL/SQLite |
| `sqlite-peewee-engineer` | SQLite with Peewee ORM: model definition, query optimization, migrations, transaction management |

---

## Perses (Observability Platform)

| Agent | Description |
|-------|-------------|
| `perses-engineer` | Perses observability platform: dashboards, plugins, operator, core development |

---

## SAP / OpenStack

| Agent | Description |
|-------|-------------|
| `python-openstack-engineer` | OpenStack services/plugins: Nova, Neutron, Cinder, Oslo libraries, Tempest, Gerrit/Zuul/DevStack |

---

## MCP & Tooling

| Agent | Description |
|-------|-------------|
| `mcp-local-docs-engineer` | Build MCP servers for local documentation: TypeScript/Node.js and Go implementations, Hugo front matter |

---

## Research & Coordination

| Agent | Description |
|-------|-------------|
| `research-coordinator-engineer` | Complex research: systematic investigation, multi-source analysis, Task tool orchestration |
| `research-subagent-executor` | Individual research subagent: OODA loop methodology, tool selection with budget management |
| `project-coordinator-engineer` | Multi-agent project orchestration: task breakdown, parallel execution, handoffs, TodoWrite integration |

---

## Toolkit Engineering

| Agent | Description |
|-------|-------------|
| `skill-creator` | Create Claude Code skills: progressive disclosure, SKILL.md structure, complexity tier selection |
| `hook-development-engineer` | Python hooks: PostToolUse/PreToolUse/SessionStart handlers, sub-50ms performance, learning DB |
| `pipeline-orchestrator-engineer` | Build pipelines: multi-component scaffolding, fan-out/fan-in patterns, routing integration |
| `system-upgrade-engineer` | Ecosystem upgrades: 6-phase pipeline for adapting to Claude Code releases or goal shifts |
| `toolkit-governance-engineer` | Toolkit internal architecture: SKILL.md edits, routing tables, ADR lifecycle, INDEX.json, hook compliance |

---

## Content & Writing

| Agent | Description |
|-------|-------------|
| `technical-documentation-engineer` | Technical documentation: API docs, integration guides, source-code-verified accuracy |
| `technical-journalist-writer` | Technical journalism: explainers, opinion pieces, long-form articles with journalist-quality structure |
| `github-profile-rules-engineer` | Extract programming rules and coding conventions from a GitHub user's public profile |

---

## Testing

| Agent | Description |
|-------|-------------|
| `testing-automation-engineer` | Testing strategy and automation: Vitest, Playwright, React Testing Library, CI/CD pipeline |

---

## Reviewers

Four umbrella agents covering all review dimensions via reference files loaded on demand. Each umbrella replaces multiple individual reviewer agents from the previous architecture.

| Agent | Description |
|-------|-------------|
| `reviewer-code` | Code quality: conventions, naming, dead code, performance, types, tests, comments, config safety (10 dimensions) |
| `reviewer-system` | System review: security, concurrency, errors, observability, APIs, migrations, dependencies, docs |
| `reviewer-domain` | Domain-specific: ADR compliance, business logic, SAP CC structural, pragmatic builder |
| `reviewer-perspectives` | Multi-perspective: newcomer, senior, pedant, contrarian, user advocate, meta-process |

Each umbrella agent loads the appropriate reference file based on the review focus. For example, `reviewer-system` loads its security reference when the task involves OWASP or authentication, and its concurrency reference when the task involves race conditions or goroutine leaks.
