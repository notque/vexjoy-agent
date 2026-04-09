# Complete Routing Tables

Extended routing tables for the `/do` router. The main SKILL.md contains routing instructions. This file contains the full category-specific skill routing and the domain agent table.

**How to read these tables**: Each entry describes what the agent/skill IS FOR and, where false positives have occurred historically, what it is NOT for. The LLM reads these descriptions and judges intent — it does not match keywords.

---

## Domain Agents

Route to these agents based on the user's task domain. Each entry describes what the agent is for, not a keyword list.

| Agent | When to Route Here |
|-------|-------------------|
| **golang-general-engineer** | User is working on Go code, .go files, Go modules, or any Go-language task that isn't covered by a force-route skill. NOT: tasks that merely mention "go" as a verb ("go ahead", "go fix this"). |
| **golang-general-engineer-compact** | Same as golang-general-engineer but explicitly requested for tight context budgets or large-scale Go tasks where conciseness matters. |
| **python-general-engineer** | User is working on Python code, .py files, pip packages, virtual environments, pytest, or any Python-language task. NOT: tasks that mention Python only as context ("this is like Python"). |
| **typescript-frontend-engineer** | User is building or fixing TypeScript frontend code: React components, Next.js pages, UI logic, browser APIs, or frontend state management. Now includes expanded React architecture references (component patterns, hooks, state management, rendering optimization). NOT: React Native mobile apps (use react-native-engineer). |
| **typescript-debugging-engineer** | User needs to debug TypeScript-specific issues: async bugs, race conditions, type errors at runtime, or hard-to-reproduce frontend failures. |
| **nodejs-api-engineer** | User is building or maintaining Node.js backends: Express APIs, REST endpoints, middleware, or server-side JavaScript. |
| **kotlin-general-engineer** | User is working on Kotlin code, coroutines, Ktor, Compose Multiplatform, Gradle KTS, or any Kotlin-language task. NOT: tasks that merely mention Kotlin as context. |
| **kubernetes-helm-engineer** | User is deploying, configuring, or troubleshooting Kubernetes workloads, Helm charts, k8s manifests, or cluster operations. |
| **prometheus-grafana-engineer** | User needs monitoring infrastructure: Prometheus scrape configs, alerting rules, Grafana dashboards, or observability setup. |
| **database-engineer** | User is designing schemas, writing SQL queries, optimizing database performance, or managing migrations. |
| **data-engineer** | User is building data pipelines, ETL/ELT processes, data warehouse integrations, or batch processing workflows. |
| **ansible-automation-engineer** | User needs infrastructure automation via Ansible: playbooks, roles, inventory management, or configuration management. |
| **rabbitmq-messaging-engineer** | User is working with RabbitMQ message queues, AMQP, pub/sub patterns, or message-driven architectures. |
| **opensearch-elasticsearch-engineer** | User needs search cluster work: index management, query optimization, Elasticsearch/OpenSearch operations. |
| **python-openstack-engineer** | User is developing OpenStack services, plugins, or components — specifically within the OpenStack ecosystem. |
| **sqlite-peewee-engineer** | User is working with SQLite databases via the Peewee ORM in Python. |
| **swift-general-engineer** | User is working on Swift code, iOS, macOS, SwiftUI, server-side Swift, or any Swift-language task including concurrency and testing. NOT: tasks that merely mention Swift as context. NOT: React Native apps targeting iOS (use react-native-engineer). |
| **performance-optimization-engineer** | User wants to improve web performance: Core Web Vitals, load times, bundle size, rendering optimization. Now includes expanded React performance references (React Compiler, memoization, concurrent features, profiling). NOT: React Native mobile performance (use react-native-engineer). |
| **php-general-engineer** | User is working on PHP code, Laravel, Symfony, Composer, or any PHP-language task including modern PHP 8.x patterns and security. NOT: tasks that merely mention PHP as context. |
| **mcp-local-docs-engineer** | User wants to build an MCP (Model Context Protocol) server or turn a repository into an MCP documentation source. |
| **research-coordinator-engineer** | User needs systematic research with multiple sources, parallel investigation, or evidence synthesis before acting. NOT: a quick web lookup or single-source check. |
| **research-subagent-executor** | Subagent that executes delegated research tasks using OODA-loop investigation, intelligence gathering, and source evaluation. Dispatched by research-coordinator-engineer, not invoked directly by users. |
| **project-coordinator-engineer** | User needs multi-agent coordination for a large project: spawning parallel agents, tracking cross-cutting tasks, or orchestrating a multi-phase effort. |
| **pipeline-orchestrator-engineer** | User wants to create a new pipeline, scaffold a new structured workflow, or compose pipeline phases. |
| **hook-development-engineer** | User wants to create or modify Python hooks for Claude Code's event-driven system (SessionStart, PostToolUse, etc.). |
| **system-upgrade-engineer** | User wants to upgrade the agent/skill/hook ecosystem after a Claude model update or system-wide change. |
| **technical-documentation-engineer-playbook** | User needs technical documentation created, maintained, or validated — API docs, READMEs, architecture guides. |
| **technical-journalist-writer** | User needs professional technical writing in a journalism style — articles, posts, or content with a specific authored voice. |
| **testing-automation-engineer-playbook** | User needs comprehensive testing strategy, E2E test setup, Playwright tests, or test infrastructure design. NOT: writing Go unit tests (use go-patterns force-route). |
| **ui-design-engineer** | User is designing or implementing UI/UX for web applications: layout, Tailwind styling, component design, or visual hierarchy. |
| **perses-engineer** | User is working with the Perses observability platform: dashboards, plugins, operator/K8s deployment, or core development. |
| **github-profile-rules-engineer** | User wants to extract coding conventions, programming rules, or style guidelines from a GitHub profile's repositories. |
| **react-native-engineer** | User is building or optimizing React Native or Expo mobile apps: list performance (FlashList, LegendList), animations (Reanimated, gesture handler), navigation (native-stack, expo-router), native UI patterns, or mobile-specific state management. NOT: React web apps (use typescript-frontend-engineer). NOT: React Native animation design mockups (use ui-design-engineer for design, then react-native-engineer for Reanimated implementation). NOT: mobile list virtualization or JS thread optimization (performance-optimization-engineer covers web Core Web Vitals only — react-native-engineer covers mobile performance). NOT: React Native apps targeting iOS/Android with Swift/Kotlin native modules (use swift-general-engineer or kotlin-general-engineer for native layer). |
| **react-portfolio-engineer** | User is building a React portfolio or gallery website, typically for creative professionals. |
| **nextjs-ecommerce-engineer** | User is building an e-commerce site with Next.js: product pages, cart, checkout flows. |
| **toolkit-governance-engineer** | User wants to maintain or modify the toolkit's own internal structure: editing skill/agent files, updating routing tables, managing ADRs, regenerating INDEX.json, or enforcing frontmatter compliance. NOT: creating brand-new agents (use skill-creator), writing application code (domain agents), or reviewing external PRs (reviewer agents). |
| **combat-effects-upgrade** | User wants zero-dependency combat visual upgrades: CSS particle replacement, Framer Motion combat juice, CSS 3D card transforms. NOT: 2D WebGL rendering (use pixijs-combat-renderer). NOT: 3D scenes (use threejs-builder). |
| **pixijs-combat-renderer** | User wants PixiJS v8 2D WebGL combat rendering: @pixi/react hybrid canvas, normal maps, GPU particles, post-processing. NOT: 3D scenes (use threejs-builder). |
| **rive-skeletal-animator** | User wants Rive skeletal animation: @rive-app/react-canvas, state machines, character pipelines, combat integration. NOT: sprite-based animation (use phaser-gamedev). |

