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
| **typescript-frontend-engineer** | User is building or fixing TypeScript frontend code: React components, Next.js pages, UI logic, browser APIs, or frontend state management. |
| **typescript-debugging-engineer** | User needs to debug TypeScript-specific issues: async bugs, race conditions, type errors at runtime, or hard-to-reproduce frontend failures. |
| **nodejs-api-engineer** | User is building or maintaining Node.js backends: Express APIs, REST endpoints, middleware, or server-side JavaScript. |
| **kubernetes-helm-engineer** | User is deploying, configuring, or troubleshooting Kubernetes workloads, Helm charts, k8s manifests, or cluster operations. |
| **prometheus-grafana-engineer** | User needs monitoring infrastructure: Prometheus scrape configs, alerting rules, Grafana dashboards, or observability setup. |
| **database-engineer** | User is designing schemas, writing SQL queries, optimizing database performance, or managing migrations. |
| **data-engineer** | User is building data pipelines, ETL/ELT processes, data warehouse integrations, or batch processing workflows. |
| **ansible-automation-engineer** | User needs infrastructure automation via Ansible: playbooks, roles, inventory management, or configuration management. |
| **rabbitmq-messaging-engineer** | User is working with RabbitMQ message queues, AMQP, pub/sub patterns, or message-driven architectures. |
| **opensearch-elasticsearch-engineer** | User needs search cluster work: index management, query optimization, Elasticsearch/OpenSearch operations. |
| **python-openstack-engineer** | User is developing OpenStack services, plugins, or components — specifically within the OpenStack ecosystem. |
| **sqlite-peewee-engineer** | User is working with SQLite databases via the Peewee ORM in Python. |
| **performance-optimization-engineer** | User wants to improve web performance: Core Web Vitals, load times, bundle size, rendering optimization. |
| **mcp-local-docs-engineer** | User wants to build an MCP (Model Context Protocol) server or turn a repository into an MCP documentation source. |
| **research-coordinator-engineer** | User needs systematic research with multiple sources, parallel investigation, or evidence synthesis before acting. NOT: a quick web lookup or single-source check. |
| **project-coordinator-engineer** | User needs multi-agent coordination for a large project: spawning parallel agents, tracking cross-cutting tasks, or orchestrating a multi-phase effort. |
| **pipeline-orchestrator-engineer** | User wants to create a new pipeline, scaffold a new structured workflow, or compose pipeline phases. |
| **hook-development-engineer** | User wants to create or modify Python hooks for Claude Code's event-driven system (SessionStart, PostToolUse, etc.). |
| **skill-creator-engineer** | User wants to create or improve a Claude Code skill, workflow automation, or agent configuration. |
| **system-upgrade-engineer** | User wants to upgrade the agent/skill/hook ecosystem after a Claude model update or system-wide change. |
| **technical-documentation-engineer** | User needs technical documentation created, maintained, or validated — API docs, READMEs, architecture guides. |
| **technical-journalist-writer** | User needs professional technical writing in a journalism style — articles, posts, or content with a specific authored voice. |
| **testing-automation-engineer** | User needs comprehensive testing strategy, E2E test setup, Playwright tests, or test infrastructure design. NOT: writing Go unit tests (use go-testing force-route). |
| **ui-design-engineer** | User is designing or implementing UI/UX for web applications: layout, Tailwind styling, component design, or visual hierarchy. |
| **perses-dashboard-engineer** | User is creating, managing, or configuring Perses observability dashboards, datasources, variables, or projects. |
| **perses-plugin-engineer** | User is developing Perses plugins: panel plugins, datasource plugins, CUE schemas. |
| **perses-core-engineer** | User is contributing to Perses core: Go backend, API handlers, or upstream Perses development. |
| **perses-operator-engineer** | User is deploying Perses via Kubernetes operator, CRDs, or managing Perses in a k8s cluster. |
| **github-profile-rules-engineer** | User wants to extract coding conventions, programming rules, or style guidelines from a GitHub profile's repositories. |
| **react-portfolio-engineer** | User is building a React portfolio or gallery website, typically for creative professionals. |
| **nextjs-ecommerce-engineer** | User is building an e-commerce site with Next.js: product pages, cart, checkout flows. |
| **toolkit-governance-engineer** | User wants to maintain or modify the toolkit's own internal structure: editing skill/agent files, updating routing tables, managing ADRs, regenerating INDEX.json, or enforcing frontmatter compliance. NOT: creating brand-new agents (use skill-creator-engineer), writing application code (domain agents), or reviewing external PRs (reviewer agents). |

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
| **go-pr-quality-gate** | User wants to run Go-specific quality checks before submitting a PR: vet, staticcheck, test coverage. |
| **python-quality-gate** | User wants Python quality checks: ruff linting, mypy type checking, or combined Python quality validation. |
| **condition-based-waiting** | User needs retry logic, backoff strategies, polling loops, or health check patterns in their code. |
| **testing-anti-patterns** | User wants to identify or fix flaky tests, or review tests for common anti-patterns. |
| **subagent-driven-development** | User wants to execute a complex plan using subagents in fresh contexts, or needs a two-stage review/implementation cycle. |
| **workflow-orchestrator** | User wants to execute an existing plan with structured phases, or says "run the plan", "execute this". |
| **dispatching-parallel-agents** | User has 2+ independent failures, subtasks, or files that can be fixed simultaneously. |
| **parallel-code-review** | User wants comprehensive review of a codebase from multiple reviewer perspectives simultaneously. |
| **with-anti-rationalization** | User explicitly requests maximum rigor, thorough verification, or wants anti-rationalization patterns injected. |
| **plan-manager** | User wants to see the status of plans, audit existing plans, or manage the plan lifecycle. |
| **planning-with-files** | User needs persistent planning with file-backed state across a long multi-session task. |
| **go-testing (FORCE)** | User wants to write, run, or fix Go tests — _test.go files, table-driven tests, test helpers, testify assertions, or benchmarks. NOT: "test this idea" (exploration), "test my theory" (validation) — those are not Go test code. |
| **go-concurrency (FORCE)** | User is working with Go concurrency primitives: goroutines, channels, sync.Mutex, WaitGroups, context cancellation, or concurrent data structures. |
| **go-error-handling (FORCE)** | User is working with Go error handling: fmt.Errorf, errors.Is, errors.As, %w wrapping, sentinel errors, or error type design. |
| **go-code-review (FORCE)** | User wants a review of Go code, a Go PR, or Go-specific code quality assessment. |
| **go-anti-patterns** | User wants to identify anti-patterns, code smells, or over-engineering in Go code. |
| **go-sapcc-conventions (FORCE)** | User is working on SAP Converged Cloud Go repositories (go-bits, keppel, go-api-declarations, sap-cloud-infrastructure) where SAPCC-specific conventions apply. |
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

