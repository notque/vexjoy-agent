---
name: do
description: "Route requests to agents with skills."
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

/do is a **ROUTER**, not a worker. Its ONLY job is to classify requests, assemble a dispatch package (agent + skill + pipeline + directives), and send it. The dispatched agent reads the skill and executes it. The router never opens the package.

**What the main thread does:** (1) Classify the request, (2) Select which agent to dispatch and which skill/pipeline to attach, (3) Dispatch the agent via Agent tool, (4) Evaluate if more work is needed, (5) Dispatch ANOTHER agent if yes, (6) Report results.

**What the dispatched agent does:** reads its own .md file, loads the attached skill's SKILL.md, loads reference files, and executes the methodology. The agent is the consumer of the skill. The router is the logistics layer.

The main thread is an **orchestrator**. If you find yourself reading source code, writing code, or doing analysis, you are doing the agent's job. Pause and dispatch instead.

**NEVER shortcut to built-in agent types** (Explore, general-purpose, etc.) without first running the routing manifest through the Haiku agent. The manifest contains domain-specific agents and skills that the model's general knowledge does not know about. A "codebase overview" request has a `codebase-overview` skill. A "Go debugging" request has `golang-general-engineer` + `go-patterns`. The Haiku routing agent surfaces these. Skipping the manifest means the dispatched agent works from general knowledge instead of domain expertise on disk.

---

## The Completeness Standard

The marginal cost of completeness is near zero. Do the whole thing. Do it right. Do it with tests. Do it with documentation. Do it so well that the user is genuinely impressed.

This is not aspirational. It is the execution standard for every agent dispatched through /do. It derives from the toolkit's core principle (docs/PHILOSOPHY.md: "Tokens Are Expensive, Use Progressive Context") and extends it: spending tokens on thoroughness is not just acceptable, it is required.

**What this means for routing and dispatch:**

- When asked for something, the answer is the finished product, not a plan to build it. Plans exist to organize execution, not to replace it.
- Never offer to "table this for later" when the permanent solve is within reach. Never present a workaround when the real fix exists. Never leave a dangling thread when tying it off takes five more minutes of agent time.
- Do not truncate output or stop mid-task. Dispatch agents that deliver complete, executable solutions. If an agent returns partial work, route a follow-up agent to finish it.
- Search before building. Test before shipping. Ship the complete thing.
- Time is not an excuse. Complexity is not an excuse. The router exists to decompose complexity into agent-sized work. Use it.

**The standard for every dispatched agent:** the result should make the user think "that's done" not "that's a start." Inject this expectation into agent prompts for all Simple+ work.

When the model feels confident handling a task directly, treat that confidence as a signal to route, not a signal to proceed. Direct handling skips the agent's domain knowledge, the skill's methodology, and the agent's reference files — each of which exists because prior work put expertise on disk that the main thread does not have.

---

## Instructions

### Phase Banners (MANDATORY)

Every phase MUST display a banner BEFORE executing: `/do > Phase N: PHASE_NAME — description...`

After Phase 2, display the full routing decision banner (`===` block). Phase banners tell the user *where they are*; the routing banner tells them *what was decided*. Both required.

---

### Phase 1: CLASSIFY

**Goal**: Determine request complexity and whether routing is needed.

Read and follow the repository CLAUDE.md before making any routing decision, because it contains project-specific conventions that affect agent selection and skill pairing.

| Complexity | Agent | Skill | Phases | Direct Action |
|------------|-------|-------|--------|---------------|
| Trivial | No | No | No | **ONLY reading a file the user named by exact path** |
| Simple | **Required** | **Required** | No | Dispatch agent with skill |
| Medium | **Required** | **Required** | **Required** | Dispatch agent with skill + composed phases |
| Complex | Required (2+) | Required (2+) | **Required** | Dispatch multiple agents with skills + composed phases |

**Trivial = reading a file the user named by exact path.** Everything else is Simple+ and MUST consult the routing manifest via the Haiku agent. The manifest surfaces domain-specific agents and skills. When uncertain, classify UP not down.

