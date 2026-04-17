# Skills

Skills are workflow methodologies — reusable process guides that tell Claude Code *how* to approach a task. Each skill lives in its own directory with a `SKILL.md` file.

Skills are invoked via `/do [request]` (routed automatically) or directly as `/skill-name`. Skills marked **user-invocable: false** are internal and used by agents or other skills.

---

## Routing & Execution

| Skill | Description |
|-------|-------------|
| `do` | Classify user requests and route to the correct agent + skill. Primary entry point for all delegated work. |
| `fast` | Zero-ceremony inline execution for 3 or fewer file edits |
| `quick` | Tracked lightweight execution with composable rigor flags: --discuss, --research, --full |
| `workflow` | Structured multi-phase workflows: review, debug, refactor, deploy, create, research, and more |
| `workflow-help` | Interactive guide to workflow system: agents, skills, routing, execution patterns |
| `install` | Verify Claude Code Toolkit installation, diagnose issues, and guide first-time setup |

---

## Feature Lifecycle

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `feature-lifecycle` | no | Feature lifecycle: design, plan, implement, validate, release. Phase-gated workflow. |

---

## Planning & Task Management

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `planning` | yes | Planning lifecycle umbrella: spec, pre-plan, plan-files, check, manage, pause, resume intents |
| `decision-helper` | no | Weighted decision scoring for architectural choices |
| `plant-seed` | no | Capture forward-looking idea as a seed for future feature design |

---

## Code Implementation

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `test-driven-development` | no | RED-GREEN-REFACTOR cycle with strict phase gates for TDD |
| `socratic-debugging` | no | Question-only debugging: guide users to find root causes themselves |
| `pair-programming` | no | Collaborative coding with enforced micro-steps and user-paced control |
| `subagent-driven-development` | no | Fresh-subagent-per-task execution with two-stage review gates |
| `condition-based-waiting` | no | Polling, retry, and backoff patterns |

---

## Code Review & Quality

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `systematic-code-review` | no | 4-phase code review: UNDERSTAND, VERIFY, ASSESS risks, DOCUMENT findings |
| `parallel-code-review` | no | Parallel 3-reviewer code review: Security, Business-Logic, Architecture |
| `full-repo-review` | yes | Comprehensive 3-wave review of all repo source files, producing a prioritized issue backlog |
| `codex-code-review` | yes | Second-opinion code review from OpenAI Codex CLI. Structures feedback as CRITICAL/IMPROVEMENTS/POSITIVE. |
| `code-cleanup` | no | Detect stale TODOs, unused imports, and dead code |
| `code-linting` | no | Run Python (ruff) and JavaScript (Biome) linting |
| `comment-quality` | no | Review and fix temporal references in code comments |
| `universal-quality-gate` | no | Multi-language code quality gate with auto-detection and linters |
| `python-quality-gate` | no | Python quality checks: ruff, pytest, mypy, bandit in deterministic order |
| `verification-before-completion` | no | Defense-in-depth verification before declaring any task complete |
| `with-anti-rationalization` | no | Anti-rationalization enforcement for maximum-rigor task execution |
| `testing-anti-patterns` | no | Identify and fix testing mistakes: flaky, brittle, over-mocked tests |
| `roast` | no | Constructive critique via 5 HackerNews personas with claim validation |

---

## Git & PR Workflows

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `pr-workflow` | yes | PR lifecycle umbrella: sync, review, fix, status, cleanup, feedback, PR mining, branch-name, ci-check |
| `git-commit-flow` | no | Phase-gated git commit workflow with validation |
| `github-notification-triage` | no | Triage GitHub notifications and report actions needed |

---

## Go Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `go-patterns` | no | Go development patterns: testing, concurrency, errors, review, and conventions |
| `sapcc-audit` | no | Full-repo SAP CC Go compliance audit against review standards |
| `sapcc-review` | no | Gold-standard SAP CC Go code review: 10 parallel domain specialists |
| `codebase-analyzer` | no | Statistical rule discovery from Go codebase patterns |

---

## TypeScript / Frontend

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `typescript-check` | no | TypeScript type checking via tsc --noEmit with actionable error output |
| `vitest-runner` | no | Run Vitest tests and parse results into actionable output |
| `e2e-testing` | no | Playwright-based end-to-end testing workflow |
| `distinctive-frontend-design` | no | Context-driven aesthetic exploration with anti-cliche validation |
| `frontend-slides` | no | Browser-based HTML presentation generation |
| `threejs-builder` | no | Three.js app builder: Design, Build, Animate, Polish in 4 phases |
| `nano-banana-builder` | no | Image generation and post-processing via Gemini Nano Banana APIs |

---

## Testing Infrastructure

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `integration-checker` | no | Verify cross-component wiring and data flow |
| `endpoint-validator` | no | Deterministic API endpoint validation with pass/fail reporting |
| `testing-agents-with-subagents` | no | Test agents via subagents: known inputs, captured outputs, verification |

---

## Perses (Observability)

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `perses` | no | Perses platform operations: dashboards, plugins, deployment, migration, and quality |

---

## Security

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `security-threat-model` | no | Security threat model: scan toolkit for attack surface, supply-chain risks |

---

