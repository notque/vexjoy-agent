---
summary: "Catalog of all skills by category."
read_when:
  - "browsing the skill catalog"
  - "documenting a new skill"
---

# Skills

Skills are workflow methodologies — reusable process guides that tell Claude Code *how* to approach a task. Each skill lives in its own directory with a `SKILL.md` file.

Skills are invoked via `/do [request]` (routed automatically) or directly as `/skill-name`. Skills marked **user-invocable: false** are internal and used by agents or other skills.

---

## Routing & Execution

| Skill | Description |
|-------|-------------|
| `do` | Classify user requests and route to the correct agent + skill. Primary entry point for all delegated work. |
| `quick` | Tracked lightweight execution with composable rigor flags: --trivial, --discuss, --research, --full |
| `workflow` | Structured multi-phase workflows: review, debug, refactor, deploy, create, research, and more |
| `workflow-help` | Interactive guide to workflow system: agents, skills, routing, execution patterns |
| `install` | Verify VexJoy Agent installation, diagnose issues, and guide first-time setup |

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
| `csuite` | no | C-suite executive decision support: strategy, technology, growth, competitive intelligence, project evaluation. |
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
| `code-cleanup` | no | Detect stale TODOs, unused imports, and dead code |
| `code-linting` | no | Run Python (ruff) and JavaScript (Biome) linting |
| `comment-quality` | no | Review and fix temporal references in code comments |
| `universal-quality-gate` | no | Multi-language code quality gate with auto-detection and linters |
| `python-quality-gate` | no | Python quality checks: ruff, pytest, mypy, bandit in deterministic order |
| `verification-before-completion` | no | Defense-in-depth verification before declaring any task complete |
| `with-anti-rationalization` | no | _(demoted to verification-before-completion)_ Anti-rationalization enforcement for maximum-rigor task execution |
| `testing-preferred-patterns` | no | Identify and fix testing mistakes: flaky, brittle, over-mocked tests |
| `roast` | no | Constructive critique via 5 HackerNews personas with claim validation |
| `condense` | yes | Maximize information density: preserve all instructions, remove prose filler. |
| `security-review` | yes | Local security review of git changes: deterministic scan + Security reviewer over the diff. |

---

## Git & PR Workflows

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `pr-workflow` | yes | PR lifecycle umbrella: commit, codex-review, sync, review, fix, status, cleanup, feedback, PR mining, branch-name, ci-check |
| `github-notification-triage` | no | Triage GitHub notifications and report actions needed |

---

## Go Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `go-patterns` | no | Go development patterns: testing, concurrency, errors, review, and conventions |
| `sapcc-audit` | no | Full-repo SAP CC Go compliance audit against review standards |
| `sapcc-review` | no | Gold-standard SAP CC Go code review: 10 parallel domain specialists |
| `codebase-analyzer` | no | _(demoted to codebase-overview)_ Statistical rule discovery from Go codebase patterns |

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
| `text-animation` | no | Dependency-free kinetic typography: roll/slot text, reveals, typewriter, crossfade. |
| `webgl-card-effects` | no | Standalone WebGL fragment shaders for card visual effects: holographic foil, shimmer, rarity glow. |

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
| `publish` | no | Content-publishing umbrella: outline, pre-publish check, SEO, batch-edit, link/image/taxonomy audits, WordPress upload |
| `topic-brainstormer` | no | Generate blog topic ideas: problem mining, gap analysis, expansion |
| `series-planner` | no | Plan multi-part content series: structure, cross-linking, cadence |
| `content-engine` | no | Repurpose source assets into platform-native social content |
| `content-calendar` | no | Manage editorial content through six pipeline stages |
| `joy-check` | no | Validate content framing on joy-grievance spectrum |
| `professional-communication` | no | Transform technical communication into structured business formats |
| `image-to-video` | no | FFmpeg-based video creation from image and audio |
| `video-editing` | no | Video editing pipeline: cut footage, assemble clips via FFmpeg and Remotion |
| `image-gen` | no | AI image generation: Gemini and Nano Banana backends; single/series/batch workflows with prompt-to-disk. |
| `translate` | yes | Document translation: quick/normal/refined modes with chunked parallel subagents and glossary support. |

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
| `architecture-deepening` | yes | Proactive architecture improvement: find shallow modules, propose deepening opportunities, design conversation. |
| `explanation-traces` | yes | Query and display structured decision traces from routing, agent selection, and skill execution. |
| `multi-persona-critique` | yes | Critique a written proposal or design artifact via 5 philosophical personas in parallel, with consensus synthesis. |
| `fact-check` | no | Verify factual claims against sources before publish. |
| `headlines` | no | Generate headlines, titles, and subject lines: charge, volume, tighten. |
| `markdown-converter` | no | Convert PDF, Office, HTML, data, media, ZIP to Markdown. |
| `news-collection` | no | Collect, filter, and freshness-qualify news items. |
| `video-transcript` | no | Extract video transcripts: yt-dlp subtitles to clean paragraphs. |

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
| `skill-composer` | no | _(demoted to workflow)_ DAG-based multi-skill orchestration with dependency resolution |
| `agent-evaluation` | no | Evaluate agents and skills for quality and standards compliance |
| `agent-comparison` | no | A/B test agent variants for quality and token cost |
| `routing-table-updater` | no | Maintain /do routing tables when skills or agents change |
| `generate-claudemd` | no | Generate project-specific CLAUDE.md from repo analysis |
| `agent-creator` | no | Scaffold vexjoy-agent operator .md files: frontmatter, routing block, operator context, reference loading table, phase/gate workflow. |
| `html-artifact` | no | Generate rich self-contained HTML artifacts instead of markdown. |
| `objective-loop` | no | Loop /do cycles until done-criteria verify or budget stops. |
| `toolkit-evolution` | yes | Closed-loop toolkit self-improvement: discover gaps, diagnose, propose, critique, build, test, evolve. |
| `reference-enrichment` | yes | Analyze agent/skill reference depth and generate missing domain-specific reference files. |

