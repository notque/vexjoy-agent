# Quick Reference Card

**Everything in one place. Scan in 2 minutes.**

---

## Slash Commands

The primary entry point is `/do`, which routes your request to the appropriate agent and skill.

### Core Entry Point
| Command | Purpose | Example |
|---------|---------|---------|
| `/do` | **Smart router** - figures out what you need | `/do debug this failing test` |

### Available via `/do` Routing
These workflows are activated through `/do` with natural language:

| Want This? | Try This |
|------------|----------|
| Test-driven development | `/do write tests using TDD` |
| Systematic debugging | `/do debug authentication failure` |
| Verification | `/do verify before marking done` |
| Code linting | `/do lint src/` |
| Devil's advocate critique | `/do roast @README.md` |
| Evaluate agent/skill quality | `/do evaluate agents/my-agent.md` |
| Explore without modifying | `/do read-only how does auth work` |
| Multi-step task planning | `/do orchestrate add payment system` |
| Go quality checks | `/do run Go quality gate on this package` |
| Go code review | `/do review this Go code` |
| Check CI status | `/do check CI status` |
| Comment quality | `/do check comment quality` |
| Business communication | `/do make this professional` |

---

## Natural Language Triggers

Just say these phrases. The right skill activates automatically.

### High Reliability (Almost Always Works)
| Say This | Activates |
|----------|-----------|
| "TDD" | test-driven-development |
| "test first" | test-driven-development |
| "red green refactor" | test-driven-development |
| "lint" | code-linting |
| "format code" | code-linting |
| "read only" | read-only-ops |
| "don't modify" | read-only-ops |

### Medium Reliability (Usually Works)
| Say This | Activates |
|----------|-----------|
| "debug" | systematic-debugging |
| "investigate" | systematic-debugging |
| "verify" | verification-before-completion |
| "make sure it works" | verification-before-completion |
| "orchestrate" | workflow-orchestrator |
| "plan this out" | workflow-orchestrator |
| "research then write" | research-to-article |
| "explore codebase" | explore-pipeline |

### Use `/do` Instead (Triggers Unreliable)
| Intent | Use |
|--------|-----|
| Evaluate an agent | `/do evaluate agents/my-agent.md` |
| Check CI status | `/do check CI status` |
| Critique/roast something | `/do roast this design` |

---

## Agents

Request deep expertise: *"Use the [name] agent"*

### Core Engineering
| Agent | Domain |
|-------|--------|
| `golang-general-engineer` | Go 1.24+, concurrency, testing (with frontmatter hooks) |
| `golang-general-engineer-compact` | Go - lightweight version for simple tasks |
| `python-general-engineer` | Python, async, typing, pytest (with frontmatter hooks) |
| `python-openstack-engineer` | OpenStack, Oslo libraries |
| `typescript-frontend-engineer` | TypeScript 5+, React patterns |
| `typescript-debugging-engineer` | TypeScript debugging, race conditions, async issues |
| `nodejs-api-engineer` | Node.js APIs, Express, auth |

### Infrastructure & Operations
| Agent | Domain |
|-------|--------|
| `kubernetes-helm-engineer` | K8s, Helm, OpenStack-on-K8s |
| `opensearch-elasticsearch-engineer` | Search clusters, optimization |
| `prometheus-grafana-engineer` | Monitoring, alerting, dashboards |
| `rabbitmq-messaging-engineer` | Message queues, HA clustering |
| `ansible-automation-engineer` | Infrastructure automation |

### Frontend & UI
| Agent | Domain |
|-------|--------|
| `react-portfolio-engineer` | Portfolio sites, galleries |
| `nextjs-ecommerce-engineer` | E-commerce, Stripe, auth |
| `ui-design-engineer` | Design systems, Tailwind, a11y |

### Quality & Testing
| Agent | Domain |
|-------|--------|
| `testing-automation-engineer` | Vitest, Playwright, E2E |
| `performance-optimization-engineer` | Core Web Vitals, bundles |
| `database-engineer` | PostgreSQL, Prisma, migrations |
| `reviewer-security` | Security review, vulnerability analysis |
| `reviewer-business-logic` | Domain correctness review |

### Specialized
| Agent | Domain |
|-------|--------|
| `technical-documentation-engineer` | Docs, API references |
| `technical-journalist-writer` | Technical journalism |
| `skill-creator` | Create new skills |
| `hook-development-engineer` | Claude Code hooks |
| `project-coordinator-engineer` | Multi-agent orchestration |
| `research-coordinator-engineer` | Research coordination |
| `mcp-local-docs-engineer` | MCP server development |
| `sqlite-peewee-engineer` | SQLite with Peewee ORM |

