# Design Philosophy

> **Audience:** This document is for contributors and developers who want to understand *why* the toolkit is built the way it is. If you're using the toolkit, start with [start-here.md](start-here.md). If you're building agents or skills, see [for-developers.md](for-developers.md).

The principles behind the toolkit's architecture. These aren't aspirational. They're the decisions that shaped every agent, skill, hook, and pipeline in the system.

## Zero-Expertise Operation

The system should require no specialized knowledge from the user. Say what you want done. The system handles the rest.

A user who has never heard of agents, skills, hooks, pipelines, routing tables, or INDEX files should get the same quality output as someone who built them. The entire internal machinery — agents, skills, hooks, and pipelines — exists to absorb complexity that would otherwise fall on the user.

**What this means in practice:**

- The user says "fix this bug." The system classifies it, selects a debugging agent, applies a systematic methodology, creates a branch, runs tests, reviews the fix, and presents a PR. The user never chooses an agent or invokes a skill by name.
- The user says "review this PR." The system dispatches specialized reviewers across multiple waves covering security, business logic, architecture, performance, naming, error handling, and test coverage. The user never configures which reviewers to run.
- The user says "write a blog post about X." The system researches, drafts in a calibrated voice, validates against voice patterns, and presents the result. The user never loads a voice profile or runs a validation script.

**The test for every feature we build:** does this require the user to know something internal? If yes, redesign it so it doesn't.

This is not about hiding complexity. It's about absorbing it. The hooks, agents, and skills exist precisely so that expertise is encoded in the system rather than required from the person using it. A first-time user and a power user should both get production-quality results — the power user just understands *why* it works.

**Automation corollary:** anything that can fire automatically, should. Gates enforce themselves via hooks. Context injects itself via SessionStart and UserPromptSubmit handlers. Quality checks run via CI. Learning happens via PostToolUse capture. The user's job is to describe intent. The system's job is everything else.

## Everything That Can Be Deterministic, Should Be

The foundational principle. LLMs should orchestrate deterministic programs, not simulate them.

**Division of labor:**
- **Solved problems** (delegate to code): file searching, test execution, build validation, data parsing, frontmatter checking, path existence
- **Unsolved problems** (reserve for LLMs): contextual diagnosis, design decisions, pattern interpretation, code review judgment

The question is never "Can the LLM do this?" It's "Should the LLM do this?" If a process is deterministic and measurable, write a Python script for it. This keeps variance confined to decisions rather than execution.

**Four-layer architecture:**

| Layer | Role | Example |
|-------|------|---------|
| Router | Classifies and dispatches | `/do` skill |
| Agent | Domain-specific constraints | `golang-general-engineer` |
| Skill | Deterministic methodology/workflow | `systematic-debugging` |
| Script | Concrete operations with predictable output | `scripts/learning-db.py` |

LLMs orchestrate. Programs execute.

## Load Only What You Need

A handyman brings tools for the specific job, not every tool they own. Context works the same way — it's a scarce resource, not a dumpster.

The anti-pattern: stuffing thousands of lines of unfocused instructions into a single system prompt. It causes confusion and degrades AI performance.

The solution: only pull the relevant information for the specific task. This is why the toolkit has specialized agents instead of one giant system prompt. Each agent carries exactly the domain knowledge needed. Go idioms for Go work, Kubernetes patterns for K8s work, nothing else.

Three mechanisms enforce this:
- **Agents**: specialized instruction files tailored to specific domains, loaded only when their triggers match
- **Skills**: workflow methodologies that invoke deterministic scripts (Python CLIs, validation tools) rather than relying on LLM judgment alone, activated only when their workflow applies
- **Progressive Disclosure**: SKILL.md contains the workflow orchestration and tells the model *when* to load deep context. Detailed catalogs, agent rosters, specification tables, and output templates live in `references/` and are loaded only when the current workflow phase needs them. A skill with 26 chart types keeps the selection logic in SKILL.md and each chart's parameter spec in its own reference file — the model loads only the spec for the chart it selected. A review skill with 4 waves keeps the orchestration in SKILL.md and each wave's agent roster in a separate reference file — Wave 2 agents don't consume tokens during Wave 1

## Tokens Are Cheap, Quality Is Expensive

