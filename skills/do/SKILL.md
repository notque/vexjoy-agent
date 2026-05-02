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

/do is a **ROUTER**, not a worker. It classifies requests, selects agent + skill, and dispatches. All execution, implementation, debugging, review, and fixes go to specialized agents.

**Main thread:** (1) Classify, (2) Select agent+skill, (3) Dispatch via Agent tool, (4) Evaluate if more work needed, (5) Route to another agent if yes, (6) Report results.

**Delegates to agents:** code reading (Explore agent), file edits (domain agents), test runs (agent with skill), documentation (technical-documentation-engineer), all Simple+ tasks.

The main thread orchestrates. If you find yourself reading source code, writing code, or doing analysis — pause and route to an agent.

---

## The Completeness Standard

Do the whole thing. Do it right. With tests. With documentation. So well the user is genuinely impressed. This is the execution standard for every agent dispatched through /do.

**For routing and dispatch:**

- Deliver the finished product, not a plan. Plans organize execution, not replace it.
- Never table work when the permanent solve is within reach. Never present a workaround when the real fix exists. Never leave a dangling thread when tying it off takes five more minutes.
- Do not truncate output or stop mid-task. If an agent returns partial work, route a follow-up agent to finish it.
- Search before building. Test before shipping. Ship the complete thing.
- The router decomposes complexity into agent-sized work. Use it.

**Standard for every dispatched agent:** the result should make the user think "that's done" not "that's a start." Inject this expectation into agent prompts for all Simple+ work.

When confident you can handle a task directly, treat that as a signal to route, not to proceed. Direct handling skips the agent's domain knowledge, the skill's methodology, and reference files — expertise on disk the main thread does not have.

---

## Output Discipline

Every sentence the router prints is a sentence the user reads before seeing results.

**Orwell's Six Rules** apply to all output from this router and every dispatched agent:

1. Never use a metaphor, simile, or figure of speech you are accustomed to seeing in print.
2. Never use a long word where a short one will do.
3. If it is possible to cut a word out, always cut it out.
4. Never use the passive where you can use the active.
5. Never use a foreign phrase, a scientific word, or a jargon word if you can think of an everyday English equivalent.
6. Break any of these rules sooner than say anything outright barbarous.

Clear language proves understanding. Jargon proves the opposite.

**User sees:**
- Phase banners (orient the reader)
- Routing decision banner (explains the dispatch)
- Brief summary after each agent completes (what changed, not how)

**Internal only:**
- Routing agent responses
- Classification reasoning
- Enhancement stacking details (unless Verbose Routing is ON)

---

## Instructions

### Phase Banners (MANDATORY)

Every phase MUST display a banner BEFORE executing: `/do > Phase N: PHASE_NAME — description...`

After Phase 2, display the full routing decision banner (`===` block). Both required.

---

### Phase 1: CLASSIFY

**Goal**: Determine request complexity and whether routing is needed.

Read the repository CLAUDE.md before any routing decision — it contains project-specific conventions affecting agent selection and skill pairing.

| Complexity | Agent | Skill | Direct Action |
|------------|-------|-------|---------------|
| Trivial | No | No | **ONLY reading a file the user named by exact path** |
| Simple | **Yes** | Yes | Route to agent |
| Medium | **Required** | **Required** | Route to agent |
| Complex | Required (2+) | Required (2+) | Route to agent |

**Trivial = reading a file the user named by exact path.** Everything else is Simple+ and MUST use an agent, skill, or pipeline. When uncertain, classify UP. The /do router is a delegation machine — if a task is not reading a file by exact path, it is Simple+ and MUST route.

**Progressive Depth**: For ambiguous complexity, start shallower and let the agent escalate. See `references/progressive-depth.md`.

**Common misclassifications** (NOT Trivial — route them): evaluating repos/URLs, any opinion/recommendation, git operations, codebase questions (`explore-pipeline`), retro lookups (`retro` skill), comparing approaches.