### Voice Writers
| Agent | Domain |
|-------|--------|
| Custom voice writers | Create with `/create-voice` for your own voice profiles |

### Roasters (5 HN Personas)
| Agent | Perspective |
|-------|-------------|
| `reviewer-contrarian` | Challenge assumptions |
| `reviewer-newcomer` | Accessibility critique |
| `reviewer-pragmatic-builder` | Operational reality |
| `reviewer-skeptical-senior` | Sustainability |
| `reviewer-pedant` | Precision/terminology |

---

## Skills

Loaded automatically or via `Skill("name")`.

### Workflow Automation
| Skill | Purpose |
|-------|---------|
| `workflow-orchestrator` | Brainstorm → Plan → Execute |
| `test-driven-development` | RED-GREEN-REFACTOR enforcement |
| `systematic-debugging` | Reproduce → Isolate → Identify → Verify |
| `systematic-refactoring` | CHARACTERIZE → PLAN → EXECUTE → VALIDATE |
| `verification-before-completion` | Never done without verification |
| `planning-with-files` | Manus-style persistent markdown planning |
| `plan-manager` | Plan lifecycle management |

### Pipelines
| Skill | Purpose |
|-------|---------|
| `research-to-article` | 7-phase content generation with parallel research |
| `explore-pipeline` | Systematic codebase exploration |
| `pr-pipeline` | End-to-end PR creation |
| `doc-pipeline` | Documentation generation |
| `article-evaluation-pipeline` | Voice authenticity validation |

### Code Quality
| Skill | Purpose |
|-------|---------|
| `code-linting` | Python (ruff) + JS (Biome) |
| `go-patterns` | Go testing, concurrency, errors, review, conventions |
| `python-quality-gate` | Python quality checks |
| `universal-quality-gate` | Multi-language quality checking |
| `comment-quality` | Timeless documentation |
| `roast` | Devil's advocate critique via HN personas |

### Voice System
| Skill | Purpose |
|-------|---------|
| `voice-writer` | Unified voice content generation with validation |
| `voice-calibrator` | Create voice profiles from samples |
| `anti-ai-editor` | Remove AI-sounding patterns |

### Knowledge Extraction
| Skill | Purpose |
|-------|---------|
| `codebase-analyzer` | Extract patterns statistically |
| `codebase-overview` | Rapid context building |
| `pr-miner` | Extract PR review comments |
| `pr-mining-coordinator` | Coordinate mining jobs |

### Domain-Specific
| Skill | Purpose |
|-------|---------|
| `professional-communication` | Tech → Business transformation |
| `github-actions-check` | CI/CD status checking |
| `read-only-ops` | Exploration without modification |
| `agent-evaluation` | Evaluate agents/skills |
| `condition-based-waiting` | Retry patterns, backoff, polling |

---

## New Claude Code Features (2026)

| Feature | In Frontmatter | Purpose |
|---------|----------------|---------|
| `once: true` | Hook config | Run hook only once per session |
| `user-invocable: false` | Skill | Hide from slash menu |
| `context: fork` | Skill | Run in isolated sub-agent |
| `agent: name` | Skill | Declare executor agent |
| `hooks:` | Agent | Define agent-specific lifecycle hooks |
| YAML tool lists | Skill | Cleaner `allowed-tools` format |

---

## Decision Cheat Sheet

```
What do you need?
│
├─ "Just get it done" ──────────► /do [describe task]
│
├─ Specific workflow ───────────► /do [describe workflow]
│   ├─ TDD ─────────────────────► /do write tests using TDD
│   ├─ Debug ───────────────────► /do debug this failure
│   ├─ Lint ────────────────────► /do lint this project
│   └─ Verify ──────────────────► /do verify this is correct
│
├─ Deep domain expertise ───────► "Use the [X] agent"
│   ├─ Go code ─────────────────► golang-general-engineer
│   ├─ Kubernetes ──────────────► kubernetes-helm-engineer
│   └─ React ───────────────────► react-portfolio-engineer
│
├─ Complex multi-step task ─────► Triggers auto-planning
│   └─ Creates task_plan.md automatically
│
└─ Don't know ──────────────────► Just describe what you want
                                  Claude figures it out
```

---

## File Locations

```
agents/            ← Specialized agents
skills/            ← Skills + shared-patterns/ directories
  └─ shared-patterns/  ← Reusable patterns (pipeline-architecture, etc.)
hooks/             ← Python hooks and utility scripts
  └─ lib/          ← Shared libraries
scripts/           ← Deterministic Python scripts
docs/              ← This documentation
```

---

## Getting Help

- **Don't know what to use?** → `/do [what you want]`
- **Want to see commands?** → Check this file
- **Building new tools?** → [../CLAUDE-soul-template.md](../CLAUDE-soul-template.md)
