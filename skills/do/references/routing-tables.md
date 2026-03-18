# Complete Routing Tables

Extended routing tables for the `/do` router. The main SKILL.md contains the core tables (Domain Agents, Task-Type Agents, Skill Overrides, Force Routes). This file contains the full category-specific skill routing.

---

## Process & Execution Skills

| Triggers | Skill |
|----------|-------|
| branch name | branch-naming |
| git commit | git-commit-flow |
| lint, format | code-linting |
| quality check | universal-quality-gate |
| tsc, type check, TypeScript errors | typescript-check |
| vitest, test runner, run tests | vitest-runner |
| CI, build status | github-actions-check |
| read only, explore | read-only-ops |
| Go quality, Go PR | go-pr-quality-gate |
| Python quality, ruff, mypy | python-quality-gate |
| retry, backoff, polling, health check | condition-based-waiting |
| test anti-patterns, flaky tests | testing-anti-patterns |
| subagent, fresh context, two-stage review | subagent-driven-development |
| execute plan, run plan | workflow-orchestrator |
| parallel, independent failures | dispatching-parallel-agents |
| parallel review, comprehensive review | parallel-code-review |
| extra rigor, maximum verification | with-anti-rationalization |
| checkpoint, save context | checkpoint-context |
| plan status, check plans, audit plans | plan-manager |
| plan with files, persistent planning | planning-with-files |
| **Go test, _test.go, table-driven** | **go-testing (FORCE)** |
| **goroutine, channel, sync.Mutex, concurrent** | **go-concurrency (FORCE)** |
| **error handling, fmt.Errorf, errors.Is, %w** | **go-error-handling (FORCE)** |
| **review Go, Go PR, Go code review** | **go-code-review (FORCE)** |
| **anti-pattern, code smell, over-engineering** | **go-anti-patterns** |
| **fish shell, config.fish, fish function** | **fish-shell-config** |

---

## Analysis & Discovery Skills

| Triggers | Skill |
|----------|-------|
| codebase overview, understand repo | codebase-overview |
| codebase patterns, statistical analysis | codebase-analyzer (code-cartographer) |
| code cleanup, stale TODOs, unused | code-cleanup |
| comment quality, temporal refs | comment-quality |
| evaluate agent, grade skill | agent-evaluation |
| compare agents, A/B test | agent-comparison |
| test agent, validate agent | testing-agents-with-subagents |
| mine PR, extract review comments | pr-miner |
| coordinate mining, batch PRs | pr-mining-coordinator |
| compose skills, multi-skill workflow | skill-composer |
| update routing table | routing-table-updater |
| docs sync, README coverage | docs-sync-checker |
| multi-perspective analysis, 10 lenses | do-perspectives |
| parallel multi-angle extraction | do-parallel |
| plan lifecycle, create plan, track plans | plans |
| error pattern, teach Claude | learn |
| professional email, business communication | professional-communication |
| workflow explanation, how does this work | workflow-help |

---

## PR & Git Skills

| Triggers | Skill |
|----------|-------|
| submit PR, create pull request | pr-pipeline |
| **push, push this, push changes, commit and push, sync to GitHub, push to GitHub** | **pr-sync (FORCE)** |
| **create a PR, create PR, open PR, open pull request, ship this, send this** | **pr-sync (FORCE)** |
| **commit, commit this, commit changes, stage and commit** | **git-commit-flow (FORCE)** |
| **check CI, CI status, actions status, did CI pass** | **github-actions-check (FORCE)** |
| PR cleanup, merged branch | pr-cleanup |
| PR review comments, fix feedback | pr-fix |
| address PR feedback, what did reviewers say | pr-review-address-feedback |
| PR status, branch status | pr-status |
| **review PR, code review PR, run review** | **/pr-review command** (comprehensive review with retro learning) |

### PR Workflow Policies

| Repo Type | Detection | Commit/Push/PR | Review Gate | Merge |
|-----------|-----------|----------------|-------------|-------|
| **protected-org** (configured organizations) | `scripts/classify-repo.py` pattern match | **Human-gated**: confirm each step with user | Their reviewers handle review | **NEVER auto-merge** |
| **personal** (all other repos) | Default | Auto-execute | `/pr-review` → fix loop (max 3 iterations) | Create PR after review passes |

---

## Content Creation Skills

| Triggers | Skill |
|----------|-------|
| write blog, blog post | blog-post-writer |
| edit content, remove AI patterns | anti-ai-editor |
| **de-ai docs, clean ai patterns, scan and fix docs** | **de-ai-pipeline** (SCAN → FIX → VERIFY loop) |
| content outline, post outline | post-outliner |
| brainstorm topics, topic ideas | topic-brainstormer |
| pre-publish, publication check | pre-publish-checker |
| SEO, search optimization | seo-optimizer |
| create voice, new voice, build voice | create-voice |
| voice calibration, refine voice | voice-calibrator |
| voice validation, check voice | voice-validator |
| content series, multi-part | series-planner |
| content calendar, editorial calendar | content-calendar |
| link audit, broken links | link-auditor |
| image audit, image optimization | image-auditor |
| batch edit, bulk content | batch-editor |
| taxonomy, categories, tags | taxonomy-manager |
| upload to WordPress, create draft | wordpress-uploader |
| index post, ping search engines, notify search engines, submit url, indexnow | search-engine-indexer (script) |

---

## Voice Skills

| Triggers | Skill |
|----------|-------|
| create voice, new voice, build voice, voice from samples | create-voice |
| multi-step voice generation | voice-orchestrator |
| voice calibration, writing style | voice-calibrator |
| voice validation loop | voice-validator |

