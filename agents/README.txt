# Agents

Specialized domain experts that Claude Code can spawn for complex tasks requiring deep knowledge.

---

## What are Agents?

Agents are **domain experts** defined as comprehensive markdown files. Each agent embodies:
- **Deep domain knowledge** - Extensive patterns, anti-patterns, and best practices
- **Real code examples** - Production-ready snippets, not aspirational pseudocode
- **Operator Model configuration** - Hardcoded, default, and optional behaviors

Agents differ from skills: **agents know things deeply**, **skills know how to do things**.

```
Agent: "I understand Go concurrency patterns and can review your code"
Skill: "I know the 4-phase debugging methodology"
```

---

## Available Agents

### Language & Framework Experts

| Agent | Domain | Lines |
|-------|--------|-------|
| [`golang-general-engineer`](golang-general-engineer.md) | Go development, patterns, concurrency | 95K |
| [`golang-general-engineer-compact`](golang-general-engineer-compact.md) | Go (compact variant for faster loading) | ~30K |
| [`python-general-engineer`](python-general-engineer.md) | Python development, best practices | ~40K |
| [`python-openstack-engineer`](python-openstack-engineer.md) | OpenStack Python development | 37K |
| [`typescript-frontend-engineer`](typescript-frontend-engineer.md) | TypeScript, React patterns | 34K |
| [`nodejs-api-engineer`](nodejs-api-engineer.md) | Node.js backend development | 43K |
| [`nextjs-ecommerce-engineer`](nextjs-ecommerce-engineer.md) | Next.js e-commerce | 35K |
| [`react-portfolio-engineer`](react-portfolio-engineer.md) | React portfolio sites | 29K |

### Code Quality & Review

| Agent | Domain | Lines |
|-------|--------|-------|
| [`testing-automation-engineer`](testing-automation-engineer.md) | Test strategies, automation | 45K |
| [`technical-documentation-engineer`](technical-documentation-engineer.md) | Technical writing, API docs | 97K |
| [`technical-journalist-writer`](technical-journalist-writer.md) | Technical articles, journalism | ~50K |

### Infrastructure & DevOps

| Agent | Domain | Lines |
|-------|--------|-------|
| [`kubernetes-helm-engineer`](kubernetes-helm-engineer.md) | K8s, Helm, OpenStack-on-K8s | 45K |
| [`ansible-automation-engineer`](ansible-automation-engineer.md) | Ansible automation | 47K |
| [`prometheus-grafana-engineer`](prometheus-grafana-engineer.md) | Monitoring, alerting | 30K |
| [`opensearch-elasticsearch-engineer`](opensearch-elasticsearch-engineer.md) | Search infrastructure | 61K |
| [`rabbitmq-messaging-engineer`](rabbitmq-messaging-engineer.md) | Message queues | 24K |

### Specialized Domains

| Agent | Domain | Lines |
|-------|--------|-------|
| [`database-engineer`](database-engineer.md) | PostgreSQL, Prisma, optimization | 55K |
| [`sqlite-peewee-engineer`](sqlite-peewee-engineer.md) | SQLite, Peewee ORM | ~35K |
| [`ui-design-engineer`](ui-design-engineer.md) | UI/UX, Tailwind, accessibility | 42K |
| [`performance-optimization-engineer`](performance-optimization-engineer.md) | Web performance, Core Web Vitals | 39K |

### Meta Agents (Create Other Agents/Skills)

| Agent | Domain | Lines |
|-------|--------|-------|
| [`agent-creator-engineer`](agent-creator-engineer.md) | Create new agents | 80K |
| [`skill-creator-engineer`](skill-creator-engineer.md) | Create new skills | 117K |
| [`hook-development-engineer`](hook-development-engineer.md) | Create Claude Code hooks | 61K |
| [`mcp-local-docs-engineer`](mcp-local-docs-engineer.md) | Build MCP servers | 27K |

### Coordination & Research

| Agent | Domain | Lines |
|-------|--------|-------|
| [`project-coordinator-engineer`](project-coordinator-engineer.md) | Multi-agent orchestration | 36K |
| [`research-coordinator-engineer`](research-coordinator-engineer.md) | Complex research tasks, multi-source analysis | 2K |
| [`research-subagent-executor`](research-subagent-executor.md) | Execute research subtasks for coordinator | 1.5K |

### Specialized Roasters (Critique Personas)