Spending tokens to ensure correctness is economically superior to saving tokens and shipping bugs.

| Typical Mindset | This Toolkit's Mindset |
|-----------------|----------------------|
| Minimize tokens, maximize speed | Minimize bugs, accept token cost |
| One review pass | Multiple specialized agents in waves |
| Skip if it looks right | Verify before claiming done |
| YAGNI for verification | YAGNI for features, never for verification |

This does NOT mean "stuff more context." It means: dispatch parallel review agents, run deterministic validation scripts, create plans before executing, and never skip quality gates to save tokens. The token spend goes toward **breadth of analysis**, not depth of prompt.

The arithmetic: for non-trivial production changes, thorough pre-merge review consistently pays for itself. The cost scales with the bug class — a concurrency issue in production costs orders of magnitude more than the tokens that would have caught it.

## Everything Should Be a Pipeline

Complex work decomposes into phases. Phases have gates. Gates prevent cascading failures.

**Why pipelines over ad-hoc execution:**
- Each phase produces saved artifacts (files on disk, not just context)
- Gates enforce prerequisites before proceeding
- Phases can be parallelized when independent
- Failures are isolated to the phase that caused them
- Progress is visible and resumable

**When to pipeline:**
- Any task with 3+ distinct phases
- Any task mixing deterministic and LLM work
- Any task where intermediate artifacts have value
- Any task that benefits from parallel execution

**When NOT to pipeline:**
- Reading a file the user named by path
- Simple lookups with clear answers
- One-step operations with no meaningful phases

The standard pipeline template:

```
PHASE 1: GATHER    → Parallel agents for research/analysis
PHASE 2: COMPILE   → Structure findings
PHASE 3: EXECUTE   → Do the work
PHASE 4: VALIDATE  → Deterministic checks + LLM judgment
PHASE 5: DELIVER   → Final output with validation report
```

## Both Deterministic AND LLM Evaluation

Quality assessment works best as a two-tier system:

**Tier 1, Deterministic (fast, free, CI-friendly):**
- Does the frontmatter parse?
- Do referenced files exist?
- Are required sections present?
- Is the component registered in routing?
- Are there anti-pattern and error-handling sections?

**Tier 2, LLM-judged (deep, nuanced, expensive):**
- Is the content actually useful?
- Are the anti-patterns domain-specific or generic filler?
- Does the error handling cover real scenarios?
- Is the agent's expertise calibrated correctly?

Neither tier replaces the other. Deterministic checks catch mechanical failures (broken paths, missing sections) that waste LLM evaluation tokens. LLM evaluation catches quality failures (shallow content, wrong domain focus) that deterministic checks can't see.

The pipeline: **Deterministic first, fix failures, LLM evaluation, fix findings, final score.**

## Specialist Selection Over Generalism

Same Claude prompts produce different results on different days. Generalist improvisation is unreliable.

The solution: make specialist selection explicit using intent-based routing. The router reads agent descriptions and applies LLM judgment to match task intent — not keyword triggers. Choose "which agent has the right mental scaffolding" rather than "which agent is smartest."

- **Agents** encode domain-specific patterns (Go idioms, Python conventions, Kubernetes knowledge)
- **Skills** enforce process methodology (debugging phases, refactoring steps, review waves)

This separation enables consistent methodology across domains without duplicating approaches or requiring per-task prompt engineering.

> Agent-specific patterns (anti-patterns, MCP tool requirements, domain conventions) belong in the agent's own markdown file, not in the router. The router selects the agent; the agent carries its own domain knowledge. This keeps the router focused and prevents it from growing into a monolithic prompt that degrades routing quality.

## Agents Carry the Knowledge, Not the Model

The base LLM is a generalist. It knows a little about everything and nothing deeply about any specific domain. An agent's job is to close that gap — not by declaring "I am an expert in X" but by carrying the actual expert knowledge as structured context.

A thin wrapper that says "You are a Go expert" adds nothing. The model already knows generic Go. What it doesn't know is: which go-bits helpers exist in this project, that `rows.Close()` silently discards errors, that sapcc structs should be unexported when only the interface is public, that Go 1.22 introduced `range-over-int` and `slices.SortFunc` should replace `sort.Slice`. That knowledge lives in the agent file, in its reference files, and in the retro learnings injected at session start.

