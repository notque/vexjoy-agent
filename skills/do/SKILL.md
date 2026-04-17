---
name: do
description: "Classify user requests and route to the correct agent + skill. Primary entry point for all delegated work."
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
    - "which agent"
    - "delegate to skill"
    - "smart router"
  category: meta-tooling
---

# /do - Smart Router

/do is a **ROUTER**, not a worker. Its ONLY job is to classify requests, select the right agent + skill, and dispatch. It delegates all execution, implementation, debugging, review, and fixes to specialized agents.

**What the main thread does:** (1) Classify, (2) Select agent+skill, (3) Dispatch via Agent tool, (4) Evaluate if more work needed, (5) Route to ANOTHER agent if yes, (6) Report results.

**The main thread delegates to agents:** code reading (Explore agent), file edits (domain agents), test runs (agent with skill), documentation (technical-documentation-engineer), all Simple+ tasks.

The main thread is an **orchestrator**. If you find yourself reading source code, writing code, or doing analysis — pause and route to an agent instead.

---

## The Completeness Standard

The marginal cost of completeness is near zero. Do the whole thing. Do it right. Do it with tests. Do it with documentation. Do it so well that the user is genuinely impressed.

This is not aspirational. It is the execution standard for every agent dispatched through /do. It derives from the toolkit's core principle (docs/PHILOSOPHY.md: "Tokens Are Cheap, Quality Is Expensive") and extends it: spending tokens on thoroughness is not just acceptable, it is required.

**What this means for routing and dispatch:**

- When asked for something, the answer is the finished product, not a plan to build it. Plans exist to organize execution, not to replace it.
- Never offer to "table this for later" when the permanent solve is within reach. Never present a workaround when the real fix exists. Never leave a dangling thread when tying it off takes five more minutes of agent time.
- Do not truncate output or stop mid-task. Dispatch agents that deliver complete, executable solutions. If an agent returns partial work, route a follow-up agent to finish it.
- Search before building. Test before shipping. Ship the complete thing.
- Time is not an excuse. Complexity is not an excuse. The router exists to decompose complexity into agent-sized work. Use it.

**The standard for every dispatched agent:** the result should make the user think "that's done" not "that's a start." Inject this expectation into agent prompts for all Simple+ work.

---

## Instructions

### Phase Banners (MANDATORY)

Every phase MUST display a banner BEFORE executing: `/do > Phase N: PHASE_NAME — description...`

After Phase 2, display the full routing decision banner (`===` block). Phase banners tell the user *where they are*; the routing banner tells them *what was decided*. Both required.

---

### Phase 1: CLASSIFY

**Goal**: Determine request complexity and whether routing is needed.

Read and follow the repository CLAUDE.md before making any routing decision, because it contains project-specific conventions that affect agent selection and skill pairing.

| Complexity | Agent | Skill | Direct Action |
|------------|-------|-------|---------------|
| Trivial | No | No | **ONLY reading a file the user named by exact path** |
| Simple | **Yes** | Yes | Route to agent |
| Medium | **Required** | **Required** | Route to agent |
| Complex | Required (2+) | Required (2+) | Route to agent |

**Trivial = reading a file the user named by exact path.** Everything else is Simple+ and MUST use an agent, skill, or pipeline. When uncertain, classify UP not down. Routing up finds the agent who ships it complete; tokens are cheap, and an agent that actually ships is what the user came for.

**Progressive Depth**: For requests where complexity is ambiguous, consider starting at a shallower depth and allowing the agent to escalate. See `references/progressive-depth.md` for the escalation protocol and signal format.

**Common misclassifications** (these are NOT Trivial — route them): evaluating repos/URLs, any opinion/recommendation, git operations, codebase questions (`explore-pipeline`), retro lookups (`retro` skill), comparing approaches.

**Maximize skill/agent/pipeline usage.** If a skill or pipeline exists for the task, USE IT. Skills encode domain patterns earned through prior work; using them gives you that expertise for free.