**Voice selection:** Use `create-voice` to build voice profiles from writing samples, then `voice-orchestrator` for multi-step generation in that voice. Custom voice profiles are matched via their skill triggers.

**Wabi-sabi principle:** Perfection is an AI tell. Natural imperfections are features. Don't over-polish.

---

## Feature Lifecycle Skills

Sequential pipeline: design → plan → implement → validate → release. Each skill advances state via `scripts/feature-state.py`.

| Triggers | Skill | Phase |
|----------|-------|-------|
| **design feature, feature design, think through, explore approaches** | **feature-design (FORCE)** | 1 - Design |
| **plan feature, break down design, create tasks** | **feature-plan (FORCE)** | 2 - Plan |
| **implement feature, execute plan, start building** | **feature-implement (FORCE)** | 3 - Implement |
| **validate feature, run quality gates, check feature** | **feature-validate (FORCE)** | 4 - Validate |
| **release feature, merge feature, ship it** | **feature-release (FORCE)** | 5 - Release |

**Auto-detection**: When `.feature/` exists, `feature-state.py status` determines current phase and routes to the matching skill automatically.

**Entry point**: New features always enter via `feature-design`. Skipping phases is not supported.

---

## Pipeline Skills

| Triggers | Skill |
|----------|-------|
| create pipeline, new pipeline, scaffold pipeline | pipeline-scaffolder (pipeline-orchestrator-engineer) |
| **upgrade agents, system upgrade, claude update, upgrade skills, apply claude update, apply retro** | **system-upgrade (system-upgrade-engineer)** |
| create skill pipeline, new skill formal, skill with gates | skill-creation-pipeline (skill-creator-engineer) |
| create hook pipeline, new hook formal, hook with gates | hook-development-pipeline (hook-development-engineer) |
| research pipeline, formal research, research with artifacts | research-pipeline (research-coordinator-engineer) |
| upgrade agent, improve agent, fix agent quality, align agent to template | agent-upgrade (skill-creator-engineer) |
| research then write, article with research | research-to-article |
| document this, create readme, write docs | doc-pipeline |
| submit PR, create pull request | pr-pipeline |
| understand codebase, explore repo | explore-pipeline |
| evaluate article, check voice authenticity | article-evaluation-pipeline |
| mcp pipeline, repo to mcp, create mcp from repo, generate mcp, mcp builder, mcp from repo | mcp-pipeline-builder (mcp-local-docs-engineer) |

---

## GitHub Profile Analysis Skills

| Triggers | Skill |
|----------|-------|
| github rules, profile analysis, coding style extraction, github conventions, programming rules | github-profile-rules (github-profile-rules-engineer) |

---

## Validation Skills

| Triggers | Skill |
|----------|-------|
| endpoint validation, API check | endpoint-validator |
| service health, restart needed | service-health-check |
| cron audit, script reliability | cron-job-auditor |

---

## Roaster Agents

Invoked via the roast skill or directly:

| Triggers | Agent | Focus |
|----------|-------|-------|
| contrarian, alternatives, assumptions | reviewer-contrarian | Challenge premises |
| newcomer, onboarding, first-run | reviewer-newcomer | Accessibility critique |
| builder, production, ops | reviewer-pragmatic-builder | Operational reality |
| senior, maintenance, long-term | reviewer-skeptical-senior | Sustainability |
| pedant, accuracy, terminology | reviewer-pedant | Precision/verifiability |

---

## Quick Routing Examples

| Request | Routes To |
|---------|-----------|
| "debug Go tests" | golang-general-engineer + systematic-debugging |
| "write Go tests for X" | **go-testing (FORCE)** |
| "add worker pool" | **go-concurrency (FORCE)** |
| "add auth to Python API" | python-general-engineer + workflow-orchestrator |
| "review my K8s manifests" | kubernetes-helm-engineer + systematic-code-review |
| "roast this design doc" | roast skill (5 personas) |
| "execute plan with subagents" | subagent-driven-development |
| "fix these 3 failing test files" | dispatching-parallel-agents |
| "debug TypeScript race condition" | typescript-debugging-engineer + systematic-debugging |
| "write in custom voice" | voice-orchestrator + [your-voice-skill] |
| "comprehensive code review" | parallel-code-review (3 reviewers) |
| "design a rate limiter feature" | **feature-design (FORCE)** |
| "plan this feature" | **feature-plan (FORCE)** |
| "build this feature" | **feature-implement (FORCE)** |
| "review this PR" | /pr-review command (retro-enabled) |
| "submit a PR" | pr-pipeline |
| "research then write article" | research-to-article pipeline |
| "create a pipeline for X" | pipeline-orchestrator-engineer + pipeline-scaffolder |
| "upgrade system for new Claude version" | system-upgrade-engineer + system-upgrade |
| "claude update, apply to agents" | system-upgrade-engineer + system-upgrade |
| "create skill with quality gates" | skill-creator-engineer + skill-creation-pipeline |
| "create hook (formal, with perf test)" | hook-development-engineer + hook-development-pipeline |
| "research with saved artifacts" | research-coordinator-engineer + research-pipeline |
| "upgrade this specific agent" | skill-creator-engineer + agent-upgrade |
| "create a 3D scene" | typescript-frontend-engineer + threejs-builder |
| "generate image with Python" | python-general-engineer + gemini-image-generator |
| "extract coding rules from github user X" | github-profile-rules-engineer + github-profile-rules |
| "analyze github profile conventions" | github-profile-rules-engineer + github-profile-rules |
