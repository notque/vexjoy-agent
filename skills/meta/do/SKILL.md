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

/do is a **ROUTER**, not a worker. Classify requests, select the right agent + skill, dispatch. All execution goes to specialized agents.

**Main thread:** (1) Classify, (2) Select agent+skill, (3) Dispatch, (4) Evaluate, (5) Route again if needed, (6) Report.

If you find yourself reading source code, writing code, or doing analysis — pause and route to an agent.

---

## The Completeness Standard

Do the whole thing. Do it right. Do it with tests. Do it with documentation.

- The answer is the finished product, not a plan. Plans organize execution, not replace it.
- Never table work when the permanent solve is within reach. Never present a workaround when the real fix exists.
- If an agent returns partial work, route a follow-up to finish it.
- Search before building. Test before shipping.
- The router decomposes complexity into agent-sized work. Use it.

**The standard:** the result should make the user think "that's done" not "that's a start." Inject this into agent prompts for all Simple+ work.

Model confidence in handling a task directly is a signal to route, not to proceed. Direct handling skips domain knowledge, methodology, and reference files that exist on disk.

---

## Output Discipline

Every word the router prints, and every word in a dispatched agent prompt, follows the **Dense-Complete Writing standard** — the toolkit's structural guide for all output, code comments, authored files, and thinking. It is Russell's five density rules plus the Completeness clause — treat content as fixed and wording as negotiable: carry every required point through the draft, then choose the shortest plain words that say those points exactly — extending Orwell's six rules (1946). Every word in a prompt costs tokens on the agent's context window. Full rules: `skills/shared-patterns/dense-complete-writing.md`.

**User sees:** phase banners, routing decision banner, brief post-agent summary (what changed, not how).

**Internal only:** Haiku routing responses, classification reasoning, enhancement stacking details (unless Verbose Routing ON).

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

**Trivial = reading a file the user named by exact path.** Everything else is Simple+ and MUST route. When uncertain, classify UP.

**Delegation is mandatory.** /do is a delegation machine. Classify Simple+ tasks to agents without reasoning about whether you could handle them directly. Anything beyond reading a user-named file MUST route.

**Progressive Depth**: For ambiguous complexity, start shallow and let the agent escalate. See `references/progressive-depth.md`.

**Common misclassifications** (NOT Trivial — route them): evaluating repos/URLs, opinions/recommendations, git operations, codebase questions (`explore-pipeline`), retro lookups (`retro`), comparing approaches.

**Maximize skill/agent/pipeline usage.** If a skill exists for the task, USE IT.

**Check for parallel patterns FIRST**: 2+ independent failures or 3+ subtasks → `dispatching-parallel-agents`; broad research → `research-coordinator-engineer`; multi-agent coordination → `project-coordinator-engineer`; plan + "execute" → `subagent-driven-development`; new feature → `feature-lifecycle` (check `.feature/` directory; if present, run `feature-state.py status`).

**Parallel dispatch is mandatory.** When the router detects 2+ independent items, dispatch all in parallel in a single message. Do not consolidate into one agent.

**Optional: Force Direct** — OFF by default. Only applies when user explicitly requests it.

**Creation Request Detection** (MANDATORY scan before Gate):

Scan for creation signals:
- Verbs: "create", "scaffold", "build", "add new", "new [component]", "implement new"
- Targets: agent, skill, pipeline, hook, feature, plugin, workflow, voice profile
- Implicit: "I need a [component]", "build me a [component]"

If ANY creation signal found AND complexity Simple+: set `is_creation = true`, Phase 4 Step 0 is MANDATORY (write ADR before dispatching).

**Not creation**: debugging, reviewing, fixing, refactoring, explaining, auditing existing components. When ambiguous, check whether output is a NEW file.

**Gate**: Complexity classified. If creation detected, output `[CREATION REQUEST DETECTED]` before routing banner. Display banner (ALL classifications). Trivial: handle directly. Simple+: proceed to Phase 2.

---

### Phase 2: ROUTE

**Goal**: Select the correct agent + skill. Semantic intent routing (Haiku) is primary; the deterministic pre-router is a safety-net, not a short-circuit. FORCE-labeled entries are preferred when intent matches semantically (not keyword-based).