---

## Process & Execution Skills

| Skill | When to Route Here |
|-------|-------------------|
| **fast (FORCE)** | User wants a quick fix that is clearly one line or a trivial mechanical change: fixing a typo, correcting a variable name, adjusting a constant. The task takes under 2 minutes with no design judgment required. NOT: "fix" in general ("fix this bug", "fix the tests") — those require diagnosis and are not trivial. |
| **quick (FORCE)** | User wants a small, self-contained change that is larger than a typo but still contained: adding a CLI flag, extracting a helper function, renaming an interface. NOT: "quick" as a speed preference ("do this quickly"). |
| **branch-naming** | User needs to name a git branch following conventions, or asks what to name a branch for a task. |
| **git-commit-flow** | User wants to stage and commit code changes to git — writing a commit message, staging files, creating a commit. NOT: "commit to a timeline", "commit to the team", "are we committed to this approach" — those are about dedication, not git. |
| **code-linting** | User wants to run linters or formatters, fix lint errors, or check code style compliance. |
| **universal-quality-gate** | User wants a quality check on code without a specific language or domain in mind. |
| **typescript-check** | User wants to run TypeScript type checking, fix tsc errors, or validate TypeScript types. |
| **vitest-runner** | User wants to run Vitest tests, parse test results, or check if Vitest tests pass. NOT: running Jest, Mocha, or other test runners. |
| **github-actions-check** | User wants to know if CI passed, check GitHub Actions status, or see build results. NOT: "check this out" (browsing), "check my work" (review), "check the logic" (analysis) — those do not involve CI. |
| **read-only-ops** | User explicitly wants read-only operations: browsing, exploring, or examining without any modifications. |
| **python-quality-gate** | User wants Python quality checks: ruff linting, mypy type checking, or combined Python quality validation. |
| **condition-based-waiting** | User needs retry logic, backoff strategies, polling loops, or health check patterns in their code. |
| **distinctive-frontend-design** | User wants context-driven aesthetic exploration for a frontend project with anti-cliche validation: typography exploration, visual identity, design language. |
| **do** | Primary entry point for all delegated work: classifies user requests and routes to the correct agent + skill combination. |
| **quality-loop** (default) | Automatically applied to Medium+ code modification requests. Orchestrates: implement → test → review → fix → retest → PR. Does not apply to: Trivial/Simple tasks, force-route matches (go-patterns, pr-workflow, feature-lifecycle), review-only tasks, research, or content creation. Reference: `skills/do/references/quality-loop.md`. |
| **e2e-testing** | User wants Playwright-based end-to-end testing: page object models, browser tests, test flakiness reduction. NOT: unit tests or integration tests (use test-driven-development or vitest-runner). |
| **kotlin-coroutines** | User wants Kotlin structured concurrency patterns: coroutineScope, Flow, Channel, SupervisorJob, or dispatchers. Companion skill for kotlin-general-engineer. |
| **kotlin-testing** | User wants Kotlin testing patterns: JUnit 5, Kotest, coroutine test dispatchers, MockK. Companion skill for kotlin-general-engineer. |
| **testing-anti-patterns** | User wants to identify or fix flaky tests, or review tests for common anti-patterns. |
| **subagent-driven-development** | User wants to execute a complex plan using subagents in fresh contexts, or needs a two-stage review/implementation cycle. |
| **workflow-orchestrator** | User wants to execute an existing plan with structured phases, or says "run the plan", "execute this". |
| **parallel-code-review** | User wants comprehensive review of a codebase from multiple reviewer perspectives simultaneously. |
| **php-quality** | User wants PHP code quality checks: PSR standards compliance, strict types enforcement, framework idioms. Companion skill for php-general-engineer. |
| **php-testing** | User wants PHP testing patterns: PHPUnit, test doubles, database testing. Companion skill for php-general-engineer. |
| **codex-code-review** | User wants a second-opinion code review from OpenAI Codex CLI (GPT-5.4 xhigh), a cross-model review, or says "codex review", "second opinion", "get another perspective". NOT: a standard Claude-only review (use systematic-code-review or parallel-code-review). |
| **with-anti-rationalization** | User explicitly requests maximum rigor, thorough verification, or wants anti-rationalization patterns injected. |
| **plan-manager** | User wants to see the status of plans, audit existing plans, or manage the plan lifecycle. |
| **planning-with-files** | User needs persistent planning with file-backed state across a long multi-session task. |
| **go-patterns (FORCE)** | User wants Go development patterns: testing (_test.go, table-driven, benchmarks), concurrency (goroutines, channels, sync), error handling (fmt.Errorf, errors.Is/As, sentinels), anti-patterns (code smells, over-engineering), code review (Go PR quality), SAP CC conventions (sapcc, go-bits, keppel), or quality gates (make check, lint). |
| **sapcc-review** | User wants a SAPCC compliance review of a Go PR or repository for SAP Converged Cloud conventions. |
| **sapcc-audit** | User wants a full SAPCC audit of an entire repository against SAP Converged Cloud standards. |
| **fish-shell-config** | User is configuring fish shell: editing config.fish, writing fish functions, or fixing fish-specific syntax. |
| **adr-consultation** | User wants multi-agent consultation before making an architectural decision: dispatch 3+ agents to stress-test a plan before committing. |
| **forensics** | User wants to diagnose a failed or stuck workflow after the fact: what went wrong, why it failed, session crash post-mortem, or incident review. NOT: debugging live code (use systematic-debugging). |
| **pause-work** | User wants to stop working on a task and create a handoff artifact for resumption later: save progress, session handoff, stopping for now. |
| **resume-work** | User wants to pick up where they left off in a previous session: restore context, continue work, "what was I doing". |
| **plan-checker** | User wants to validate a plan before execution begins: check against 10 verification dimensions, pre-execution review, "is this plan ready". |
| **integration-checker** | User wants to verify that components are correctly wired together: exports are imported and used, data flows through connections, output shapes match inputs. |
| **pre-planning-discussion** | User wants to resolve ambiguities before planning begins: clarify gray areas, surface assumptions, "before we plan". |
| **pair-programming** | User wants collaborative coding with enforced micro-steps: announce each change, show diff, wait for confirmation before applying. |
| **spec-writer** | User wants to write a structured specification with user stories, acceptance criteria, scope boundaries, and risks. |
| **decision-helper** | User wants a weighted decision framework for architectural or technology choices: pros/cons, trade-off matrix, "which is better", "should I use X or Y". |
| **socratic-debugging** | User wants to be guided to find the root cause themselves through questions rather than being given the answer directly: coaching mode, "teach me to find it". |
| **plant-seed** | User wants to capture a forward-looking idea with trigger conditions so it surfaces automatically during future feature design. |
| **install** | User wants to verify Claude Code Toolkit installation, diagnose setup issues, or check if the toolkit is correctly configured. |
| **skill-creator** | User wants to create or improve a Claude Code skill, workflow automation, or agent configuration. |
| **swift-concurrency** | User wants Swift concurrency patterns: async/await, Actor, Task, Sendable, structured concurrency. Companion skill for swift-general-engineer. |
| **swift-testing** | User wants Swift testing patterns: XCTest, Swift Testing framework, async test patterns. Companion skill for swift-general-engineer. |
| **systematic-code-review** | User wants a structured 4-phase code review: UNDERSTAND changes, VERIFY claims against actual behavior, ASSESS security/performance/architecture risks, DOCUMENT findings with severity classification. |
| **systematic-debugging** | User wants to diagnose why something is broken or not working as expected — root cause analysis, reproduce-isolate-identify-verify. Common phrasings: "why is this broken", "what's wrong with", "figure out why", "can't figure out", "not working", "slow", "performance", "taking too long", "optimize". NOT: debugging a past session (use forensics), guided self-discovery (use socratic-debugging). |
| **systematic-refactoring** | User wants to improve existing code structure without changing behavior — extract, rename, simplify, restructure. Common phrasings: "clean this up", "improve this code", "make this better", "code quality". NOT: adding new features (use a domain agent), fixing a bug (use systematic-debugging). |
| **test-driven-development** | User wants RED-GREEN-REFACTOR cycle with strict phase gates: write failing test first, make it pass with minimal code, then refactor. Common phrasings: "TDD", "test first", "red green refactor", "write tests before code". |
| **threejs-builder** | User wants to build a Three.js 3D web application: scenes, WebGL, 3D animation, or 3D graphics in the browser. 4-phase workflow: Design, Build, Animate, Polish. |
| **webgl-card-effects** | User wants GPU-accelerated visual effects on card components: holographic foil, metallic shimmer, rarity glow, or interactive tilt-shine. Uses standalone WebGL2 fragment shaders with a shared context singleton — no Three.js required. Triggers: "card effects", "holographic", "foil effect", "card shimmer", "card glow", "shader card", "WebGL card", "rarity effects", "Balatro effect". Category: frontend. NOT: 3D scenes or post-processing pipelines (use threejs-builder). |
| **phaser-gamedev** | User wants to build a 2D browser game using Phaser 3: platformers, arcade shooters, top-down RPGs, side-scrollers, or any canvas-based 2D gameplay. Covers scenes, arcade and Matter.js physics, tilemaps, spritesheets, animation state machines, and mobile controls. Triggers: "phaser", "2d game", "platformer", "arcade physics", "tilemap", "sprite sheet", "side scroller". Category: game-development. NOT: 3D games (use threejs-builder) or native mobile (use react-native-engineer). |
| **game-asset-generator** | User needs AI-generated or sourced game assets: 3D models via Meshy API (text-to-3D, image-to-3D), Gaussian Splat environments via World Labs, pixel art sprites, images/textures via fal.ai, or free pre-built assets from Sketchfab/Poly Haven/Poly.pizza. Triggers: "game asset", "generate 3d model", "text to 3d", "image to 3d", "meshy", "gaussian splat", "generate sprite", "pixel art", "game environment", "fal.ai", "fal ai". Category: game-development. NOT: game engine scripting, physics, or shader authoring (use threejs-builder or phaser-gamedev for scene integration). |
| **game-pipeline** | User wants to orchestrate the full game development lifecycle across phases: scaffolding (project setup, EventBus), assets, visual design polish (juice, screen shake, particles), audio (Web Audio API), QA (Playwright visual regression), or deployment (GitHub Pages, Vercel, iOS via Capacitor). Triggers: "make game", "game pipeline", "game audio", "game testing", "game qa", "playtest", "deploy game", "ship game", "promo video", "game polish", "add juice", "screen shake", "capacitor ios". Category: game-development. NOT: Unity/Godot/native engines. |
| **verification-before-completion** | User wants defense-in-depth verification before declaring a task complete: run full test suite, validate build, check for stub patterns, confirm artifacts exist. |
| **worktree-agent** | Mandatory rules for agents operating in git worktree isolation: verify working directory, create feature branches, use absolute paths. Not user-invoked directly. |