---

## Analysis & Discovery Skills

| Skill | When to Route Here |
|-------|-------------------|
| **codebase-overview** | User wants a high-level understanding of a repository's structure, architecture, or purpose. |
| **codebase-analyzer (code-cartographer)** | User wants statistical analysis of a codebase: pattern frequency, structural metrics, or data-driven insights about the code. |
| **code-cleanup** | User wants to remove stale TODOs, unused code, dead imports, or generally clean up accumulated debt. |
| **comment-quality** | User wants to audit code comments for accuracy, temporal references, or staleness. |
| **agent-evaluation** | User wants to grade or evaluate a skill, agent, or pipeline for quality and standards compliance. NOT: evaluating code output or test results. |
| **agent-comparison** | User wants to A/B test two agents or compare their outputs on the same task. |
| **agent-upgrade** | User wants to audit and systematically improve a specific agent to bring it up to current template standards. |
| **testing-agents-with-subagents** | User wants to validate an agent by running it against real test cases in subagents. |
| **skill-eval** | User wants to improve a skill through measured testing, optimize its description, or benchmark it against scenarios. |
| **full-repo-review** | User wants a comprehensive 3-wave review of all source files in the entire repository. |
| **repo-value-analysis** | User wants to systematically analyze an external repository to determine what ideas or patterns are worth adopting. |
| **data-analysis** | User wants to analyze data: CSV files, metrics, A/B test results, cohort analysis, statistical distributions, KPIs, or funnel data. |
| **pr-miner** | User wants to extract review comments or learnings from past GitHub PRs. |
| **pr-mining-coordinator** | User wants to coordinate batch mining across multiple PRs. |
| **skill-composer** | User wants to compose multiple skills into a multi-skill workflow. |
| **routing-table-updater** | User wants to update routing tables after adding or changing agents/skills. |
| **docs-sync-checker** | User wants to check if README files or documentation are in sync with the actual code. |
| **do-perspectives** | User wants multi-perspective analysis of a problem from 10 different lenses simultaneously. |
| **do-parallel** | User wants parallel multi-angle extraction of insights from a document or codebase. |
| **plans** | User wants to manage the plan lifecycle: create, track, or review plans. |
| **learn** | User wants to teach Claude a new error pattern or record a reusable insight. |
| **retro** | User wants to interact with the learning system: view stats, list accumulated knowledge, search learnings, or graduate mature entries into agents/skills. |
| **generate-claudemd** | User wants to generate a project-specific CLAUDE.md by analyzing the current repository's structure and conventions. |
| **professional-communication** | User needs to write a professional email or formal business communication. |
| **workflow-help** | User wants an explanation of how a workflow, pipeline, or process works. |

