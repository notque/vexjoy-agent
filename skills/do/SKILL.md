---
name: do
description: |
  Classify user requests and route to the correct agent + skill combination.
  Use for any user request that needs delegation: code changes, debugging,
  reviews, content creation, research, or multi-step workflows. Invoked as
  the primary entry point via "/do [request]". Do NOT handle code changes
  directly - always route to a domain agent. Do NOT skip routing for
  anything beyond pure fact lookups or single read commands.
version: 2.0.0
user-invocable: true
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Skill
  - Task
---

# /do - Smart Router

## Operator Context

This skill operates as the primary routing operator for the Claude Code agent system, classifying requests and dispatching them to specialized agents and skills. It implements the **Router** architectural pattern -- parse request, select agent, pair skill, execute -- with **Domain Intelligence** embedded in trigger matching and force-routing rules.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before any routing decision
- **Over-Engineering Prevention**: Route to the simplest agent+skill that satisfies the request. Do not stack unnecessary skills
- **Route Code Changes**: NEVER edit code directly. Any code modification MUST be routed to a domain agent
- **Force-Route Compliance**: When force-route triggers match, invoke that skill BEFORE any other action
- **Anti-Rationalization Injection**: Auto-inject anti-rationalization patterns for code, review, security, and testing tasks
- **Plan Before Execute**: Create `task_plan.md` for Simple+ complexity before routing to agents
- **Parallel First**: Check for parallelizable patterns BEFORE standard sequential routing
- **Branch Safety**: Route to agents that create branches; never allow direct main/master commits
- **Mandatory Pre-Merge Review Loop**: For repos without organization-gated workflows, run up to 3 iterations of `/pr-review` → fix before creating a PR. Fully automated: review, fix, re-review until clean or max 3 iterations. This is how we catch missed README updates, stale references, and quality gaps.
- **Organization-Gated Workflow**: Repos under protected organizations (configured via `scripts/classify-repo.py`) require user confirmation before EACH git action: commit message approval, push approval, PR creation approval. NEVER auto-execute these steps. NEVER auto-merge. Their CI gates and human reviewers handle quality — we assist mindfully. Configure protected orgs by editing the classification script.
- **Routing Banner**: ALWAYS display the routing decision banner as the FIRST visible output after classifying the request. This is mandatory — never skip it, never defer it to later in execution. Show the banner BEFORE creating plans, BEFORE invoking agents, BEFORE any work begins.
- **Creation Protocol**: For any "create" or "new" request involving a significant component (pipeline, agent, skill, feature) at Simple+ complexity, automatically sequence: (1) ADR at `adr/[name].md`, (2) task plan at `task_plan.md`, (3) implementation via domain agent. The user should never need to say "do the ADR first, then plan, then implement" — this sequence IS the default. Show the full three-step sequence in the routing banner when a creation request is detected.

### Default Behaviors (ON unless disabled)
- **Retro Knowledge Injection**: Auto-inject L1/L2 accumulated knowledge from `retro/` for cross-feature learning (benchmark: +5.3 avg, 67% win rate). Relevance-gated by keyword matching.
- **Enhancement Stacking**: Add verification-before-completion, TDD, or parallel reviewers when signals detected
- **MCP Auto-Invocation**: Use Context7 for documentation lookups; use gopls MCP for Go workspace intelligence (symbols, diagnostics, references)
- **Dynamic Discovery**: Check `agents/INDEX.json` first, fall back to static routing tables
- **Local Agent Discovery**: Route to `.claude/agents/` local agents when `[cross-repo]` output is present
- **Gap Reporting**: When no agent/skill matches, report the gap and suggest creating one
- **Post-Task Learning**: After Simple+ tasks, extract reusable patterns and record via `retro-record-adhoc` to build the knowledge store from all work, not just feature lifecycles

### Optional Behaviors (OFF unless enabled)
- **Dry Run Mode**: Show routing decision without executing
- **Verbose Routing**: Explain why each alternative was rejected
- **Force Direct**: Override routing for explicitly trivial operations

## What This Skill CAN Do
- Route to any agent, skill, or command in the system
- Decompose multi-part requests into parallel or sequential sub-tasks
- Stack enhancement skills (TDD, verification, anti-rationalization) on top of primary routing
- Detect force-route triggers and invoke mandatory skills
- Launch up to 10 parallel agents in a single message