---

## Analysis & Discovery Skills

| Skill | When to Route Here |
|-------|-------------------|
| **codebase-overview** | User wants a high-level understanding of a repository's structure, architecture, or purpose. |
| **codebase-analyzer** | User wants statistical analysis of codebase patterns: pattern frequency, structural metrics, style vectors, or data-driven insights about code. NOT: a high-level overview (use codebase-overview). |
| **code-cleanup** | User wants to remove stale TODOs, unused code, dead imports, or generally clean up accumulated debt. |
| **comment-quality** | User wants to audit code comments for accuracy, temporal references, or staleness. |
| **agent-evaluation** | User wants to grade or evaluate a skill, agent, or pipeline for quality and standards compliance. NOT: evaluating code output or test results. |
| **agent-comparison** | User wants to A/B test agents, run autoresearch, optimize a skill description, or optimize a skill body with benchmark tasks. |
| **agent-upgrade** | User wants to audit and systematically improve a specific agent to bring it up to current template standards. |
| **testing-agents-with-subagents** | User wants to validate an agent by running it against real test cases in subagents. |
| **skill-eval** | User wants to evaluate a skill, test triggers manually, benchmark it against scenarios, or inspect skill quality without running the autoresearch optimizer. |
| **full-repo-review** | User wants a comprehensive 3-wave review of all source files in the entire repository. |
| **github-notification-triage** | User wants to triage GitHub notifications: fetch, classify, and report actions needed. Common phrasings: "check notifications", "github inbox", "triage notifications". |
| **repo-value-analysis** | User wants to systematically analyze an external repository to determine what ideas or patterns are worth adopting. |
| **kb-compile** | User wants to compile raw knowledge base sources into structured wiki articles: concept articles, source summaries, and an index. Works on a `research/{topic}/` directory initialized with `kb-init.py`. Triggers: "compile knowledge base", "kb compile", "compile wiki", "build knowledge base", "compile raw sources". Category: research. |
| **kb-lint** | User wants to health-check a knowledge base wiki for structural consistency, broken references, orphaned concepts, empty articles, or stale index. Produces a structured lint report and optionally auto-fixes index gaps. Triggers: "lint knowledge base", "kb lint", "check kb health", "knowledge base health", "kb consistency". Category: research. |
| **kb-query** | User wants to query a compiled knowledge base to answer a question, drawing on wiki concept and source articles. Optionally files the answer as a permanent query record that feeds back into the next compile cycle. Triggers: "query knowledge base", "kb query", "ask knowledge base", "search kb", "kb question". Category: research. |
| **roast** | User wants constructive critique of a design doc, idea, or code via 5 HackerNews personas with claim validation. Common phrasings: "roast this", "devil's advocate", "stress test this idea", "poke holes in this". |
| **data-analysis** | User wants to analyze data: CSV files, metrics, A/B test results, cohort analysis, statistical distributions, KPIs, or funnel data. |
| **kairos-lite** | User wants a project status briefing, health check, or to see what happened overnight — GitHub notifications, CI status, toolkit health. Common phrasings: "what happened", "morning briefing", "check notifications", "project status", "health check". NOT: specific PR status (use github-actions-check), specific CI debugging (use systematic-debugging). |
| **pr-workflow** (miner mode) | User wants to extract review comments or learnings from past GitHub PRs, or coordinate batch mining. |
| **skill-composer** | User wants to compose multiple skills into a multi-skill workflow. |
| **routing-table-updater** | User wants to update routing tables after adding or changing agents/skills. |
| **security-threat-model** | User wants a security threat model: scan for attack surface, supply-chain risks, injection vectors, or security posture audit. |
| **docs-sync-checker** | User wants to check if README files or documentation are in sync with the actual code. |
| **do-perspectives** | User wants multi-perspective analysis of a problem from 10 different lenses simultaneously. |
| **do → parallel-analysis** | User wants parallel multi-angle extraction of insights from a document or codebase. Loaded from `skills/do/references/parallel-analysis.md`. |
| **plan-manager** | User wants to manage the plan lifecycle: create, track, or review plans. |
| **learn** | User wants to teach Claude a new error pattern or record a reusable insight. |
| **retro** | User wants to interact with the learning system: view stats, list accumulated knowledge, search learnings, or graduate mature entries into agents/skills. |
| **generate-claudemd** | User wants to generate a project-specific CLAUDE.md by analyzing the current repository's structure and conventions. |
| **professional-communication** | User needs to write a professional email or formal business communication. |
| **workflow-help** | User wants an explanation of how a workflow, pipeline, or process works. Also when user is lost or stuck: "help", "I'm stuck", "what should I do", "I don't know how", "where do I start". |

