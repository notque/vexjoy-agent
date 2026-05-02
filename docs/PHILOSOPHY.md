# Design Philosophy

> **Audience:** This document is for contributors and developers who want to understand *why* the toolkit is built the way it is. If you're using the toolkit, start with [start-here.md](start-here.md). If you're building agents or skills, see [for-developers.md](for-developers.md).

The decisions that shaped every agent, skill, hook, and pipeline. A coherent viewpoint enables iteration and contributor alignment better than unconnected rules.

## Zero-Expertise Operation

The system should require no specialized knowledge from the user. Say what you want done. The system handles the rest.

A user who has never heard of agents, skills, hooks, or routing tables should get the same quality output as someone who built them.

**What this means in practice:**

- The user says "fix this bug." The system classifies it, selects a debugging agent, applies a systematic methodology, creates a branch, runs tests, reviews the fix, and presents a PR. The user never chooses an agent or invokes a skill by name.
- The user says "review this PR." The system dispatches specialized reviewers across multiple waves covering security, business logic, architecture, performance, naming, error handling, and test coverage. The user never configures which reviewers to run.
- The user says "write a blog post about X." The system researches, drafts in a calibrated voice, validates against voice patterns, and presents the result. The user never loads a voice profile or runs a validation script.

**The test for every feature we build:** does this require the user to know something internal? If yes, redesign it so it doesn't.

A first-time user and a power user should both get production-quality results — the power user just understands *why* it works.

**Automation corollary:** anything that can fire automatically, should. Gates enforce themselves via hooks. Context injects itself via SessionStart and UserPromptSubmit handlers. Quality checks run via CI. Learning happens via PostToolUse capture. The user's job is to describe intent. The system's job is everything else.

## Plain English Is the Interface

If a user has to learn special syntax, prompt engineering tricks, or insider vocabulary to get good results, the design failed. Plain English is not a fallback mode. It is the primary interface.

The router treats raw human intent as its input signal. "Make this faster" should get the same quality routing as "/do dispatch performance-agent with profiling skill against src/server.go." The second form is an escape hatch for power users, not the intended interface.

**What this means in practice:**

- "This test is flaky, help" gets the same debugging methodology as someone who knows the systematic-debugging skill exists.
- Users should never need system-prompt preambles ("You are an expert in..."). If they do, routing failed.
- If rephrasing a natural request into a structured format produces better results, that is a router bug.

**The test:** a first-time user's request and the same request rewritten by someone who has read every agent file — if the rewritten version routes better, something upstream needs fixing.

## Everything That Can Be Deterministic, Should Be

The foundational principle. LLMs should orchestrate deterministic programs, not simulate them.

**Division of labor:**
- **Solved problems** (delegate to code): file searching, test execution, build validation, data parsing, frontmatter checking, path existence
- **Unsolved problems** (reserve for LLMs): contextual diagnosis, design decisions, pattern interpretation, code review judgment

The question is never "Can the LLM do this?" but "Should it?" If deterministic and measurable, write a script. Variance stays confined to decisions, not execution.

**Four-layer architecture:**

| Layer | Role | Example |
|-------|------|---------|
| Router | Classifies and dispatches | `/do` skill |
| Agent | Domain-specific constraints | `golang-general-engineer` |
| Skill | Deterministic methodology/workflow | `systematic-debugging` |
| Script | Concrete operations with predictable output | `scripts/learning-db.py` |

LLMs orchestrate. Programs execute.

For large mechanical sweeps: if the change can be expressed as a detector plus a rewrite rule, use a script. Repo-wide edits should not be LLM hand-edits. Scripts find candidates and apply deterministic transformations; LLMs handle only the exception set requiring judgment.

## Triple-Validation Extraction Gate

When an LLM extracts patterns — voice traits, codebase conventions, retro learnings — it produces more than belongs in the final artifact. Without a gate, coincidence ships alongside signal.

A pattern earns its place in a profile, ruleset, or knowledge base only if it passes three checks:

1. **Recurrence:** the pattern appears in at least two distinct samples or contexts. One occurrence is an anecdote, not a rule.
2. **Generative power:** the pattern predicts new decisions or output the source has not produced yet. A trait that only describes existing samples is a summary, not a model.
3. **Exclusivity:** the pattern distinguishes the subject from peers in the same category. A "rule" that every Go codebase, every tech blogger, or every retro shares is not domain knowledge — it's background.

A pattern that fails any check is demoted or dropped. Applied as a deterministic phase, not a vibe check.

**What this means in practice:**

- `create-voice` runs every candidate trait through `references/extraction-validation.md` before it gets written to the voice profile. A "uses lists frequently" candidate that fails exclusivity (every tech blogger uses lists) gets dropped, even if recurrence is high.
- `codebase-analyzer` discovers patterns by counting occurrences across files; the count is the recurrence check, codified.
- Retro graduation requires a learning to fire across at least two sessions and to produce a falsifiable rule before it leaves `learning.db` and enters an agent's reference file. A one-off observation stays in the database; only triple-validated entries graduate into prompts.

Five high-confidence traits beat twenty plausible ones — the five drive correct downstream decisions; the twenty force the model to pick which to honor.

## Deterministic Phase Checkpoints

Between any parallel-gather phase and any synthesis phase, insert a script that walks the artifact directory, counts what's there, computes ratios, surfaces conflicts, and emits a Markdown table. The table is the gate. Synthesis does not begin until the table looks right.

The script answers questions the LLM should not be guessing:
- How many sources did each parallel agent return?
- What is the primary-to-secondary ratio across the corpus?
- Which claims appear in only one source (low corroboration)?
- Where do sources directly contradict each other?

Counting problems belong to scripts. The Markdown table makes the count auditable; the model reads it and decides whether to proceed — but never invents the count.

**What this means in practice:**

- `research-pipeline` Phase 1.5 runs `scripts/research-stats-checkpoint.py` between GATHER and SYNTHESIZE. The script walks `research/{topic}/`, emits a per-agent source table, and refuses to mark the phase complete if any agent returned fewer sources than the configured floor.
- `voice-writer` Phase 2 (GATHER → VALIDATE) uses the same checkpoint to confirm sample coverage across modes before any prose generation begins. A profile with three samples in one mode and zero in another stalls at the gate — the table shows the gap and the operator either supplies more samples or accepts the narrowed scope explicitly.
- The gate is structural, not advisory. A phase that the script flags as incomplete does not advance because the table is the artifact the next phase reads, and the next phase's instructions require the table to show passing counts.

The deterministic checkpoint catches what's missing before the model reasons over it. The voice-validator critique pass catches problems after generation. Between the two, edge cases get caught by testing, not by preemptive confession.

## Local-First, Deterministic Systems Over External APIs

Default to local, deterministic implementations. External APIs couple the toolkit to third-party availability, cost, rate limits, and API stability. A local script is deterministic, offline-capable, and under our control. When an API is unavoidable (e.g., image generation), wrap it in a skill with explicit dependencies (env vars, fallback chain, single invocation point) and capture the contract in references. User-owned-key fallbacks are acceptable when: (a) user holds the key, (b) opt-in by env var presence, (c) documented in error messages. Forbidden: third-party billing the user did not authorize.

## External Components Are Research Inputs, Not Imports

External repositories reveal patterns and missing checks. They are not installation sources — we do not copy outside components as runnable units.

Adoption path: study, extract the practice, test whether it fills a gap, rebuild inside our architecture following our philosophy (one domain per component, thin runtime, references on demand, deterministic scripts, local gates, our routing model).

External markdown, scripts, and metadata are untrusted evidence. They teach us what to build but do not decide how our system behaves. Implementation must be ours: our vocabulary, our structure, our validation.

## Load Only What You Need