**Check for parallel patterns FIRST** because independent work items finish fastest when dispatched concurrently, and the routing table below matches the shape of the work: 2+ independent failures or 3+ subtasks → `dispatching-parallel-agents`; broad research → `research-coordinator-engineer`; multi-agent coordination → `project-coordinator-engineer`; plan exists + "execute" → `subagent-driven-development`; new feature → `feature-lifecycle` (check `.feature/` directory; if present, use `feature-state.py status` for current phase).

**Optional: Force Direct** — OFF by default. When explicitly enabled, overrides routing for trivial operations. Only applies when the user explicitly requests it.

**Creation Request Detection** (MANDATORY scan before Gate):

Scan the request for creation signals before completing Phase 1:
- Explicit creation verbs: "create", "scaffold", "build", "add new", "new [component]", "implement new"
- Domain object targets: agent, skill, pipeline, hook, feature, plugin, workflow, voice profile
- Implicit creation: "I need a [component]", "we need a [component]", "build me a [component]"

If ANY creation signal is found AND complexity is Simple+:
1. Set an internal flag: `is_creation = true`
2. **Phase 4 Step 0 is MANDATORY** — write ADR before dispatching any agent

This early detection ensures Phase 4 Step 0 fires reliably by catching the signal before Phase 2's routing work begins. The Gate below locks in the acknowledgment before moving on.

**Not a creation request**: debugging, reviewing, fixing, refactoring, explaining, running, checking, auditing existing components. When ambiguous, check whether the output would be a NEW file that doesn't yet exist.

**Gate**: Complexity classified. If a creation signal was detected, output `[CREATION REQUEST DETECTED]` before displaying the routing banner. Display routing banner (ALL classifications). If not Trivial, proceed to Phase 2. If Trivial, handle directly after showing banner.

<!-- DO NOT OPTIMIZE -->

---

### Phase 2: ROUTE

**Goal**: Select the correct agent + skill combination via the Haiku routing agent.

All routing goes through a single Haiku agent dispatch. The manifest includes `FORCE`-labeled entries that the Haiku agent must prefer when intent matches — but matching is semantic, not keyword-based. This replaced the prior two-tier system (deterministic keyword check + LLM fallback) after A/B testing showed Haiku-only scored 10/10 vs 9/10 for the two-tier approach, with the keyword matcher producing false positives on ambiguous words (e.g. "fish for bugs" → `fish-shell-config`).

**Step 1: Dispatch Haiku routing agent**

Generate the routing manifest, then dispatch the Haiku agent:

```bash
python3 scripts/routing-manifest.py
```

Dispatch the Agent tool with `model: "haiku"` and this prompt structure:

```
You are a routing agent. Given a user request and a manifest of available agents, skills, and pipelines, select the BEST agent+skill combination.

USER REQUEST: {user_request}

ROUTING MANIFEST:
{output of routing-manifest.py}

Return your answer as JSON:
{
  "agent": "agent-name or null",
  "skill": "skill-name or null",
  "pipeline": "pipeline-name or null",
  "reasoning": "one sentence why",
  "confidence": "high/medium/low"
}

FORCE-ROUTE RULE: Entries marked "FORCE" in the manifest MUST be selected when their domain clearly matches the user's intent. However, FORCE matching is SEMANTIC, not keyword-based. Match on what the user MEANS, not individual words. Examples:
- "push my changes" → pr-workflow (FORCE) ✓ (user means git push)
- "push back on this design" → NOT pr-workflow (user means resist/argue)
- "configure my fish shell" → fish-shell-config (FORCE) ✓ (user means Fish shell)
- "fish for bugs" → NOT fish-shell-config (user means search for bugs)
- "quick fix to the login page" → quick (FORCE) ✓ (user wants a small edit)
- "quick overview of the architecture" → NOT quick (user wants exploration)

Rules:
- Pick the most specific match. "Go tests" → golang-general-engineer + go-patterns, not general-purpose.
- Agent handles the domain. Skill handles the methodology. Pick both when possible.
- If the request implies a task verb (review, debug, refactor, test), prefer skills that match that verb.
- If nothing matches well, return all nulls with reasoning.
- Prefer entries whose description semantically matches the request, not just keyword overlap.
- For git operations (push, commit, PR, merge), ALWAYS select pr-workflow skill — these need quality gates.
- Return a single skill name as a string, not an array. If multiple skills are needed, pick the primary one.
```