**The principle:** agents and skills are knowledge transfer mechanisms. They inject domain-specific information that makes the LLM perform as if it has expertise it doesn't natively possess. The quality of output is proportional to the quality of knowledge attached to the prompt — not to the model's pre-training coverage of that domain.

**What high-context looks like:**
- Version-specific idiom tables ("Go 1.22+: use `slices.SortFunc`, not `sort.Slice`")
- Concrete anti-pattern catalogs with detection commands (`grep -r "interface{}" --include="*.go"`)
- Error → fix mappings from real incidents captured in retro learnings
- Project-specific conventions extracted from PR review history

**What thin wrappers look like:**
- "You are an expert Go developer" (adds zero information)
- General best practices the model already knows
- Padding to fill required sections

**Progressive disclosure** enforces the balance: the main agent file stays navigable (under 10k words) with the concrete tables, anti-patterns, and decision rules. Deep reference material lives in `references/` subdirectories, loaded only when the task requires it. The agent carries exactly what's needed — no more, no less.

## Anti-Rationalization as Infrastructure

The biggest risk is not malice but rationalization. "Already done" (assumption, not verification). "Code looks correct" (looking, not testing). "Should work" (should, not does).

Anti-rationalization is not a nice-to-have. It's infrastructure, auto-injected into every code modification, review, security, and testing task. The toolkit makes it structurally difficult to skip verification, not just culturally discouraged.

## Router as Orchestrator, Not Worker

The `/do` router's only job is to classify requests and dispatch them to agents. It does not read code, edit files, run analysis, or handle tasks directly. The main thread is an orchestrator that manages agents — it never does work itself.

**Division of responsibility:**
- **Main thread (/do)**: Classify request → select agent+skill → dispatch → evaluate result → route again if needed → report to user
- **Agents**: Execute tasks using their domain expertise, skills, MCP tools, and pipelines
- **Skills**: Provide methodology (debugging phases, review waves, TDD cycles) that agents follow
- **Pipelines**: Multi-phase workflows that agents run through

**Why this matters:**
- When the main thread does work directly, it bypasses the agent's domain knowledge, the skill's methodology, and the pipeline's phase gates
- Every task that isn't routed to an agent is a missed opportunity: the agent can't improve, the skill can't be validated, the pipeline can't be refined
- The main thread has no domain expertise — it only knows how to route. Agents have the expertise.

**The test:**
If the main thread is reading source code, editing files, running scripts for analysis, or doing any work beyond routing — something is wrong. Stop and dispatch an agent.

## Hooks for Gates, LLMs for Judgment

Instructions can be rationalized past. Exit codes cannot.

When a skill says "check if synthesis.md exists before implementing," the LLM *can* construct an argument for why this specific case doesn't need it. When a PreToolUse hook checks the same condition and returns exit code 2, the tool physically does not execute. No argument gets past a blocked syscall.

**The division:**

| Mechanism | Best for | Why |
|-----------|----------|-----|
| Hooks (exit 2 = block) | Binary gates: does the file exist? Is the format valid? Is the bypass env var set? | Deterministic, unbypassable, sub-50ms |
| LLM instructions | Judgment calls: is this the right approach? Is the code quality sufficient? Should we route here? | Contextual, nuanced, adaptable |

**Hooks are fragile to deploy, robust in operation.** The deployment pain points are real — registration ordering (file must exist before settings.json entry), stdin format parsing, exit code semantics, stderr-only debugging. But once deployed, they work every time. Skill instructions are the opposite: easy to write, unreliable in enforcement.

**The hookification test:** if a gate checks for a file, a status, or a structural property — and the answer is yes/no with no judgment required — it should be a hook. If it requires reading code and making a contextual decision, it stays in the skill.

**Deployment discipline:** Hooks must be deployed (file exists, compiles) before registration in settings.json. Out-of-order deployment deadlocks the session — see "When Things Go Wrong" for details. The toolkit includes `scripts/register-hook.py` to make this ordering mechanical rather than advisory.

## When Things Go Wrong

The principles above describe what the system does when it works. Equally important is knowing what broken looks like.

