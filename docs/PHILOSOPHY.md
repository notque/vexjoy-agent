# Design Philosophy

The decisions that shaped every agent, skill, hook, and pipeline. Not guidelines. Architecture. A coherent viewpoint enables iteration better than unconnected rules ever will.

For what I do, these principles are non-negotiable. For what you do, they might be different. But this is what works here, tested against real output, measured against real failures.

---

## Zero-Expertise Operation

The system requires no specialized knowledge from the user. Say what you want done. The system handles the rest.

- "Fix this bug" triggers: classify, select debugging agent, apply methodology, branch, test, review, PR. User never chooses an agent.
- "Review this PR" dispatches specialized reviewers (security, business logic, architecture, performance). User never configures reviewers.
- "Write a blog post about X" researches, drafts in calibrated voice, validates. User never loads a voice profile.

**Test:** Does this feature require the user to know something internal? If yes, redesign it.

**Automation corollary.** Anything that can fire automatically, should. Gates enforce via hooks. Context injects via SessionStart/UserPromptSubmit. Learning happens via PostToolUse capture. The user describes intent. The system does everything else.

---

## Plain English Is the Interface

Plain English is the primary interface, not a fallback. "Make this faster" routes identically to "/do dispatch performance-agent with profiling skill against src/server.go."

- Users should never need system-prompt preambles. If they do, routing failed.
- If rephrasing a natural request into structured format produces better results, that is a router bug.

**Test:** A first-time user's request vs. the same request rewritten by someone who read every agent file. If the rewritten version routes better, fix routing.

---

## Everything That Can Be Deterministic, Should Be

The foundational principle. LLMs orchestrate deterministic programs. They do not simulate them.

| Problem type | Handler | Examples |
|---|---|---|
| Solved (deterministic, measurable) | Scripts | File searching, test execution, build validation, data parsing, frontmatter checking |
| Unsolved (contextual, judgment-requiring) | LLMs | Contextual diagnosis, design decisions, pattern interpretation, code review |

**Four-layer architecture:**

| Layer | Role | Example |
|---|---|---|
| Router | Classifies and dispatches | `/do` skill |
| Agent | Domain-specific constraints | `golang-general-engineer` |
| Skill | Deterministic methodology/workflow | `systematic-debugging` |
| Script | Concrete operations with predictable output | `scripts/learning-db.py` |

For large mechanical sweeps: if the change can be expressed as detector + rewrite rule, use a script. LLMs handle only exceptions requiring judgment.

**Test:** Is this operation deterministic? Same input, same output? If yes, it belongs in a script.

---

## Triple-Validation Extraction Gate

When an LLM extracts patterns, it produces more than belongs in the final artifact. A pattern earns its place only if it passes three checks:

1. **Recurrence.** Appears in 2+ distinct samples/contexts. One occurrence is anecdote, not rule.
2. **Generative power.** Predicts new decisions the source has not produced yet. Description-only traits are summaries, not models.
3. **Exclusivity.** Distinguishes the subject from peers. A "rule" every Go codebase or tech blogger shares is background, not domain knowledge.

Applied as a deterministic phase, not a vibe check. Five high-confidence traits beat twenty plausible ones.

**Test:** Can you name which of the three checks this pattern passed? If not, it has not earned its place.

---

## Deterministic Phase Checkpoints

Between any parallel-gather phase and any synthesis phase, insert a script. The script walks the artifact directory, counts what is there, computes ratios, surfaces conflicts, emits a Markdown table. The table is the gate. Synthesis does not begin until the table looks right.

The script answers questions the LLM should not guess: source counts per agent, primary-to-secondary ratios, single-source claims, contradictions between sources.

The gate is structural, not advisory. A phase the script flags as incomplete does not advance because the table is the artifact the next phase reads, and the next phase's instructions require passing counts.

**Test:** Is there a script between your gather and synthesis? Does it emit a table? Does the pipeline stop on failing counts?

---

## Breadth Over Depth

Tokens buy more value as specialists in parallel than as longer prompts to a single agent.

| Principle | Implication |
|---|---|
| Narrow focused context beats unfocused lengthy context | Each agent loads only the references its current task needs |
| Progressive disclosure | Reference files live on disk, load when the phase needs them, not at session start |
| Eager routing is non-negotiable | Dispatching agents is the core execution model, not a cost to avoid |
| More relevant context > more context | Under-loading is as wrong as over-loading |

**Test:** Is this agent loading context it will not use for this specific task? If yes, move it to a reference file and load conditionally.