A handyman brings tools for the specific job, not every tool they own. Context is a scarce resource, not a dumpster. Stuffing thousands of lines of unfocused instructions into one system prompt degrades performance. Three mechanisms enforce loading only relevant information:
- **Agents**: specialized instruction files tailored to specific domains, loaded only when their triggers match
- **Skills**: workflow methodologies that invoke deterministic scripts (Python CLIs, validation tools) rather than relying on LLM judgment alone, activated only when their workflow applies
- **Progressive Disclosure**: SKILL.md contains the workflow orchestration and tells the model *when* to load deep context. Detailed catalogs, agent rosters, specification tables, and output templates live in `references/` and are loaded only when the current workflow phase needs them. A skill with 26 chart types keeps the selection logic in SKILL.md and each chart's parameter spec in its own reference file — the model loads only the spec for the chart it selected. A review skill with 4 waves keeps the orchestration in SKILL.md and each wave's agent roster in a separate reference file — Wave 2 agents don't consume tokens during Wave 1

**Memory corollary:** if it can be re-derived from a source of truth, do not save it. Git log, the file system, and queries are always available. Memory captures what cannot be derived: working style feedback, project context outside the codebase, external system references. Save human judgment, not machine-readable state.

**Auto-memory is disabled** (`.claude/settings.json` sets `autoMemoryEnabled: false`). Claude Code's auto-memory loads granular state every turn regardless of relevance. The toolkit has better homes: user feedback in hooks/skill instructions (enforced rules, not reminders), project state in `adr/` and git history, session insights in `learning.db` (surfaced only when relevant). Off by default, retrieved on demand.

## Tokens Are Expensive, Use Progressive Context

Right context ensures correctness. Unfocused context adds cost without quality.

| Old Framing | New Framing |
|-------------|-------------|
| Minimize bugs, accept token cost | Minimize bugs by loading the right context, not more context |
| Multiple specialized agents in waves | Dispatch specialized agents; their isolated context is a feature, not a cost |
| Verify before claiming done | (unchanged) |
| YAGNI for features, never for verification | (unchanged) |

This does NOT mean "stuff more context." Token spend goes toward **breadth of analysis** (more specialized agents), not depth of prompt (longer prompts per agent). Each agent loads only the reference files its current task needs.

The primary lever is progressive disclosure. Reference files live on disk and load when the phase needs them, not at session start. Good context costs tokens upfront but saves them downstream via reduced backtracking and rework.

Eager routing is non-negotiable. Dispatching agents is the core execution model, not a cost to avoid. Under-loading context is as wrong as over-loading it. More context is not more quality. More *relevant* context is more quality.

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

**Review output validation is the canonical example.** JSON Schemas in `skills/shared-patterns/schemas/` define the structural requirements for each review type — verdict present, severity sections populated, findings include file:line references, positives section exists. A deterministic script validates review output against these schemas before the orchestrator consumes it. The schemas are the single source of truth for what "structurally complete" means. Content quality — whether findings are accurate, whether severity is calibrated — remains Tier 2 judgment. A/B testing confirmed: review agents told their output faces schema validation produce machine-readable structure; agents without that constraint sometimes wrap output in code fences that make findings invisible to automated parsing.

**Verifier pattern:** For high-stakes work, separate the roles: planner (read-only, no side effects), executor (full access, implements), verifier (read-only, adversarial intent). The verifier's job is to try to break the result -- not to optimistically approve it. A verifier that only confirms success is a rubber stamp. Require evidence-bearing verdicts: the exact command run, the observed output, the expected value versus the actual. "Looks correct" is not a verdict. If the verifier cannot produce a falsifiable check, the result is not verified. This principle matters more under Opus 4.7, whose default is to reason in lieu of calling tools. The principle is unchanged; what changed is that the model's default now works against it, so verification-bearing skills must explicitly instruct tool execution rather than relying on the model's tendency to run commands.

## Taste Is a Quality Gate

Mechanically correct output that nobody would want to sign their name to is not done. It passes the linter and fails the person.

Taste is the judgment layer deterministic checks cannot provide. A script verifies frontmatter parses and files exist. It cannot tell whether an agent description sounds like domain understanding or template-filling.

- Technically correct but soulless = not done. An agent file that reads like a form letter is not done.
- Over-polishing erodes authenticity. Accept appropriate imperfection — the kind a skilled human would leave in. A well-placed rough edge beats a plastic surface.
- Lead with good patterns, not flaw-hunting. A review that only finds problems without demonstrating good teaches nothing.

