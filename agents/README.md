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
| `perses-core-engineer` | Perses core development: Go backend, React/TypeScript frontend, CUE schemas, overall architecture |
| `perses-dashboard-engineer` | Perses dashboard operations: create/manage dashboards, CUE/Go SDK, percli CLI, MCP integration |
| `perses-operator-engineer` | Perses Kubernetes operator: CRDs (v1alpha2), PersesDashboard/PersesDatasource resources, Helm |
| `perses-plugin-engineer` | Perses plugin development: scaffolding, CUE schemas, React components, Module Federation |

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
| `skill-creator-engineer` | Create Claude Code skills: progressive disclosure, SKILL.md structure, complexity tier selection |
| `hook-development-engineer` | Python hooks: PostToolUse/PreToolUse/SessionStart handlers, sub-50ms performance, learning DB |
| `pipeline-orchestrator-engineer` | Build pipelines: multi-component scaffolding, fan-out/fan-in patterns, routing integration |
| `system-upgrade-engineer` | Ecosystem upgrades: 6-phase pipeline for adapting to Claude Code releases or goal shifts |
| `toolkit-governance-engineer` | Toolkit internal architecture: SKILL.md edits, routing tables, ADR lifecycle, INDEX.json, hook compliance |
| `agent-creator-engineer` | **DEPRECATED** — use `skill-creator-engineer` instead |

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

## Reviewers — Wave 1 (Foundation)

These agents run in parallel during the first review wave, each covering a distinct concern.

| Agent | Description |
|-------|-------------|
| `reviewer-security` | OWASP Top 10, authentication, input validation, secrets detection — read-only |
| `reviewer-business-logic` | Domain correctness, edge cases, state machine verification, data validation — read-only |
| `reviewer-code-quality` | Style guide adherence, convention enforcement, bug detection (confidence ≥ 80) |
| `reviewer-language-specialist` | Language-specific idioms, modern stdlib usage, anti-patterns for Go/Python/TypeScript |
| `reviewer-silent-failures` | Swallowed errors, inadequate error handling, dangerous fallbacks — zero tolerance |
| `reviewer-test-analyzer` | Test coverage quality, behavioral coverage, resilience to refactoring, negative cases |
| `reviewer-docs-validator` | README, CLAUDE.md, dependency health, CI setup, project metadata — supports `--fix` |
| `reviewer-type-design` | Type design quality, invariant expression, encapsulation, compile-time guarantees |
| `reviewer-performance` | Hot paths, algorithmic complexity, N+1 queries, allocations, missing caching |
| `reviewer-observability` | Missing metrics, logging quality, trace propagation, health checks, alerting gaps |
| `reviewer-adr-compliance` | Verifies every ADR decision point has implementation; no scope creep |
| `reviewer-sapcc-structural` | SAP CC structural review: type exports, unnecessary wrappers, go-bits usage, test structure |

---

## Reviewers — Wave 2 (Deep Dive)

These agents receive Wave 1 findings as context for targeted follow-on analysis.

| Agent | Description |
|-------|-------------|
| `reviewer-concurrency` | Race conditions, goroutine leaks, deadlocks, mutex misuse, channel lifecycle |
| `reviewer-api-contract` | Breaking API changes, backward compatibility, schema validation, HTTP status code misuse |
| `reviewer-config-safety` | Hardcoded values, missing env var validation, secrets in source, unsafe defaults |
| `reviewer-dead-code` | Unreachable branches, unused exports, orphaned files, stale feature flags, commented-out code |
| `reviewer-dependency-audit` | CVEs, problematic licenses, deprecated packages, supply chain risks; runs govulncheck/npm audit |
| `reviewer-error-messages` | Error message quality: actionable, sufficient context, consistent formatting, localization-ready |
| `reviewer-migration-safety` | Reversible migrations, API deprecation paths, feature flag lifecycle, rollback strategies |
| `reviewer-naming-consistency` | Convention drift (userID vs userId), verb inconsistency, acronym casing, file naming |
| `reviewer-comment-analyzer` | Comment rot, misleading docs, unnecessary comments, missing critical documentation |

---

## Reviewers — Persona

These reviewers provide a specific human perspective rather than a technical domain.

| Agent | Description |
|-------|-------------|
| `reviewer-skeptical-senior` | Experienced engineer: production readiness, edge cases, failure modes, long-term maintenance |
| `reviewer-newcomer` | Fresh eyes: documentation gaps, confusing code, accessibility for developers new to the codebase |
| `reviewer-pedant` | Technical accuracy, terminology correctness, adherence to specifications |
| `reviewer-pragmatic-builder` | Production-focused: operational blind spots, runtime failure modes, deployment feasibility |
| `reviewer-contrarian` | Professional skepticism: challenges assumptions, explores alternatives, audits for lock-in |
| `reviewer-user-advocate` | User perspective: complexity vs. user value, confusion risks, proportional benefit |
| `reviewer-meta-process` | System design analysis: single points of failure, authority concentration, reversibility |
| `reviewer-code-simplifier` | Simplify recently modified code for clarity and maintainability — actively modifies code |