## What This Skill CANNOT Do
- Edit code directly (must route to a domain agent)
- Override CLAUDE.md requirements or skip verification steps
- Route to agents or skills that do not exist
- Handle Medium+ complexity tasks without creating a plan first
- Skip force-route triggers when they match

---

## Instructions

### Phase 1: CLASSIFY

**Goal**: Determine request complexity and whether routing is needed.

**Step 1: Assess complexity**

| Complexity | Agent | Skill | Direct Action |
|------------|-------|-------|---------------|
| Trivial | No | No | **Only if pure fact lookup, single read, or single shell command** |
| Simple | **Yes** (domain agent) | Yes | Never |
| Medium | **Required** | **Required** | Never |
| Complex | Required (often 2+) | Required (often 2+) | Never |

Trivial means ONLY: pure fact lookup, single shell command with no code changes, reading a specific file the user named. Everything else routes.

**Step 2: Check for parallel patterns FIRST**

| Pattern | Detection | Route To |
|---------|-----------|----------|
| 2+ independent test failures | Different files failing | dispatching-parallel-agents |
| 3+ independent subtasks | Numbered list, "and also" | dispatching-parallel-agents |
| Research breadth needed | "research", "investigate" + broad scope | research-coordinator-engineer |
| Multi-agent orchestration | "coordinate", complex project | project-coordinator-engineer |
| Implementation with plan | Plan exists + "execute" | subagent-driven-development |
| Feature lifecycle | "new feature", "build feature", .feature/ exists | feature-design (entry point) |

If a parallel pattern matches, route to the parallel mechanism FIRST.

**Feature Lifecycle Detection**: When user requests a new feature (not a bug fix or refactor), check for `.feature/` directory. If absent, route to `feature-design` as pipeline entry. If present, route to the skill matching the current phase (`feature-state.py status` determines this).

**Gate**: Complexity classified. If not Trivial, proceed to Phase 2. If Trivial, handle directly.

### Phase 2: ROUTE

**Goal**: Select the correct agent + skill combination.

**Step 1: Check force-route triggers**

These skills have MANDATORY routing. They MUST be invoked when triggers appear:

| Skill | Triggers |
|-------|----------|
| **go-testing** | Go test, *_test.go, table-driven, t.Run, t.Helper, benchmark, mock |
| **go-concurrency** | goroutine, channel, sync.Mutex, WaitGroup, worker pool, fan-out, rate limit |
| **go-error-handling** | error handling, fmt.Errorf, errors.Is, errors.As, %w, sentinel error |
| **go-code-review** | review Go, Go PR, Go code review, check Go quality |
| **go-anti-patterns** | anti-pattern, code smell, over-engineering, premature abstraction |
| **go-sapcc-conventions** | sapcc, sap-cloud-infrastructure, go-bits, keppel, go-api-declarations, go-makefile-maker |
| **create-voice** | create voice, new voice, build voice, voice from samples, calibrate voice |
| **voice-orchestrator** | write in voice, generate voice content, voice workflow |
| **feature-design** | design feature, feature design, think through feature, explore approaches |
| **feature-plan** | plan feature, feature plan, break down design, create tasks |
| **feature-implement** | implement feature, execute plan, start building, feature implement |
| **feature-validate** | validate feature, run quality gates, feature validate |
| **feature-release** | release feature, merge feature, ship it, feature release |
| **system-upgrade** | upgrade agents, system upgrade, claude update, upgrade skills, apply claude update, apply update, new claude version, apply retro to system |
| **de-ai-pipeline** | de-ai docs, clean ai patterns, fix ai writing, scan and fix docs, remove ai tells |
| **pr-sync** | push, push this, push changes, commit and push, push to GitHub, sync to GitHub, create a PR, create PR, open PR, open pull request, ship this, send this |
| **git-commit-flow** | commit, commit this, commit changes, stage and commit |
| **github-actions-check** | check CI, CI status, actions status, did CI pass, are tests passing |

If a force-route trigger matches, invoke that skill BEFORE any other action.

**Critical**: "push", "commit", "create PR", "merge" are NOT trivial git commands. They MUST route through skills that run quality gates (lint, tests, review) before executing. Running raw `git push` or `gh pr create` without routing through pr-sync or pr-pipeline bypasses all quality gates.

**Step 2: Select domain agent**

Primary lookup: `agents/INDEX.json`. Fallback: table below.