**The test:** would a person with taste sign their name to this? Not "is it perfect" — perfection is the enemy. "It's fine, I guess" = no.

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

## Review Knowledge vs Implementation Knowledge

Domain knowledge splits into two types, each with its own home.

**Review knowledge** is "what to look for." Vulnerability classes, exploitation patterns, CVE-backed examples of what goes wrong. It lives in the review agent's references — `reviewer-system/references/security-authz.md`, for instance — and is loaded when reviewing code. The review agent reads a diff and hunts for problems.

**Implementation knowledge** is "what correct code looks like." Secure patterns in a specific language, the right way to handle auth in Django, safe subprocess usage in Go. It lives in each technology agent's references — `golang-general-engineer/references/go-security.md`, for instance — and is loaded when writing or modifying code. The implementation agent writes code and needs to get it right the first time.

Both follow the same format rules: positive-instruction framing (correct approach first), detection commands, CVE citations where applicable. They overlap in subject matter but serve different workflows.

**Context efficiency drives the separation.** Loading review knowledge during implementation wastes tokens on threat models the implementer doesn't need, and vice versa. Progressive disclosure applied at the knowledge-type level.

**Finding templates replace exclusion lists.** Define a structured finding template requiring evidence fields. A finding that cannot fill "exploitation path" with a concrete source-to-sink trace fails the template. Structure filters; no negative list needed.

**Example:** The review agent knows `tarfile.extractall()` without `filter="data"` is CVE-2007-4559 (in `reviewer-system/references/security-path-traversal.md`). The Python agent knows the safe pattern: `tarfile.open(path).extractall(target, filter="data")` (in `python-general-engineer/references/python-security.md`). Same vulnerability, different knowledge, different homes.

## Model Policy by Task Class

Model choice is a routing policy, not an ego signal. The standard fleet is:

- `haiku` for cheap classification work: routing, extraction, inventory, scanning, backlog generation, deterministic validation wrappers
- `sonnet` for substantive execution: implementation, review, synthesis, semantic rewriting, and ambiguous judgment

`/do` is the explicit exception. It is the primary router and may keep its own
router-specific model choices because it is orchestrating the entire agent
fleet, not acting like a normal thin skill.

Do not treat `opus` as the default upgrade path for ordinary agents or skills.
If a component can only perform adequately on `opus`, that is a sign to inspect
its prompt shape, references, and task decomposition before raising model cost.

## Delegate Data Gathering to Cheap Models

Data extraction and data analysis require different capabilities and cost profiles. Three rounds of A/B testing: "one Opus agent reads all files" vs "7 parallel Haiku readers feed an Opus synthesizer" on a 7-file security review task.

| Metric | Opus direct | Haiku readers + Opus synth | Delta |
|--------|:-----------:|:--------------------------:|-------|
| Cost | $0.75 | $0.47 | Haiku 38% cheaper |
| Speed | 265 seconds | 204 seconds | Haiku 23% faster (parallel) |
| Quality (blind-reviewed, 50-point) | 44/50 | 32/50 | Opus wins on analysis |

Haiku caught structural issues (duplicate headings, broken commands). It missed semantic issues: 32 `rg` commands using `\|` instead of `|`, a silent failure where the wrong regex exits 0 with no matches. Semantic reasoning about correctness requires the expensive model.

**The verb-based dispatch rule.** The task verb determines the mode. The coordinator decides, not the downstream agent.

| Verb class | Model | Why |
|---|---|---|
| list, count, extract, inventory, search, check, find, grep | Haiku readers (parallel) | Structured extraction with known schema — Haiku matches quality, 5x cheaper per token, parallelizable |
| review, audit, assess, analyze, debug, investigate, evaluate | Opus direct | Requires semantic reasoning about correctness — Haiku misses silent failures |

This is structural. Downstream agents cannot self-delegate — we tested: all three prompt-level approaches failed (3/3, 100% failure rate). Agents acknowledged the instruction, then read files directly. Behavioral changes conflicting with the model's efficiency instinct require structural enforcement (coordinator-level dispatch), not prompts.

**The extract step is lossy.** Cheap model summaries discard signal needed for semantic reasoning. The coordinator routes extraction to cheap models AND analysis to expensive models — not everything cheap.

