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
argument-hint: "<request>"
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Skill
  - Task
routing:
  triggers:
    - "route task"
    - "classify request"
  category: meta-tooling
---

# /do - Smart Router

## Operator Context

This skill operates as the primary routing operator, classifying requests and dispatching them to specialized agents and skills. It implements the **Router** pattern: parse request, select agent, pair skill, execute.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before any routing decision
- **Over-Engineering Prevention**: Route to the simplest agent+skill that satisfies the request. Do not stack unnecessary skills
- **Route Code Changes**: NEVER edit code directly. Any code modification MUST be routed to a domain agent
- **Force-Route Compliance**: When force-route triggers match, invoke that skill BEFORE any other action
- **Anti-Rationalization Injection**: Auto-inject anti-rationalization patterns for code, review, security, and testing tasks
- **Plan Before Execute**: Create `task_plan.md` for Simple+ complexity before routing to agents
- **Parallel First**: Check for parallelizable patterns BEFORE standard sequential routing
- **Branch Safety**: Route to agents that create branches; never allow direct main/master commits
- **Mandatory Pre-Merge Review Loop**: For repos without organization-gated workflows, run up to 3 iterations of `/pr-review` → fix before creating a PR
- **Organization-Gated Workflow**: Repos under protected organizations (via `scripts/classify-repo.py`) require user confirmation before EACH git action. NEVER auto-execute or auto-merge
- **Routing Banner**: ALWAYS display the routing decision banner as the FIRST visible output after classifying. Show BEFORE creating plans, BEFORE invoking agents, BEFORE any work begins
- **Creation Protocol**: For "create"/"new" requests at Simple+ complexity, automatically sequence: (1) ADR, (2) task plan, (3) implementation via domain agent

### Default Behaviors (ON unless disabled)
- **Retro Knowledge Injection**: Auto-inject from learning.db (benchmark: +5.3 avg, 67% win rate). Relevance-gated by FTS5 keyword matching
- **Enhancement Stacking**: Add verification-before-completion, TDD, or parallel reviewers when signals detected
- **Negative Enhancement Rules**: Check skill's `pairs_with` before stacking. Empty `pairs_with: []` = no stacking. Do NOT stack verification on skills with built-in verification gates. Do NOT stack TDD on `fast`
- **Local Agent Discovery**: Route to `.claude/agents/` local agents when `[cross-repo]` output is present
- **Auto-Pipeline Fallback**: When no agent/skill matches, invoke auto-pipeline to classify and execute with phase gates
- **Post-Task Learning**: After Simple+ tasks, extract reusable patterns and record via `retro-record-adhoc`

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

### Role: /do is a ROUTER, not a worker

/do's ONLY job is to ROUTE requests to agents. It does NOT execute, implement, debug, review, or fix anything itself.

**What the main thread does:** (1) Classify, (2) Select agent+skill, (3) Dispatch via Agent tool, (4) Evaluate if more work needed, (5) Route to ANOTHER agent if yes, (6) Report results.

**What the main thread NEVER does:** Read code files (dispatch Explore agent), edit files (dispatch domain agent), run tests (dispatch agent with skill), write docs (dispatch technical-documentation-engineer), handle ANY Simple+ task directly.

The main thread is an **orchestrator**. If you find yourself reading source code, writing code, or doing analysis instead of dispatching an agent — STOP. Route it.

### Phase Banners (MANDATORY)

Every phase MUST display a banner BEFORE executing: `/do > Phase N: PHASE_NAME — description...`

After Phase 2, display the full routing decision banner (`===` block). Phase banners tell the user *where they are*; the routing banner tells them *what was decided*. Both required.

---

### Phase 1: CLASSIFY

**Goal**: Determine request complexity and whether routing is needed.

| Complexity | Agent | Skill | Direct Action |
|------------|-------|-------|---------------|
| Trivial | No | No | **ONLY reading a file the user named by exact path** |
| Simple | **Yes** | Yes | Never |
| Medium | **Required** | **Required** | Never |
| Complex | Required (2+) | Required (2+) | Never |