| Triggers | Agent | Default Skill |
|----------|-------|---------------|
| Go, Golang, .go, gofmt | golang-general-engineer | go-pr-quality-gate |
| Go (tight context) | golang-general-engineer-compact | go-pr-quality-gate |
| Go + sapcc (go-bits, keppel) | golang-general-engineer | go-sapcc-conventions |
| Python, .py, pip, pytest | python-general-engineer | python-quality-gate |
| Python + OpenStack | python-openstack-engineer | python-quality-gate |
| TypeScript, .ts | typescript-frontend-engineer | universal-quality-gate |
| React, Next.js | typescript-frontend-engineer | verification-before-completion |
| React portfolio | react-portfolio-engineer | distinctive-frontend-design |
| Next.js e-commerce | nextjs-ecommerce-engineer | verification-before-completion |
| Node.js, Express, API | nodejs-api-engineer | systematic-code-review |
| SQLite, Peewee | sqlite-peewee-engineer | verification-before-completion |
| Database, PostgreSQL | database-engineer | verification-before-completion |
| Kubernetes, Helm, K8s | kubernetes-helm-engineer | verification-before-completion |
| Ansible, playbook | ansible-automation-engineer | verification-before-completion |
| Prometheus, Grafana | prometheus-grafana-engineer | verification-before-completion |
| OpenSearch, Elasticsearch | opensearch-elasticsearch-engineer | verification-before-completion |
| RabbitMQ, messaging | rabbitmq-messaging-engineer | verification-before-completion |
| MCP, docs server | mcp-local-docs-engineer | verification-before-completion |
| UI, design, Tailwind | ui-design-engineer | distinctive-frontend-design |
| Performance, speed | performance-optimization-engineer | verification-before-completion |
| Testing, E2E, Playwright | testing-automation-engineer | test-driven-development |
| Documentation, README | technical-documentation-engineer | comment-quality |
| Articles, journalism | technical-journalist-writer | professional-communication |
| TypeScript debug, async bug, race condition | typescript-debugging-engineer | systematic-debugging |
| Nano Banana, Gemini image web app | typescript-frontend-engineer | nano-banana-builder |
| Python image generation, AI sprite | python-general-engineer | gemini-image-generator |
| Three.js, 3D web, WebGL | typescript-frontend-engineer | threejs-builder |
| image to video, audio visualization | (skill only) | image-to-video |

**Step 3: Select task-type agent** (if no domain agent matches)

| Triggers | Agent | Skill |
|----------|-------|-------|
| create pipeline, new pipeline, scaffold pipeline, build pipeline | pipeline-orchestrator-engineer | pipeline-scaffolder |
| upgrade agents, system upgrade, claude update, upgrade skills | system-upgrade-engineer | system-upgrade |
| github rules, profile analysis, coding style extraction | github-profile-rules-engineer | github-profile-rules |
| create agent, new agent | agent-creator-engineer | agent-evaluation |
| create skill, new skill | skill-creator-engineer | agent-evaluation |
| create hook, event handler | hook-development-engineer | verification-before-completion |
| research, investigate | research-coordinator-engineer | workflow-orchestrator |
| coordinate, multi-agent | project-coordinator-engineer | workflow-orchestrator |
| roast, critique | (roast skill runs 5 personas) | roast |
| research subtask, delegated research | research-subagent-executor | (internal) |
| security review, OWASP, XSS | reviewer-security | systematic-code-review |
| business logic, domain review | reviewer-business-logic | systematic-code-review |

**Step 4: Apply skill override** (task verb overrides default skill)

| Task Verb | Use This Skill Instead |
|-----------|----------------------|
| review, check | systematic-code-review |
| debug, fix bug | systematic-debugging |
| implement, build | workflow-orchestrator |
| refactor, rename | systematic-refactoring |
| TDD, test first | test-driven-development |

For complete category-specific skill routing, see `references/routing-tables.md`.

**Step 6: Display routing decision** (MANDATORY — do this NOW, before anything else)

For standard skills:
```
===================================================================
 ROUTING: [brief summary]
===================================================================

 Selected:
   -> Agent: [name] - [why]
   -> Skill: [name] - [why]
   -> Anti-Rationalization: [auto-injected for code/security/testing]

 Invoking...
===================================================================
```

For pipeline skills — add the Pipeline: line with all phases in order:
```
===================================================================
 ROUTING: [brief summary]
===================================================================

 Selected:
   -> Agent: [name]
   -> Skill: [name] ([N]-phase pipeline)
   Pipeline: PHASE1 → PHASE2 → PHASE3 → ... → PHASEN

 Invoking...
===================================================================
```

