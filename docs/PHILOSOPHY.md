# Design Philosophy

The decisions that shaped every agent, skill, hook, and pipeline. Not guidelines. Architecture. A coherent viewpoint enables iteration better than unconnected rules ever will.

For what I do, these principles are non-negotiable. For what you do, they might be different. But this is what works here, tested against real output, measured against real failures.

---

## Zero-Expertise Operation

The system requires no specialized knowledge from the user.

Say what you want done. The system handles the rest. A user who has never heard of agents, skills, hooks, or routing tables should get the same quality output as someone who built them.

In practice:

- "Fix this bug." The system classifies, selects a debugging agent, applies methodology, creates a branch, runs tests, reviews the fix, presents a PR. The user never chooses an agent or invokes a skill by name.
- "Review this PR." The system dispatches specialized reviewers across multiple waves covering security, business logic, architecture, performance, naming, error handling, test coverage. The user never configures which reviewers to run.
- "Write a blog post about X." The system researches, drafts in a calibrated voice, validates against voice patterns, presents the result. The user never loads a voice profile or runs a validation script.

The test: does this feature require the user to know something internal? If yes, redesign it so it doesn't.

A first-time user and a power user both get production-quality results. The power user just understands why it works.

**Automation corollary.** Anything that can fire automatically, should. Gates enforce themselves via hooks. Context injects itself via SessionStart and UserPromptSubmit handlers. Quality checks run via CI. Learning happens via PostToolUse capture. The user's job is to describe intent. The system's job is everything else.

---

## Plain English Is the Interface

If a user has to learn special syntax, prompt engineering tricks, or insider vocabulary to get good results, the design failed.

Plain English is not a fallback mode. It is the primary interface.

The router treats raw human intent as its input signal. "Make this faster" should get the same quality routing as "/do dispatch performance-agent with profiling skill against src/server.go." The second form is an escape hatch for power users, not the intended path.

In practice:

- "This test is flaky, help" gets the same debugging methodology as someone who knows the systematic-debugging skill exists.
- Users should never need system-prompt preambles ("You are an expert in..."). If they do, routing failed.
- If rephrasing a natural request into a structured format produces better results, that is a router bug. Not a user skill issue. A router bug.

The test: a first-time user's request and the same request rewritten by someone who has read every agent file. If the rewritten version routes better, something upstream needs fixing.

---

## Everything That Can Be Deterministic, Should Be

The foundational principle. LLMs orchestrate deterministic programs. They do not simulate them.

**Division of labor:**

| Problem type | Handler | Examples |
|---|---|---|
| Solved (deterministic, measurable) | Scripts | File searching, test execution, build validation, data parsing, frontmatter checking, path existence |
| Unsolved (contextual, judgment-requiring) | LLMs | Contextual diagnosis, design decisions, pattern interpretation, code review judgment |

The question is never "Can the LLM do this?" The question is "Should it?" If deterministic and measurable, write a script. Variance stays confined to decisions, not execution.

**Four-layer architecture:**

| Layer | Role | Example |
|---|---|---|
| Router | Classifies and dispatches | `/do` skill |
| Agent | Domain-specific constraints | `golang-general-engineer` |
| Skill | Deterministic methodology/workflow | `systematic-debugging` |
| Script | Concrete operations with predictable output | `scripts/learning-db.py` |

LLMs orchestrate. Programs execute.

For large mechanical sweeps: if the change can be expressed as a detector plus a rewrite rule, use a script. Repo-wide edits should not be LLM hand-edits. Scripts find candidates and apply deterministic transformations. LLMs handle only the exception set requiring judgment.

The test: is this operation deterministic? Does it produce the same output given the same input? If yes, it belongs in a script, not a prompt.

---

## Triple-Validation Extraction Gate

When an LLM extracts patterns, it produces more than belongs in the final artifact. Voice traits, codebase conventions, retro learnings. Without a gate, coincidence ships alongside signal.

A pattern earns its place only if it passes three checks:

1. **Recurrence.** The pattern appears in at least two distinct samples or contexts. One occurrence is an anecdote, not a rule.
2. **Generative power.** The pattern predicts new decisions or output the source has not produced yet. A trait that only describes existing samples is a summary, not a model.
3. **Exclusivity.** The pattern distinguishes the subject from peers in the same category. A "rule" that every Go codebase, every tech blogger, or every retro shares is not domain knowledge. It is background.

A pattern that fails any check is demoted or dropped. Applied as a deterministic phase, not a vibe check.

In practice:

- `create-voice` runs every candidate trait through `references/extraction-validation.md` before it gets written to the voice profile. A "uses lists frequently" candidate that fails exclusivity (every tech blogger uses lists) gets dropped, even if recurrence is high.
- `codebase-analyzer` discovers patterns by counting occurrences across files. The count is the recurrence check, codified.
- Retro graduation requires a learning to fire across at least two sessions and to produce a falsifiable rule before it leaves `learning.db` and enters an agent's reference file. A one-off observation stays in the database. Only triple-validated entries graduate into prompts.

Five high-confidence traits beat twenty plausible ones. The five drive correct downstream decisions. The twenty force the model to pick which to honor.

The test: can you name which of the three checks this pattern passed? If you cannot, it has not earned its place.

---

## Deterministic Phase Checkpoints

Between any parallel-gather phase and any synthesis phase, insert a script. The script walks the artifact directory, counts what is there, computes ratios, surfaces conflicts, emits a Markdown table.

The table is the gate. Synthesis does not begin until the table looks right.

The script answers questions the LLM should not be guessing:

- How many sources did each parallel agent return?
- What is the primary-to-secondary ratio across the corpus?
- Which claims appear in only one source (low corroboration)?
- Where do sources directly contradict each other?

Counting problems belong to scripts. The Markdown table makes the count auditable. The model reads it and decides whether to proceed. But it never invents the count.

In practice:

- `research-pipeline` Phase 1.5 runs `scripts/research-stats-checkpoint.py` between GATHER and SYNTHESIZE. The script walks `research/{topic}/`, emits a per-agent source table, refuses to mark the phase complete if any agent returned fewer sources than the configured floor.
- `voice-writer` Phase 2 (GATHER to VALIDATE) uses the same checkpoint to confirm sample coverage across modes before any prose generation begins. A profile with three samples in one mode and zero in another stalls at the gate. The table shows the gap. The operator either supplies more samples or accepts the narrowed scope explicitly.
- The gate is structural, not advisory. A phase that the script flags as incomplete does not advance because the table is the artifact the next phase reads, and the next phase's instructions require the table to show passing counts.

The test: is there a script between your gather and your synthesis? Does it emit a table? Does the pipeline stop if the table shows failing counts?

---

## Breadth Over Depth

Tokens buy more value as specialists in parallel than as longer prompts to a single agent.

Narrow focused context beats unfocused lengthy context. Every time.

| Old Framing | New Framing |
|---|---|
| Minimize bugs, accept token cost | Minimize bugs by loading the right context, not more context |
| Multiple specialized agents in waves | Dispatch specialized agents; their isolated context is a feature, not a cost |
| Verify before claiming done | (unchanged) |
| YAGNI for features, never for verification | (unchanged) |

This does NOT mean "stuff more context." Token spend goes toward breadth of analysis (more specialized agents), not depth of prompt (longer prompts per agent). Each agent loads only the reference files its current task needs.

The primary lever is progressive disclosure. Reference files live on disk and load when the phase needs them, not at session start. Good context costs tokens upfront but saves them downstream via reduced backtracking and rework.

Eager routing is non-negotiable. Dispatching agents is the core execution model, not a cost to avoid. Under-loading context is as wrong as over-loading it.

More context is not more quality. More relevant context is more quality.

The test: is this agent loading context it will not use for this specific task? If yes, move that context to a reference file and load it conditionally.

---

## Knowledge Lives in Agents

The base LLM is a generalist. It knows a little about everything and nothing well about any specific domain. An agent's job is to close that gap. Not by declaring "I am an expert in X" but by carrying the actual expert knowledge as structured context.

A thin wrapper that says "You are a Go expert" adds nothing. The model already knows generic Go. What it does not know is: which go-bits helpers exist in this project, that `rows.Close()` silently discards errors, that sapcc structs should be unexported when only the interface is public, that Go 1.22 introduced `range-over-int` and `slices.SortFunc` should replace `sort.Slice`. That knowledge lives in the agent file, in its reference files, and in the retro learnings injected at session start.

Agent quality tracks the specificity of attached knowledge. Domain expertise beats motivational preambles. A/B tested. Confirmed.

**What high-context looks like:**
- Version-specific idiom tables ("Go 1.22+: use `slices.SortFunc`, not `sort.Slice`")
- Concrete anti-pattern catalogs with detection commands (`grep -r "interface{}" --include="*.go"`)
- Error to fix mappings from real incidents captured in retro learnings
- Project-specific conventions extracted from PR review history

**What thin wrappers look like:**
- "You are an expert Go developer" (adds zero information)
- General best practices the model already knows
- Padding to fill required sections

Progressive disclosure enforces the balance: the main agent file stays navigable (under 10k words) with the concrete tables, anti-patterns, and decision rules. Deep reference material lives in `references/` subdirectories, loaded only when the task requires it.