**Contract: read for INTENT first.** A model reads what the user MEANS; trigger keywords are hints, never gates. Plain or non-native-English phrasing must route as well as jargon ("send my commits to the server" routes like "git push"). Cost: ~+0.1 Haiku calls/request vs the old keyword short-circuit — measured, deliberately accepted (see `references/semantic-first-ab-results.md`).

**Step 0: Semantic intent routing (PRIMARY)**

Generate the manifest, then dispatch the Haiku routing agent. Its decision is the primary route.

```bash
SDIR="${HOME}/.claude/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.hermes/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.factory/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.gemini/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.codex/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.reasonix/scripts"
python3 "$SDIR/routing-manifest.py"
```

Dispatch the Agent tool with `model: "haiku"`, omitting `isolation: "worktree"` — the routing agent only reads a manifest and returns JSON; it never touches files or git, and worktree isolation fails outside a git repo. Use this prompt structure:

```
You are a routing agent. Given a user request and a manifest of available agents, skills, and pipelines, select the BEST agent+skill combination, and optionally a pipeline.

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

SECTION-INTEGRITY RULE (HARD CONSTRAINT — never violate):
- The `agent` field MUST be a name listed in the `AGENTS:` section of the manifest, or null. Never put a skill name in `agent`.
- The `skill` field MUST be a name listed in the `SKILLS:` section of the manifest, or null. Never put an agent name in `skill`.
- The `pipeline` field MUST be a name listed in the `PIPELINES:` section of the manifest, or null.
- If no agent fits the request, return `"agent": null` — DO NOT promote a skill into the `agent` slot. The router will fall back to a default agent (e.g. `general-purpose`) and pair it with your chosen skill.
- Skills marked `FORCE (process)` are still skills, not agents. They go in the `skill` field only. Example: `zsh-shell-config` is a SKILL — if it matches, set `"skill": "zsh-shell-config"` and pick a separate agent (or null) for `agent`.

FORCE-ROUTE RULE: Entries marked "FORCE" in the manifest MUST be selected when their domain clearly matches the user's intent. However, FORCE matching is SEMANTIC, not keyword-based. Match on what the user MEANS, not individual words. Examples:
- "push my changes" → pr-workflow (FORCE) ✓ (user means git push)
- "push back on this design" → NOT pr-workflow (user means resist/argue)
- "configure my fish shell" → fish-shell-config (FORCE) ✓ (user means Fish shell)
- "fish for bugs" → NOT fish-shell-config (user means search for bugs)
- "quick fix to the login page" → quick (FORCE) ✓ (user wants a small edit)
- "quick overview of the architecture" → NOT quick (user wants exploration)

PIPELINE-SELECTION RULE: The `pipeline` field is OPTIONAL and most requests should return `null`. Return a pipeline name ONLY when BOTH conditions hold:
(1) the user's intent SEMANTICALLY matches a pipeline's `triggers` or `description` in the PIPELINES section of the manifest, AND
(2) the request genuinely benefits from a multi-phase flow (research + write, scope + gather + synthesize, multi-wave review) — not just a single skill task.
Match on MEANING, not keyword overlap. If a single agent+skill satisfies the request, return `null` for pipeline. Examples:
- "write an article in vexjoy voice about X" → pipeline: "voice-writer" ✓ (multi-phase voice content generation matches the voice-writer pipeline)
- "research X with artifacts and sources" → pipeline: "research-pipeline" ✓ (formal SCOPE → GATHER → SYNTHESIZE → VALIDATE → DELIVER flow)
- "comprehensive review of these 8 files" → pipeline: "comprehensive-review" ✓ (multi-wave per-package review across many files)
- "fix the typo on line 42 of foo.py" → pipeline: null (single trivial edit, no pipeline needed)
- "debug this failing test" → pipeline: null (one agent+skill handles it; pipeline only if user asks for systematic debugging artifacts)
- "review this 10-line function" → pipeline: null (single skill, no multi-wave review warranted)
When in doubt, return null. A pipeline pick must be defensible against the manifest's PIPELINES section.

Rules:
- Pick the most specific match. "Go tests" → golang-general-engineer + go-patterns, not general-purpose.
- Agent handles the domain. Skill handles the methodology. Pick both when possible.
- If the request implies a task verb (review, debug, refactor, test), prefer skills that match that verb.
- If nothing matches well, return all nulls with reasoning.
- Prefer entries whose description semantically matches the request, not just keyword overlap.
- For GENUINE git / version-control operations — actually pushing code, committing files to a repository, or opening/merging a pull request — ALWAYS select pr-workflow. Do NOT route metaphorical or non-version-control uses of these words (e.g. 'commit to a decision/plan', 'merge ideas in your head', 'push back on a proposal') to pr-workflow.
- Return a single skill name as a string, not an array. If multiple skills are needed, pick the primary one.
```