**Trivial = reading a file the user named by exact path.** Everything else is Simple+ and MUST use an agent, skill, or pipeline. When uncertain, classify UP not down — tokens are cheap, bad code is expensive.

**Common misclassifications** (these are NOT Trivial — route them): evaluating repos/URLs, any opinion/recommendation, git operations, codebase questions (`explore-pipeline`), retro lookups (`retro` skill), comparing approaches.

**Maximize skill/agent/pipeline usage.** If a skill or pipeline exists for the task, USE IT — even if handling directly seems faster. Display the routing banner for ALL classifications including Trivial.

**Check for parallel patterns FIRST**: 2+ independent failures or 3+ subtasks → `dispatching-parallel-agents`; broad research → `research-coordinator-engineer`; multi-agent coordination → `project-coordinator-engineer`; plan exists + "execute" → `subagent-driven-development`; new feature → `feature-design` (check `.feature/` directory; if present, use `feature-state.py status` for current phase).

**Gate**: Complexity classified. Display routing banner (ALL classifications). If not Trivial, proceed to Phase 2. If Trivial, handle directly after showing banner.

### Phase 2: ROUTE

**Goal**: Select the correct agent + skill combination from the INDEX files and routing tables.

**Step 1: Check force-route triggers**

Force-route triggers are in `skills/INDEX.json` (field: `force_route: true`). If a force-route trigger matches the request, invoke that skill BEFORE any other action.

**Critical**: "push", "commit", "create PR", "merge" are NOT trivial git commands. They MUST route through skills that run quality gates. Running raw `git push` or `gh pr create` bypasses all quality gates.

**Step 2: Select agent + skill**

Read the routing tables in `references/routing-tables.md` and the INDEX files (`agents/INDEX.json`, `skills/INDEX.json`, `pipelines/INDEX.json`) to identify candidates by trigger-overlap. Select the best match; use LLM judgment to tiebreak when multiple candidates fit equally well.

**Step 3: Apply skill override** (task verb overrides default skill)

When the request verb implies a specific methodology, override the agent's default skill. Common overrides: "review" → systematic-code-review, "debug" → systematic-debugging, "refactor" → systematic-refactoring, "TDD" → test-driven-development. Full override table in `references/routing-tables.md`.

**Step 4: Display routing decision** (MANDATORY — do this NOW, before anything else)

```
===================================================================
 ROUTING: [brief summary]
===================================================================
 Selected:
   -> Agent: [name] - [why]
   -> Skill: [name] - [why]
   -> Pipeline: PHASE1 → PHASE2 → ... (if pipeline; phases from pipelines/INDEX.json)
   -> Anti-Rationalization: [auto-injected for code/security/testing]
 Invoking...
===================================================================
```

For Trivial: show `Classification: Trivial - [reason]` and `Handling directly (no agent/skill needed)`.

This banner MUST be the FIRST visible output for EVERY /do invocation. Display BEFORE any work begins. No exceptions.

**Step 5: Record routing decision** (Simple+ only — skip Trivial):

```bash
python3 ~/.claude/scripts/learning-db.py record \
    routing "{selected_agent}:{selected_skill}" \
    "request: {first_200_chars} | complexity: {complexity} | force_used: {0|1} | llm_override: {0|1} | enhancements: {comma_separated_list}" \
    --category routing-decision \
    --tags "{applicable_flags}"
```

Tags: `force-route`, `llm-override`, `auto-pipeline` (as applicable). This call is advisory — if it fails, continue.

**Gate**: Agent and skill selected. Banner displayed. Routing decision recorded. Proceed to Phase 3.

### Phase 3: ENHANCE

**Goal**: Stack additional skills based on signals in the request.