---

## PR & Git Skills

| Skill | When to Route Here |
|-------|-------------------|
| **pr-workflow (FORCE)** | User wants to get local code changes onto GitHub — pushing a branch, creating a PR, or syncing local commits to the remote. Also handles: PR status checks, fixing review comments, cleaning up branches after merge, addressing PR feedback, and mining tribal knowledge from PRs. Common phrasings: "open a pull request", "create a PR", "make a PR", "submit PR", "push and PR", "pr status", "fix PR comments", "clean up branches", "mine PRs". NOT: "push back" (disagree with a decision), "push the boundaries" (explore limits). The intent must be about git/GitHub operations. |
| **git-commit-flow (FORCE)** | User wants to stage files and create a git commit from local changes. Common phrasings: "save my work", "commit this", "save progress", "checkpoint", "commit these changes". NOT: "commit to this approach" (deciding), "commit to the team" (dedication), "I'm committed to finishing" (resolve). The intent must be about creating a git commit object. |
| **github-actions-check (FORCE)** | User wants to know if CI passed or check GitHub Actions run status. NOT: "check this code" (review), "check my logic" (analysis), "double-check this" (verify), "check the docs" (read documentation). The intent must be about CI/CD pipeline status. |
| **/pr-review command** | User wants a comprehensive code review of a PR with retro learning applied. This is a command, not a skill — invoke it directly. |