**Step 1b: Apply the Haiku agent's recommendation**

Use the Haiku agent's `agent` and `skill` fields directly. If `confidence` is "low", fall back to reading INDEX files (`agents/INDEX.json`, `skills/INDEX.json`) and `references/routing-tables.md` to verify or override manually.

**Critical**: "push", "commit", "create PR", "merge" are NOT trivial git commands. They MUST route through skills that run quality gates. The skills bundle lint, tests, review loops, CI verification, and repo classification into the single command so the push lands cleanly.

Route to the simplest agent+skill that satisfies the request. A lean routing decision keeps attention on the work itself, not on managing the routing layer.

When `[cross-repo]` output is present, route to `.claude/agents/` local agents. They carry project-specific knowledge the generic agents cannot know.

Route all code modifications to domain agents. Domain agents carry language-specific expertise, testing methodology, and quality gates built for that language.

**Step 2: Apply skill override** (task verb overrides default skill)

When the request verb implies a specific methodology, override the agent's default skill. Common overrides: "review" → systematic-code-review, "debug" → systematic-debugging, "refactor" → systematic-refactoring, "TDD" → test-driven-development. Full override table in `references/routing-tables.md`.

**Step 3: Display routing decision** (MANDATORY — do this NOW, before anything else)

This banner MUST be the FIRST visible output for EVERY /do invocation. Display BEFORE creating plans, BEFORE invoking agents, BEFORE any work begins. No exceptions.

```
===================================================================
 ROUTING: [brief summary]
===================================================================
 Selected:
   -> Agent: [name] - [why]
   -> Skill: [name] - [why]
   -> Pipeline: PHASE1 → PHASE2 → ... (if pipeline; phases from skills/workflow/references/pipeline-index.json)
   -> Anti-Rationalization: [auto-injected for code/security/testing]
 Invoking...
===================================================================
```

For Trivial: show `Classification: Trivial - [reason]` and `Handling directly (no agent/skill needed)`.

**Optional: Dry Run Mode** — OFF by default. When enabled, show the routing decision without executing.

**Optional: Verbose Routing** — OFF by default. When enabled, explain why each alternative was rejected.

**Step 4: Record routing decision** (Simple+ only — skip Trivial):

```bash
python3 ~/.claude/scripts/learning-db.py record \
    routing "{selected_agent}:{selected_skill}" \
    "routing-decision: agent={selected_agent} skill={selected_skill} request: {first_200_chars} complexity: {complexity} enhancements: {comma_separated_list}" \
    --category effectiveness \
    --tags "{applicable_flags}"
```

Tags: `auto-pipeline` (as applicable). This call is advisory — if it fails, continue.
Valid categories: `error, pivot, review, design, debug, gotcha, effectiveness, misroute`. Use `effectiveness` for successful routing, `misroute` for reroutes.

**Gate**: Agent and skill selected. Banner displayed. Routing decision recorded. Proceed to Phase 3.

---

### Phase 3: ENHANCE

**Goal**: Stack additional skills based on signals in the request.

Retro knowledge is auto-injected by the `session-context` hook at SessionStart via the dream system's pre-built payload (nightly consolidation by `auto-dream`). If a `<retro-knowledge>` block is already in conversation context, skip — the hook handled it. Only manually inject if the hook did not fire (benchmark: +5.3 avg, 67% win rate). Relevance-gated by LLM curation during the nightly dream cycle.