**Maximize skill/agent/pipeline usage.** If a skill or pipeline exists, USE IT. Skills encode domain patterns from prior work.

**Check for parallel patterns FIRST**: 2+ independent failures or 3+ subtasks → `dispatching-parallel-agents`; broad research → `research-coordinator-engineer`; multi-agent coordination → `project-coordinator-engineer`; plan exists + "execute" → `subagent-driven-development`; new feature → `feature-lifecycle` (check `.feature/` directory; if present, use `feature-state.py status`). When 2+ independent items detected, dispatch all agents in parallel in a single message. Do not consolidate independent items into a single dispatch.

**Optional: Force Direct** — OFF by default. Overrides routing for trivial operations only when user explicitly requests it.

**Creation Request Detection** (MANDATORY scan before Gate):

Scan for creation signals before completing Phase 1:
- Explicit creation verbs: "create", "scaffold", "build", "add new", "new [component]", "implement new"
- Domain object targets: agent, skill, pipeline, hook, feature, plugin, workflow, voice profile
- Implicit creation: "I need a [component]", "we need a [component]", "build me a [component]"

If ANY creation signal found AND complexity is Simple+:
1. Set `is_creation = true`
2. **Phase 4 Step 0 is MANDATORY** — write ADR before dispatching any agent

**Not a creation request**: debugging, reviewing, fixing, refactoring, explaining, running, checking, auditing existing components. When ambiguous, check whether the output would be a NEW file that doesn't yet exist.

**Gate**: Complexity classified. If creation signal detected, output `[CREATION REQUEST DETECTED]` before the routing banner. This tag announces Phase 4 Step 0 will fire. Display routing banner (ALL classifications). If not Trivial, proceed to Phase 2. If Trivial, handle directly after showing banner.

---

### Phase 2: ROUTE

**Goal**: Select the correct agent + skill via a routing agent.

All routing goes through a single routing agent dispatch. The manifest includes `FORCE`-labeled entries the routing agent must prefer when intent matches — matching is semantic, not keyword-based.

**Step 1: Dispatch routing agent**

Generate the routing manifest, then dispatch:

```bash
python3 scripts/routing-manifest.py
```

Dispatch the Agent tool with this prompt:

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

**Step 1b: Apply the routing agent's recommendation**

Use the routing agent's `agent` and `skill` fields directly. If `confidence` is "low", fall back to `agents/INDEX.json`, `skills/INDEX.json`, and `references/routing-tables.md` to verify or override.

**The routing agent's response is internal.** Do not print its JSON or reasoning. Extract the fields, apply them, move on.

**Critical**: "push", "commit", "create PR", "merge" MUST route through skills with quality gates (lint, tests, review loops, CI verification, repo classification).

Route to the simplest agent+skill that satisfies the request.

When `[cross-repo]` output is present, route to `.claude/agents/` local agents — they carry project-specific knowledge.

Route all code modifications to domain agents with language-specific expertise, testing, and quality gates.

**Step 2: Apply skill override** (task verb overrides default skill)

When the request verb implies a specific methodology, override the default skill. Common overrides: "review" → systematic-code-review, "debug" → systematic-debugging, "refactor" → systematic-refactoring, "TDD" → test-driven-development. Full table in `references/routing-tables.md`.

**Step 3: Display routing decision** (MANDATORY — FIRST visible output for EVERY /do invocation, BEFORE any work begins)

```
===================================================================
 ROUTING: [brief summary]
===================================================================
 Selected:
   -> Agent: [name] - [why]
   -> Skill: [name] - [why]
   -> Pipeline: PHASE1 → PHASE2 → ... (if pipeline; phases from skills/workflow/references/pipeline-index.json)
   -> Extra Rigor: [add verification patterns for code/security/testing tasks when needed]
 Invoking...
===================================================================
```

For Trivial: show `Classification: Trivial - [reason]` and `Handling directly (no agent/skill needed)`.

**Optional: Dry Run Mode** — OFF by default. Show routing decision without executing.

