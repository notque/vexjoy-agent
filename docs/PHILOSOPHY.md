# Design Philosophy

The principles behind the toolkit's architecture. These aren't aspirational. They're the decisions that shaped every agent, skill, hook, and pipeline in the system.

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

## High-Context Agents, Not Big Agents

Agents should be rich and detailed within their domain. Comprehensive Go version-by-version guidelines, specific anti-pattern tables with detection commands, concrete error catalogs with fix instructions.

But they should NOT be big for the sake of being big.

**The difference:**
- **High-context**: every line serves a purpose. Tables of version-specific idioms. Concrete forbidden patterns with `grep` commands to detect them. Error catalogs with exact fix instructions.
- **Big**: verbose explanations of general concepts. Repeating what the LLM already knows. Padding to fill sections.

Progressive disclosure enforces this: main file stays navigable (under 10k words), reference files carry the deep material. The agent loads what it needs when it needs it.

## Anti-Rationalization as Infrastructure

The biggest risk is not malice but rationalization. "Already done" (assumption, not verification). "Code looks correct" (looking, not testing). "Should work" (should, not does).

Anti-rationalization is not a nice-to-have. It's infrastructure, auto-injected into every code modification, review, security, and testing task. The toolkit makes it structurally difficult to skip verification, not just culturally discouraged.

## Open Sharing Over Individual Ownership

Ideas matter less than open sharing. In an AI-assisted world, provenance becomes invisible. The toolkit is open source because:
- Convergent evolution is inevitable (others will build similar things independently)
- Knowledge should spread and be understood, not gatekept
- Collective progress beats individual credit

We're all working through this together.