### PR Workflow Policies

| Repo Type | Detection | Commit/Push/PR | Review Gate | Merge |
|-----------|-----------|----------------|-------------|-------|
| **protected-org** (configured organizations) | `scripts/classify-repo.py` pattern match | **Human-gated**: confirm each step with user | Their reviewers handle review | **NEVER auto-merge** |
| **personal** (all other repos) | Default | Auto-execute | `/pr-review` → fix loop (max 3 iterations) | Create PR after review passes |

---

## Content Creation Skills

| Skill | When to Route Here |
|-------|-------------------|
| **voice-writer** | User wants to write a blog post, article, or long-form content in a specific voice. |
| **anti-ai-editor** | User wants to edit content to remove AI-sounding patterns, genericness, or sterile phrasing. |
| **content-engine** | User wants to repurpose source assets (articles, demos, docs) into platform-native social content. Common phrasings: "repurpose this", "adapt for social", "turn this into posts", "platform variants". |
| **de-ai-pipeline (FORCE)** | User wants to scan and systematically fix AI patterns across documentation or a content repository. |
| **post-outliner** | User wants a structured outline for a blog post or article before writing. |
| **topic-brainstormer** | User wants ideas or topics to write about in a domain. |
| **pre-publish-checker** | User wants to check content before publishing: completeness, quality, consistency. |
| **seo-optimizer** | User wants to optimize content for search engines: keywords, meta descriptions, structure. |
| **create-voice** | User wants to create a new voice profile from writing samples for use in future content generation. |
| **voice-calibrator** | User wants to refine or calibrate an existing voice profile against new samples. |
| **voice-validator** | User wants to validate that generated content matches a voice profile. |
| **series-planner** | User wants to plan a multi-part content series with coherent arc and progression. |
| **content-calendar** | User wants to plan content publication over a time period. |
| **link-auditor** | User wants to find and fix broken links in documentation or content. |
| **image-auditor** | User wants to audit images for optimization, alt text, or quality issues. |
| **batch-editor** | User wants to apply edits across many content files in bulk. |
| **taxonomy-manager** | User wants to manage content categories, tags, or taxonomy systems. |
| **wordpress-uploader** | User wants to upload or create draft posts in WordPress programmatically. |
| **wordpress-live-validation** | User wants to validate WordPress posts live after upload: check rendering, canonical URLs, or publication status. |
| **joy-check** | User wants to validate that content has positive, joy-centered framing — not negative or fear-based tone. |
| **pptx-generator** | User wants to generate a PowerPoint presentation, slide deck, or pitch deck from content or research. |
| **frontend-slides** | User wants browser-based HTML presentations: reveal-style slide decks, kiosk presentations, or converting PPTX to web format. |
| **gemini-image-generator** | User wants to generate images from text prompts via Google Gemini: sprites, character art, or AI-generated visuals. |
| **bluesky-reader** | User wants to read public Bluesky feeds, fetch posts, or interact with the AT Protocol API. |
| **image-to-video** | User wants to combine a static image with audio to create a video file (album art video, podcast video, music visualization). |
| **headless-cron-creator** | User wants to generate a headless Claude Code cron job that runs a task on a schedule. |
| **auto-dream** | User wants to run or configure the background memory consolidation and graduation system: trigger a dream cycle, check dream/graduation status, review the last dream report, check graduation candidates, or configure the nightly cron. Triggers: "dream", "memory consolidation", "consolidate memories", "auto-dream", "last dream", "graduate learnings", "promote learnings". Category: meta-tooling. |
| **explanation-traces** | User wants to understand why the system made a specific decision: which agent was selected and why, which triggers were matched, which gate passed or failed, or a full session decision timeline. Reads `session-trace.json` and presents recorded decisions as a human-readable timeline — never reconstructs from memory. Triggers: "why did you", "explain routing", "show trace", "decision log", "why that agent", "explain decision", "show decisions", "trace log". Category: analysis. NOT: a general debugging request (use systematic-debugging) or live routing inspection. |
| **multi-persona-critique** | User wants to stress-test proposals, feature ideas, or architectural decisions through parallel critique from 5 philosophical personas (The Logician, Pragmatic Builder, Systems Purist, End User Advocate, Skeptical Philosopher), with consensus synthesis showing where personas agree and disagree. Can critique provided proposals or generate ideas and then critique them. Triggers: "critique these ideas", "multi-persona review", "philosophical critique", "devil's advocate on ideas", "stress test proposals", "evaluate from multiple perspectives", "critique proposals". Category: analysis. NOT: code critique (use roast), single-dimension scoring (use decision-helper). |
| **reference-enrichment** | User wants to improve an agent or skill by analyzing its reference depth and generating missing domain-specific reference files — version-specific pattern tables, anti-pattern catalogs with detection commands, and error-fix mappings. Upgrades components from Level 0-1 to Level 2-3 depth. Triggers: "enrich references", "improve reference depth", "generate references", "add reference files", "reference enrichment". Category: meta-tooling. |
| **toolkit-evolution** | User wants to run a self-improvement cycle on the toolkit, diagnose gaps, propose improvements, build winners, A/B test, and ship via PR. Also triggers for: scheduled nightly improvement, evolving a specific subsystem (routing, hooks, agents), or asking what should be improved. Triggers: "evolve toolkit", "improve the system", "self-improve", "what should we improve", "evolve routing", "evolve hooks", "toolkit evolution", "run evolution", "nightly evolution", "self-improvement cycle". Category: meta-tooling. |
| **nano-banana-builder** | User wants to build a Next.js web application using Google Gemini Nano Banana image generation APIs. |
| **video-editing** | User wants to edit video: cut footage, assemble clips, create demo videos, or build screen recordings via FFmpeg and Remotion. |
| **x-api** | User wants to post tweets, build threads, upload media, read timelines, or search via the X (Twitter) API. |