| Signal in Request | Enhancement to Add |
|-------------------|-------------------|
| Any substantive work (code, design, plan) | **Auto-inject retro knowledge** (via `session-context` hook, pre-built by nightly `auto-dream`) |
| "comprehensive" / "thorough" / "full" | Add parallel reviewers (security + business + quality) |
| "with tests" / "production ready" | Append test-driven-development + verification-before-completion |
| "research needed" / "investigate first" | Prepend research-coordinator-engineer |
| "review" with 5+ files | Use parallel-code-review (3 reviewers) |
| Complex implementation | Offer subagent-driven-development |

Before stacking any enhancement, check the target skill's `pairs_with` field in `skills/INDEX.json`. Some skills ship with their own verification gates and work best on their own terms. Specifically: empty `pairs_with: []` means no stacking allowed. Skills with built-in verification gates handle their own verification. The `quick --trivial` mode handles its own testing. Stack only compatible enhancements.

**Auto-inject anti-rationalization** for these task types, because these categories reward pattern-reinforced rigor with the highest quality gains:

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

---

### Phase 4: EXECUTE

**Goal**: Invoke the selected agent + skill and deliver results.

**Step 0: Execute Creation Protocol** (for creation requests ONLY)

If request contains "create", "new", "scaffold", "build pipeline/agent/skill/hook" AND complexity is Simple+, automatically sequence: (1) Write ADR at `adr/{kebab-case-name}.md`, (2) Register via `adr-query.py register`, (3) Proceed to plan creation. The `adr-context-injector` and `adr-enforcement` hooks handle cross-agent ADR compliance automatically. This protocol fires automatically because creation requests at Simple+ complexity need architectural grounding before implementation begins.

**Step 1: Create plan** (for Simple+ complexity)

Create `task_plan.md` before execution, because a plan turns the next N turns into progress instead of rework. The `auto-plan-detector.py` hook auto-injects `<auto-plan-required>` context. Skip only for Trivial tasks.

**Step 1b: Apply quality-loop pipeline** (for Medium+ code modifications)

When the request is a code modification (implementation, bug fix, feature addition, refactoring) at Medium or Complex complexity, load `references/quality-loop.md` and use it as the **outer orchestration wrapper** around Step 2. The quality-loop and the agent+skill are complementary layers, not alternatives:

- **Quality-loop** (outer) = the full 14-phase lifecycle: ADR → PLAN → IMPLEMENT → TEST → REVIEW → INTENT VERIFY → LIVE VALIDATE → FIX → RETEST → PR → CODEX REVIEW → ADR RECONCILE → RECORD → CLEANUP
- **Agent + skill** (inner) = the domain expertise used inside PHASE 2 (IMPLEMENT)

When quality-loop applies, it absorbs Step 0 (ADR creation) and Step 1 (plan creation) into its own PHASES 0-1. Do not run Steps 0-1 separately — the quality-loop handles them.

The router still selects the best agent+skill in Phase 2 (e.g., `golang-general-engineer` + `go-patterns`). That selection becomes the implementation agent for quality-loop PHASE 1. Force-route skills like `go-patterns` are used INSIDE the loop, not excluded from it — a Go implementation gets Go-specific patterns AND testing, review, and PR gates.

The quality-loop does NOT apply when:
- Complexity is Trivial or Simple (use fast/quick instead)
- The task is review-only, research, debugging, or content creation
- The user explicitly requests a simpler flow

**Step 2: Invoke agent with skill**

Dispatch the agent. MCP tool discovery is the agent's responsibility — each agent's markdown declares which MCP tools it needs. Do not inject MCP instructions from /do.

**MANDATORY: Inject reference loading instruction for ALL dispatched agents.** Every agent prompt MUST include: "Before starting work, read your agent .md file or skill SKILL.md to find the Reference Loading Table. Load EVERY reference file whose signal matches this task. Load greedily, not conservatively. If multiple signals match, load all matching references. Reference files contain domain-specific patterns, anti-patterns, code examples, and detection commands that make your output expert-quality. Loading these files gives you domain expertise that prior work already put on disk, earned and waiting for you to use." This applies to ALL agents and skills, not just umbrella components. The nightly enrichment pipeline generates and updates reference files autonomously, so loading the table is how a dispatched agent inherits the domain knowledge created specifically for its work.