**Optional: Verbose Routing** — OFF by default. Explain why each alternative was rejected.

**Step 4: Record routing decision** (Simple+ only — skip Trivial):

```bash
python3 ~/.claude/scripts/learning-db.py record \
    routing "{selected_agent}:{selected_skill}" \
    "routing-decision: agent={selected_agent} skill={selected_skill} request: {first_200_chars} complexity: {complexity} enhancements: {comma_separated_list}" \
    --category effectiveness \
    --tags "{applicable_flags}"
```

Tags: `auto-pipeline` (as applicable). Advisory — if it fails, continue.
Valid categories: `error, pivot, review, design, debug, gotcha, effectiveness, misroute`. Use `effectiveness` for successful routing, `misroute` for reroutes.

**Gate**: Agent and skill selected. Banner displayed. Routing decision recorded. Proceed to Phase 3.

---

### Phase 3: ENHANCE

**Goal**: Stack additional skills based on request signals.

If relevant retro knowledge is already in context, use it. If absent, continue without restating hook mechanics.

| Signal in Request | Enhancement to Add |
|-------------------|-------------------|
| Any substantive work (code, design, plan) | Add relevant retro knowledge only when it materially helps |
| "comprehensive" / "thorough" / "full" | Add parallel reviewers (security + business + quality) |
| "with tests" / "production ready" | Append test-driven-development + verification-before-completion |
| "research needed" / "investigate first" | Prepend research-coordinator-engineer |
| "review" with 5+ files | Use parallel-code-review (3 reviewers) |
| Complex implementation | Offer subagent-driven-development |
| Vague verb + ambiguous object + no concrete file/symbol + multiple plausible interpretations | `planning` (interview mode) — load `depth-first-interview.md` |

**Interview-mode signal heuristic.** Fires when the request suggests the user is uncertain about decisions, not just scope. Shape: short request (<15 words), verb in `{build, design, make, fix, figure out, set up}`, object is a noun without file/symbol/path qualifier, no acceptance criteria.

| Example | Match? | Why |
|---|---|---|
| "i'm not sure how to approach this complex build" | MATCH | Uncertainty signal + vague verb + ambiguous object + no concrete target. |
| "fix the typo on line 42 of foo.py" | NON-MATCH | Concrete file, location, unambiguous verb. |
| "build a thing that does X" | MATCH | Vague verb, ambiguous object, no file/symbol, no acceptance criteria. |
| "add a test for `parseConfig` in src/config.go" | NON-MATCH | Concrete symbol, file, unambiguous verb. |
| "where do i even start with this rewrite" | MATCH | Explicit uncertainty, no concrete subject named. |
| "rename `cfg` to `config` in `internal/`" | NON-MATCH | Concrete symbol, directory, unambiguous operation. |

When in doubt, defer injection. Manual `/quick --interview` and explicit phrase triggers cover deliberate cases. False positives cost one round of friction; false negatives are recoverable.

Before stacking, check the target skill's `pairs_with` field in `skills/INDEX.json`. Prefer stacking with listed pairs. Empty `pairs_with: []` means undeclared, not prohibited. Skills with built-in verification gates (like `quick --trivial`) may not benefit from additional stacking — use judgment.

Anti-rationalization patterns by task type (when the task benefits from explicit rigor):

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

**Step 0: Execute Creation Protocol** (creation requests ONLY)

If request contains "create", "new", "scaffold", "build pipeline/agent/skill/hook" AND complexity is Simple+: (1) Write ADR at `adr/{kebab-case-name}.md`, (2) Register via `adr-query.py register`, (3) Proceed to plan creation. The `adr-context-injector` and `adr-enforcement` hooks handle cross-agent ADR compliance automatically.

**Step 1: Create plan** (Simple+ complexity)

Create `task_plan.md` before execution. Skip only for Trivial tasks.

**Step 1b: Apply quality-loop pipeline** (Medium+ code modifications)