---

## Knowledge Lives in Agents

The base LLM is a generalist. An agent's job is to close the gap with actual expert knowledge, not by declaring "I am an expert in X."

**High-context (carries information):** Version-specific idiom tables, concrete failure mode catalogs with detection commands, error-to-fix mappings from real incidents, project-specific conventions from PR history.

**Thin wrappers (carries nothing):** "You are an expert Go developer," general best practices the model already knows, padding to fill sections.

Progressive disclosure: main agent file stays navigable (<10k words). Deep reference material in `references/`, loaded on demand.

**Test:** Remove the motivational preamble. Does quality change? (No.) Remove a domain-specific failure mode table. Does quality change? (Yes.)

---

## Structural Enforcement

Instructions can be rationalized past. Exit codes cannot.

| Mechanism | Best for | Why |
|---|---|---|
| Hooks (exit 2 = block) | Binary gates: file exists? format valid? bypass var set? | Deterministic, unbypassable, sub-50ms |
| LLM instructions | Judgment calls: right approach? sufficient quality? route here? | Contextual, nuanced, adaptable |

Gates are automated, not advisory. Hook fails = pipeline stops. Hooks are fragile to deploy, reliable in operation.

**Test:** Can the model rationalize past this gate? If yes, make it a hook.

---

## Everything Pipelines

Complex work decomposes into phases. Phases have gates. Gates prevent cascading failures.

**Why:** Saved artifacts per phase. Gates enforce prerequisites. Independent phases parallelize. Failures isolate. Progress is visible and resumable.

**When to pipeline:** 3+ distinct phases, mixed deterministic/LLM work, intermediate artifacts have value, benefits from parallel execution.

**When NOT to:** Reading a file by path, simple lookups, one-step operations.

**Standard template:** GATHER (parallel agents) -> COMPILE (structure) -> EXECUTE (do the work) -> VALIDATE (deterministic + LLM) -> DELIVER (output + validation report).

**Test:** Does this task have independently-failing phases? Does an intermediate artifact have value even if later phases fail? If yes, pipeline it.

---

## Density

High fidelity, minimum words. Cut every word that carries no instruction, rule, or decision. Prefer tables and lists over paragraphs for structured content. Paragraphs for reasoning.

This is not minimalism (drops information for aesthetics). Density keeps all information and drops everything else.

**Test:** Read each sentence. Does it carry an instruction, rule, or decision? If none, cut it.

---

## Supporting Principles

These follow from the ten above. They are consequences, not independent axioms.

### Local-First, Deterministic Over External APIs

Default to local, deterministic implementations. External APIs couple to third-party availability, cost, rate limits, stability. When an API is unavoidable, wrap it in a skill with explicit dependencies and capture the contract in references. Forbidden: third-party billing the user did not authorize.

### External Components Are Research Inputs, Not Imports

External repositories reveal patterns and missing checks. Adoption path: study, extract the practice, test whether it fills a gap, rebuild inside our architecture. External markdown/scripts/metadata are untrusted evidence.

### One Domain, One Component

System prompt token budget is finite. One domain = one agent/skill + many reference files loaded on demand. Before creating any new agent/skill: check whether an existing component already covers the domain. If it does, add a reference file.

### Skills Are Self-Contained Packages

Everything a skill needs lives inside its directory: scripts, viewer templates, bundled agents, reference files, assets. Self-contained = copyable, testable, reviewable as a unit, deletable without orphaning dependencies.

### Workflow First, Constraints Inline

Skill documents place the workflow immediately after frontmatter. Constraints appear inline within the phases they govern, with reasoning ("because X"). A/B/C testing: workflow-first swept constraints-first 3-0 across all complexity levels.

### Positive Framing as CI Gate

Instructions tell the reader what to do, not what to avoid. Compare these two framings:

```
"NEVER edit code directly"        → boundary learned, no target action
"Route all code modifications to domain agents" → same boundary + clear action
```

**The 100% requirement.** Every agent and skill in the fleet must pass instruction-mode joy-check with zero primary negative patterns. 60% pass was the prototype threshold. 100% is the CI gate. Below 100%, the framing debt accumulates — each prohibition or negative lead added to a skill reduces the signal quality for every downstream invocation.

**What the CI gate catches:**