**Step 0b: Apply the Haiku agent's recommendation**

Use `agent` and `skill` fields directly. If `confidence` is "low", verify against INDEX files and `INDEX files`. Haiku response is internal — never print to user.

**Dispatch-time section validator (MANDATORY before every `Agent(subagent_type=...)` call).** The Haiku router can mis-place a skill name in the `agent` field, and the harness then rejects the dispatch with `Agent type 'X' not found`. Before invoking the Agent tool, assert the `agent` field maps to a name in the manifest's `AGENTS:` section. Pseudocode:

```
agents_section = grep_section(manifest, "AGENTS:", "SKILLS:")
skills_section = grep_section(manifest, "SKILLS:", "PIPELINES:")
agent_names = [first_token(line) for line in agents_section]
skill_names = [first_token(line) for line in skills_section]

if haiku.agent and haiku.agent not in agent_names:
    if haiku.agent in skill_names:
        # Cross-section slip: Haiku put a skill in the agent slot.
        haiku.skill = haiku.skill or haiku.agent  # promote to skill if empty
        haiku.agent = None                         # clear bad agent pick
    record_misroute(reason="agent-slot held skill name", value=haiku.agent)

if haiku.agent is None:
    haiku.agent = "general-purpose"  # safe fallback; pair with chosen skill
```

If the Haiku JSON is malformed, fall back to `general-purpose` + verification-before-completion. Always validate the agent name against the AGENTS: section before passing it to `subagent_type`.

Route to the simplest agent+skill that satisfies the request. When `[cross-repo]` output is present, route to `.claude/agents/` local agents. Route all code modifications to domain agents.

**Step 1: Deterministic safety-net** (`pre-route.py` — runs AFTER the semantic decision, never short-circuits it)

Run the pre-router and use its result ONLY as a guardrail over the semantic pick:

```bash
SDIR="${HOME}/.claude/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.hermes/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.factory/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.gemini/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.codex/scripts"; [ -d "$SDIR" ] || SDIR="${HOME}/.reasonix/scripts"
python3 "$SDIR/pre-route.py" --request "{user_request}" --json-compact
```

- **(a) Safety-critical force-route override.** If pre-route returns `"confidence": "high"` with a `force_route` match for `pr-workflow` or a security skill, and the semantic pick disagrees, override to the force-route. Git and security work MUST hit quality gates. Record `match_type` in routing decision tags.
- **(b) Guards stay active.** Its phrase/unigram guards continue to suppress false matches (e.g. "fish out", metaphorical commit/merge). A guarded request stays with the semantic decision.
- Otherwise the semantic decision from Step 0 stands. The pre-router no longer overrides a good semantic pick on the long tail.

**Critical**: genuine "push", "commit", "create PR", "merge" MUST route through skills with quality gates (lint, tests, CI verification) — enforced by the safety-net override above.

**Step 2: Apply skill override** (task verb overrides default skill)

When the request verb implies a specific methodology, override the agent's default skill. Common overrides: "review" → systematic-code-review, "debug" → systematic-debugging, "refactor" → systematic-refactoring, "TDD" → test-driven-development. Full override table in `INDEX files`.

**Step 3: Display routing decision** (MANDATORY — FIRST visible output, before any work)

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

**Optional: Dry Run Mode** — OFF by default. When enabled, show the routing decision without executing.

**Optional: Verbose Routing** — OFF by default. When enabled, explain why each alternative was rejected.