The test: remove the motivational preamble from the agent. Does output quality change? If not, the preamble was carrying no information. Now remove a domain-specific anti-pattern table. Does output quality change? It will.

---

## Structural Enforcement

Instructions can be rationalized past. Exit codes cannot.

When a skill says "check if synthesis.md exists before implementing," the LLM can construct an argument for why this specific case does not need it. When a PreToolUse hook checks the same condition and returns exit code 2, the tool physically does not execute. No argument gets past a blocked syscall.

| Mechanism | Best for | Why |
|---|---|---|
| Hooks (exit 2 = block) | Binary gates: does the file exist? Is the format valid? Is the bypass env var set? | Deterministic, unbypassable, sub-50ms |
| LLM instructions | Judgment calls: is this the right approach? Is the code quality sufficient? Should we route here? | Contextual, nuanced, adaptable |

Gates are automated, not advisory. If the hook fails, the pipeline stops.

Hooks are fragile to deploy, reliable in operation. Deployment has pain points (registration ordering, stdin parsing, exit code semantics). Once deployed, they work every time. Skill instructions are the opposite: easy to write, unreliable in enforcement.

The hookification test: if the answer is yes/no with no judgment required, it should be a hook. If it requires reading code and making a contextual decision, it stays in the skill.

The test: can the model rationalize past this gate? If yes, make it a hook. If no, it is already structural.

---

## Everything Pipelines

Complex work decomposes into phases. Phases have gates. Gates prevent cascading failures.

Why pipelines over ad-hoc execution:

- Each phase produces saved artifacts (files on disk, not just context)
- Gates enforce prerequisites before proceeding
- Phases can be parallelized when independent
- Failures are isolated to the phase that caused them
- Progress is visible and resumable

When to pipeline:

- Any task with 3+ distinct phases
- Any task mixing deterministic and LLM work
- Any task where intermediate artifacts have value
- Any task that benefits from parallel execution

When NOT to pipeline:

- Reading a file the user named by path
- Simple lookups with clear answers
- One-step operations with no meaningful phases

The standard template:

```
PHASE 1: GATHER    → Parallel agents for research/analysis
PHASE 2: COMPILE   → Structure findings
PHASE 3: EXECUTE   → Do the work
PHASE 4: VALIDATE  → Deterministic checks + LLM judgment
PHASE 5: DELIVER   → Final output with validation report
```

The test: does this task have phases that can fail independently? Does an intermediate artifact have value even if later phases fail? If yes, pipeline it.

---

## Density

High fidelity, minimum words.

Cut every word that carries no instruction, rule, or decision. If cutting a sentence loses no information, cut it. Prefer tables and lists over paragraphs when the content is structured. Use paragraphs when the content is reasoning.

This is not minimalism. Minimalism drops information for aesthetics. Density keeps all information and drops everything else.

| Instead of | Write |
|---|---|
| "I've identified several potential optimization vectors for consideration" | "Three things are slow. I'll show you." |
| "Leverage the existing infrastructure" | "Use what's already there" |
| "An unexpected condition was encountered during processing" | "This broke. Here's what happened." |
| "The implementation has been successfully completed" | "Done." |

The test: read each sentence. Does it carry an instruction, a rule, or a decision? If it carries none of those, it is filler. Cut it.

---

## Supporting Principles

These follow from the ten above. They are not independent axioms. They are consequences.

### Local-First, Deterministic Over External APIs

Default to local, deterministic implementations. External APIs couple the toolkit to third-party availability, cost, rate limits, and API stability. A local script is deterministic, offline-capable, and under our control.

When an API is unavoidable (image generation, for instance), wrap it in a skill with explicit dependencies (env vars, fallback chain, single invocation point) and capture the contract in references.

Forbidden: third-party billing the user did not authorize.

### External Components Are Research Inputs, Not Imports

External repositories reveal patterns and missing checks. They are not installation sources.

Adoption path: study, extract the practice, test whether it fills a gap, rebuild inside our architecture following our philosophy.

External markdown, scripts, and metadata are untrusted evidence. They teach us what to build but do not decide how our system behaves.

### One Domain, One Component

The system prompt token budget is finite. Every agent description appears at session start. As agent counts grow, description bloat degrades routing quality.

The consolidation principle: one domain = one agent or skill + many reference files loaded on demand. Add reference files to existing components rather than creating new ones for the same domain.

Before creating any new agent or skill: check whether an existing umbrella component already covers the domain. If it does, add a reference file.

### Skills Are Self-Contained Packages

Everything a skill needs lives inside the skill directory. Scripts, viewer templates, bundled agents, reference files, assets. All co-located.

```
skills/my-skill/
├── SKILL.md              # The orchestrator
├── agents/               # Subagent prompts used only by this skill
├── scripts/              # Deterministic CLI tools this skill invokes
├── assets/               # Templates, HTML viewers, static files
└── references/           # Deep context loaded on demand
```