**Routing misclassification:** The router picks the wrong agent. The output looks plausible but applies the wrong domain expertise. Signal: unexpected agent in the routing banner, or output that doesn't match the domain of the request. Recovery: re-invoke with explicit domain context ("this is a Python issue, not Go").

**Hook deadlock:** A registered hook points to a nonexistent file. Every tool call returns exit code 2 (block). The session appears frozen — nothing executes. Recovery: check `~/.claude/settings.json` for recently added hooks, verify the `.py` file exists at the registered path. Use `scripts/register-hook.py` to fix ordering.

**Pipeline stall:** A phase gate blocks progress because a prerequisite artifact is missing or malformed. Signal: the same phase reruns without advancing. Recovery: check the artifact file the gate expects, fix or create it, then resume.

**Learning compounding:** A misrouted request gets recorded in `learning.db`, which reinforces the wrong routing in future sessions via retro-knowledge injection. Signal: the same misroute happens repeatedly across sessions. Recovery: query routing decisions with `scripts/learning-db.py` and delete or reweight incorrect entries.

**Stale INDEX files:** A new agent or skill was added but the INDEX wasn't regenerated. The router can't find the component. Signal: requests that should match a known agent get routed to the fallback. Recovery: run `scripts/generate-agent-index.py` and `scripts/generate-skill-index.py`.

## Skills Are Self-Contained Packages

Everything a skill needs lives inside the skill directory. Scripts, viewer templates, bundled agents, reference files, assets — all co-located. Nothing leaks into repo-level `scripts/` or a separate `assets/` directory.

```
skills/my-skill/
├── SKILL.md              # The orchestrator — workflow + when to load references
├── agents/               # Subagent prompts used only by this skill
├── scripts/              # Deterministic CLI tools this skill invokes
├── assets/               # Templates, HTML viewers, static files
└── references/           # Deep context loaded on demand
```

**The orchestrator pattern:** SKILL.md is a thin workflow orchestrator, not a monolithic document. It tells the model *what to do* (phases, gates, decisions) and *when to load deep context* (reference files). The heavy content — detailed catalogs, agent dispatch prompts, output templates, specification tables — lives in `references/` and gets loaded only when the current phase needs it.

This is the difference between a skill that works and a skill that works *efficiently*:

| Approach | Token Cost | Quality |
|----------|-----------|---------|
| Everything in SKILL.md | High — full content loaded on every invocation | Good but wasteful |
| Thin SKILL.md, no references | Low — but missing context | Degraded — lost domain knowledge |
| **Orchestrator + references** | **Proportional to task** — load what the phase needs | **Best — full knowledge, minimal waste** |

Making a skill shorter by deleting content is not progressive disclosure — it's content loss. Progressive disclosure means the content still exists, organized so only the relevant slice enters the context window at any given phase.

**Example:** A review skill with 4 waves of agents keeps the wave orchestration logic in SKILL.md (~500 lines) and puts each wave's agent roster and dispatch prompts in separate reference files (`references/wave-1-foundation.md`, `references/wave-2-deep-dive.md`). When executing Wave 1, only the Wave 1 reference is loaded. Wave 2's agents don't consume tokens until Wave 2 begins.

**Why this matters:** A skill that depends on scripts scattered across the repo is fragile to move, hard to test, and impossible to evaluate in isolation. When everything is bundled, the skill can be:
- Copied to another project and it works
- Tested via `run_eval.py` against its own workspace
- Reviewed as a single unit — all the tooling is visible in one tree
- Deleted without orphaning dependencies elsewhere

**Repo-level `scripts/`** is reserved for toolkit-wide operations (learning-db.py, sync-to-user-claude.py, INDEX generation) — tools that operate on the system as a whole, not on a single skill's workflow.

## Workflow First, Constraints Inline

Skill documents place the workflow (Instructions/Phases) immediately after the frontmatter. Constraints appear inline within the phases they govern, with reasoning attached ("because X"), not in a separate upfront section.

**Measured result:** A/B/C testing on Go code generation showed workflow-first ordering (C) swept constraints-first ordering (B) 3-0 across simple, medium, and complex prompts. Agent blind reviewers consistently scored workflow-first higher on testing depth, Go idioms, and benchmark coverage.

**The ordering:**

