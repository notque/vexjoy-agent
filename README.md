# Claude Code Toolkit

<img src="docs/repo-hero.png" alt="Claude Code Toolkit" width="100%">

Claude Code Toolkit is a complete agent-driven workflow system for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). It gives Claude domain-specific expertise, step-by-step workflows, and automated quality gates. The result is Claude working like a team of Go, Python, Kubernetes, review, and content specialists instead of one generalist.

## How It Works

It starts from the moment you type a request. You don't pick agents, configure workflows, or learn any internal concepts. You just say what you want done.

```
/do debug this Go test
```

A router reads your intent and selects a Go specialist agent paired with a systematic debugging methodology. The agent creates a branch, gathers evidence before guessing, runs through phased diagnosis, applies a fix, executes tests, reviews its own work, and presents a PR. You describe the problem. The system handles everything else.

This works because the toolkit separates *what you know* from *what the system knows*. Agents carry domain expertise (Go idioms, Python conventions, Kubernetes patterns). Skills enforce process methodology (TDD cycles, debugging phases, review waves). Hooks automate quality gates that fire on lifecycle events. Scripts handle deterministic operations where you want predictable output, not LLM judgment. The router ties it all together, classifying requests, selecting the right combination, and dispatching.

The result: consistent, domain-specific output across Go, Python, TypeScript, infrastructure, content, and more. No configuration required. A first-time user and a power user get the same quality results. The power user just understands why.

## Built with the Toolkit

A game built entirely by Claude Code using these agents, skills, and pipelines. Every step from design through implementation.

<div align="center">
<video src="https://github.com/user-attachments/assets/0e74abeb-dc7e-42ba-8239-a7a98cb1ab09" width="100%" autoplay loop muted playsinline></video>
</div>

## Installation

Requires [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and working (`claude --version` should print a version number).

```bash
git clone https://github.com/notque/claude-code-toolkit.git ~/claude-code-toolkit
cd ~/claude-code-toolkit
./install.sh --symlink
```

The installer links agents, skills, hooks, commands, and scripts into `~/.claude/`, where Claude Code loads extensions from. Use `--symlink` to get updates via `git pull`, or run without it for a stable copy.

**Detailed setup:** [docs/start-here.md](docs/start-here.md)

## The Core Workflow

1. **Routing.** You type a request. The `/do` router classifies intent, selects a domain agent and a workflow skill, and dispatches. No menus, no configuration.

2. **Planning.** For non-trivial work, the system creates a plan before touching code. Plans have phases, gates, and saved artifacts at each step.

3. **Execution.** A domain-specific agent handles the work using its skill's methodology. Go work gets Go idioms. Python work gets Python conventions. Reviews get multi-wave specialist panels.

4. **Quality gates.** Hooks fire automatically: anti-rationalization checks on code modifications, error learning after failures, context injection at session start. Quality is structural, not advisory.

5. **Verification.** Tests run. Deterministic scripts validate what LLM judgment cannot. The system does not claim completion without evidence.

6. **Delivery.** Changes land on a feature branch. PRs include lint checks, test runs, and review gates. Nothing merges without CI passing.

## What's Inside

### 43 Domain Agents

Agents carry domain-specific expertise. Not thin wrappers that say "you are an expert," but concrete knowledge: version-specific idiom tables, anti-pattern catalogs with detection commands, error-to-fix mappings from real incidents.

**Software Engineering**
- Go, Python, TypeScript, PHP, Kotlin, Swift, Node.js, React Native
- Database design, data pipelines, SQLite/Peewee ORM
- Kubernetes, Ansible, Prometheus/Grafana, OpenSearch, RabbitMQ, OpenStack

**Code Review**
- Multi-perspective review (newcomer, senior, pedant, contrarian, user advocate)
- Domain-specific review (ADR compliance, business logic, structural)
- Playbook-enhanced review with adversarial verification

**Frontend & Creative**
- React portfolios, Next.js e-commerce, UI/UX design
- PixiJS combat rendering, Rive skeletal animation, combat visual effects
- Performance optimization, TypeScript debugging

**Infrastructure**
- Pipeline orchestration, project coordination, research coordination
- System upgrades, toolkit governance, technical documentation
- MCP server development, Perses observability platform

### 125 Workflow Skills

Skills enforce methodology. They are phased workflows with gates that prevent skipping steps.

**Development Workflows:** test-driven development, systematic debugging, feature lifecycle, subagent-driven development, pair programming

**Code Quality:** parallel code review (3 simultaneous reviewers), systematic code review, code cleanup, universal quality gates, linting

**Content & Research:** voice-validated writing, research pipelines, content calendars, SEO optimization, topic brainstorming, content repurposing

**Operations:** PR workflow with quality gates, git commit flow, GitHub Actions checks, cron job auditing, service health checks, Kubernetes debugging

**Meta:** skill evaluation, agent comparison, A/B testing, toolkit evolution, reference enrichment, routing table management

### 69 Hooks

Event-driven automation that fires on session start, before/after tool use, at compaction, and on stop. Error learning, context injection, quality enforcement, and anti-rationalization all run automatically.

### 81 Scripts

Deterministic Python utilities for mechanical operations: INDEX generation, learning database management, voice validation, routing manifests, reference validation. LLMs orchestrate; programs execute.

## Choose Your Path

**[I just want to use it](docs/start-here.md)** | Install in 2 minutes, learn a few commands. Done.

**[I do knowledge work](docs/for-knowledge-workers.md)** | Content pipelines, research workflows, community moderation. No code required.

**[I'm a developer](docs/for-developers.md)** | Architecture, extension points, how to add your own agents and skills.

**[I'm an AI power user](docs/for-ai-wizards.md)** | Routing tables, pipeline architecture, hook system, the learning database.

**[I'm an AI agent](docs/for-claude-code.md)** | Machine-dense component inventory. Tables, file paths, schemas, routing rules.

**[I'm on LinkedIn](docs/for-linkedin.md)** | 🚀 Thought leadership. Agree? 👇

## Philosophy

The toolkit is built on tested principles, not aspirations. Key ideas:

- **Zero-expertise operation.** The system requires no specialized knowledge from the user. Say what you want done. The system handles the rest.
- **LLMs orchestrate, programs execute.** If a process is deterministic and measurable, use a script. Reserve LLM judgment for design decisions and contextual diagnosis.
- **Tokens are cheap, quality is expensive.** Dispatch parallel review agents, run validation scripts, create plans before executing. Quality gates run on every invocation regardless of token budget.
- **Agents carry the knowledge, not the model.** Agent quality is proportional to the specificity of attached knowledge, not the confidence of attached tone. We tested this empirically with A/B experiments.
- **Anti-rationalization as infrastructure.** The toolkit enforces verification structurally. Quality gates are built into the pipeline, not left to discipline.
- **Everything should be a pipeline.** Complex work decomposes into phases. Phases have gates. Gates prevent cascading failures.

Read the full design philosophy: **[PHILOSOPHY.md](docs/PHILOSOPHY.md)**

## License

MIT. See [LICENSE](LICENSE).