---

## Session Management

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `read-only-ops` | no | Read-only exploration, inspection, and reporting without modifications |
| `session-handoff` | no | Package session state for the next agent, or rehydrate it at start. |

---

## Infrastructure & DevOps

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `headless-cron-creator` | no | Generate headless Claude Code cron jobs with safety |
| `cron-job-auditor` | no | Audit cron scripts for reliability and safety |
| `service-health-check` | no | Service health monitoring: Discover, Check, Report in 3 phases |
| `fish-shell-config` | no | Fish shell configuration and PATH management |
| `wordpress-live-validation` | no | Validate published WordPress posts in browser via Playwright |
| `cobalt-core` | yes | Cobalt Core infrastructure knowledge: KVM exporters, hypervisor tooling, OpenStack compute. |
| `cve-source-check` | yes | Audit CVE/vulnerability source coverage for a technology stack. |
| `public-web-deploy` | no | Publish a public website safely: DNS, web server, HTTPS, hardening, verify. |
| `shell-process-patterns` | no | Safely start, supervise, and terminate shell processes: background jobs, PID capture, signals, traps, cleanup verification. |
| `zsh-shell-config` | no | Zsh shell configuration, PATH management, completions, and framework setup. |

---

## Kotlin Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `kotlin` | no | Kotlin development: coroutines, Flow, testing with JUnit 5 and Kotest |

---

## PHP Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `php` | no | PHP development: code quality, PSR standards, testing with PHPUnit |

---

## Swift Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `swift` | no | Swift development: concurrency patterns, async/await, actors, testing with XCTest and Swift Testing framework |

---

## Kubernetes

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `kubernetes-debugging` | no | Kubernetes debugging for pod failures and networking |
| `kubernetes-security` | no | Kubernetes security: RBAC, PodSecurity, network policies |

---

## Engineering

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `cli-design` | no | Design a CLI interface: args, flags, help, output, errors, exit codes, config. |
| `enterprise-search` | yes | Enterprise search: relevance tuning, query understanding, index management, search quality, ranking optimization, schema design. |
| `opensearch-detection-engineer` | yes | OpenSearch SIEM detection: SIGMA, query DSL, MITRE ATT&CK mapping, anomaly/correlation rules, alert validation, SOC escalation. |

---

## Business & Operations

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `customer-support` | yes | Customer support workflows — ticket triage, response drafting, knowledge base articles, escalation handling, customer research. |
| `design` | yes | Design workflows — UX copy, design systems, design critique, accessibility review, design handoff, user research synthesis. |
| `finance` | yes | Finance and accounting: journal entries, reconciliation, variance analysis, financial statements, audit support, month-end close, SOX testing. |
| `hr` | yes | People operations workflows — recruiting pipeline, performance reviews, compensation analysis, offer drafting, interview prep, onboarding, org planning. |
| `legal` | yes | Legal workflows — contract review, compliance checks, NDA triage, risk assessment, legal briefs. |
| `marketing` | yes | Marketing: SEO audits, campaign planning, content strategy, email sequences, competitive analysis, brand review, performance reporting. |
| `operations` | yes | Business operations: vendor management, runbooks, process docs, risk assessment, capacity planning, change management, compliance tracking. |
| `product-management` | yes | Product management: feature specs, roadmaps, stakeholder updates, user research synthesis, competitive analysis, metrics, sprint planning. |
| `productivity` | yes | Personal productivity: pick what to work on next, prioritize tasks, plan your day, weekly reviews, meeting optimization, goals, status updates. |
| `sales` | yes | Sales workflows — call prep, pipeline analysis, outreach, competitive intelligence, forecasting. |

---

## Game Development

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `game-asset-generator` | no | Deterministic palette/matrix pixel art (not AI). |
| `game-pipeline` | no | Game lifecycle orchestrator: scaffold, assets, audio, QA, deploy. |
| `game-sprite-pipeline` | no | AI sprite generation: portraits, idle loops, animated sheets via Codex/Nano Banana. |
| `motion-pipeline` | yes | CPU-only motion data processing pipeline for game animation: BVH import, contact detection, root decomposition, motion blending, FABRIK IK. |
| `phaser-gamedev` | no | Phaser 3 2D game dev: scenes, physics, tilemaps, sprites, polish. |

---

## Worktree Isolation

| Skill | Invocable | Description |
|-------|-----------|-------------|
| `worktree-agent` | no | _(demoted to do references)_ Mandatory rules for agents in git worktree isolation |

---

## Shared / Internal

| Skill | Description |
|-------|-------------|
| `shared-patterns` | Reusable prompt patterns referenced by multiple skills |