---

## Voice Skills

| Skill | When to Route Here |
|-------|-------------------|
| **create-voice** | User wants to build a new voice profile from their writing samples. This is the entry point for establishing a new voice. |
| **voice-writer** | User wants to generate content in an established voice — multi-step generation with validation. |
| **voice-calibrator** | User wants to refine an existing voice profile or improve how well it captures their writing style. |
| **voice-validator** | User wants to run a validation loop to confirm generated content matches the voice profile. |

**Voice selection:** Use `create-voice` to build voice profiles from writing samples, then `voice-writer` for multi-step generation in that voice. Custom voice profiles are matched via their skill triggers.

**Wabi-sabi principle:** Perfection is an AI tell. Natural imperfections are features. Don't over-polish.

---

## Feature Lifecycle Skills

Sequential pipeline: design → plan → implement → validate → release. Each skill advances state via `scripts/feature-state.py`.

| Skill | Phase | When to Route Here |
|-------|-------|--------------------|
| **feature-lifecycle (FORCE)** | 1-5 | All feature lifecycle phases: design, plan, implement, validate, release. Routes to the correct phase based on feature state. Entry point for all new features. |

**Auto-detection**: When `.feature/` exists, `feature-state.py status` determines current phase and feature-lifecycle routes to the matching phase reference automatically.

**Entry point**: New features always enter via feature-lifecycle (design phase). Skipping phases is not supported.

---

## Pipeline Skills

All workflow pipelines live in `skills/workflow/references/` and are accessed via the workflow umbrella skill.

| Pipeline | When to Route Here | Phases |
|----------|--------------------|--------|
| **workflow** (umbrella) | All structured multi-phase workflows. Routes to the correct workflow based on intent. Includes: toolkit-improvement, system-upgrade, research-to-article, explore, doc-generation, comprehensive-review, article-evaluation, voice-calibrator, de-ai, auto-pipeline, and more. Each workflow lives in `skills/workflow/references/`. |
| **toolkit-improvement** (FORCE) | User wants to evaluate, audit, or improve the toolkit itself. Dispatches 30+ reviewer agents in waves, synthesizes findings, has a skeptical grader challenge them, creates ADRs, implements fixes, and validates. Use for: "improve the toolkit", "evaluate the repo", "audit the system", "find issues", "self-improvement", "repo health check", "what can be better", "how can we improve", "make the toolkit better". NOT: reviewing a single PR (use /pr-review) or fixing one bug (use /systematic-debugging). | EVALUATE → RESEARCH → SYNTHESIZE → CRITIQUE → REPORT → ADR → IMPLEMENT → VALIDATE → REMEDIATE → RECORD |
| **system-upgrade** (system-upgrade-engineer) | User wants to upgrade the Claude Code toolkit after a model update, apply system-wide changes, or roll out agent improvements. NOT: upgrading a specific library dependency in user code. | CHANGELOG → AUDIT → PLAN → IMPLEMENT → VALIDATE → DEPLOY |
| **workflow** (skill-creation, skill-creator) | User wants to create a new skill with formal quality gates, phase structure, and integration. | DISCOVER → DESIGN → SCAFFOLD → VALIDATE → INTEGRATE |
| **research-pipeline** (research-coordinator-engineer) | User wants formal research with saved artifacts, multiple sources, and a synthesized deliverable. NOT: a quick lookup or single-source check. | SCOPE → GATHER → SYNTHESIZE → VALIDATE → DELIVER |
| **agent-upgrade** (skill-creator) | User wants to audit and improve a specific agent to bring it up to current template standards. | AUDIT → DIFF → PLAN → IMPLEMENT → RE-EVALUATE |
| **pr-workflow** (pipeline mode) | User wants the full structured PR workflow with review gates. | CLASSIFY → STAGE → REVIEW → COMMIT → PUSH → CREATE → VERIFY → CLEANUP |
| **voice-writer** | User wants to write content in a specific voice with multi-step generation and validation. | LOAD → GROUND → GENERATE → VALIDATE → REFINE → JOY-CHECK → OUTPUT → CLEANUP |
| **github-profile-rules** (github-profile-rules-engineer) | User wants to extract programming rules or coding conventions from a GitHub user's repositories. | ADR → FETCH → RESEARCH → SAMPLE → COMPILE → GENERATE → VALIDATE → OUTPUT |
| **workflow-orchestrator** | User wants to orchestrate a plan with structured phases — brainstorm, plan, execute. | BRAINSTORM → WRITE-PLAN → EXECUTE-PLAN |
| **do-perspectives** | User wants multi-lens analysis of a problem from 10 different perspectives. | VALIDATE → ANALYZE → SYNTHESIZE → APPLY → VERIFY |