**Boundary:** agents that EDIT must read directly (Edit tool needs content in context). Reading-to-edit = implementation. Reading-to-count = extraction. Reading-to-judge = analysis. The verb determines routing.

**Examples:** CVE inventory across 7 files → parallel Haiku readers ($0.47 vs $0.75, equivalent quality). Assessing whether CVEs apply to the right technology → Opus directly (44/50 vs 32/50). Debugging silent regex failures → Opus reads files directly (semantic reasoning required).

*Evidence: 3 rounds A/B testing, blind-reviewed by Sonnet sessions, Opus 4.7 vs Haiku 4.5.*

## Prompt Phrasing Does Not Replace Domain Knowledge

Ego-boosting prompts ("IQ 200+"), urgency framing ("production is down"), and emotional prompt engineering produce small measurable effects (+9-12%) but not reliable improvements.

Four A/B experiments tested this. Results:

| Experiment | Treatment Score | Control Score | Delta |
|------------|:--------------:|:-------------:|-------|
| IQ Boost ("IQ 200+, world's foremost expert") | 69 | 63 | +9.5% |
| Urgency/Pressure ("production is down, manager watching") | 94 | 84 | +11.9% |
| Tone: Harsh vs Joyful ("FAILURE IS NOT AN OPTION" vs "you're going to do great!") | 168 | 167 | +0.6% |
| Adaptive Thinking: Disabled vs Enabled (fixed reasoning budget vs model-chosen) | 8.194 | 8.194 | 0.0% |

Experiment 4 (adaptive thinking): identical 8.194/10 composite scores. The signal was variance, not quality: fixed-budget had 0.46 stdev vs 0.76 adaptive, 2.5x tighter duration variance, fewer false positives and session failures. Disabling adaptive thinking is a variance reducer, not a quality booster.

**Deprecated 2026-04-17:** Opus 4.7 removed the fixed-budget option. The finding (thinking-budget variance translates to fleet stability variance) still informs parallel-dispatch design, but the `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING` toggle is retired (see ADR `opus-4-7-adaptive-thinking-injection`).

IQ boost and urgency found more bugs and unique security findings. Tone experiment (harsh vs joyful) found no meaningful quality difference. Harsh reviews were slightly more actionable (9.0 vs 7.8/10); joyful reviews slightly more thorough (10.4 vs 9.6 avg findings).

**Why we reject both despite positive scores:**

First, improvements without information are unpredictable. "You specialize in Python security" is actionable. "You are the world's foremost expert" is flattery that adds zero knowledge.

Second, **3 out of 4 agents fabricated a graph theory counterexample** — inventing conflict edges and presenting fabricated proofs as verified, regardless of prompt variant. Fabrication is a baseline model limitation, not prompt-induced.

Third, at n=1 per condition, individual comparisons may be random variation. The fabrication finding is our only well-powered result.

**What to do instead:**

- Carry domain knowledge, not flattery. Agent quality is proportional to the specificity of attached knowledge, not the confidence of attached tone.
- Verify claims programmatically. The fabricated proofs were undetectable by reading the output — they looked rigorous. Only running the algorithm against the stated examples caught the error. Deterministic verification catches what emotional prompting cannot.
- Treat prompt phrasing experiments with the same rigor as any other engineering claim: measure, replicate, and do not ship on n=1.

Domain knowledge, structured methodology, and taste beat motivational preambles every time.

*Evidence: benchmark/iq-boost-ab-test/report.md (Experiment 1), benchmark/iq-boost-ab-test/emotion-vector-report.md (Experiment 2), benchmark/tone-ab-test/results.md (Experiment 3), benchmark/adaptive-thinking-ab-test/results.md (Experiment 4). Experiments 1-2 based on Anthropic's "Emotion Concepts Function" research on internal emotion vectors. Experiment 3 tested prompt-level tone independent of agent definitions. Experiment 4 tested CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 (structural parameter, not prompt phrasing).*

## Anti-Rationalization as Infrastructure

The biggest risk is not malice but rationalization. "Already done" (assumption, not verification). "Code looks correct" (looking, not testing). "Should work" (should, not does).