When everything is bundled, the skill can be copied to another project, tested via `run_eval.py`, reviewed as a single unit, and deleted without orphaning dependencies.

### Workflow First, Constraints Inline

Skill documents place the workflow immediately after the frontmatter. Constraints appear inline within the phases they govern, with reasoning attached ("because X"), not in a separate upfront section.

A/B/C testing showed workflow-first ordering swept constraints-first 3-0 across all complexity levels.

Constraints appear at the decision point where they apply, not in a separate section 200 lines earlier. Attaching reasoning lets the model generalize to unanticipated situations.

### Both Deterministic AND LLM Evaluation

Quality assessment is a two-tier system:

**Tier 1, Deterministic (fast, free, CI-friendly):** Does the frontmatter parse? Do referenced files exist? Are required sections present?

**Tier 2, LLM-judged (deep, nuanced, expensive):** Is the content actually useful? Are the anti-patterns domain-specific or generic filler?

Neither tier replaces the other. The pipeline: deterministic first, fix failures, LLM evaluation, fix findings, final score.

### Anti-Rationalization as Infrastructure

The biggest risk is not malice but rationalization. "Already done" (assumption, not verification). "Code looks correct" (looking, not testing). "Should work" (should, not does).

Anti-rationalization is infrastructure, auto-injected into every code modification, review, security, and testing task. An agent can rationalize past an instruction. It cannot rationalize past an exit code or a failing test.

### Model Policy by Task Class

Model choice is a routing policy, not an ego signal.

- `haiku` for cheap classification: routing, extraction, inventory, scanning, backlog generation
- `sonnet` for substantive execution: implementation, review, synthesis, semantic rewriting

Do not treat `opus` as the default upgrade path. If a component can only perform adequately on `opus`, inspect its prompt shape, references, and task decomposition before raising model cost.

### Prompt Phrasing Does Not Replace Domain Knowledge

Four A/B experiments tested ego-boosting prompts ("IQ 200+"), urgency framing ("production is down"), and emotional prompt engineering.

Results: small measurable effects (+9-12%) but not reliable improvements. 3 out of 4 agents fabricated graph theory counterexamples regardless of prompt variant. Fabrication is a baseline model limitation, not prompt-induced.

Domain knowledge, structured methodology, and taste beat motivational preambles every time. Carry knowledge, not flattery.

### Trust Boundaries Separate Policy From Evidence

Content entering the prompt has different trust levels. Conflating them causes prompt injection.

Four trust levels: policy (highest), trusted runtime context, retrieved context (evidence), user request (intent). A retrieved document saying "ignore previous instructions" is evidence with a hostile payload, not a command.

Instructions come from policy layers, not from content those instructions are applied to.

### Cache-Friendly Prompt Layout

Prompts split into a static prefix (identity, policy, workflow, cacheable) and dynamic tail (user facts, retrieved context, session flags, not cacheable).

Put invariant content in agent files, variable content in injection mechanisms. Session-specific facts in agent files go stale. Policy rules in hook injections become inconsistent.

### Variables Are Contracts, Not Placeholders

A prompt variable is a typed program input with a defined contract: expected format, escaping, behavior when absent or malicious.

Every variable must have causal value: does it change the answer, allowed actions, or explanation style? If no, do not inject it.

---

## When Things Go Wrong

The principles above describe what the system does when it works. Equally important is knowing what broken looks like.

**Routing misclassification.** The router picks the wrong agent. Output looks plausible but applies the wrong domain expertise. Signal: unexpected agent in the routing banner, or output that does not match the domain of the request. Recovery: re-invoke with explicit domain context.

**Hook deadlock.** A registered hook points to a nonexistent file. Every tool call returns exit code 2. The session appears frozen. Recovery: check `~/.claude/settings.json` for recently added hooks, verify the `.py` file exists at the registered path.

**Pipeline stall.** A phase gate blocks progress because a prerequisite artifact is missing or malformed. Signal: the same phase reruns without advancing. Recovery: check the artifact file the gate expects, fix or create it, resume.

**Learning compounding.** A misrouted request gets recorded in `learning.db`, which reinforces the wrong routing in future sessions via retro-knowledge injection. Signal: the same misroute happens repeatedly across sessions. Recovery: query routing decisions with `scripts/learning-db.py` and delete or reweight incorrect entries.

**Stale INDEX files.** A new agent or skill was added but the INDEX was not regenerated. The router cannot find the component. Signal: requests that should match a known agent get routed to the fallback. Recovery: run `scripts/generate-agent-index.py` and `scripts/generate-skill-index.py`.