### Workflow Companion Map

Workflows that work together in common sequences:

| Workflow | Sequence | When |
|----------|----------|------|
| **Content creation** | research-pipeline → voice-writer | Research-backed articles in a specific voice |
| **Feature lifecycle** | workflow (explore) → workflow-orchestrator → pr-workflow | Understand → implement → ship |
| **Code review** | workflow (comprehensive-review) → pr-workflow | Review then submit |
| **Agent improvement** | agent-upgrade → skill-creator | Audit agent, then scaffold missing skills |
| **Toolkit improvement** | workflow (toolkit-improvement) → system-upgrade → agent-upgrade | Evaluate → fix → upgrade system → upgrade agents |
| **System upgrade** | system-upgrade → agent-upgrade | Upgrade system, then individual agents |
| **Voice development** | workflow (voice-calibrator) → voice-writer → workflow (article-evaluation) | Calibrate → write → evaluate |
| **Documentation** | workflow (explore) → workflow (doc-generation) | Understand codebase → generate docs |
| **Perses** | perses (dac mode) → perses (plugin mode) | Dashboard-as-Code + plugin development |

---

## GitHub Profile Analysis Skills

| Skill | When to Route Here |
|-------|-------------------|
| **github-profile-rules** (github-profile-rules-engineer) | User wants to extract programming rules, coding conventions, or style guidelines by analyzing a GitHub user's public repositories. |

---

## Reddit Skills

| Skill | When to Route Here |
|-------|-------------------|
| **reddit-moderate** | User wants to moderate a subreddit: check the modqueue, review reports, or take moderation actions. |

---

## Validation Skills

| Skill | When to Route Here |
|-------|-------------------|
| **endpoint-validator** | User wants to validate that API endpoints are reachable and returning expected responses. |
| **kubernetes-debugging** | User wants to debug Kubernetes pod failures, networking issues, or resource problems using structured triage: describe, logs, events, exec. Companion skill for kubernetes-helm-engineer. |
| **kubernetes-security** | User wants to harden Kubernetes clusters: RBAC, PodSecurity standards, network policies, secret management, supply chain controls. Companion skill for kubernetes-helm-engineer. |
| **service-health-check** | User wants to check if a service is healthy or needs restarting. |
| **cron-job-auditor** | User wants to audit cron jobs or scheduled scripts for reliability and correctness. |

---

## Decision Support Skills

Umbrella skill for all C-suite decision support. Detects mode (STRATEGY, TECHNOLOGY, GROWTH, COMPETITIVE, EVALUATION) and loads domain-specific references on demand.

| Skill | When to Route Here |
|-------|-------------------|
| **csuite** | User wants executive decision support across any domain: CEO-level strategy (market entry, partnerships, resource allocation, "should I/we", "invest in", "strategic"), CTO-level technology (build vs buy, vendor evaluation, tech stack, architecture decisions, "should we use/adopt"), CMO-level growth (content strategy, audience, marketing, SEO, brand, community building), competitive intelligence (competitor analysis, market landscape, differentiation, positioning), or project evaluation (feasibility, effort estimate, ROI, priority, go/no-go, viability). NOT: technical architecture micro-choices between two libraries (use decision-helper), writing content (use voice-writer), SEO optimization of a specific post (use seo-optimizer). |

---

## Perses Skills

| Skill | When to Route Here |
|-------|-------------------|
| **perses (FORCE)** (perses-engineer) | User wants to work with the Perses observability platform: dashboards, plugins, deployment, migration, linting, datasources, variables, projects, CUE schemas, or code review. Routes to the correct sub-workflow based on intent. NOT: general Prometheus/Grafana work (use prometheus-grafana-engineer). |

---

## Reviewer Agents

Consolidated reviewer agents, each covering multiple review perspectives:

| Agent | When to Route Here |
|-------|-------------------|
| **reviewer-code-playbook** | Code quality review: conventions, naming, dead code, performance, types, tests, comments, config safety. Use for code style, readability, simplification, language idioms, naming consistency, unused code, comment accuracy, hot paths, type design, test coverage, and configuration review. |
| **reviewer-system-playbook** | System review: security, concurrency, errors, observability, APIs, migrations, dependencies, docs. Use for vulnerability scans, race conditions, goroutine leaks, silent failures, error messages, logging quality, API contracts, migration safety, dependency audits, and documentation validation. |
| **reviewer-perspectives** | Multi-perspective review: newcomer, senior, pedant, contrarian, user advocate, meta-process. Use for fresh-eyes critique, skeptical senior review, technical precision, assumption challenges, user impact analysis, and system design meta-review. |
| **reviewer-domain** | Domain-specific review: ADR compliance, business logic, SAP CC structural, pragmatic builder. Use for architecture decision compliance, domain correctness, sapcc Go conventions, and production readiness critique. |

---

## Quick Routing Examples