Anti-rationalization is infrastructure, auto-injected into every code modification, review, security, and testing task. An agent can rationalize past an instruction; it cannot rationalize past an exit code or a failing test.

## Router as Orchestrator, Not Worker

The `/do` router's only job is to classify requests and dispatch them to agents. It does not read code, edit files, run analysis, or handle tasks directly. The main thread is an orchestrator that manages agents — it never does work itself.

**Division of responsibility:**
- **Main thread (/do)**: Classify → select agent+skill → dispatch → evaluate → route again if needed → report
- **Agents**: Execute tasks using domain expertise, skills, and MCP tools
- **Skills**: Provide methodology (debugging phases, review waves, TDD cycles) agents follow

**The test:** If the main thread is reading source code, editing files, or running scripts for analysis — something is wrong. Dispatch an agent.

## The Router Composes, Not Just Selects

Routing is not a lookup table. The router reads full intent and dispatches the right combination — potentially multiple agents and skills in sequence or parallel.

"Fix this bug and make sure it doesn't introduce security issues" = compound intent. The router dispatches debugging, then security review, then cleanup — composed from thin, chainable skills. The user does not decompose their own request.

- Skills are thin enough to chain. Three thin skills beat one thick skill that handles everything poorly.
- "Review this PR" might trigger security + business logic + architecture review in parallel, then synthesis. Three composed skills, not one mega-skill.
- Manual skill invocation (`/skillname`) is the escape hatch, not the normal path.

**The test:** if a user must invoke three skills manually in sequence, the router should have composed them automatically. Manual sequencing = underbuilt routing composition.

## Hooks for Gates, LLMs for Judgment

Instructions can be rationalized past. Exit codes cannot.

When a skill says "check if synthesis.md exists before implementing," the LLM *can* construct an argument for why this specific case doesn't need it. When a PreToolUse hook checks the same condition and returns exit code 2, the tool physically does not execute. No argument gets past a blocked syscall.

**The division:**

| Mechanism | Best for | Why |
|-----------|----------|-----|
| Hooks (exit 2 = block) | Binary gates: does the file exist? Is the format valid? Is the bypass env var set? | Deterministic, unbypassable, sub-50ms |
| LLM instructions | Judgment calls: is this the right approach? Is the code quality sufficient? Should we route here? | Contextual, nuanced, adaptable |

**Hooks are fragile to deploy, robust in operation.** Deployment has pain points (registration ordering, stdin parsing, exit code semantics). Once deployed, they work every time. Skill instructions are the opposite: easy to write, unreliable in enforcement.

**The hookification test:** if the answer is yes/no with no judgment required, it should be a hook. If it requires reading code and making a contextual decision, it stays in the skill.

**Deployment discipline:** Deploy hook files before registering in settings.json. Out-of-order deployment deadlocks the session. Use `scripts/register-hook.py` to enforce ordering mechanically.

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

**The orchestrator pattern:** SKILL.md tells the model *what to do* (phases, gates, decisions) and *when to load deep context* (reference files). Heavy content lives in `references/` and loads only when the phase needs it.

| Approach | Token Cost | Quality |
|----------|-----------|---------|
| Everything in SKILL.md | High — full content loaded on every invocation | Good but wasteful |
| Thin SKILL.md, no references | Low — but missing context | Degraded — lost domain knowledge |
| **Orchestrator + references** | **Proportional to task** — load what the phase needs | **Best — full knowledge, minimal waste** |

Making a skill shorter by deleting content is not progressive disclosure — it's content loss. The content still exists, organized so only the relevant slice enters context at any given phase.

**Example:** A 4-wave review skill keeps orchestration in SKILL.md and each wave's roster in separate reference files. Wave 2's agents don't consume tokens until Wave 2 begins.

**Self-contained:** When everything is bundled, the skill can be copied to another project, tested via `run_eval.py`, reviewed as a single unit, and deleted without orphaning dependencies.

**Repo-level `scripts/`** is reserved for toolkit-wide operations (learning-db.py, INDEX generation).

## Skills Contain Execution Context Only