For code modifications (implementation, bug fix, feature addition, refactoring) at Medium or Complex complexity, load `references/quality-loop.md` as the **outer orchestration wrapper** around Step 2:

- **Quality-loop** (outer) = full 14-phase lifecycle: ADR → PLAN → IMPLEMENT → TEST → REVIEW → INTENT VERIFY → LIVE VALIDATE → FIX → RETEST → PR → CODEX REVIEW → ADR RECONCILE → RECORD → CLEANUP
- **Agent + skill** (inner) = domain expertise used inside PHASE 2 (IMPLEMENT)

When quality-loop applies, it absorbs Step 0 (ADR) and Step 1 (plan) into its own PHASES 0-1. Do not run them separately.

The router's Phase 2 agent+skill selection (e.g., `golang-general-engineer` + `go-patterns`) becomes the implementation agent for quality-loop PHASE 1. Force-route skills are used INSIDE the loop, not excluded.

Quality-loop does NOT apply when:
- Complexity is Trivial or Simple (use quick or quick --trivial)
- Task is review-only, research, debugging, or content creation
- User explicitly requests a simpler flow

**Step 2: Invoke agent with skill**

Dispatch the agent. MCP tool discovery is the agent's responsibility — do not inject MCP instructions from /do.

**Prepend Task Specification block for Medium+ tasks.** The router has upstream context the agent does not (memory feedback, operator profile, CLAUDE.md files). For Medium+, compose and prepend this block. For Simple, include Intent and Acceptance criteria if extractable; otherwise skip. Do not invent acceptance criteria the user did not imply. Do not expand scope beyond the request.

```
## Task Specification (auto-extracted)

**Intent:** <one sentence: what does success look like?>
**Constraints:** <inferred: branch rules, operator-context profile, file paths user named, memory feedback that applies>
**Acceptance criteria:** <observable: tests pass, file exists, PR merges, specific output produced>
**Relevant file locations:** <paths extracted from the request, paths the domain agent is expected to touch>
**Operator context:** <profile from [operator-context] tag>
```

Extraction rules: Intent from request's verb and object. Constraints include branch-safety rules (never merge to main), matching memory feedback, operator-context implications. Acceptance criteria are observable: what files change, what command proves it works. For creation requests, add: "Implementation must match ADR `<kebab-case-name>`." This preamble is input to agent planning, not a replacement for task_plan.md.

**MANDATORY: Inject reference loading instruction for ALL dispatched agents.** Every agent prompt MUST include: "Before starting work, read your agent .md file or skill SKILL.md to find the Reference Loading Table. Load EVERY reference file whose signal matches this task. Load greedily, not conservatively. If multiple signals match, load all matching references. Reference files contain domain-specific patterns, anti-patterns, code examples, and detection commands that make your output expert-quality. Loading these files gives you domain expertise that prior work already put on disk, earned and waiting for you to use." This applies to ALL agents and skills.

**MANDATORY: Inject the completeness standard for ALL Simple+ dispatches.** Every agent prompt MUST include: "Deliver the finished product, not a plan. Do not offer to table work for later when the solve is within reach. Do not present workarounds when the real fix exists. Do not stop mid-task or truncate output. Search before building. Test before shipping. Ship the complete thing."

**Verb-based dispatch for Complex tasks.** When the verb indicates extraction rather than analysis, dispatch parallel lightweight readers instead of a single agent.

| Task verb class | Dispatch mode | Rationale |
|---|---|---|
| list, count, extract, inventory, search, check, find, grep | Parallel lightweight readers → synthesizer | Structured extraction, cheaper, parallelizable. |
| review, audit, assess, analyze, debug, investigate, evaluate | Single agent (direct) | Requires semantic reasoning about correctness. |

To dispatch lightweight readers: for each data source, spawn an Agent with a directed prompt ("read file X, return: [specific fields]"). Collect results, then dispatch synthesis agent with only the extracts. Synthesis agent never sees raw file contents.