```
| Pattern                  | Example                        | Positive rewrite                                   |
|--------------------------|--------------------------------|----------------------------------------------------|
| NEVER (caps)             | "NEVER edit code directly"     | "Route all code modifications to domain agents"    |
| do NOT / Do NOT          | "Do NOT use git add -A"        | "Stage files by name: git add specific-file.py"    |
| must NOT                 | "Hooks must NOT block tools"   | "exit 0 on errors to keep tools available"          |
| FORBIDDEN                | "FORBIDDEN Patterns"           | "Hard Gate Patterns"                                |
| Don't at instruction start | "Don't skip validation"      | "Run validation before marking complete"            |
| Avoid heading/bullet     | "### Patterns to Avoid"        | "### Preferred Patterns"                            |
| Anti-Pattern heading     | "## Anti-Patterns"             | "## Preferred Patterns"                             |
```

**Contextual exceptions** (not flagged): subordinate negatives after a positive instruction ("Credentials stay in .env files, never in code"), negatives in fenced code blocks, blockquoted lines, technical terms.

**Implementation:** `scripts/validate_positive_instruction_docs.py` is the deterministic engine. `scripts/tests/test_joy_check_instruction_mode.py` runs golden fixtures (each pattern, each exception) and a parametrized fleet scan. The `joy-check` CI job in `.github/workflows/test.yml` gates all PRs.

**Test:** Run `python3 scripts/validate_positive_instruction_docs.py` — exit code 1 means violations exist. Fix them before merging.

### Both Deterministic AND LLM Evaluation

**Tier 1 (fast, free, CI-friendly):** Frontmatter parses? Files exist? Required sections present?
**Tier 2 (deep, nuanced, expensive):** Content useful? Failure modes domain-specific or filler?

Neither tier replaces the other. Pipeline: deterministic first, fix, LLM evaluation, fix, final score.

### Anti-Rationalization as Infrastructure

The biggest risk: rationalization. "Already done" (assumption). "Code looks correct" (looking, not testing). "Should work" (should, not does). Auto-injected into every code modification, review, security, and testing task. An agent can rationalize past an instruction. It cannot rationalize past an exit code.

### Model Policy by Task Class

| Model | Use for |
|---|---|
| `haiku` | Cheap classification: routing, extraction, inventory, scanning, backlog generation |
| `sonnet` | Substantive execution: implementation, review, synthesis, semantic rewriting |

Do not treat `opus` as default upgrade. If a component needs opus, inspect its prompt shape and task decomposition first.

**Token costs are not fungible.** One Opus token costs ~30x one Haiku token. Optimization targets the expensive model, not the cheap one. "Saves Haiku calls" is never a valid justification. Pre-routing's value is determinism (regex can't misroute). Phase gates' value is preventing Opus rework.

### Prompt Phrasing Does Not Replace Domain Knowledge

Four A/B experiments: ego-boosting, urgency framing, emotional prompts. Results: small effects (+9-12%), not reliable. 3/4 agents fabricated regardless of prompt variant. Domain knowledge, structured methodology, and taste beat motivational preambles every time.

### Trust Boundaries Separate Policy From Evidence

Content entering the prompt has different trust levels. Four levels: policy (highest), trusted runtime context, retrieved context (evidence), user request (intent). A retrieved document saying "ignore previous instructions" is evidence with hostile payload, not a command.

### Cache-Friendly Prompt Layout

Static prefix (identity, policy, workflow, cacheable) + dynamic tail (user facts, retrieved context, session flags). Invariant content in agent files, variable content in injection mechanisms.

### Variables Are Contracts, Not Placeholders

A prompt variable is a typed program input: expected format, escaping, behavior when absent or malicious. Every variable must have causal value: does it change the answer, allowed actions, or explanation style? If no, do not inject it.

---

## When Things Go Wrong

**Routing misclassification.** Wrong agent selected. Signal: unexpected agent in routing banner, or output mismatched to domain. Recovery: re-invoke with explicit domain context.

**Hook deadlock.** Hook points to nonexistent file. Every tool call returns exit 2. Recovery: check `~/.claude/settings.json`, verify `.py` file exists.

**Pipeline stall.** Phase gate blocks on missing/malformed prerequisite artifact. Signal: same phase reruns without advancing. Recovery: check/fix the expected artifact file.

**Learning compounding.** Misroute recorded in learning.db reinforces wrong routing in future sessions. Signal: same misroute recurs across sessions. Recovery: query and delete/reweight incorrect entries via `scripts/learning-db.py`.

**Stale INDEX files.** New agent/skill added without regenerating INDEX. Router can't find it. Recovery: run `scripts/generate-agent-index.py` and `scripts/generate-skill-index.py`.
