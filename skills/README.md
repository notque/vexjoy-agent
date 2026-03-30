# Skills

Skills are workflow methodologies — reusable process guides that tell Claude Code *how* to approach a task. Each skill lives in its own directory with a `SKILL.md` file.

Skills are invoked via `/do [request]` (routed automatically) or directly as `/skill-name`. Skills marked **user-invocable: false** are internal and used by agents or other skills.

---

## Routing & Execution

| Skill | Description |
|-------|-------------|
| `do` | Primary entry point — classify requests and route to the correct agent + skill |
| `fast` | Zero-ceremony inline execution for tasks needing 3 or fewer file edits |
| `quick` | Lightweight tracked execution with optional `--discuss`, `--research`, `--full` rigor flags |
| `workflow-help` | Interactive guide to the repository workflow system |

---

## Feature Lifecycle

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `feature-lifecycle` | no | Phase-gated feature workflow: design, plan, implement, validate, release. Routes to correct phase via references. |

---

## Planning & Task Management

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `plans` | yes | Deterministic plan lifecycle management via `plan-manager.py` CLI |
| `plan-checker` | yes | Validate plans against 10 verification dimensions before execution |
| `plan-manager` | no | Programmatic plan lifecycle — list, show, create, check, complete, abandon |
| `planning-with-files` | no | Persistent markdown files as working memory for complex multi-phase tasks |
| `pre-planning-discussion` | yes | Resolve implementation ambiguities before planning begins (discussion or assumptions mode) |
| `spec-writer` | no | Structured specification with user stories, acceptance criteria, and scope boundaries |
| `decision-helper` | no | Weighted decision scoring framework for architectural and technology choices |

---

## Code Implementation

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `test-driven-development` | no | RED-GREEN-REFACTOR cycle with strict phase gates |
| `systematic-debugging` | no | Evidence-based 4-phase root cause analysis: Reproduce, Isolate, Identify, Verify |
| `systematic-refactoring` | no | Safe phase-gated refactoring with characterization tests |
| `socratic-debugging` | no | Question-only debugging mode that guides users to find root causes themselves |
| `pair-programming` | no | Collaborative coding with enforced micro-steps and user-controlled pace |
| `subagent-driven-development` | no | Fresh-subagent-per-task execution with two-stage review (ADR compliance + code quality) |
| `condition-based-waiting` | no | Condition-based polling and retry patterns with exponential backoff |

---

## Code Review & Quality

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `systematic-code-review` | no | 4-phase code review: Understand, Verify, Assess, Document with severity classification |
| `parallel-code-review` | no | Parallel 3-reviewer orchestration (Security + Business-Logic + Architecture) — unified verdict |
| `full-repo-review` | yes | 3-wave review against all source files, producing a prioritized issue backlog |
| `code-cleanup` | yes | Systematic detection of stale TODOs, unused imports, dead code, and high complexity |
| `code-linting` | no | Run Python (ruff) and JavaScript (Biome) linting and formatting with auto-fix |
| `comment-quality` | no | Analyze and improve code comment quality, detect comment rot |
| `universal-quality-gate` | no | Multi-language quality gate with auto-detection and language-specific linters |
| `python-quality-gate` | no | Python-specific quality checks with ruff, mypy, and pytest |
| `verification-before-completion` | no | Defense-in-depth 4-level artifact verification before declaring any task complete |
| `with-anti-rationalization` | no | Explicit anti-rationalization enforcement for maximum-rigor task execution |
| `testing-anti-patterns` | no | Identify and fix common testing mistakes across unit, integration, and E2E suites |
| `roast` | no | Constructive critique through 5 HackerNews commenter personas with evidence-based validation |

---

## Git & PR Workflows

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `pr-workflow` | yes | Pull request lifecycle: sync, review, fix, status, cleanup, and PR mining. Loads the appropriate reference based on task (push, create PR, fix review comments, check status, etc.). |
| `git-commit-flow` | no | Phase-gated git commit workflow with validation and CLAUDE.md compliance |
| `branch-naming` | no | Generate and validate Git branch names from descriptions or commit messages |
| `github-actions-check` | no | Check GitHub Actions workflow status after push and report CI results |
| `github-notification-triage` | yes | Triage GitHub notifications — report actions needed, clear noise |

---

## Go Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `go-patterns` | no | Go development patterns: testing, concurrency, errors, review, anti-patterns, quality gates, and SAP CC conventions. Loads the appropriate reference based on task context. |
| `sapcc-audit` | yes | Full-repo SAP CC Go compliance audit with parallel agents dispatched by package group |
| `sapcc-review` | yes | Gold-standard SAP CC Go review dispatching 10 domain-specialist agents in parallel |
| `codebase-analyzer` | no | Statistical rule discovery through Go codebase measurement, producing a Style Vector |

---

## TypeScript / Frontend

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `typescript-check` | no | Run `tsc --noEmit` and parse errors into actionable, file-grouped output |
| `vitest-runner` | no | Run Vitest tests and parse results into structured failure reports |
| `e2e-testing` | no | Playwright-based E2E testing with Page Object Model and flaky test quarantine |
| `distinctive-frontend-design` | no | Design system and UI/UX generation with opinionated visual differentiation |
| `frontend-slides` | no | Build interactive browser-based slide presentations |
| `threejs-builder` | no | Three.js scene construction and interactive 3D web experiences |
| `nano-banana-builder` | no | Image generation and post-processing via Google Gemini Nano Banana APIs |