**Simple, Medium, and Complex all require an agent AND a skill from the manifest.** If a matching skill exists, it must be attached. "No skill needed" is never correct for Simple+ tasks. The manifest has 110 skills covering analysis, code quality, content, debugging, frontend, infrastructure, language-specific patterns, meta-tooling, process, research, security, testing, and voice. One of them matches.

**Opus 4.7 override:** Opus 4.7 defaults to fewer subagents and more direct handling. That default is correct for ad-hoc prompting; it is wrong here. The /do router is a delegation machine by design. Do not apply the model's default judiciousness. Classify Simple+ tasks to agents without reasoning about whether you could handle them directly. If a task is reading a file the user named by exact path, it is Trivial; if it is anything else — including tasks the model feels capable of handling in one response — it is Simple+ and MUST route.

**Progressive Depth**: For requests where complexity is ambiguous, consider starting at a shallower depth and allowing the agent to escalate. See `references/progressive-depth.md` for the escalation protocol and signal format.

**Common misclassifications** (these are NOT Trivial, route them): evaluating repos/URLs, any opinion/recommendation, git operations, codebase overview/understanding requests (`codebase-overview` skill), retro lookups (`retro` skill), comparing approaches. "Understand this repo" is Medium with `codebase-overview` skill, not Simple with no skill.

**Maximize skill/agent/pipeline usage.** If a skill or pipeline exists for the task, USE IT. Skills encode domain patterns earned through prior work; using them gives you that expertise for free.

**Check for parallel patterns FIRST** because independent work items finish fastest when dispatched concurrently, and the routing table below matches the shape of the work: 2+ independent failures or 3+ subtasks → `dispatching-parallel-agents`; broad research → `research-coordinator-engineer`; multi-agent coordination → `project-coordinator-engineer`; plan exists + "execute" → `subagent-driven-development`; new feature → `feature-lifecycle` (check `.feature/` directory; if present, use `feature-state.py status` for current phase).

**Opus 4.7 override:** Opus 4.7 is more judicious about spawning subagents by default. When the router detects 2+ independent items, dispatch all agents in parallel in a single message. Do not consolidate independent items into a single agent dispatch to "save subagent spawns" — that consolidation is the model's default under Opus 4.7 and it is wrong for this router.

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

**Gate**: Complexity classified. If a creation signal was detected, output `[CREATION REQUEST DETECTED]` before displaying the routing banner. Display routing banner (ALL classifications). If not Trivial, proceed to Phase 2 (mandatory: run the manifest and Haiku agent). If Trivial, handle directly after showing banner. Do NOT skip Phase 2 by dispatching built-in agent types directly.

---

### Phase 2: ROUTE

**Goal**: Determine which agent to dispatch and which skill to attach to it. The Haiku routing agent makes this selection.

All routing goes through a single Haiku agent dispatch. The manifest includes `FORCE`-labeled entries that the Haiku agent must prefer when intent matches — but matching is semantic, not keyword-based. This replaced the prior two-tier system (deterministic keyword check + LLM fallback) after A/B testing showed Haiku-only scored 10/10 vs 9/10 for the two-tier approach, with the keyword matcher producing false positives on ambiguous words (e.g. "fish for bugs" → `fish-shell-config`).

**Step 1: Dispatch Haiku routing agent**

Generate the routing manifest, then dispatch the Haiku agent:

```bash
python3 scripts/routing-manifest.py
```

Dispatch the Agent tool with `model: "haiku"` and this prompt structure:

```
You are a routing agent. Given a user request and a manifest of available agents and skills, select the BEST agent+skill combination.

USER REQUEST: {user_request}

ROUTING MANIFEST:
{output of routing-manifest.py}

Return your answer as JSON:
{
  "agent": "agent-name or null",
  "skill": "skill-name or null",
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

**Step 2: Apply skill override** (task verb overrides which skill the agent carries)

When the request verb implies a specific methodology, override the default skill attached to the dispatch. Common overrides: "review" → systematic-code-review, "debug" → systematic-debugging, "refactor" → systematic-refactoring, "TDD" → test-driven-development. Full override table in `references/routing-tables.md`.

**Step 3: Display dispatch decision** (MANDATORY — do this NOW, before anything else)

This banner MUST be the FIRST visible output for EVERY /do invocation. Display BEFORE creating plans, BEFORE dispatching agents, BEFORE any work begins. No exceptions.

```
===================================================================
 ROUTING: [brief summary]