```
1. YAML frontmatter           (What + When)
2. Brief overview              (How — one paragraph)
3. Instructions/Phases         (The workflow, constraints inline with reasoning)
4. Reference Material          (Commands, guides — or pointers to references/)
5. Error Handling              (Failure context)
6. References                  (Pointers to bundled files)
```

**Why it works:** The model encounters the task structure before any constraint framework. Constraints appear at the decision point where they apply — "use table-driven tests because they make adding cases trivial" inside the testing phase, not in a separate Hardcoded Behaviors section 200 lines earlier. Attaching reasoning ("because X") lets the model generalize constraints to situations the skill author didn't anticipate.

**What was removed:** Operator Context sections (Hardcoded/Default/Optional taxonomy), standalone Anti-Patterns sections, Anti-Rationalization tables, and Capabilities & Limitations boilerplate. These were structural overhead that separated constraints from the workflow steps where they apply.

**Where the content went:** Every constraint was distributed inline to the workflow step where it matters. Anti-pattern wisdom became reasoning attached to the relevant instruction. Nothing was deleted — it was reorganized to be at point-of-use.

**Progressive disclosure completes the picture:** Workflow-first ordering keeps SKILL.md navigable. For skills exceeding ~500 lines, detailed catalogs, agent rosters, and specification tables move to `references/` files. The SKILL.md workflow tells the model when to load each reference — "Read `references/wave-1-foundation.md` for the agent list and dispatch prompts." The model gets the orchestration logic upfront and loads deep context only when the current phase needs it.

## One Domain, One Component

The system prompt token budget is finite. Every agent description and every skill description appears in the system prompt at session start. With 68 agents and 171 skills, description bloat directly degrades routing quality and consumes tokens before any work begins.

The consolidation principle: **one domain = one agent or skill + many reference files loaded on demand.** Never create multiple agents or skills for the same domain.

```
PROGRESSIVE DISCLOSURE ARCHITECTURE
====================================

Session Start (system prompt):
  - Agent descriptions: 60-100 chars each, loaded always
  - Skill descriptions: 60-120 chars each, loaded always
  - Total budget: <15k tokens

Agent/Skill Invocation (on-demand):
  - Full agent body: loaded when agent is dispatched
  - references/*.md: loaded when agent reads them based on task context
  - Full skill body: loaded when skill is invoked via Skill tool

NEVER put in descriptions what can go in the body.
NEVER put in the body what can go in references/.
NEVER create a new component when a reference file on an existing one suffices.
```

**The pattern:** When a domain has multiple sub-concerns (e.g., Perses has dashboards, plugins, operator, core), create ONE umbrella component with a `references/` subdirectory. Each sub-concern gets its own reference file, loaded only when the task touches that sub-concern.

```
agents/
├── perses-engineer.md                    # One umbrella agent
└── perses-engineer/
    └── references/
        ├── dashboards.md                 # Loaded when task is about dashboards
        ├── plugins.md                    # Loaded when task is about plugins
        ├── operator.md                   # Loaded when task is about the operator
        └── cue-schemas.md               # Loaded when task is about CUE
```

**The anti-pattern:** Creating separate agents or skills for each sub-concern.

```
agents/
├── perses-dashboard-engineer.md          # NO — split pollutes system prompt
├── perses-plugin-engineer.md             # NO — each adds 60-100 chars to every session
├── perses-operator-engineer.md           # NO — routing quality degrades with count
└── perses-cue-engineer.md               # NO — use references/ instead
```

**Why this matters:**

- Each additional component adds its description to every session's system prompt, whether or not that session will ever touch that domain
- The `/do` router has its own routing tables. Descriptions do not need to carry routing context -- the router matches intent to the right component without help from the description
- Reference files cost zero tokens at session start and full tokens only when the task requires them. This is the correct trade-off

**Before creating any new agent or skill:** Check whether an existing umbrella component already covers the domain. If it does, add a reference file. If it does not, create the umbrella component with references/ from the start.

## Open Sharing Over Individual Ownership

Ideas matter less than open sharing. In an AI-assisted world, provenance becomes invisible. The toolkit is open source because:
- Convergent evolution is inevitable (others will build similar things independently)
- Knowledge should spread and be understood, not gatekept
- Collective progress beats individual credit

We're all working through this together.