---

## Testing Infrastructure

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `integration-checker` | no | Verify cross-component wiring: exports used, data flows, output/input shape matching |
| `endpoint-validator` | no | Deterministic API endpoint validation with structured pass/fail reporting |
| `testing-agents-with-subagents` | no | RED-GREEN-REFACTOR testing for agents using subagent dispatch |

---

## Perses (Observability)

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `perses` | no | Perses platform operations: dashboards, plugins, deployment, migration, and quality. Loads the appropriate reference based on task (onboarding, dashboard creation, plugin development, etc.). |

---

## Security

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `security-threat-model` | no | Phase-gated threat model: attack surface scan, deny-list config, supply-chain audit, learning DB check |

---

## Content & Voice

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `voice-validator` | no | Critique-and-rewrite enforcement loop for voice fidelity |
| `create-voice` | no | Create a new voice profile from writing samples (7-phase pipeline) |
| `anti-ai-editor` | no | Review and revise content to remove AI-sounding patterns |
| `post-outliner` | no | Create structural blueprints for blog posts before writing |
| `topic-brainstormer` | no | Generate blog post topic ideas through problem mining and gap analysis |
| `series-planner` | no | Plan multi-part content series with structure and publishing cadence |
| `seo-optimizer` | no | Analyze and optimize blog post SEO: keywords, titles, headers, internal linking |
| `content-engine` | no | Repurpose source assets into platform-native social content variants |
| `content-calendar` | no | Manage editorial content pipeline through 6 stages (Ideas to Published) |
| `joy-check` | no | Validate content for joy-centered tonal framing; flag defensive or bitter framing |
| `professional-communication` | no | Transform technical updates into executive-ready summaries using deterministic templates |
| `batch-editor` | no | Safe bulk editing across Hugo markdown posts with mandatory preview before apply |
| `pptx-generator` | no | 6-phase PPTX presentation generation with visual QA |
| `image-auditor` | no | Non-destructive 4-phase image validation: accessibility, broken references, oversized files |
| `gemini-image-generator` | no | CLI-based image generation from text prompts using Google Gemini APIs |
| `image-to-video` | no | FFmpeg-based static image + audio to MP4 video creation |
| `video-editing` | no | FFmpeg/Remotion video editing pipeline for demos, vlogs, and screen recordings |

---

## Social & APIs

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `x-api` | yes | Post tweets, build threads, upload media, and read timelines via the X API |
| `bluesky-reader` | no | Read public Bluesky feeds via the AT Protocol API |
| `reddit-moderate` | yes | Reddit community moderation with LLM-powered report classification |

---

## Codebase Analysis & Research

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `codebase-overview` | no | Systematic 4-phase codebase exploration: Detect, Explore, Map, Summarize |
| `repo-value-analysis` | no | 6-phase analysis of external repositories for ideas worth adopting |
| `forensics` | no | Post-mortem diagnostic analysis of failed or stuck workflows (read-only) |
| `data-analysis` | no | Decision-first data analysis with statistical rigor gates |
| `docs-sync-checker` | no | Deterministic 4-phase documentation drift detector |
| `link-auditor` | no | Hugo site link health analysis: orphan pages, broken links, image paths |
| `taxonomy-manager` | no | Audit and maintain blog taxonomy for consistency, SEO, and navigation |

---

## Toolkit Meta-Skills

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `adr-consultation` | yes | Multi-agent ADR consultation: 3 parallel reviewers produce PROCEED/BLOCKED verdict |
| `retro` | yes | Interact with the learning system: stats, search, and graduate entries to agents/skills |
| `learn` | no | Manually teach Claude Code an error pattern and solution with high confidence |
| `skill-eval` | yes | Evaluate and improve skills: trigger testing, description optimization, A/B benchmarks |
| `skill-composer` | no | DAG-based multi-skill orchestration with dependency resolution and context passing |
| `agent-evaluation` | no | Evaluate agents/skills for quality and standards compliance using a 6-step rubric |
| `agent-comparison` | no | A/B test agent variants measuring quality and token cost across benchmarks |
| `routing-table-updater` | no | Maintain `/do` routing tables when skills or agents are added or modified |
| `generate-claudemd` | no | Generate a project-specific CLAUDE.md by analyzing repo code and build system |

---

## Session Management

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `pause-work` | no | Create session handoff artifacts (HANDOFF.json + .continue-here.md) |
| `resume-work` | no | Restore session state from handoff artifacts and route to next action |
| `read-only-ops` | no | Read-only exploration, status checks, and reporting without modifications |

---

## Infrastructure & DevOps

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `headless-cron-creator` | no | Generate headless Claude Code cron jobs with lockfile, budget cap, and dry-run safety |
| `cron-job-auditor` | no | Deterministic audit of cron/scheduled job scripts for reliability and error handling |
| `service-health-check` | no | Validate service health, endpoint availability, and dependency status |
| `fish-shell-config` | no | Fish shell configuration: config.fish, functions, abbreviations, PATH management |
| `wordpress-uploader` | no | WordPress REST API integration for posts and media via deterministic Python scripts |
| `wordpress-live-validation` | no | Validate published WordPress posts in a real browser using Playwright |

---

## Shared / Internal

| Skill | Description |
|-------|-------------|
| `shared-patterns` | Reusable prompt patterns referenced by multiple skills |
| `install` | Toolkit installation helper |