**MANDATORY: Inject the completeness standard for ALL Simple+ dispatches.** Every agent prompt MUST include: "Deliver the finished product, not a plan. Do not offer to table work for later when the solve is within reach. Do not present workarounds when the real fix exists. Do not stop mid-task or truncate output. Search before building. Test before shipping. Ship the complete thing."

Route to agents that create feature branches for all commits. Feature branches isolate the change so it ships cleanly after review, and the branch itself becomes the unit of review and revert.

When dispatching agents for file modifications, explicitly include "commit your changes on the branch" in the agent prompt. That instruction closes the loop so the orchestrator sees the committed work and moves forward with it as the authoritative state.

When dispatching agents with `isolation: "worktree"`, inject the `worktree-agent` skill rules into the agent prompt. The skill at `skills/worktree-agent/SKILL.md` contains mandatory rules that prevent worktree isolation failures (leaked changes, branch confusion, auto-plan hook interference). At minimum include: "Verify your CWD contains .claude/worktrees/. Create feature branch before edits. Skip task_plan.md creation (handled by orchestrator). Stage specific files only."

For repos without organization-gated workflows, run up to 3 iterations of `/pr-review` → fix before creating a PR, because pre-merge review lets you land once and move on. For repos under protected organizations (via `scripts/classify-repo.py`), require user confirmation before EACH git action. Confirm before executing or merging so the organization's compliance requirements get the explicit approval they exist to capture.

**Step 3: Handle multi-part requests**

Detect: "first...then", "and also", numbered lists, semicolons. Sequential dependencies execute in order. Independent items launch multiple Task tools in single message. Max parallelism: 10 agents.

**Step 4: Auto-Pipeline Fallback** (when no agent/skill matches AND complexity >= Simple)

Always invoke `auto-pipeline` for unmatched requests. Every unmatched request is a new routing pattern to capture, and the pipeline picks up the work while the gap gets recorded. If no pipeline matches either, fall back to closest agent + verification-before-completion.

When uncertain which route: **ROUTE ANYWAY.** Add verification-before-completion as safety net. Routing up finds the right agent and gives the work a home; routing down leaves the main thread improvising in isolation.

**Gate**: Agent invoked, results delivered. Proceed to Phase 5.

---

### Phase 5: LEARN

**Goal**: Ensure session insights are captured to `learning.db`.

**Routing outcome recording** (Simple+ tasks, observable facts only — no self-grading):
```bash
python3 ~/.claude/scripts/learning-db.py record \
    routing "{selected_agent}:{selected_skill}" \
    "routing-decision: agent={selected_agent} skill={selected_skill} tool_errors: {0|1} user_rerouted: {0|1}" \
    --category effectiveness
```

Record only observable facts (tool_errors, user_rerouted). Routing outcome quality is measured by user reroutes, not self-assessment.

**Auto-capture** (hooks, zero LLM cost): `error-learner.py` (PostToolUse), `review-capture.py` (PostToolUse), `session-learning-recorder.py` (Stop).

**Skill-scoped recording** (preferred — one-liner):
```bash
python3 ~/.claude/scripts/learning-db.py learn --skill go-patterns "insight about testing"
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

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/routing-tables.md`: Complete category-specific skill routing
- `${CLAUDE_SKILL_DIR}/references/progressive-depth.md`: Progressive depth escalation protocol
- `agents/INDEX.json`: Agent triggers and metadata
- `skills/INDEX.json`: Skill triggers, force-route flags, pairs_with
- `skills/workflow/SKILL.md`: Workflow phases, triggers, composition chains
- `skills/workflow/references/pipeline-index.json`: Pipeline metadata, triggers, phases

<!-- END DO NOT OPTIMIZE -->