---

## PR & Git Skills

| Skill | When to Route Here |
|-------|-------------------|
| **pr-pipeline** | User wants the full structured PR workflow: stage, review, commit, push, create PR, verify. Use when the user wants the complete pipeline with all gates. |
| **pr-sync (FORCE)** | User wants to get local code changes onto GitHub — pushing a branch, creating a PR, or syncing local commits to the remote. NOT: "push back" (disagree with a decision), "push the boundaries" (explore limits), "push back on this" (resistance), "push my luck" (risk-taking). The intent must be about git/GitHub synchronization. |
| **git-commit-flow (FORCE)** | User wants to stage files and create a git commit from local changes. NOT: "commit to this approach" (deciding), "commit to the team" (dedication), "I'm committed to finishing" (resolve). The intent must be about creating a git commit object. |
| **github-actions-check (FORCE)** | User wants to know if CI passed or check GitHub Actions run status. NOT: "check this code" (review), "check my logic" (analysis), "double-check this" (verify), "check the docs" (read documentation). The intent must be about CI/CD pipeline status. |
| **pr-cleanup** | User wants to delete merged branches or clean up stale PRs after merging. |
| **pr-fix** | User wants to address specific PR review comments left by human reviewers. |
| **pr-review-address-feedback** | User wants to understand and respond to PR feedback, or asks what reviewers said. |
| **pr-status** | User wants to know the current status of a PR or branch without taking action. |
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
| **bluesky-reader** | User wants to read public Bluesky feeds, fetch posts, or interact with the AT Protocol API. |
| **image-to-video** | User wants to combine a static image with audio to create a video file (album art video, podcast video, music visualization). |
| **headless-cron-creator** | User wants to generate a headless Claude Code cron job that runs a task on a schedule. |
| **nano-banana-builder** | User wants to build a Next.js web application using Google Gemini Nano Banana image generation APIs. |

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
| **feature-design (FORCE)** | 1 - Design | User wants to think through a new feature, explore approaches, or design before committing to implementation. Entry point for all new features. |
| **feature-plan (FORCE)** | 2 - Plan | User wants to break down an approved feature design into atomic implementation tasks. Requires design phase to be complete. |
| **feature-implement (FORCE)** | 3 - Implement | User wants to execute the feature plan and build the code. Requires plan phase to be complete. |
| **feature-validate (FORCE)** | 4 - Validate | User wants to run quality gates, tests, and review on the implemented feature. |
| **feature-release (FORCE)** | 5 - Release | User wants to merge and ship a validated feature. Requires validate phase to be complete. |

**Auto-detection**: When `.feature/` exists, `feature-state.py status` determines current phase and routes to the matching skill automatically.

**Entry point**: New features always enter via `feature-design`. Skipping phases is not supported.

---

## Pipeline Skills

All pipelines live in the `pipelines/` directory (synced to `~/.claude/skills/` at install time).