## Content & Voice

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `voice-writer` | yes | Unified voice content generation pipeline with mandatory validation and joy-check |
| `voice-validator` | no | Critique-and-rewrite loop for voice fidelity validation |
| `create-voice` | no | Create voice profiles from writing samples |
| `anti-ai-editor` | no | Remove AI-sounding patterns from content |
| `post-outliner` | no | Create structural blueprints for blog posts: outlines, word counts |
| `topic-brainstormer` | no | Generate blog topic ideas: problem mining, gap analysis, expansion |
| `series-planner` | no | Plan multi-part content series: structure, cross-linking, cadence |
| `seo-optimizer` | no | Blog post SEO: keywords, titles, meta descriptions, internal linking |
| `content-engine` | no | Repurpose source assets into platform-native social content |
| `content-calendar` | no | Manage editorial content through 6 pipeline stages |
| `joy-check` | no | Validate content framing on joy-grievance spectrum |
| `professional-communication` | no | Transform technical communication into structured business formats |
| `batch-editor` | no | Bulk find/replace and frontmatter updates across Hugo posts |
| `pre-publish-checker` | no | Pre-publication validation for Hugo posts: front matter, SEO, links, images |
| `pptx-generator` | no | PPTX presentation generation with visual QA: slides, pitch decks |
| `image-auditor` | no | Non-destructive image validation for accessibility and health |
| `gemini-image-generator` | no | Generate images from text prompts via Google Gemini |
| `image-to-video` | no | FFmpeg-based video creation from image and audio |
| `video-editing` | no | Video editing pipeline: cut footage, assemble clips via FFmpeg and Remotion |

---

## Social & APIs

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `x-api` | no | Post tweets, build threads, upload media via the X API |
| `bluesky-reader` | no | Read public Bluesky feeds via AT Protocol API |
| `reddit-moderate` | no | Reddit moderation via PRAW: fetch modqueue, classify reports, take actions |

---

## Codebase Analysis & Research

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `codebase-overview` | no | Systematic codebase exploration and architecture mapping |
| `repo-value-analysis` | no | Analyze external repositories for adoptable ideas and patterns |
| `research-pipeline` | yes | Formal 5-phase research pipeline with artifact saving and source quality gates |
| `forensics` | no | Post-mortem diagnostic analysis of failed workflows |
| `data-analysis` | no | Decision-first data analysis with statistical rigor gates |
| `docs-sync-checker` | no | Detect documentation drift against filesystem state |
| `link-auditor` | no | Hugo site link health: scan markdown, build link graph, validate paths |
| `taxonomy-manager` | no | Audit and maintain blog taxonomy: categories, tags, orphans, duplicates |

---

## Toolkit Meta-Skills

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `adr-consultation` | no | Multi-agent consultation for architecture decisions |
| `retro` | yes | Learning system interface: stats, search, graduate learnings. Backed by learning.db (SQLite + FTS5). |
| `learn` | no | Manually teach error pattern and solution to learning database |
| `auto-dream` | yes | Background memory consolidation and learning graduation -- overnight knowledge lifecycle |
| `kairos-lite` | yes | Proactive monitoring -- checks GitHub, CI, and toolkit health, produces briefings |
| `skill-eval` | no | Evaluate skills: trigger testing, A/B benchmarks, structure validation |
| `skill-creator` | no | Create and iteratively improve skills through eval-driven validation |
| `skill-composer` | no | DAG-based multi-skill orchestration with dependency resolution |
| `agent-evaluation` | no | Evaluate agents and skills for quality and standards compliance |
| `agent-comparison` | no | A/B test agent variants for quality and token cost |
| `routing-table-updater` | no | Maintain /do routing tables when skills or agents change |
| `generate-claudemd` | no | Generate project-specific CLAUDE.md from repo analysis |

---

## Session Management

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `read-only-ops` | no | Read-only exploration, inspection, and reporting without modifications |

---

## Infrastructure & DevOps

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `headless-cron-creator` | no | Generate headless Claude Code cron jobs with safety |
| `cron-job-auditor` | no | Audit cron scripts for reliability and safety |
| `service-health-check` | no | Service health monitoring: Discover, Check, Report in 3 phases |
| `fish-shell-config` | no | Fish shell configuration and PATH management |
| `wordpress-uploader` | no | WordPress REST API integration for posts and media uploads |
| `wordpress-live-validation` | no | Validate published WordPress posts in browser via Playwright |

---

## Kotlin Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `kotlin-coroutines` | no | Kotlin structured concurrency, Flow, and Channel patterns |
| `kotlin-testing` | no | Kotlin testing with JUnit 5, Kotest, and coroutine dispatchers |

---

## PHP Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `php-quality` | no | PHP code quality: PSR standards, strict types, framework idioms |
| `php-testing` | no | PHP testing patterns: PHPUnit, test doubles, database testing |

---

## Swift Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `swift-concurrency` | no | Swift concurrency: async/await, Actor, Task, Sendable patterns |
| `swift-testing` | no | Swift testing: XCTest, Swift Testing framework, async patterns |

---

## Kubernetes

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `kubernetes-debugging` | no | Kubernetes debugging for pod failures and networking |
| `kubernetes-security` | no | Kubernetes security: RBAC, PodSecurity, network policies |

---

## Worktree Isolation

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `worktree-agent` | no | Mandatory rules for agents in git worktree isolation |

---

## Shared / Internal

| Skill | Description |
|-------|-------------|
| `shared-patterns` | Reusable prompt patterns referenced by multiple skills |