| Request | Routes To | Reasoning |
|---------|-----------|-----------|
| "fix the typo in main.go" | **fast (FORCE)** | Mechanical one-character fix, no design judgment |
| "rename this variable" | **fast (FORCE)** | Trivial rename, no logic change |
| "add a --verbose flag to the CLI" | **quick (FORCE)** | Small self-contained change |
| "small refactor: extract helper function" | **quick (FORCE)** | Contained, no design ambiguity |
| "debug Go tests" | golang-general-engineer + systematic-debugging | Debugging task in Go domain |
| "write Go tests for X" | **go-patterns (FORCE)** | Go testing domain — force-route |
| "add worker pool" | **go-patterns (FORCE)** | Go concurrency domain — force-route |
| "add auth to Python API" | python-general-engineer + workflow-orchestrator | Python domain, multi-step implementation |
| "review my K8s manifests" | kubernetes-helm-engineer + systematic-code-review | K8s domain, review task |
| "roast this design doc" | roast (5 personas) | Multi-persona critique |
| "execute plan with subagents" | subagent-driven-development | Explicit subagent execution |
| "debug TypeScript race condition" | typescript-debugging-engineer + systematic-debugging | TS debugging domain |
| "write in custom voice" | voice-writer + [your-voice-skill] | Voice generation task |
| "comprehensive code review" | parallel-code-review (3 reviewers) | Multi-reviewer parallel review |
| "design a rate limiter feature" | **feature-lifecycle (FORCE)** | New feature entry point (design phase) |
| "plan this feature" | **feature-lifecycle (FORCE)** | Feature plan phase |
| "build this feature" | **feature-lifecycle (FORCE)** | Feature implementation phase |
| "review this PR" | /pr-review command (retro-enabled) | PR review command |
| "submit a PR" | pr-workflow (pipeline mode) | Full PR workflow with gates |
| "push my changes" | **pr-workflow (FORCE)** | Intent: get local changes onto GitHub |
| "push back on this decision" | (not a routing target) | Intent: disagree — "push" is not a git push |
| "commit this" | **git-commit-flow (FORCE)** | Intent: create a git commit |
| "commit to this approach" | (not a routing target) | Intent: decide — "commit" is not a git commit |
| "did CI pass?" | **github-actions-check (FORCE)** | Intent: check CI status |
| "check my logic here" | (domain agent + review) | Intent: review — not CI |
| "get a second opinion on this code" | codex-code-review | Cross-model review via Codex CLI |
| "codex review this PR" | codex-code-review | Explicit Codex review request |
| "research then write article" | research-pipeline → voice-writer | Research-backed content creation |
| "create a pipeline for X" | pipeline-orchestrator-engineer + workflow | Pipeline creation |
| "improve the toolkit" | toolkit-improvement (FORCE) | Full 10-phase evaluation + improvement |
| "evaluate the repo" | toolkit-improvement (FORCE) | Full 10-phase evaluation + improvement |
| "audit the system" | toolkit-improvement (FORCE) | Full 10-phase evaluation + improvement |
| "find issues" | toolkit-improvement (FORCE) | Full 10-phase evaluation + improvement |
| "what can be better" | toolkit-improvement (FORCE) | Full 10-phase evaluation + improvement |
| "self-improvement" | toolkit-improvement (FORCE) | Full 10-phase evaluation + improvement |
| "upgrade system for new Claude version" | system-upgrade-engineer + system-upgrade | System-wide upgrade |
| "create skill with quality gates" | skill-creator + workflow (skill-creation) | Formal skill creation |
| "create hook (formal, with perf test)" | hook-development-engineer + workflow (hook-development) | Formal hook creation |
| "research with saved artifacts" | research-coordinator-engineer + research-pipeline | Formal research pipeline |
| "upgrade this specific agent" | skill-creator + agent-upgrade | Single agent improvement |
| "create a 3D scene" | typescript-frontend-engineer + threejs-builder | Frontend domain, 3D task |
| "generate image with Python" | python-general-engineer + gemini-image-generator | Python domain, image generation |
| "extract coding rules from github user X" | github-profile-rules-engineer + github-profile-rules | Profile analysis |
| "analyze github profile conventions" | github-profile-rules-engineer + github-profile-rules | Convention extraction |
| "review sapcc Go repo" | golang-general-engineer + sapcc-review | SAPCC domain review |
| "audit sapcc conventions" | golang-general-engineer + sapcc-audit | SAPCC full audit |
| "work on sapcc Go code" | **go-patterns (FORCE)** | SAPCC conventions domain — auto-detected by hook |
| "moderate reddit" | reddit-moderate | Reddit moderation |
| "check my modqueue" | reddit-moderate | Reddit moderation |
| "open a pull request" | **pr-workflow (FORCE)** | Intent: create a PR on GitHub |
| "make a PR" | **pr-workflow (FORCE)** | Intent: create a PR on GitHub |
| "save my work" | **git-commit-flow (FORCE)** | Intent: commit current changes |
| "checkpoint" | **git-commit-flow (FORCE)** | Intent: save progress as a commit |
| "I'm stuck" | workflow-help | User is lost — guide them |
| "where do I start" | workflow-help | User needs orientation |
| "why is this broken" | systematic-debugging | Diagnosis request — root cause analysis |
| "figure out why" | systematic-debugging | Diagnosis request — root cause analysis |
| "it's slow" | systematic-debugging | Performance issue — diagnosis needed |
| "clean this up" | systematic-refactoring | Code improvement — refactoring |
| "make this better" | systematic-refactoring | Code quality improvement |
| "review this" | comprehensive-review | Multi-wave code review |
| "look at this code" | comprehensive-review | Code review request |
| "debug the goroutine leak" | golang-general-engineer + systematic-debugging | Go domain + diagnosis |
| "optimize FlatList scroll performance" | react-native-engineer | React Native list performance domain |
| "add Reanimated spring animation" | react-native-engineer | React Native animation domain |
| "set up expo-router navigation" | react-native-engineer | React Native navigation domain |
| "write a blog post about X" | voice-writer | Blog content generation |
| "article about kubernetes" | voice-writer | Long-form content in voice |
| "write for the website" | voice-writer | Website content generation |
