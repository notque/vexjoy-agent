# Design Philosophy

The principles behind the toolkit's architecture. These aren't aspirational. They're the decisions that shaped every agent, skill, hook, and pipeline in the system.

## Zero-Expertise Operation

The system should require no specialized knowledge from the user. Say what you want done. The system handles the rest.

A user who has never heard of agents, skills, hooks, pipelines, routing tables, or INDEX files should get the same quality output as someone who built them. The entire internal machinery — 69 agents, 136 skills, 50 hooks, 27 pipelines — exists to absorb complexity that would otherwise fall on the user.

**What this means in practice:**

- The user says "fix this bug." The system classifies it, selects a debugging agent, applies a systematic methodology, creates a branch, runs tests, reviews the fix, and presents a PR. The user never chooses an agent or invokes a skill by name.
- The user says "review this PR." The system dispatches 20+ reviewers across 3 waves covering security, business logic, architecture, performance, naming, error handling, and test coverage. The user never configures which reviewers to run.
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

## The Handyman Principle

Context is a scarce resource, not a dumpster.

The anti-pattern: stuffing thousands of lines of unfocused instructions into a single system prompt. It causes confusion and degrades AI performance.

The solution: only pull the relevant information for the specific task. This is why the toolkit has specialized agents instead of one giant system prompt. Each agent carries exactly the domain knowledge needed. Go idioms for Go work, Kubernetes patterns for K8s work, nothing else.

Three mechanisms enforce this:
- **Agents**: specialized instruction files tailored to specific domains, loaded only when their triggers match
- **Skills**: deterministic tools (actual programs) rather than text advice, invoked only when their workflow applies
- **Progressive Disclosure**: summary in the main file, details in `references/` subdirectory. Right context at the right time, not everything at once

## Tokens Are Cheap, Quality Is Expensive

Spending tokens to ensure correctness is economically superior to saving tokens and shipping bugs.

| Typical Mindset | This Toolkit's Mindset |
|-----------------|----------------------|
| Minimize tokens, maximize speed | Minimize bugs, accept token cost |
| One review pass | 20+ agents in 3 waves |
| Skip if it looks right | Verify before claiming done |
| YAGNI for verification | YAGNI for features, never for verification |

This does NOT mean "stuff more context." It means: dispatch parallel review agents, run deterministic validation scripts, create plans before executing, and never skip quality gates to save tokens. The token spend goes toward **breadth of analysis**, not depth of prompt.

The arithmetic: a bug found in production costs 10x more in debugging time than the tokens spent on a thorough pre-merge review.

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

The solution: make specialist selection explicit using keyword-matching routing. Choose "which agent has the right mental scaffolding" rather than "which agent is smartest."

- **Agents** encode domain-specific patterns (Go idioms, Python conventions, Kubernetes knowledge)
- **Skills** enforce process methodology (debugging phases, refactoring steps, review waves)

This separation enables consistent methodology across domains without duplicating approaches or requiring per-task prompt engineering.

> Agent-specific patterns (anti-patterns, MCP tool requirements, domain conventions) belong in the agent's own markdown file, not in the router. The router selects the agent; the agent carries its own domain knowledge. This keeps the router focused and prevents it from growing into a monolithic prompt that degrades routing quality.

## Agents Carry the Knowledge, Not the Model

The base LLM is a generalist. It knows a little about everything and a lot about nothing specific. An agent's job is to close that gap — not by declaring "I am an expert in X" but by carrying the actual expert knowledge as structured context.

A thin wrapper that says "You are a Go expert" adds nothing. The model already knows generic Go. What it doesn't know is: which go-bits helpers exist in this project, that `rows.Close()` silently discards errors, that sapcc structs should be unexported when only the interface is public, that Go 1.22 introduced `range-over-int` and `slices.SortFunc` should replace `sort.Slice`. That knowledge lives in the agent file, in its reference files, and in the retro learnings injected at session start.

**The principle:** agents and skills are knowledge transfer mechanisms. They inject domain-specific information that makes the LLM perform as if it has expertise it doesn't natively possess. The quality of output is proportional to the quality of knowledge attached to the prompt — not to the model's pre-training coverage of that domain.

**What high-context looks like:**
- Version-specific idiom tables ("Go 1.22+: use `slices.SortFunc`, not `sort.Slice`")
- Concrete anti-pattern catalogs with detection commands (`grep -r "interface{}" --include="*.go"`)
- Error → fix mappings from real incidents ("PR #707 found that...")
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

**Deployment discipline:**

The correct order is always: deploy the file, verify it compiles, then register in settings.json. Never the reverse. A registered hook pointing to a nonexistent file causes Python's "file not found" exit code 2 — identical to an intentional block — on every single tool call. This deadlocks the entire session. The toolkit includes `scripts/register-hook.py` specifically to make this ordering mechanical rather than advisory, because advisory patterns fail exactly when you're moving fast and not thinking about them.

## Open Sharing Over Individual Ownership

Ideas matter less than open sharing. In an AI-assisted world, provenance becomes invisible. The toolkit is open source because:
- Convergent evolution is inevitable (others will build similar things independently)
- Knowledge should spread and be understood, not gatekept
- Collective progress beats individual credit

We're all working through this together.