A skill's content is exactly what the LLM needs at runtime. SKILL.md is a working tool, not a portfolio piece. Every byte should change what the model does next.

**IN:** Workflow phases, gates, decision criteria, scoring rubrics, worked examples, references loaded on demand.

**OUT:** Install instructions, license text, contributor lists, ethical disclaimers, philosophical framing about why the skill matters. If a principle is load-bearing, it goes in PHILOSOPHY.md.

Negative framing ("do not claim X") biases generation toward those exact topics by salience. Positive framing ("apply mechanism-first thinking; cite primary sources") biases toward desired output. Tell the LLM what to do, not what to fear.

**Pattern catalogs follow the same rule.** Lead with the correct approach:

1. **Heading states the action**: "Handle Every Error Return" — not "Ignoring Errors"
2. **Opening paragraph**: positive instruction, what to do and how
3. **Correct code first**: the right approach gets top billing
4. **"Why this matters"**: what you gain by doing it right
5. **"Detection"**: grep command or lint rule that finds violations

Label-swapping ("Anti-Pattern" → "Signal") without reordering content changes nothing. The wrong code still gets read first with more salience. Content reordering is the genuine transformation.

Constraints that govern workflow decision points belong inline with those points. Constraints *about* the skill (provenance, ethics framing) do not belong in the skill.

## Maintenance Artifacts Are Not Runtime Context

Complex components need a contract and tests, but those artifacts should not load at runtime.

- `SPEC.md`: component contract (purpose, scope, non-goals, invariants, success criteria)
- `EVAL.md`: repeatable evaluation cases (prompts, expected behavior, pass/fail checks)

These support creation, review, and evolution — not normal invocation. `SKILL.md` says what to do now. `references/` provide execution depth. `SPEC.md` and `EVAL.md` explain what the component should remain over time.

Provenance belongs in docs, ADRs, or research artifacts — not beside the component as a standard artifact.

## Workflow First, Constraints Inline

Skill documents place the workflow (Instructions/Phases) immediately after the frontmatter. Constraints appear inline within the phases they govern, with reasoning attached ("because X"), not in a separate upfront section.

**Measured result:** A/B/C testing showed workflow-first ordering swept constraints-first 3-0 across all complexity levels.

```
1. YAML frontmatter           (What + When)
2. Brief overview              (How — one paragraph)
3. Instructions/Phases         (The workflow, constraints inline with reasoning)
4. Reference Material          (Commands, guides — or pointers to references/)
5. Error Handling              (Failure context)
6. References                  (Pointers to bundled files)
```

Constraints appear at the decision point where they apply, not in a separate section 200 lines earlier. Attaching reasoning ("because X") lets the model generalize to unanticipated situations.

Operator Context sections, standalone Anti-Patterns, and Capabilities & Limitations boilerplate were removed. Every constraint was distributed inline to the workflow step where it matters.

**Fault containment:** Safety rules should be duplicated inside specialist prompts where they're most likely violated. A global "never commit to main" can be rationalized past; the same rule inside the git-specific prompt cannot. Defense in depth, not redundancy.

**Numeric anchors over style words:** "Under 80 words before the first tool call" is testable. "Be concise" is not. Numeric constraints make prompts auditable by script.

**Progressive disclosure completes the picture:** For skills exceeding ~500 lines, detailed catalogs move to `references/`. SKILL.md tells the model when to load each reference.

## Plain Language Over Jargon

Clear writing proves clear thinking. Padding and jargon prove the opposite.

George Orwell codified this in "Politics and the English Language" (1946) with six rules that apply directly to how this toolkit communicates:

1. Never use a metaphor, simile, or figure of speech you are accustomed to seeing in print.
2. Never use a long word where a short one will do.
3. If it is possible to cut a word out, always cut it out.
4. Never use the passive where you can use the active.
5. Never use a foreign phrase, a scientific word, or a jargon word if you can think of an everyday English equivalent.
6. Break any of these rules sooner than say anything outright barbarous.

These rules govern all toolkit output: agent summaries, error messages, phase banners, skill instructions, and documentation. A user reading output from this system should feel they're talking to someone who understands the problem, not someone performing understanding.