**Pipeline Phase Registry** — use these when the matched skill is a pipeline:

| Skill | Phases |
|-------|--------|
| `system-upgrade` | CHANGELOG → AUDIT → PLAN → IMPLEMENT → VALIDATE → DEPLOY |
| `skill-creation-pipeline` | DISCOVER → DESIGN → SCAFFOLD → VALIDATE → INTEGRATE |
| `hook-development-pipeline` | SPEC → IMPLEMENT → TEST → REGISTER → DOCUMENT |
| `research-pipeline` | SCOPE → GATHER → SYNTHESIZE → VALIDATE → DELIVER |
| `agent-upgrade` | AUDIT → DIFF → PLAN → IMPLEMENT → RE-EVALUATE |
| `explore-pipeline` | SCAN → MAP → ANALYZE → REPORT |
| `research-to-article` | RESEARCH → COMPILE → GROUND → GENERATE → VALIDATE → REFINE → OUTPUT |
| `pr-pipeline` | CLASSIFY → STAGE → REVIEW → COMMIT → PUSH → CREATE → VERIFY → CLEANUP |
| `voice-orchestrator` | LOAD → GROUND → GENERATE → VALIDATE → REFINE → OUTPUT → CLEANUP |
| `github-profile-rules` | PROFILE-SCAN → CODE-ANALYSIS → REVIEW-MINING → PATTERN-SYNTHESIS → RULES-GENERATION → VALIDATION → OUTPUT |
| `doc-pipeline` | RESEARCH → OUTLINE → GENERATE → VERIFY → OUTPUT |
| `workflow-orchestrator` | BRAINSTORM → WRITE-PLAN → EXECUTE-PLAN |
| `de-ai-pipeline` | SCAN → FIX → VERIFY (loop max 3) → REPORT |

If a skill is not in this registry but has explicit phases in its SKILL.md, show those phases. If it's not a pipeline, omit the Pipeline: line entirely.

This banner MUST be the FIRST visible output. Display it immediately after selecting agent + skill, BEFORE creating plans, BEFORE enhancement stacking, BEFORE invoking agents.

**Gate**: Agent and skill selected. Banner displayed. Proceed to Phase 3.

### Phase 3: ENHANCE

**Goal**: Stack additional skills based on signals in the request.

| Signal in Request | Enhancement to Add |
|-------------------|-------------------|
| Any substantive work (code, design, plan) | **Auto-inject retro knowledge** (L1/L2 from prior features via `retro-knowledge-injector` hook) |
| "comprehensive" / "thorough" / "full" | Add parallel reviewers (security + business + quality) |
| "with tests" / "production ready" | Append test-driven-development + verification-before-completion |
| "research needed" / "investigate first" | Prepend research-coordinator-engineer |
| Multiple independent problems (2+) | Use dispatching-parallel-agents |
| "review" with 5+ files | Use parallel-code-review (3 reviewers) |
| Complex implementation | Offer subagent-driven-development |

**Auto-inject retro knowledge** (DEFAULT ON — benchmark validated: +5.3 avg, 67% win rate):

The `retro-knowledge-injector` hook automatically loads accumulated L1/L2 knowledge from `retro/` when:
1. The prompt indicates substantive work (not trivial lookups)
2. L2 tags match the current task keywords (relevance gate)
3. The knowledge store has content from completed features

This is the system's cross-feature learning mechanism. Agents receiving retro knowledge should:
- **Adapt, don't copy** — note where patterns apply AND where they don't
- **Document transfer** — explicitly state which prior learnings were reused
- **Skip when irrelevant** — if the L1/L2 content doesn't apply, ignore it entirely

**Auto-inject anti-rationalization** for these task types:

| Task Type | Patterns Injected |
|-----------|-------------------|
| Code modification | anti-rationalization-core, verification-checklist |
| Code review | anti-rationalization-core, anti-rationalization-review |
| Security work | anti-rationalization-core, anti-rationalization-security |
| Testing | anti-rationalization-core, anti-rationalization-testing |
| Debugging | anti-rationalization-core, verification-checklist |

For explicit maximum rigor, use `/with-anti-rationalization [task]`.

**Gate**: Enhancements applied. Proceed to Phase 4.

### Phase 4: EXECUTE

**Goal**: Invoke the selected agent + skill and deliver results.