===================================================================
 Dispatching:
   -> Agent: [name] - [why this agent]
      carries skill: [name] - [what methodology the agent will follow]
      phases: [composed from phase-composition.md, e.g. PLAN → IMPLEMENT → TEST → REVIEW → PR]
   -> Extra Rigor: [verification patterns attached to dispatch, if any]
 The agent will load its references and execute the skill.
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

Tags: `auto-pipeline` (as applicable), `thinking:slow` (if "think carefully" directive injected in Phase 4 Step 2), `thinking:fast` (if "respond quickly" directive injected in Phase 4 Step 2). This call is advisory — if it fails, continue.
Valid categories: `error, pivot, review, design, debug, gotcha, effectiveness, misroute`. Use `effectiveness` for successful routing, `misroute` for reroutes.

**Gate**: Agent and skill selected for dispatch. Banner displayed. Routing decision recorded. Proceed to Phase 3.

---

### Phase 3: ENHANCE

**Goal**: Compose phases and attach additional directives to the dispatch package. Enhancements are instructions the dispatched agent will receive, not work the router performs.

**Step 0: Compose phases** (Medium+ only)

For Medium+ tasks, load `references/phase-composition.md` and compose the phase sequence from the task type and complexity. Attach the composed phases to the dispatch package. The agent follows these phases as its execution structure.

Simple tasks skip phase composition. The agent executes the skill directly.

If relevant retro knowledge is already present in context, use it. If it is absent, continue without spending prompt space restating hook mechanics.

| Signal in Request | Enhancement to Attach |
|-------------------|----------------------|
| Any substantive work (code, design, plan) | Attach relevant retro knowledge only when it materially helps the agent |
| "comprehensive" / "thorough" / "full" | Dispatch parallel reviewers (security + business + quality) |
| "with tests" / "production ready" | Attach test-driven-development + verification-before-completion to dispatch |
| "research needed" / "investigate first" | Dispatch research-coordinator-engineer first |
| "review" with 5+ files | Dispatch parallel-code-review (3 reviewers) |
| Complex implementation | Offer subagent-driven-development |

Before attaching any enhancement, check the target skill's `pairs_with` field in `skills/INDEX.json` for known-compatible pairings. Skills with built-in verification gates handle their own verification. The `quick --trivial` mode handles its own testing. An empty `pairs_with: []` just means pairings have not been declared yet, not that stacking is prohibited.

Add anti-rationalization patterns for these task types when the task benefits from explicit rigor:

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

**Goal**: Resolve routing names to file paths, assemble the dispatch package, and send it. The package contains: resolved paths to the agent .md, skill SKILL.md, and reference files; composed phases; thinking directives; and the completeness standard. The dispatched agent reads the files at those paths and executes. The router waits for results.

**Step 0: Execute Creation Protocol** (for creation requests ONLY)

If request contains "create", "new", "scaffold", "build pipeline/agent/skill/hook" AND complexity is Simple+, automatically sequence: (1) Write ADR at `adr/{kebab-case-name}.md`, (2) Register via `adr-query.py register`, (3) Proceed to plan creation. The `adr-context-injector` and `adr-enforcement` hooks handle cross-agent ADR compliance automatically. This protocol fires automatically because creation requests at Simple+ complexity need architectural grounding before implementation begins.

**Step 1: Create plan** (for Simple+ complexity)

Create `task_plan.md` before execution, because a plan turns the next N turns into progress instead of rework. Skip only for Trivial tasks.

**Step 1b: Phase composition was applied in Phase 3 Step 0.** The composed phases are already attached to the dispatch package. No separate pipeline loading needed.

**Step 2: Resolve and dispatch the agent**

Run the dispatch resolver to convert routing names into concrete file paths:

```bash
python3 ~/.claude/scripts/resolve-dispatch.py \
    --agent {agent_name} \
    --skill {primary_skill} \
    --skill {enhancement_skill}  # (repeatable, from Phase 3 enhancements) \
    --inject {pattern_name}      # (repeatable, e.g. anti-rationalization-core) \
    --request "{user_request}"
```