| Pipeline | When to Route Here | Phases |
|----------|--------------------|--------|
| **pipeline-scaffolder** (pipeline-orchestrator-engineer) | User wants to create a new pipeline, scaffold a new structured workflow from a spec. | LOAD → SCAFFOLD → INTEGRATE → REPORT |
| **system-upgrade** (system-upgrade-engineer) | User wants to upgrade the Claude Code toolkit after a model update, apply system-wide changes, or roll out agent improvements. NOT: upgrading a specific library dependency in user code. | CHANGELOG → AUDIT → PLAN → IMPLEMENT → VALIDATE → DEPLOY |
| **skill-creation-pipeline** (skill-creator-engineer) | User wants to create a new skill with formal quality gates, phase structure, and integration. | DISCOVER → DESIGN → SCAFFOLD → VALIDATE → INTEGRATE |
| **hook-development-pipeline** (hook-development-engineer) | User wants to create a new hook with formal spec, performance testing, and registration. | SPEC → IMPLEMENT → TEST → REGISTER → DOCUMENT |
| **research-pipeline** (research-coordinator-engineer) | User wants formal research with saved artifacts, multiple sources, and a synthesized deliverable. NOT: a quick lookup or single-source check. | SCOPE → GATHER → SYNTHESIZE → VALIDATE → DELIVER |
| **agent-upgrade** (skill-creator-engineer) | User wants to audit and improve a specific agent to bring it up to current template standards. | AUDIT → DIFF → PLAN → IMPLEMENT → RE-EVALUATE |
| **research-to-article** | User wants to research a topic and turn the findings into a written article. | RESEARCH → COMPILE → GROUND → GENERATE → VALIDATE → REFINE → OUTPUT |
| **doc-pipeline** | User wants to generate documentation for a codebase, create a README, or write technical docs from scratch. | RESEARCH → OUTLINE → GENERATE → VERIFY → OUTPUT |
| **pr-pipeline** | User wants the full structured PR workflow with review gates. | CLASSIFY → STAGE → REVIEW → COMMIT → PUSH → CREATE → VERIFY → CLEANUP |
| **explore-pipeline** | User wants to understand a codebase: its structure, patterns, quality, and architecture. | SCAN → MAP → ANALYZE → [COMPILE → ASSESS → SYNTHESIZE → REFINE] → REPORT |
| **article-evaluation-pipeline** | User wants to evaluate whether an article sounds authentic or has AI patterns. | FETCH → VALIDATE → ANALYZE → REPORT |
| **mcp-pipeline-builder** (mcp-local-docs-engineer) | User wants to turn a repository into an MCP documentation server. | ANALYZE → DESIGN → GENERATE → VALIDATE → EVALUATE → REGISTER |
| **voice-writer** | User wants to write content in a specific voice with multi-step generation and validation. | LOAD → GROUND → GENERATE → VALIDATE → REFINE → JOY-CHECK → OUTPUT → CLEANUP |
| **comprehensive-review** | User wants a thorough review from multiple reviewer waves simultaneously. | WAVE-0 → WAVE-1 → WAVE-2 → AGGREGATE → FIX |
| **do-perspectives** | User wants multi-lens analysis of a problem from 10 different perspectives. | VALIDATE → ANALYZE → SYNTHESIZE → APPLY → VERIFY |
| **github-profile-rules** (github-profile-rules-engineer) | User wants to extract programming rules or coding conventions from a GitHub user's repositories. | ADR → FETCH → RESEARCH → SAMPLE → COMPILE → GENERATE → VALIDATE → OUTPUT |
| **voice-calibrator** | User wants to calibrate or refine a voice profile from samples. | VOICE-GROUNDING → VOICE-METRICS → THINKING-PATTERNS → VALIDATION |
| **workflow-orchestrator** | User wants to orchestrate a plan with structured phases — brainstorm, plan, execute. | BRAINSTORM → WRITE-PLAN → EXECUTE-PLAN |
| **de-ai-pipeline** | User wants to scan and fix AI patterns across documentation systematically. | SCAN → FIX → VERIFY (loop max 3) → REPORT |
| **auto-pipeline** | No agent or skill matched — auto-fallback that classifies and executes with phase gates. | DEDUP → CLASSIFY → SELECT → ADAPT → EXECUTE/CRYSTALLIZE |

### Pipeline Companion Map

Pipelines that work together in common workflows:

| Workflow | Pipeline Sequence | When |
|----------|-------------------|------|
| **Pipeline creation** | domain-research → chain-composer → pipeline-scaffolder → pipeline-test-runner → pipeline-retro | Creating new domain pipelines |
| **Content creation** | research-pipeline → voice-writer | Research-backed articles in a specific voice |
| **Feature lifecycle** | explore-pipeline → workflow-orchestrator → pr-pipeline | Understand → implement → ship |
| **Code review** | comprehensive-review → pr-pipeline | Review then submit |
| **Agent improvement** | agent-upgrade → skill-creation-pipeline | Audit agent, then scaffold missing skills |
| **System upgrade** | system-upgrade → agent-upgrade | Upgrade system, then individual agents |
| **Voice development** | voice-calibrator → voice-writer → article-evaluation-pipeline | Calibrate → write → evaluate |
| **Documentation** | explore-pipeline → doc-pipeline | Understand codebase → generate docs |
| **Perses** | perses-dac-pipeline → perses-plugin-pipeline | Dashboard-as-Code + plugin development |

### Pipeline Infrastructure

These pipelines create/manage other pipelines (meta-pipelines):

| Pipeline | Purpose |
|----------|---------|
| domain-research | Discover subdomains within a domain for pipeline generation |
| chain-composer | Compose type-safe pipeline chains from the step menu |
| pipeline-scaffolder | Scaffold skills/agents/hooks from Pipeline Spec JSON |
| pipeline-test-runner | Test generated pipeline skills against real targets |
| pipeline-retro | Trace test failures to generator root causes (Three-Layer Pattern) |

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
| **service-health-check** | User wants to check if a service is healthy or needs restarting. |
| **cron-job-auditor** | User wants to audit cron jobs or scheduled scripts for reliability and correctness. |

---

## Perses Skills

| Skill | When to Route Here |
|-------|-------------------|
| **perses-dashboard-create** (perses-dashboard-engineer) | User wants to create a new Perses dashboard from scratch. |
| **perses-deploy** (perses-dashboard-engineer) | User wants to deploy or install a Perses server instance. |
| **perses-onboard** (perses-dashboard-engineer) | User wants to connect to or set up a new Perses environment. |
| **perses-grafana-migrate (FORCE)** | User wants to migrate a Grafana dashboard to Perses format. NOT: any other migration or conversion task. |
| **perses-dac-pipeline (FORCE)** | User wants dashboard-as-code: managing Perses dashboards via CUE, GitOps, or code-driven workflows. |
| **perses-datasource-manage** (perses-dashboard-engineer) | User wants to add or configure a Prometheus or other datasource in Perses. |
| **perses-variable-manage** (perses-dashboard-engineer) | User wants to add or edit variables or filters in a Perses dashboard. |
| **perses-project-manage** (perses-dashboard-engineer) | User wants to create Perses projects, configure RBAC, or manage roles. |
| **perses-lint (FORCE)** | User wants to validate or lint a Perses dashboard definition for correctness. NOT: "check the dashboard" meaning visual review. |
| **perses-query-builder** (perses-dashboard-engineer) | User wants to build PromQL or LogQL queries for use in Perses panels. |
| **perses-dashboard-review** (perses-dashboard-engineer) | User wants a review of an existing Perses dashboard for quality or correctness. |
| **perses-plugin-create (FORCE)** | User wants to create a new Perses plugin: a panel plugin or datasource plugin. |
| **perses-plugin-pipeline** (perses-plugin-engineer) | User wants the full plugin development workflow with scaffolding, schema, testing. |
| **perses-cue-schema** (perses-plugin-engineer) | User wants to work on Perses CUE schema definitions or plugin data models. |
| **perses-plugin-test** (perses-plugin-engineer) | User wants to test a Perses plugin or validate its schema. |
| **perses-code-review** (perses-core-engineer) | User wants a code review of a Perses-related PR or Go code in Perses repositories. |

---

## Roaster Agents

Invoked via the roast skill or directly:

| Agent | When to Route Here |
|-------|-------------------|
| **reviewer-contrarian** | Reviewer that challenges fundamental assumptions, proposes alternatives, and questions premises. |
| **reviewer-newcomer** | Reviewer that critiques from a fresh-eyes perspective: onboarding friction, accessibility, missing context. |
| **reviewer-pragmatic-builder** | Reviewer focused on operational reality: production readiness, ops burden, deployment concerns. |
| **reviewer-skeptical-senior** | Reviewer focused on long-term sustainability, maintenance cost, and technical debt. |
| **reviewer-pedant** | Reviewer focused on technical precision, spec compliance, and terminology accuracy. |
| **reviewer-meta-process** | Reviewer that analyzes the system design itself: single points of failure, inappropriate authority concentration, complexity vs. value, reversibility. Use for "architecture health", "meta-process review", "is this too centralized", "complexity audit". NOT: code quality, security, or premise challenges. |
| **reviewer-user-advocate** | Reviewer that evaluates decisions from the end-user's perspective: complexity burden, confusing UX, benefit vs. cost. Use for user-facing design reviews, configuration complexity, or "is this worth it for users". |