**Step 0: Execute Creation Protocol** (for creation requests ONLY)

Detect creation requests by checking if the request contains: "create", "new", "scaffold", "build pipeline", "build agent", "build skill", "build hook". If detected AND complexity is Simple+:

```
1. Write ADR: adr/{kebab-case-name}.md
   - Include: Context, Decision, Component list, Consequences
2. Register session: python3 scripts/adr-query.py register --adr adr/{name}.md
3. Display in banner: "ADR: adr/{name}.md (registered)"
4. Proceed to Step 1 (plan creation)
```

If NOT a creation request, skip to Step 1. The ADR session persists across sub-agent dispatches. The `adr-context-injector` hook injects relevant ADR sections into every sub-agent prompt. The `adr-enforcement` hook checks compliance after every Write/Edit.

**Step 1: Create plan** (for Simple+ complexity)

Create `task_plan.md` before execution. The `auto-plan-detector.py` hook auto-detects and injects `<auto-plan-required>` context. See `skills/planning-with-files/SKILL.md` for template. Skip only for Trivial tasks.

**Step 2: Retro knowledge injection**

The `retro-knowledge-injector` hook automatically queries learning.db and injects relevant knowledge into agent context via `<retro-knowledge>` blocks. No manual injection step is needed — the hook handles this on every `UserPromptSubmit`.

**Step 2.5: Inject MCP tool discovery into agent dispatch prompt**

MCP server instructions are injected into the main session but NOT propagated to subagents. Subagents have MCP tools available as deferred tools but don't know to use `ToolSearch` to activate them. When dispatching agents, include this block in the agent prompt:

```
MCP TOOL DISCOVERY (do this FIRST, before reading code):
- Use ToolSearch("gopls") to check for Go analysis tools (go_file_context,
  go_diagnostics, go_symbol_references, go_package_api). If found AND
  working in a Go repo: use go_file_context after reading .go files,
  go_diagnostics after edits, go_symbol_references before renaming.
- Use ToolSearch("context7") to check for library documentation tools
  (resolve-library-id, query-docs). If found: use for verifying library
  API usage and looking up unfamiliar dependencies.
- If ToolSearch returns no results for either, proceed without them.
```

**When to include**: Include gopls block when dispatching Go-related agents (`golang-general-engineer`, `golang-general-engineer-compact`, or any agent working on `.go` files). Include Context7 block for any agent that may encounter library/dependency questions. Skip entirely for trivial tasks or non-code agents.

**Step 3: Invoke agent with skill**

Let the agent do the work. Do not intervene in agent execution.

**Step 4: Handle multi-part requests**

Detect: "first...then", "and also", numbered lists, semicolons.
- Sequential dependencies: Execute in order
- Independent items: Launch multiple Task tools in single message
- Max parallelism: 10 agents

**Step 5: Handle uncertainty**

When no agent/skill matches:
```
===================================================================
 GAP DETECTED: No match for [domain]
===================================================================
 Closest: [Agent X] + [Skill Y]
 Or create: /do create an agent for [domain]
===================================================================
```

When uncertain which route: **ROUTE ANYWAY.** Route to the most likely agent + skill, add verification-before-completion as safety net, let the agent ask clarifying questions.

**Gate**: Agent invoked, results delivered. Proceed to Phase 5.

### Phase 5: LEARN

**Goal**: Ensure session insights are captured to `learning.db`.

**Auto-capture** (hooks, zero LLM cost):
- `error-learner.py` (PostToolUse) → captures tool errors + solutions
- `review-capture.py` (PostToolUse) → captures review agent findings
- `session-learning-recorder.py` (Stop) → warns on substantive sessions with no learnings