This outputs a Dispatch Package block with resolved paths to the agent .md, all skill SKILL.md files, injection files (shared-patterns), and all reference directories. Prepend this block to the agent prompt. The agent reads these files as its first action.

For Medium+ tasks, also prepend a Task Specification block:

```
## Task Specification

**Intent:** <what does success look like>
**Constraints:** <branch rules, operator profile, memory feedback>
**Acceptance criteria:** <what proves it works>
```

After the Dispatch Package and Task Specification, append:

"Deliver the finished product, not a plan. Do not offer to table work for later when the solve is within reach. Do not present workarounds when the real fix exists. Do not stop mid-task or truncate output. Search before building. Test before shipping. Ship the complete thing."

**Opus 4.7 override: Inject complexity-calibrated thinking directive.** Opus 4.7 exposes thinking rate to prompt-level control. Prepend the appropriate directive to the dispatched agent's prompt as a single sentence (verbatim, no framing), because calibrating thinking rate per task class reduces both over-reasoning on simple work and under-reasoning on complex work:

| Complexity | Thinking Directive |
|---|---|
| Trivial | None (handled directly, no agent dispatched) |
| Simple | "Prioritize responding quickly rather than thinking deeply. When in doubt, respond directly." |
| Medium | None (let adaptive thinking decide) |
| Complex | "Think carefully and step-by-step before responding; this problem is harder than it looks." |

Category overrides (regardless of complexity class). Always inject "Think carefully and step-by-step before responding; this problem is harder than it looks." for: security work (threat modeling, vulnerability analysis, auth changes), API or schema design, migrations (data, code, legacy systems), code review spanning 5+ files, architectural decisions (ADR writing, design proposals). Always inject "Prioritize responding quickly rather than thinking deeply. When in doubt, respond directly." for: lookups with clear answers (what file contains X, what commit did Y), status checks (is CI green, is the PR mergeable), simple renames or straightforward refactors inside a single function.

Record the injected directive in the Phase 2 Step 4 `--tags` field as `thinking:slow` (for "think carefully") or `thinking:fast` (for "respond quickly"), so the learning-db can correlate dispatch outcome with thinking-rate choice.

Route to agents that create feature branches for all commits. Feature branches isolate the change so it ships cleanly after review, and the branch itself becomes the unit of review and revert.

When dispatching agents for file modifications, explicitly include "commit your changes on the branch" in the agent prompt. That instruction closes the loop so the orchestrator sees the committed work and moves forward with it as the authoritative state.

When dispatching agents with `isolation: "worktree"`, inject the `worktree-agent` skill rules into the agent prompt. The skill at `skills/worktree-agent/SKILL.md` contains mandatory rules that prevent worktree isolation failures (leaked changes, branch confusion, auto-plan hook interference). At minimum include: "Verify your CWD contains .claude/worktrees/. Create feature branch before edits. Skip task_plan.md creation (handled by orchestrator). Stage specific files only."

For repos without organization-gated workflows, run up to 3 iterations of `/pr-review` → fix before creating a PR, because pre-merge review lets you land once and move on. For repos under protected organizations (via `scripts/classify-repo.py`), require user confirmation before EACH git action. Confirm before executing or merging so the organization's compliance requirements get the explicit approval they exist to capture.

**Step 3: Handle multi-part requests**

Detect: "first...then", "and also", numbered lists, semicolons. Sequential dependencies execute in order. Independent items launch multiple Task tools in single message. Max parallelism: 10 agents.

**Step 4: Fallback** (when no agent/skill matches AND complexity >= Simple)

Route to the closest matching agent with verification-before-completion as safety net. Routing up finds the right agent and gives the work a home; routing down leaves the main thread improvising in isolation. Record the routing gap for future pattern capture.

**Gate**: Agent dispatched, results received. Proceed to Phase 5.

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
- `${CLAUDE_SKILL_DIR}/references/routing-tables.md`: Category-specific skill routing
- `${CLAUDE_SKILL_DIR}/references/progressive-depth.md`: Progressive depth escalation protocol
- `${CLAUDE_SKILL_DIR}/references/phase-composition.md`: Phase composition for Medium+ tasks
- `agents/INDEX.json`: Agent triggers and metadata
- `skills/INDEX.json`: Skill triggers, force-route flags, pairs_with