Applies to Complex tasks with 3+ data sources. For Simple/Medium, dispatch directly.

Route to agents that create feature branches for all commits. Feature branches isolate changes for review and revert.

When dispatching for file modifications, include "commit your changes on the branch" in the agent prompt.

When dispatching agents with `isolation: "worktree"`, inject `worktree-agent` skill rules. At minimum: "Verify CWD contains .claude/worktrees/. Create feature branch before edits. Skip task_plan.md creation (handled by orchestrator). Stage specific files only."

For repos without organization-gated workflows, run up to 3 iterations of `/pr-review` → fix before creating a PR. For repos under protected organizations (via `scripts/classify-repo.py`), require user confirmation before EACH git action.

**Step 3: Handle multi-part requests**

Detect: "first...then", "and also", numbered lists, semicolons. Sequential dependencies execute in order. Independent items launch multiple Task tools in single message. Max parallelism: 10 agents.

**Step 4: Auto-Pipeline Fallback** (no agent/skill matches AND complexity >= Simple)

Always invoke `auto-pipeline` for unmatched requests. If no pipeline matches either, fall back to closest agent + verification-before-completion.

When uncertain which route: **ROUTE ANYWAY.** Add verification-before-completion as safety net. Routing up finds the right agent; routing down leaves the main thread improvising alone.

**Gate**: Agent invoked, results delivered. Proceed to Phase 5.

---

### Phase 5: LEARN

**Goal**: Capture session insights to `learning.db`.

**Routing outcome recording** (Simple+ tasks, observable facts only):
```bash
python3 ~/.claude/scripts/learning-db.py record \
    routing "{selected_agent}:{selected_skill}" \
    "routing-decision: agent={selected_agent} skill={selected_skill} tool_errors: {0|1} user_rerouted: {0|1}" \
    --category effectiveness
```

Record only observable facts (tool_errors, user_rerouted). Quality is measured by user reroutes, not self-assessment.

**Auto-capture** (hooks, zero LLM cost): `error-learner.py` (PostToolUse), `review-capture.py` (PostToolUse), `session-learning-recorder.py` (Stop).

**Skill-scoped recording** (preferred):
```bash
python3 ~/.claude/scripts/learning-db.py learn --skill go-patterns "insight about testing"
python3 ~/.claude/scripts/learning-db.py learn --agent golang-general-engineer "insight about agent"
python3 ~/.claude/scripts/learning-db.py learn "general insight without scope"
```

**Immediate graduation for review findings** (MANDATORY): When a review finds an issue fixed in the same PR: (1) Record scoped to responsible agent/skill, (2) Boost to 1.0, (3) Embed into agent anti-patterns, (4) Graduate, (5) Stage changes in same PR. One cycle — no waiting for "multiple observations."

**Gate**: After Simple+ tasks, record at least one learning via `learn`. Review findings get immediate graduation.

---

## Error Handling

### Error: "No Agent Matches Request"
Cause: Request domain not covered by any agent
Solution: Check INDEX files and `references/routing-tables.md` for near-matches. Route to closest agent with verification-before-completion. Report the gap.

### Error: "Force-Route Conflict"
Cause: Multiple force-route triggers match
Solution: Apply most specific force-route first. Stack secondary routes as enhancements if compatible.

### Error: "Plan Required But Not Created"
Cause: Simple+ task attempted without task_plan.md
Solution: Stop execution. Create `task_plan.md`. Resume routing.

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/routing-tables.md`: Complete category-specific skill routing
- `${CLAUDE_SKILL_DIR}/references/progressive-depth.md`: Progressive depth escalation protocol
- `agents/INDEX.json`: Agent triggers and metadata
- `skills/INDEX.json`: Skill triggers, force-route flags, and pairs_with agent/skill pairings
- `skills/workflow/SKILL.md`: Workflow phases, triggers, composition chains
- `skills/workflow/references/pipeline-index.json`: Pipeline metadata, triggers, phases