**Manual recording** (for design decisions, gotchas, and insights hooks can't detect):

```bash
python3 scripts/learning-db.py record TOPIC KEY "VALUE" --category CATEGORY
```

Categories: `error | pivot | review | design | debug | gotcha | effectiveness`

Record specific, actionable insights — not generic advice. "Force-route triggers must not contain sibling skill names" is good. "Be careful with routing" is not.

**Gate**: Hooks handle capture automatically. Manual recording is for high-value insights only.

---

## MCP Auto-Invocation

| MCP | Triggers | Rule |
|-----|----------|------|
| **Context7** | Library/API docs, unfamiliar library, setup steps, "how do I use X", **Claude Code hooks/settings/slash commands/API** | **AUTO-USE for documentation lookups** |
| **gopls** | Go workspace, .go files, go.mod, Go symbols, Go diagnostics | **AUTO-USE for Go development** — use `go_workspace` at session start, `go_file_context` after reading .go files, `go_diagnostics` after edits, `go_symbol_references` before renaming. Scoped to Go agents/skills only. |

Do not wait for explicit requests. If the task involves documentation or API reference, use Context7 proactively. This explicitly includes **Claude Code itself** — hooks schema, settings.json format, slash commands, CLAUDE.md syntax, MCP server setup, and SDK usage. If the task involves Go development in a Go workspace, use gopls MCP tools proactively.

**IMPORTANT — Subagent propagation**: MCP server instructions are only injected into the main session's system prompt — subagents spawned via the Agent tool do NOT receive them. MCP tools appear as deferred tools in subagent contexts but agents won't use them unless told to call `ToolSearch`. Always include MCP tool discovery instructions in agent dispatch prompts (see Phase 4, Step 2.5).

---

## Error Handling

### Error: "No Agent Matches Request"
Cause: Request domain not covered by any agent
Solution:
1. Check `agents/INDEX.json` and `references/routing-tables.md` for near-matches
2. Route to closest agent with verification-before-completion as safety net
3. Report the gap and suggest `/do create an agent for [domain]`

### Error: "Force-Route Conflict"
Cause: Multiple force-route triggers match the same request
Solution:
1. Force-routes are ordered by specificity (go-testing > golang-general-engineer)
2. Apply most specific force-route first
3. Stack secondary routes as enhancements if compatible

### Error: "Plan Required But Not Created"
Cause: Simple+ task attempted without task_plan.md
Solution:
1. Stop execution immediately
2. Create `task_plan.md` with goal, phases, and key questions
3. Resume routing after plan is in place

---

## Anti-Patterns

### Anti-Pattern 1: Handling Code Directly
**What it looks like**: Editing source files without routing to a domain agent
**Why wrong**: Bypasses domain expertise, testing methodology, and quality gates
**Do instead**: Route to the domain agent. Always. Even for "simple" changes.

### Anti-Pattern 2: Under-Routing
**What it looks like**: Treating code changes as "trivial" to avoid routing overhead
**Why wrong**: Under-routing wastes implementations. Over-routing only wastes tokens. Tokens are cheap; bad code is expensive.
**Do instead**: Default to routing. Only handle directly if genuinely trivial (pure fact lookup, single read).

### Anti-Pattern 3: Skipping Force-Routes
**What it looks like**: Writing Go tests without invoking go-testing, or Go concurrency without go-concurrency
**Why wrong**: Force-routes encode critical domain patterns that prevent common mistakes
**Do instead**: Check force-route table BEFORE selecting a general agent. Force-routes override defaults.

### Anti-Pattern 4: Sequential When Parallel Is Possible
**What it looks like**: Fixing 3 independent test failures one at a time
**Why wrong**: Independent work items can run concurrently, saving significant time
**Do instead**: Detect independent items and use dispatching-parallel-agents.

### Anti-Pattern 5: Raw Git Commands Instead of Skills
**What it looks like**: Running `git push`, `git commit`, `gh pr create`, or `gh pr merge` directly without routing through pr-sync, git-commit-flow, or pr-pipeline
**Why wrong**: Bypasses lint checks, test runs, review loops, CI verification, and repo classification. This is how broken code gets merged. A CI failure after merge costs more than a pre-push check.
**Do instead**: Route ALL git submission actions through their skills. "push" routes to pr-sync. "commit" routes to git-commit-flow. "create PR" routes to pr-pipeline. No exceptions, even when the user asks to "just push it."

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition gates

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "This is trivial, I'll handle it directly" | Trivial assessment is often wrong for code | Route to agent unless pure fact lookup |
| "No agent matches, I'll just do it myself" | Missing agent is a gap to report, not a bypass | Report gap, route to closest match |
| "Force-route doesn't apply here" | If triggers match, force-route applies. No exceptions | Check trigger table literally |
| "Routing overhead isn't worth it for this" | Routing overhead < cost of unreviewed code changes | Route anyway; tokens are cheap |
| "User wants it fast, skip the plan" | Fast without a plan produces wrong results faster | Create plan, then execute |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/routing-tables.md`: Complete category-specific skill routing (Process, Analysis, PR, Content, Voice, Pipeline, Validation, Roaster Agents, Quick Examples)