| Agent | Domain | Lines |
|-------|--------|-------|
| [`contrarian-provocateur-roaster`](contrarian-provocateur-roaster.md) | Challenge assumptions, explore alternatives | ~260 |
| [`enthusiastic-newcomer-roaster`](enthusiastic-newcomer-roaster.md) | Fresh perspective on docs and onboarding | ~260 |
| [`pragmatic-builder-roaster`](pragmatic-builder-roaster.md) | Production concerns, operational reality | ~260 |
| [`skeptical-senior-roaster`](skeptical-senior-roaster.md) | Long-term sustainability, maintenance burden | ~260 |
| [`well-actually-pedant-roaster`](well-actually-pedant-roaster.md) | Terminology precision, factual accuracy | ~260 |

**Total Agents**: 32 (including specialized variants)

---

## Using Agents

### Via Hook Evaluation (Automatic)

The `skill-evaluator.py` hook automatically presents priority agents during evaluation:

**Priority agents** (shown in hook evaluation):
1. golang-general-engineer
2. database-engineer
3. testing-automation-engineer
4. technical-documentation-engineer
5. agent-creator-engineer
6. skill-creator-engineer
7. hook-development-engineer

When your prompt involves relevant domains, Claude evaluates whether to spawn these agents.

### Via Task Tool (Explicit)

Agents are spawned using the Task tool with `subagent_type`:

```
Task(subagent_type="golang-general-engineer", prompt="Review this Go code for concurrency issues...")
```

### Via Smart Router (/do)

```
/do review this Go code for best practices
```

The `/do` command analyzes intent and routes to appropriate agent. See `commands/do.md` for complete routing table.

### Parallel Agent Execution

Multiple agents can run in parallel for independent tasks using `/do-parallel`:

```
/do-parallel test agents with domain-specific questions
```

See `commands/do-parallel.md` for details on concurrent agent execution.

---

## Agent Architecture

Each agent follows the Operator Model pattern:

### Structure

```markdown
---
name: agent-name
description: Use this agent when [trigger phrase]
version: 1.0.0
tools: [list of allowed tools]
---

# Agent Name

## Purpose
What this agent does and why it exists.

## Operator Context
### Hardcoded Behaviors (Always Apply)
### Default Behaviors (ON unless disabled)
### Optional Behaviors (OFF unless enabled)

## Core Knowledge
[Extensive domain expertise...]

## Patterns & Anti-Patterns
[Real examples with explanations...]

## Troubleshooting
[Common issues and solutions...]
```

### Depth Over Brevity

Agents are long. The average is 1,400+ lines. Each includes:

- Production-ready code examples
- Comprehensive error handling sections
- Real patterns from actual codebases

Short prompts with generic guidance are less effective. Specific, detailed context does.

---

## Creating New Agents

Use the `agent-creator-engineer` agent:

```
/do create an agent for Terraform infrastructure
```

The creator agent guides you through:
1. Domain analysis
2. Knowledge gathering
3. Pattern extraction
4. Template application
5. Quality validation

See [`agent-creator-engineer.md`](agent-creator-engineer.md) for the complete template.

---

## Quality Standards

Agents are evaluated on:

| Criterion | Points | Requirements |
|-----------|--------|--------------|
| YAML Front Matter | 10 | Valid structure, description |
| Operator Context | 15 | Hardcoded/default/optional behaviors |
| Error Handling | 15 | Recovery procedures, common errors |
| Reference Files | 10 | Supporting documentation |
| Validation Scripts | 10 | Automated quality checks |
| Content Depth | 30 | >1500 lines = EXCELLENT |
| Examples | 10 | Real, tested code |

**Grading**: A (90+), B (75-89), C (60-74), F (<60)

Use `skill: agent-evaluation` to validate new agents.

---

## Agent vs Skill Decision Tree

```
Does this require deep domain knowledge?
├── YES → Create an Agent
│         "Reviewing Go requires knowing idiomatic patterns"
│
└── NO → Is this a repeatable methodology?
         ├── YES → Create a Skill
         │         "Debugging follows these phases regardless of language"
         │
         └── NO → Just write instructions in CLAUDE.md
```

---

## Performance Characteristics

Agents are designed for:
- **Complex reasoning** - Multi-step analysis requiring expertise
- **Domain-specific tasks** - Language reviews, architecture decisions
- **Production quality** - Real code that works, not examples

For simple tasks, use skills or direct Claude Code interaction instead.