---

## Quick Routing Examples

| Request | Routes To | Reasoning |
|---------|-----------|-----------|
| "fix the typo in main.go" | **fast (FORCE)** | Mechanical one-character fix, no design judgment |
| "rename this variable" | **fast (FORCE)** | Trivial rename, no logic change |
| "add a --verbose flag to the CLI" | **quick (FORCE)** | Small self-contained change |
| "small refactor: extract helper function" | **quick (FORCE)** | Contained, no design ambiguity |
| "debug Go tests" | golang-general-engineer + systematic-debugging | Debugging task in Go domain |
| "write Go tests for X" | **go-testing (FORCE)** | Creating _test.go files — force-route |
| "add worker pool" | **go-concurrency (FORCE)** | Goroutines and concurrency — force-route |
| "add auth to Python API" | python-general-engineer + workflow-orchestrator | Python domain, multi-step implementation |
| "review my K8s manifests" | kubernetes-helm-engineer + systematic-code-review | K8s domain, review task |
| "roast this design doc" | roast skill (5 personas) | Multi-persona critique |
| "execute plan with subagents" | subagent-driven-development | Explicit subagent execution |
| "fix these 3 failing test files" | dispatching-parallel-agents | 3 independent failures = parallel |
| "debug TypeScript race condition" | typescript-debugging-engineer + systematic-debugging | TS debugging domain |
| "write in custom voice" | voice-writer + [your-voice-skill] | Voice generation task |
| "comprehensive code review" | parallel-code-review (3 reviewers) | Multi-reviewer parallel review |
| "design a rate limiter feature" | **feature-design (FORCE)** | New feature entry point |
| "plan this feature" | **feature-plan (FORCE)** | Feature plan phase |
| "build this feature" | **feature-implement (FORCE)** | Feature implementation phase |
| "review this PR" | /pr-review command (retro-enabled) | PR review command |
| "submit a PR" | pr-pipeline | Full PR workflow with gates |
| "push my changes" | **pr-sync (FORCE)** | Intent: get local changes onto GitHub |
| "push back on this decision" | (not a routing target) | Intent: disagree — "push" is not a git push |
| "commit this" | **git-commit-flow (FORCE)** | Intent: create a git commit |
| "commit to this approach" | (not a routing target) | Intent: decide — "commit" is not a git commit |
| "did CI pass?" | **github-actions-check (FORCE)** | Intent: check CI status |
| "check my logic here" | (domain agent + review) | Intent: review — not CI |
| "research then write article" | research-to-article pipeline | Research-backed content creation |
| "create a pipeline for X" | pipeline-orchestrator-engineer + pipeline-scaffolder | Pipeline creation |
| "upgrade system for new Claude version" | system-upgrade-engineer + system-upgrade | System-wide upgrade |
| "create skill with quality gates" | skill-creator-engineer + skill-creation-pipeline | Formal skill creation |
| "create hook (formal, with perf test)" | hook-development-engineer + hook-development-pipeline | Formal hook creation |
| "research with saved artifacts" | research-coordinator-engineer + research-pipeline | Formal research pipeline |
| "upgrade this specific agent" | skill-creator-engineer + agent-upgrade | Single agent improvement |
| "create a 3D scene" | typescript-frontend-engineer + threejs-builder | Frontend domain, 3D task |
| "generate image with Python" | python-general-engineer + gemini-image-generator | Python domain, image generation |
| "extract coding rules from github user X" | github-profile-rules-engineer + github-profile-rules | Profile analysis |
| "analyze github profile conventions" | github-profile-rules-engineer + github-profile-rules | Convention extraction |
| "review sapcc Go repo" | golang-general-engineer + sapcc-review | SAPCC domain review |
| "audit sapcc conventions" | golang-general-engineer + sapcc-audit | SAPCC full audit |
| "work on sapcc Go code" | **go-sapcc-conventions (FORCE)** | SAPCC repo — auto-detected by hook |
| "moderate reddit" | reddit-moderate | Reddit moderation |
| "check my modqueue" | reddit-moderate | Reddit moderation |