| Signal in Request | Enhancement to Add |
|-------------------|-------------------|
| Any substantive work (code, design, plan) | **Auto-inject retro knowledge** (via `retro-knowledge-injector` hook) |
| "comprehensive" / "thorough" / "full" | Add parallel reviewers (security + business + quality) |
| "with tests" / "production ready" | Append test-driven-development + verification-before-completion |
| "research needed" / "investigate first" | Prepend research-coordinator-engineer |
| Multiple independent problems (2+) | Use dispatching-parallel-agents |
| "review" with 5+ files | Use parallel-code-review (3 reviewers) |
| Complex implementation | Offer subagent-driven-development |

**Auto-inject anti-rationalization** for these task types:

| Task Type | Patterns Injected |
|-----------|-------------------|
| Code modification | anti-rationalization-core, verification-checklist |
| Code review | anti-rationalization-core, anti-rationalization-review |
| Security work | anti-rationalization-core, anti-rationalization-security |
| Testing | anti-rationalization-core, anti-rationalization-testing |
| Debugging | anti-rationalization-core, verification-checklist |
| External content evaluation | **untrusted-content-handling** |

For explicit maximum rigor, use `/with-anti-rationalization [task]`.

**Gate**: Enhancements applied. Proceed to Phase 4.

### Phase 4: EXECUTE

**Goal**: Invoke the selected agent + skill and deliver results.

**Step 0: Execute Creation Protocol** (for creation requests ONLY)

If request contains "create", "new", "scaffold", "build pipeline/agent/skill/hook" AND complexity is Simple+: (1) Write ADR at `adr/{kebab-case-name}.md`, (2) Register via `adr-query.py register`, (3) Proceed to plan creation. The `adr-context-injector` and `adr-enforcement` hooks handle cross-agent ADR compliance automatically.

**Step 1: Create plan** (for Simple+ complexity)

Create `task_plan.md` before execution. The `auto-plan-detector.py` hook auto-injects `<auto-plan-required>` context. Skip only for Trivial tasks.

**Step 2: Invoke agent with skill**

Dispatch the agent. MCP tool discovery is the agent's responsibility — each agent's markdown declares which MCP tools it needs. Do not inject MCP instructions from /do.

**Step 3: Handle multi-part requests**

Detect: "first...then", "and also", numbered lists, semicolons. Sequential dependencies execute in order. Independent items launch multiple Task tools in single message. Max parallelism: 10 agents.

**Step 4: Auto-Pipeline Fallback** (when no agent/skill matches AND complexity >= Simple)

Invoke `auto-pipeline` (MANDATORY — "handle directly" is not an option). If no pipeline matches either, fall back to closest agent + verification-before-completion.

When uncertain which route: **ROUTE ANYWAY.** Add verification-before-completion as safety net.

**Gate**: Agent invoked, results delivered. Proceed to Phase 5.

### Phase 5: LEARN

**Goal**: Ensure session insights are captured to `learning.db`.

**Routing outcome recording** (Simple+ tasks, observable facts only — no self-grading):
```bash
python3 ~/.claude/scripts/learning-db.py record \
    routing "{selected_agent}:{selected_skill}" \
    "{existing_value} | tool_errors: {0|1} | user_rerouted: {0|1}" \
    --category routing-decision
```

Do NOT record subjective outcomes like "success" or "misroute" — that is self-grading.

**Auto-capture** (hooks, zero LLM cost): `error-learner.py` (PostToolUse), `review-capture.py` (PostToolUse), `session-learning-recorder.py` (Stop).

**Skill-scoped recording** (preferred — one-liner):
```bash
python3 ~/.claude/scripts/learning-db.py learn --skill go-testing "insight about testing"
python3 ~/.claude/scripts/learning-db.py learn --agent golang-general-engineer "insight about agent"
python3 ~/.claude/scripts/learning-db.py learn "general insight without scope"
```

**Immediate graduation for review findings** (MANDATORY): When a review finds an issue and it gets fixed in the same PR: (1) Record scoped to responsible agent/skill, (2) Boost to 1.0, (3) Embed into agent anti-patterns, (4) Graduate, (5) Stage changes in same PR. One cycle — no waiting for "multiple observations."