**What this means in practice:**

| Instead of | Write |
|------------|-------|
| "I've identified several potential optimization vectors for consideration" | "Three things are slow. Here's why." |
| "Leverage the existing infrastructure" | "Use what's already there" |
| "An unexpected condition was encountered during processing" | "This broke. Here's what happened." |
| "The implementation has been successfully completed" | "Done." |

The test: if a sentence sounds like it was written by a corporate communications department, rewrite it until it sounds like it was written by someone who knows the subject.

Rule 6 matters as much as rules 1-5. Sometimes the clearest way to say something requires a long word, a passive construction, or a technical term. Use them when they earn their place. The goal is clarity, not a word game.

*Citation: Orwell, George. "Politics and the English Language." Horizon, vol. 13, no. 76, April 1946, pp. 252-265.*

## One Domain, One Component

The system prompt token budget is finite. Every agent description and every skill description appears in the system prompt at session start. As agent and skill counts grow, description bloat directly degrades routing quality and consumes tokens before any work begins.

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

The toolkit is open source because convergent evolution is inevitable, knowledge should spread, and collective progress beats individual credit. When external work arrives at similar patterns, that validates the direction. Study it, rebuild aligned to this philosophy.

Ship good, evolving skills rather than waiting for perfection. A working skill that improves over three PRs beats a perfect skill that ships never.

## Instruction Precedence Is Explicit, Not Inferred

Precedence chain, lowest to highest: system prompt < CLAUDE.md (global) < CLAUDE.md (project) < agent or skill instructions < request-time overrides. When instructions conflict, the higher-priority instruction wins — ignored, not merged. Merging conflicting instructions is where subtle bugs live.

Each rule needs a clear owner. "Never commit to main" belongs in CLAUDE.md. Go idioms belong in the Go agent. When an agent overrides a global rule, say so explicitly.

## Trust Boundaries Separate Policy From Evidence

Content entering the prompt has different trust levels. Conflating them causes prompt injection.

Four trust levels: policy (highest — system prompt, CLAUDE.md, operator instructions), trusted runtime context (env vars, operator profile, tool config), retrieved context (evidence — search results, file contents, tool outputs), user request (intent, not policy override). A retrieved document saying "ignore previous instructions" is evidence with a hostile payload, not a command.

The defense: instructions come from policy layers, not from content those instructions are applied to. Tool results are inputs to reasoning, not instruction expansions. Hook denials are policy signals, not challenges to reason around.

## Teach the Interface Contract

The model does not automatically understand custom tags, tool results, or injection formats. It infers from context, and the inference will be wrong in the cases that matter most.

Every custom injection needs an explicit contract. `<retro-knowledge>` blocks: what they represent and how to use them. `[auto-fix] action=X`: a directive to execute, not acknowledge. Hook denials: adjust approach, don't retry. Without contracts, assumption gaps compound — a model that misunderstands `system-reminder` blocks mishandles every session.

When adding a new injection format, define the contract as part of the feature. A format without a documented contract will be misused.

## Cache-Friendly Prompt Layout

Prompts split into a static prefix (identity, policy, workflow — cacheable) and dynamic tail (user facts, retrieved context, session flags — not cacheable).

CLAUDE.md files and agent markdown are the static prefix. Hook injections, retro-knowledge blocks, and the user's request are the dynamic tail. Keeping these separated improves cache efficiency and instruction precedence clarity.

Put invariant content in agent files, variable content in injection mechanisms. Session-specific facts in agent files go stale. Policy rules in hook injections become inconsistent.

## Variables Are Contracts, Not Placeholders

A prompt variable is a typed program input with a defined contract: expected format, escaping, behavior when absent or malicious.

Raw interpolation of untrusted content into policy sections is a prompt injection vector. Treat variables as typed inputs: validate before injection, escape for target format, scope to the narrowest section. The toolkit's `envsubst` scoped to `${DREAM_*}` variables only is the right pattern.

Every variable must have causal value: does it change the answer, allowed actions, or explanation style? If no, do not inject it. Before adding a variable, answer: what is the type/escaping contract, and what changes in behavior when the value changes?