**Learning capture is automatic.** The router records nothing by hand. The `routing-decision-recorder` hook (PostToolUse:Agent) writes the `routing` decision row on every dispatch; `routing-outcome-recorder` (SubagentStop) records the success/failure outcome; `error-learner` and `review-capture` capture the rest. See the note after Phase 4 and ADR `learn-step-to-hook`.

**Gate**: Agent+skill selected. Banner displayed. Proceed to Phase 3.

---

### Phase 3: ENHANCE

**Goal**: Stack additional skills based on request signals. Use retro knowledge if present in context.

| Signal in Request | Enhancement to Add |
|-------------------|-------------------|
| Any substantive work (code, design, plan) | Add relevant retro knowledge only when it materially helps the task |
| "comprehensive" / "thorough" / "full" | Add parallel reviewers (security + business + quality) |
| "with tests" / "production ready" | Append test-driven-development + verification-before-completion |
| "research needed" / "investigate first" | Prepend research-coordinator-engineer |
| "review" with 5+ files | Use parallel-code-review (3 reviewers) |
| Diff-scope review detected (comprehensive/full review on a real diff) | Run `python3 scripts/right-size-review.py --base {base} --head {head}` (or `--files N --packages M`); dispatch the matching tier — Tier 1→parallel-code-review (3), Tier 2→Wave 1 (12), Tier 3→Wave 1+2 subset (17), Tier 4→full (27). Escalate one tier on any CRITICAL finding. No tier signal → current full behavior. |
| Complex implementation | Offer subagent-driven-development |
| "local only" / "no push" / "keep it local" / "don't commit" / "stay local" | Inject `local-only` constraint (see `shared-patterns/local-only.md`). Prepend to agent prompt: "**LOCAL-ONLY MODE.** Do not push, commit, create PRs, or deploy. All work stays on disk. Read-only git is fine." |
| Voice profile skill selected (voice-vexjoy, voice-dragonball-z, voice-andy-nemmity, etc.) | Stack `voice-writer` as the execution pipeline. Voice-writer's 13-phase pipeline is required for all voice content generation. The selected voice-* skill loads as the voice profile in Phase 1 (LOAD). |
| Vague verb + ambiguous object + no concrete file/symbol named + multiple plausible interpretations | `planning` (interview mode) — load `depth-first-interview.md` |

**Interview-mode heuristic.** Fires when: short request (<15 words), verb in `{build, design, make, fix, figure out, set up}`, object has no file/symbol/path qualifier, no acceptance criteria.

| Example | Match? | Why |
|---|---|---|
| "i'm not sure how to approach this complex build" | MATCH | Uncertainty + vague verb + no concrete target |
| "fix the typo on line 42 of foo.py" | NO | Concrete file, location, verb |
| "build a thing that does X" | MATCH | Vague verb + ambiguous object + no file named |
| "add a test for `parseConfig` in src/config.go" | NO | Concrete symbol + file + verb |
| "where do i even start with this rewrite" | MATCH | Explicit uncertainty, no concrete subject |
| "rename `cfg` to `config` in `internal/`" | NO | Concrete symbol + directory + mechanical op |

When in doubt, defer injection. False positives cost one round of friction; false negatives are recoverable via `/quick --interview`.

Before stacking, check `pairs_with` in `skills/INDEX.json`. Prefer listed pairs. Empty `pairs_with: []` means undeclared, not prohibited. Skills with built-in verification gates may not benefit from stacking.

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

**Goal**: Invoke the selected agent + skill and deliver results.

**Step 0: Execute Creation Protocol** (creation requests ONLY)

If creation signal + Simple+: (1) Write ADR at `adr/{kebab-case-name}.md`, (2) Register via `adr-query.py register`, (3) Proceed to plan. ADR hooks (`adr-context-injector`, `adr-enforcement`) handle cross-agent compliance automatically.

**Step 1: Create plan** (Simple+)

Create `task_plan.md` before execution. Skip for Trivial only.

**Step 1b: Apply quality-loop pipeline** (Medium+ code modifications)

For code modifications at Medium/Complex, load `references/quality-loop.md` as the **outer orchestration wrapper**:

- **Quality-loop** (outer) = 14-phase lifecycle: ADR → PLAN → IMPLEMENT → TEST → REVIEW → INTENT VERIFY → LIVE VALIDATE → FIX → RETEST → PR → CODEX REVIEW → ADR RECONCILE → RECORD → CLEANUP
- **Agent + skill** (inner) = domain expertise inside IMPLEMENT phase

Quality-loop absorbs Steps 0-1. The Phase 2 agent+skill selection becomes the implementation agent. Force-route skills are used INSIDE the loop.

Does NOT apply when: Trivial/Simple (use `quick`), review-only/research/debugging/content creation, or user requests simpler flow.

**Step 1b (native Workflow dispatch): run the deterministic variant when the harness supports it, else the prose pipeline.** When the Haiku router emitted a pipeline `pick` (#686), decide the executor with the ADR decision table (`harness-conditional-workflow-dispatch`):

```
pick = haiku_route.pipeline                         # #686, may be null
cap  = scripts/detect-workflow-capability.py        # env proxy: {harness, workflow_capable}
reg  = scripts/workflow-registry.py                 # auto-derived {meta.name: path}
{scope, tier} = scripts/right-size-review.py        # #688 right-sizing (review picks)
complex4 = (complexity == Complex) or (tier == 4)   # ADR native-fast-path Stage 2

if pick is not None and reg.get(pick) and cap.workflow_capable and (Workflow tool in MY tool list):
        # NAMED pipeline: env proxy AND LLM tool-list self-check (authoritative gate)
                                                            -> Workflow.run(reg[pick], {scope, tier})
elif pick is not None and reg.get(pick):                    -> run the prose pipeline markdown (unchanged)
elif pick is None and complex4 and cap.workflow_capable and (Workflow tool in MY tool list):
        # NO named pipeline + Complex/tier-4: generic native fan-out (Stage 2)
                                                            -> Workflow.run("fan-out-workflow", {scope, tier, roster})
elif pick is None and complex4:                             # Workflow tool absent -> floor
                                                            -> dispatching-parallel-agents (prose fan-out, unchanged)
else:                                                       -> agent + skill direct (simpler; unchanged)
```

`roster` is built from the Phase-3 enhancement signals (e.g. "comprehensive" → 3 reviewers with `systematic-code-review`; research → research subagents with `research-pipeline`), scaled by `tier` per `right-size-review.py`. **Each entry is `{agentType, skills: [...], lens}` — `skills` is a LIST carrying the FULL Phase-3 enhancement stack** the orchestrator would have stacked for a direct dispatch: the primary skill, plus `test-driven-development`/`verification-before-completion` when the "with tests"/"production ready" signals match, plus the per-task-type anti-rationalization patterns (Phase 3 task-type table), plus any retro/right-sizing/local-only additions. The workflow emits one `Skill("<name>")` per element of `skills` for every dispatched agent (full stack, not one bare skill), and embeds the /do mandatory injections (completeness standard, density standard, `agents/base-instructions.md` load, reference-loading instruction) into each agent prompt — so a workflow agent gets the same context a direct /do dispatch injects. The native path scales work to scope, passes schema-validated typed results in-memory (no disk round-trips), and bounds synthesis by the native token budget. `comprehensive-review-workflow.js` is the named-pipeline form; `fan-out-workflow.js` is the generic complexity-trigger form for Complex/tier-4 work with no named pipeline. The prose floor (`dispatching-parallel-agents` for fan-out, the pipeline markdown for named picks) runs identically on Codex/Gemini/Factory or when the `Workflow` tool is absent. `cap.workflow_capable` is an env-derived PROXY; the orchestrator's own tool-list check is the authoritative gate — both must hold. A `pick` with no registry entry is prose-only.

**Banner parity (R4):** expand the pipeline name → phase list for the routing banner on BOTH paths, so the banner reads identically regardless of executor. For the complexity-trigger fan-out, both the native `fan-out-workflow` and the prose `dispatching-parallel-agents` floor expand to the same phases (`fan-out → synthesize`) — the banner reads identically whether the Workflow tool runs or the floor does.

**Step 1c (inline-authored Workflow scripts): when the user explicitly asks to "run through a workflow" with no named pipeline `pick`, the orchestrator MUST dictate roster size and skill stacks — never delegate those defaults to the Workflow tool's heuristics.** The Workflow tool's authoring defaults skew toward many-skeptic adversarial fan-outs and rarely emit `Skill(...)` directives. Override both. Before emitting any inline `script:`, the orchestrator builds the same `roster` object Step 1b uses for the registered fan-out path and pins these constraints in the script:

| Constraint | Rule |
|------------|------|
| **Agent count** | Dictate explicit roster length per task class (table below). Never let the Workflow tool decide via "comprehensiveness" heuristics. |
| **Skill stacks** | EVERY `agent()` call inside the script MUST be preceded by one `Skill("<name>")` directive per element of that roster entry's `skills` list. Empty `skills` is a routing bug — fail closed and re-route. |
| **Adversarial passes** | Default to **single skeptic per finding**, not 3–5. Escalate to 3 only when the request explicitly says "adversarial," "heavy refute," or "high-stakes review" — and only on the findings that survive the first pass. |
| **Phase count** | Match the named pipeline's phase shape if a similar pipeline exists in the registry. Don't invent novel phase names when `comprehensive-review-workflow`, `fan-out-workflow`, or `research-pipeline` already covers the shape. |

Roster-size table (agent counts dictated, NOT advisory):

| Request class | Roster size | Skeptic pass |
|---------------|-------------|--------------|
| PR review (Tier 1, ≤6 files) | 3 reviewers | none default; 1 skeptic on user request |
| PR review (Tier 2–3) | 12 / 17 reviewers per `right-size-review.py` | 1 skeptic on findings flagged "Critical" only |
| PR review (Tier 4) | 27 reviewers | 1 skeptic on Critical+High findings |
| Adversarial validation of N findings | 1 skeptic × N (not 3 × N) | escalate to 3 only on user-flagged "needs heavy pushback" |
| Research fan-out | 3–5 researchers per `research-pipeline` Wave 1 | n/a |
| Generic complexity-trigger fan-out | use `fan-out-workflow` registered roster | n/a |

When the orchestrator emits an inline `script:`, the script body MUST follow this shape (skill directives in EVERY worker, count dictated by the roster):

```js
const ROSTER = [/* dictated count, NOT model-chosen */
  {agentType: "reviewer-system",       skills: ["systematic-code-review", "anti-rationalization-review"], lens: "security"},
  {agentType: "reviewer-domain",       skills: ["systematic-code-review", "anti-rationalization-review"], lens: "domain"},
  {agentType: "reviewer-perspectives", skills: ["systematic-code-review", "anti-rationalization-review"], lens: "newcomer"},
];
const findings = await parallel(ROSTER.map(r => async () => {
  for (const s of r.skills) await Skill(s);   // FULL stack, one directive per skill
  return agent(buildPrompt(r), {agentType: r.agentType, schema: FINDINGS_SCHEMA});
}));
```

If the orchestrator catches itself authoring `parallel(Array.from({length: N}, ...))` with a model-chosen N, or omitting `Skill(...)` directives, **stop and rebuild the script from the roster table above**. The Workflow tool's autonomy here is a footgun the router has to disarm.

**Step 2: Invoke agent with skill**

Dispatch the agent. MCP tool discovery is the agent's responsibility — do not inject MCP instructions from /do.

**Prepend Task Specification for Medium+ tasks.** The router has upstream context the agent lacks. Compose and prepend this block. For Simple tasks, include Intent and Acceptance if extractable. Do not invent criteria or expand scope.

```
## Task Specification (auto-extracted)

**Intent:** <one sentence: what does success look like?>
**Constraints:** <branch rules, operator-context, file paths, memory feedback>
**Acceptance criteria:** <observable: tests pass, file exists, PR merges, specific output>
**Relevant file locations:** <paths from request + expected paths>
**Operator context:** <from [operator-context] tag>
```

Extraction: Intent from verb+object. Constraints include branch safety (never merge to main), memory feedback, operator context. Acceptance = observable outcomes. For creation requests, add "Implementation must match ADR `<kebab-case-name>`."

**MANDATORY: Inject reference loading instruction for ALL dispatched agents.** Every agent prompt MUST include: "Before starting work, read your agent .md file to find the Reference Loading Table. Load EVERY reference file whose signal matches this task. Load greedily — if multiple signals match, load all matching references."

**MANDATORY: Inject the completeness standard for ALL Simple+ dispatches.** Every agent prompt MUST include: "Deliver the finished product. Ship the complete thing."

**MANDATORY: Inject the Dense-Complete Writing standard for ALL Simple+ dispatches.** Every agent prompt MUST include: "Write to the Dense-Complete Writing standard — your structural guide for everything you do. It governs your output, code comments, any skill or reference files you write, AND every one of your thinking turns: (1) shortest accurate word; (2) cut every word that carries no instruction, rule, or decision; (3) plain English, not jargon; (4) concrete over abstract; (5) heavy qualifications in separate short sentences; (6) Completeness: treat content as fixed and wording as negotiable: carry every required point through the draft, then choose the shortest plain words that say those points exactly. Say everything the task needs and not one word more. Report what changed, not how. Full rules: `skills/shared-patterns/dense-complete-writing.md`."

**MANDATORY: Inject base instructions for ALL dispatched agents.** Every agent prompt MUST include: "Before starting work, also load `agents/base-instructions.md` for universal operational rules."

**MANDATORY: Stamp the routing marker on every routed agent prompt.** Prepend verbatim: `[do-route] agent={agent} skill={skill} complexity={complexity}` (use `skill=-` when routing agent-only). This is the SOLE signal the `routing-decision-recorder` hook uses to record a `routing` decision row — dispatches without it (pr-review reviewer sub-agents, nested fan-out) are correctly excluded from route-health, and the hook reads `agent`/`skill` straight from the marker (no prompt-sniffing). Stamp it on each agent in a parallel roster.

**Token budget signal (optional, documented).** Read `orchestration.token_budget` from `.claude/settings.json` (default 500000 when absent). Subtract a rough estimate of tokens already spent this session; prepend to each dispatched agent prompt: "~{remaining} tokens available for this task; prioritize accordingly." This is an advisory signal, not a hard runtime cap — it nudges agents to right-size their own work. Keep it cheap: read the key once per session, skip injection if the key is absent and no default is desired.

```bash
TOKEN_BUDGET=$(python3 -c "import json,sys; print(json.load(open('.claude/settings.json')).get('orchestration',{}).get('token_budget',500000))" 2>/dev/null || echo 500000)
```

**Inject thinking directive.** Prepend verbatim, no framing:

| Complexity | Thinking Directive |
|---|---|
| Trivial | None (no agent) |
| Simple | "Prioritize responding quickly rather than thinking deeply. When in doubt, respond directly." |
| Medium | None (adaptive) |
| Complex | "Think carefully and step-by-step before responding; this problem is harder than it looks." |

**Category overrides** (regardless of complexity): `thinking:slow` for security work, API/schema design, migrations, 5+ file reviews, architectural decisions. `thinking:fast` for lookups, status checks, single-function renames/refactors.

Thinking class (`thinking:slow` / `thinking:fast`) is captured automatically by the routing hooks via the dispatch metadata; the router sets the directive but records nothing by hand.

**Verb-based model dispatch for Complex tasks (3+ data sources).** Extraction verbs use parallel Haiku readers; analysis verbs use single Opus agent (38% cheaper, 23% faster for extraction — A/B tested).

| Task verb class | Dispatch mode |
|---|---|
| list, count, extract, inventory, search, check, find, grep | Parallel Haiku readers → Opus synthesizer |
| review, audit, assess, analyze, debug, investigate, evaluate | Single Opus agent (direct) |

Haiku dispatch: spawn Agent with `model: "haiku"` per data source, collect extracts, synthesize with Opus. Simple/Medium: dispatch directly.

Route to agents that create feature branches. Include "commit your changes on the branch" in agent prompts for file modifications.

For `isolation: "worktree"` agents, inject `worktree-agent` skill rules: "Verify CWD contains .claude/worktrees/. Create feature branch before edits. Skip task_plan.md. Stage specific files only."

Non-org repos: up to 3 iterations of `/pr-review` → fix before PR creation. Org-gated repos (via `scripts/classify-repo.py`): require user confirmation before EACH git action.

**Step 3: Handle multi-part requests**

Detect: "first...then", "and also", numbered lists, semicolons. Sequential dependencies execute in order. Independent items launch multiple Task tools in single message. Max parallelism: 10 agents.

**Step 4: Auto-Pipeline Fallback** (no match AND complexity >= Simple)

Invoke `auto-pipeline` for unmatched requests. If no pipeline matches, fall back to closest agent + verification-before-completion.

When uncertain: **ROUTE ANYWAY** with verification-before-completion as safety net.

**Gate**: Agent invoked, results delivered. Learning capture runs automatically (see note below) — the router does not record by hand.

---

### Learning Capture (automatic — no router step)

Learning capture is fully automatic via hooks. The router records nothing by hand:

| Capture | Hook | Event |
|---------|------|-------|
| Routing decision row (`{agent}:{skill}`, `category=effectiveness`) | `routing-decision-recorder` | PostToolUse:Agent |
| Routing outcome - validate pending (decision-row exists, re-queue late rows) | `routing-outcome-recorder` | SubagentStop |
| Routing outcome - finalize (boost/decay) on the next user turn | `routing-outcome-finalizer` | UserPromptSubmit |
| Routing outcome - session-end fallback for autonomous runs | `session-learning-recorder` | Stop |
| Right-sizing tier feedback (when a `rightsizing:` banner is emitted) | `routing-decision-recorder` | PostToolUse:Agent |
| Tool errors and fixes | `error-learner` | PostToolUse |
| Review findings | `review-capture` | PostToolUse:Agent |

These keep the routing feedback loop fed: `learning-db.py route-health` reads the decision rows (denominator) and the boost/decay outcomes (numerator) the hooks write. See ADR `learn-step-to-hook`.

**Outcome fidelity (note).** A routed dispatch's outcome is resolved on the user's NEXT turn from three deterministic inputs - this dispatch's tool errors, the user's reaction, and whether they re-routed the same intent - at zero LLM cost. `routing-decision-recorder` writes the decision row; `routing-outcome-recorder` (SubagentStop) records a *provisional* pending outcome (no eager boost/decay); `routing-outcome-finalizer` (UserPromptSubmit) finalizes it once: **failure** on tool errors OR a clear rejection/rework/re-route, **success** otherwise (explicit acceptance, or a neutral/new topic - no complaint = accepted, matching the prior LLM step's default). A Stop fallback resolves any dispatch with no next prompt (autonomous runs) from the error flag alone. Residual: the reaction detector is **deterministic and high-precision** - it fires failure only on strong, unambiguous markers and errs toward success on ambiguity, so it is conservative rather than full semantic judgment. It does not eagerly score "no error = success" anymore.

**OPTIONAL (not a gate):** curated free-text insight and graduation of review findings are now opt-in, handled via the `retro` skill (`retro graduate`), not a forced router step:

```bash
python3 ~/.claude/scripts/learning-db.py learn --skill go-patterns "insight"
python3 ~/.claude/scripts/learning-db.py learn --agent golang-general-engineer "insight"
```

Routing rows are `category=effectiveness`, which `retro graduate` excludes — so these never require graduation.

---

## Error Handling

### Error: "No Agent Matches Request"
Cause: Request domain not covered by any agent
Solution: Check INDEX files and `INDEX files` for near-matches. Route to closest agent with verification-before-completion. Report the gap.

### Error: "Force-Route Conflict"
Cause: Multiple force-route triggers match the same request
Solution: Apply most specific force-route first. Stack secondary routes as enhancements if compatible.

### Error: "Plan Required But Not Created"
Cause: Simple+ task attempted without task_plan.md
Solution: Stop execution. Create `task_plan.md`. Resume routing after plan is in place.

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/progressive-depth.md`: Progressive depth escalation protocol
- `agents/INDEX.json`: Agent triggers, metadata, and `not_for` disambiguation
- `skills/INDEX.json`: Skill triggers, force-route flags, pairs_with, and `not_for` disambiguation
- `skills/workflow/SKILL.md`: Workflow phases, triggers, composition chains
- `skills/workflow/references/pipeline-index.json`: Pipeline metadata, triggers, phases
- `scripts/routing-manifest.py`: Generates compact routing manifest from INDEX files (single source of truth)