**Gate**: After Simple+ tasks, record at least one learning via `learn`. Review findings get immediate graduation.

---

## Error Handling

### Error: "No Agent Matches Request"
Cause: Request domain not covered by any agent
Solution: Check INDEX files and `references/routing-tables.md` for near-matches. Route to closest agent with verification-before-completion. Report the gap.

### Error: "Force-Route Conflict"
Cause: Multiple force-route triggers match the same request
Solution: Apply most specific force-route first. Stack secondary routes as enhancements if compatible.

### Error: "Plan Required But Not Created"
Cause: Simple+ task attempted without task_plan.md
Solution: Stop execution. Create `task_plan.md`. Resume routing after plan is in place.

---

## Anti-Patterns

### Anti-Pattern 1: Handling Code Directly
**What it looks like**: Editing source files without routing to a domain agent
**Why wrong**: Bypasses domain expertise, testing methodology, and quality gates
**Do instead**: Route to the domain agent. Always. Even for "simple" changes.

### Anti-Pattern 2: Under-Routing
**What it looks like**: Treating code changes as "trivial" to avoid routing overhead
**Why wrong**: Under-routing wastes implementations. Over-routing only wastes tokens. Tokens are cheap; bad code is expensive.
**Do instead**: Default to routing. Trivial = reading a file the user named by path. Nothing else qualifies.

### Anti-Pattern 3: Skipping Force-Routes
**What it looks like**: Writing Go tests without invoking go-testing, or Go concurrency without go-concurrency
**Why wrong**: Force-routes encode critical domain patterns that prevent common mistakes
**Do instead**: Check force-route triggers BEFORE selecting a general agent. Force-routes override defaults.

### Anti-Pattern 4: Sequential When Parallel Is Possible
**What it looks like**: Fixing 3 independent test failures one at a time
**Why wrong**: Independent work items can run concurrently, saving significant time
**Do instead**: Detect independent items and use dispatching-parallel-agents.

### Anti-Pattern 5: Raw Git Commands Instead of Skills
**What it looks like**: Running `git push`, `git commit`, `gh pr create`, or `gh pr merge` directly
**Why wrong**: Bypasses lint checks, test runs, review loops, CI verification, and repo classification
**Do instead**: Route ALL git submission actions through their skills. No exceptions.

### Anti-Pattern 6: Force-Route Triggers Containing Sibling Skill Names
**What it looks like**: A force-route trigger list includes the name of another skill
**Why wrong**: The router matches the sibling name as a trigger for the wrong skill
**Do instead**: Triggers must contain only user-language keywords, never sibling skill names.

### Anti-Pattern 7: Duplicate Trigger Phrases Across Skills
**What it looks like**: Two skills claim the same trigger phrase
**Why wrong**: The router cannot deterministically pick between them
**Do instead**: Each trigger phrase must map to exactly one skill. Check for collisions before adding.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition gates

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "This is trivial, I'll handle it directly" | Trivial = reading a named file, nothing else | Route to agent; show banner regardless |
| "No agent matches, I'll just do it myself" | Missing agent is a gap to report, not a bypass | Report gap, route to closest match |
| "Force-route doesn't apply here" | If triggers match, force-route applies. No exceptions | Check triggers literally |
| "Routing overhead isn't worth it for this" | Routing overhead < cost of unreviewed code changes | Route anyway; tokens are cheap |
| "User wants it fast, skip the plan" | Fast without a plan produces wrong results faster | Create plan, then execute |
| "User seems impatient, skip the review" | **There is never time pressure.** A denied tool call is NOT permission to skip quality gates | Run the full review loop |
| "Just push it, we can fix later" | Post-merge fixes cost 2 PRs instead of 1 | Route through pr-sync/pr-pipeline |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/routing-tables.md`: Complete category-specific skill routing
- `agents/INDEX.json`: Agent triggers and metadata
- `skills/INDEX.json`: Skill triggers, force-route flags, pairs_with
- `pipelines/INDEX.json`: Pipeline phases, triggers, composition chains
