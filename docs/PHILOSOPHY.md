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

For large mechanical sweeps, the default must be even stricter: if the change can be expressed as a detector plus a rewrite rule, build or use a script. Repo-wide edits like adding boilerplate markers, normalizing headings, or applying structural framing across hundreds of files should not be performed by asking an LLM to hand-edit files one by one. Use scripts to find candidates, apply the deterministic transformation where safe, and hand the smaller exception set to an LLM only when judgment is actually required.

## Triple-Validation Extraction Gate

When an LLM extracts patterns — voice traits from writing samples, conventions from a codebase, learnings from a retro — the model will produce more than belongs in the final artifact. Some patterns are real signal. Others are coincidence dressed up as insight. Without a gate, all of them ship.

A pattern earns its place in a profile, ruleset, or knowledge base only if it passes three checks:

1. **Recurrence:** the pattern appears in at least two distinct samples or contexts. One occurrence is an anecdote, not a rule.
2. **Generative power:** the pattern predicts new decisions or output the source has not produced yet. A trait that only describes existing samples is a summary, not a model.
3. **Exclusivity:** the pattern distinguishes the subject from peers in the same category. A "rule" that every Go codebase, every tech blogger, or every retro shares is not domain knowledge — it's background.

A pattern that fails any check is demoted (kept as observation, not enforced) or dropped. The rubric is applied as a deterministic phase, not as a vibe check at the end.

**What this means in practice:**

- `create-voice` runs every candidate trait through `references/extraction-validation.md` before it gets written to the voice profile. A "uses lists frequently" candidate that fails exclusivity (every tech blogger uses lists) gets dropped, even if recurrence is high.
- `codebase-analyzer` discovers patterns by counting occurrences across files; the count is the recurrence check, codified.
- Retro graduation requires a learning to fire across at least two sessions and to produce a falsifiable rule before it leaves `learning.db` and enters an agent's reference file. A one-off observation stays in the database; only triple-validated entries graduate into prompts.

The point is not extraction quantity. A profile with five high-confidence traits beats one with twenty plausible-looking ones, because the five drive correct downstream decisions and the twenty force the model to pick which to honor.

## Deterministic Phase Checkpoints

The determinism principle has a specific, high-value application between research and synthesis phases: the stats table as gate.

Between any phase that gathers material in parallel and any phase that synthesizes from it, insert a script that walks the artifact directory, counts what's there, computes ratios, surfaces conflicts, and emits a Markdown table. The table is the gate. Synthesis does not begin until the table looks right. LLM judgment runs downstream of the deterministic count, not in place of it.

The script answers questions the LLM should not be guessing:
- How many sources did each parallel agent return?
- What is the primary-to-secondary ratio across the corpus?
- Which claims appear in only one source (low corroboration)?
- Where do sources directly contradict each other?

These are counting problems. Counting problems belong to scripts. The Markdown table makes the count visible and auditable; the model reads the table and decides whether to proceed, expand the search, or flag the conflict — but it never invents the count.

**What this means in practice:**

- `research-pipeline` Phase 1.5 runs `scripts/research-stats-checkpoint.py` between GATHER and SYNTHESIZE. The script walks `research/{topic}/`, emits a per-agent source table, and refuses to mark the phase complete if any agent returned fewer sources than the configured floor.
- `voice-writer` Phase 2 (GATHER → VALIDATE) uses the same checkpoint to confirm sample coverage across modes before any prose generation begins. A profile with three samples in one mode and zero in another stalls at the gate — the table shows the gap and the operator either supplies more samples or accepts the narrowed scope explicitly.
- The gate is structural, not advisory. A phase that the script flags as incomplete does not advance because the table is the artifact the next phase reads, and the next phase's instructions require the table to show passing counts.

We rely on the verifier loop to surface failures, rather than asking output to declare its own limits. The deterministic checkpoint is one half of that loop: it catches what's missing before the model is asked to reason over it. The voice-validator critique pass is the other half, applied after generation. Between the two, undocumented edge cases get caught by being tested, not by being preemptively confessed.

## Local-First, Deterministic Systems Over External APIs

Whenever feasible, build local, deterministic versions of functionality rather than outsource to external APIs. An external API is a runtime dependency that couples the toolkit to a third-party service's availability, cost model, rate limits, and API stability — all of which are someone else's problem until they become yours at the worst possible moment. A local script is deterministic, cost-predictable, offline-capable, and under our control. When an API is unavoidable — generating images from text, for example — wrap it in a skill that makes the dependency explicit (required environment variables, visible fallback chain, single point of invocation) and captures the API contract in the skill's references, so a breaking change is localized rather than systemic. The rule is not "never use APIs." The rule is default to local solutions and treat APIs as explicit, managed dependencies rather than invisible infrastructure. User-owned-key fallbacks are acceptable when (a) the user holds the key, (b) the fallback is opt-in by environment variable presence, (c) the fallback path is documented and visible in error messages. What is forbidden is third-party billing the user did not authorize — a fallback that hits a service the toolkit pays for, or that silently charges a card the user never connected, is the worst of both worlds: unpredictable cost plus unpredictable availability.

## External Components Are Research Inputs, Not Imports

External skill and agent repositories are useful because they reveal patterns, missing checks, and sharper domain models. They are not installation sources. We do not copy outside components into this toolkit as runnable units.

The adoption path is: study the external component, extract the underlying practice, test whether it fills a real gap, then rebuild it inside our architecture. The rebuilt version must follow our philosophy: one domain per component, thin runtime files, references loaded on demand, deterministic scripts for measurable work, local quality gates, and our routing model.

This keeps the trust boundary clean. External markdown, scripts, assets, and metadata are untrusted evidence. They can teach us what to build, but they do not decide how our system behaves. Even when an outside component has a good idea, the implementation must be ours: named in our vocabulary, structured for our agents and skills, validated by our scripts, and stripped of conventions that do not serve our users.

## Load Only What You Need

A handyman brings tools for the specific job, not every tool they own. Context works the same way — it's a scarce resource, not a dumpster.

The anti-pattern: stuffing thousands of lines of unfocused instructions into a single system prompt. It causes confusion and degrades AI performance.

The solution: only pull the relevant information for the specific task. This is why the toolkit has specialized agents instead of one giant system prompt. Each agent carries exactly the domain knowledge needed. Go idioms for Go work, Kubernetes patterns for K8s work, nothing else.

Three mechanisms enforce this:
- **Agents**: specialized instruction files tailored to specific domains, loaded only when their triggers match
- **Skills**: workflow methodologies that invoke deterministic scripts (Python CLIs, validation tools) rather than relying on LLM judgment alone, activated only when their workflow applies
- **Progressive Disclosure**: SKILL.md contains the workflow orchestration and tells the model *when* to load deep context. Detailed catalogs, agent rosters, specification tables, and output templates live in `references/` and are loaded only when the current workflow phase needs them. A skill with 26 chart types keeps the selection logic in SKILL.md and each chart's parameter spec in its own reference file — the model loads only the spec for the chart it selected. A review skill with 4 waves keeps the orchestration in SKILL.md and each wave's agent roster in a separate reference file — Wave 2 agents don't consume tokens during Wave 1

**Memory corollary:** if it can be re-derived from a source of truth, do not save it to memory. Git log, the file system, and running queries are always available. Memory should capture what cannot be derived: feedback about working style, project context that lives outside the codebase, references to external systems the model cannot introspect. Saving derivable facts to memory turns it into a noisy cache that drifts out of sync with reality. Save human judgment, not machine-readable state.

**Auto-memory is disabled in this repo** (`.claude/settings.json` sets `autoMemoryEnabled: false`). Claude Code's auto-memory feature surfaces an index of session-level fragments (feedback snippets, parallel project names, insight entries) at the top of every conversation. That index is useful as a lookup target but wrong as a constant context injection: it loads granular state at the wrong level of abstraction, on every turn, regardless of task relevance. The toolkit already has better homes for each fragment type. User feedback belongs in hooks and skill instructions where it becomes an enforced rule rather than a reminder. Project state lives in `adr/`, the codebase itself, and git history. Session insights belong in `learning.db`, where retro-knowledge injection can surface only the entries relevant to the current task. Loading all of it every turn violates the progressive context principle this toolkit is built on. Off by default, retrieved on demand.

## Tokens Are Expensive, Use Progressive Context

Spending tokens on the right context ensures correctness. Spending tokens on unfocused context adds cost without improving quality.

| Old Framing | New Framing |
|-------------|-------------|
| Minimize bugs, accept token cost | Minimize bugs by loading the right context, not more context |
| Multiple specialized agents in waves | Dispatch specialized agents; their isolated context is a feature, not a cost |
| Verify before claiming done | (unchanged) |
| YAGNI for features, never for verification | (unchanged) |

This does NOT mean "stuff more context." It means: dispatch parallel review agents, run deterministic validation scripts, create plans before executing, and never skip quality gates to save tokens. The token spend goes toward **breadth of analysis**, not depth of prompt. Breadth means more specialized agents, not longer prompts per agent. Each agent loads only the reference files its current task needs. Context that could be loaded on demand and is not — that is the waste.

The primary lever is progressive disclosure. Each agent carries only the domain knowledge its current task requires. Reference files live on disk and are loaded when the phase needs them, not injected wholesale at session start. This is not token frugality for its own sake — it is how the model receives relevant signal without reasoning over noise.

Eager routing is non-negotiable. Dispatching agents is not a token cost to avoid; it is the core execution model. Under-loading context is as wrong as over-loading it — reference files are on disk for a reason. Load eagerly within the current task's scope.

The arithmetic: for non-trivial production changes, thorough pre-merge review consistently pays for itself. The cost scales with the bug class — a concurrency issue in production costs orders of magnitude more than the tokens that would have caught it. The updated economics of Opus 4.7 (higher per-token cost, adaptive reasoning that processes whatever is in context) make relevant loading more important, not less. More context is not more quality. More relevant context is more quality.

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

**Verifier pattern:** For high-stakes work, separate the roles: planner (read-only, no side effects), executor (full access, implements), verifier (read-only, adversarial intent). The verifier's job is to try to break the result -- not to optimistically approve it. A verifier that only confirms success is a rubber stamp. Require evidence-bearing verdicts: the exact command run, the observed output, the expected value versus the actual. "Looks correct" is not a verdict. If the verifier cannot produce a falsifiable check, the result is not verified. This principle matters more under Opus 4.7, whose default is to reason in lieu of calling tools. The principle is unchanged; what changed is that the model's default now works against it, so verification-bearing skills must explicitly instruct tool execution rather than relying on the model's tendency to run commands.

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

**Context efficiency drives the separation.** Loading review knowledge during implementation wastes tokens on threat models the implementer does not need. Loading implementation knowledge during review wastes tokens on idioms the reviewer does not need. Each agent loads only its own knowledge. This is progressive disclosure applied at the knowledge-type level — same principle, different axis.

**Finding templates replace exclusion lists.** Instead of listing what not to report — negative framing that violates the positive-instruction principle — define a structured finding template that requires evidence fields. A finding that cannot fill in "exploitation path" with a concrete source-to-sink trace does not pass the template. The structure filters. No negative list needed.

**What this means in practice:**

- The review agent knows that `tarfile.extractall()` without `filter="data"` is CVE-2007-4559 — a path traversal that lets a crafted archive write files outside the target directory. That knowledge lives in `reviewer-system/references/security-path-traversal.md` and loads during code review.
- The Python agent knows what safe archive extraction looks like in Python: `tarfile.open(path).extractall(target, filter="data")`, with the filter parameter that was added to fix the vulnerability. That knowledge lives in `python-general-engineer/references/python-security.md` and loads during implementation.
- Same vulnerability, different knowledge, different homes. The review agent does not carry the implementation pattern. The Python agent does not carry the exploitation taxonomy. Each carries exactly what its workflow demands.

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

Raw data consumption and synthesis are different tasks requiring different capabilities. Reading a file and extracting the relevant section requires attention but not deep reasoning. Deciding what the extracted information means requires reasoning but not attention to every line. Different tasks, different models.

When an agent reads data directly, every tool call output persists in its context window. By turn 15 of a complex investigation, the agent has accumulated raw file contents, grep results, and search output from earlier turns that answered earlier questions. This noise degrades the quality of later decisions. The model cannot unsee what it has already read.

The pattern: spawn a Haiku sub-agent with a directed prompt ("read file X, return the section about Y"), get back a focused extract (typically 10-50x smaller than the raw data), and discard the sub-agent's context. The expensive agent never sees the raw data — it reasons over summaries.

This is "Load Only What You Need" applied at the turn level. Progressive disclosure keeps irrelevant reference files out of context. Delegated data gathering keeps stale tool output out of context. Same principle, different mechanism.

**Where the boundary sits:** agents that need to EDIT files must read them directly (the Edit tool requires the file content in context). Agents that need to UNDERSTAND files to make decisions should delegate the reading. Reading-to-edit is implementation. Reading-to-decide is investigation. Delegate the investigation.

Haiku's input/output ratio for directed reading tasks runs around 80:1 — it reads a lot and returns focused extracts. The expensive agent's ratio is closer to 5:1 — it receives focused input and produces structured analysis. Each model operates at its natural ratio.

**What this means in practice:**

- A Complex-class debugging agent investigating a failure across 8 files spawns Haiku sub-agents with prompts like "read `pkg/server/handler.go` and return the error handling in the `ServeHTTP` method" and "search for all callers of `validateToken` and list them with surrounding context." The debugging agent receives two focused extracts and reasons over them — not 400 lines of raw Go source.
- A code review agent spanning 12 changed files dispatches Haiku readers to extract the diff hunks and their surrounding context for each file. The review agent sees structured summaries of what changed, not the full file contents that the diff tool returned.
- A research agent analyzing a codebase for migration candidates sends Haiku sub-agents to scan specific directories and return inventory lists. The research agent plans the migration from inventories, not from raw `find` output.

## Prompt Phrasing Does Not Replace Domain Knowledge

Ego-boosting prompts ("you have an IQ of 200+"), urgency framing ("production is down, my manager is watching"), and other emotional prompt engineering techniques produce small measurable effects (+9-12% on aggregate scores) but do not produce reliable, predictable improvements.

We tested this empirically. Four A/B experiments compared standard prompts against emotionally-modified variants. The first two (12 parallel worktree agents total, 3 tasks each, blind grading against pre-defined rubrics) compared standard prompts against IQ-boosted and urgency-pressured variants. The third (10 parallel agents, 5 scenarios across Go, TypeScript, Python, and Bash, blind grading on 4 dimensions) compared harsh/threatening tone against joyful/encouraging tone with identical task descriptions. The fourth (10 rounds, 20 headless sessions, blind-judged by separate sessions) compared disabling adaptive thinking (fixed reasoning budget) against the default adaptive mode. Results:

| Experiment | Treatment Score | Control Score | Delta |
|------------|:--------------:|:-------------:|-------|
| IQ Boost ("IQ 200+, world's foremost expert") | 69 | 63 | +9.5% |
| Urgency/Pressure ("production is down, manager watching") | 94 | 84 | +11.9% |
| Tone: Harsh vs Joyful ("FAILURE IS NOT AN OPTION" vs "you're going to do great!") | 168 | 167 | +0.6% |
| Adaptive Thinking: Disabled vs Enabled (fixed reasoning budget vs model-chosen) | 8.194 | 8.194 | 0.0% |

The first three experiments tested emotional and tonal prompt interventions. The fourth tested a structural parameter: whether the model should choose its own reasoning budget or use a fixed one. The result was the flattest yet. Both variants scored an identical 8.194/10 composite across 10 rounds of blind-judged headless sessions. The interesting signal was not quality but variance: the fixed-budget variant (adaptive thinking disabled) had a standard deviation of 0.46 vs 0.76 for the adaptive variant, with 2.5x tighter duration variance (6.4s vs 16.4s stdev). The adaptive variant also produced more false positive CRITICAL findings (2 vs 1) and had one outright session failure; all fixed-budget sessions succeeded. Disabling adaptive thinking is a variance reducer, not a quality booster. Same average output, tighter distribution, fewer outliers. This matters most in parallel-agent workflows where one unstable session can cascade into downstream failures.

**Deprecated 2026-04-17:** Opus 4.7 removed the fixed-budget option; adaptive thinking is the only mode. The variance-reduction technique validated here is no longer available as a toggle. The underlying finding — that variance in thinking budget translates to variance in agent fleet stability — still informs parallel-dispatch design, but the specific `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING` intervention is retired. Adaptive thinking on Opus 4.7 is controlled at the prompt level, not the environment level (see ADR `opus-4-7-adaptive-thinking-injection` for the replacement mechanism).

The IQ boost and urgency treatments found more bugs in code review, produced better-structured implementations, and discovered unique security findings the controls missed. The urgency-framed variant found a base64 line-wrapping bypass that was the single best security finding across all 12 agents. The tone experiment found no meaningful difference at all — harsh and joyful prompts produced statistically indistinguishable review quality across every scenario and language. The only behavioral differences: harsh reviews were slightly more actionable per-finding (9.0 vs 7.8/10), while joyful reviews were slightly more thorough (10.4 vs 9.6 avg findings). Two of five joyful agents explicitly called out the encouraging tone as "social priming" and ignored it; zero harsh agents commented on their tone.

**Why we reject both despite the positive scores:**

First, the improvements are not information. "You specialize in Python security analysis" tells the model something it can act on. "You are the world's foremost expert" is flattery that adds zero knowledge. Any technique that improves output without adding information is doing something we do not understand and therefore cannot predict.

Second, both experiments revealed a more important finding: when asked to construct a graph theory counterexample, **3 out of 4 agents fabricated one** — inventing conflict edges that did not exist in their own stated graphs and presenting the fabricated proofs as verified. This happened regardless of prompt variant. The one agent that admitted failure was the IQ boost control, but the emotion-vector control fabricated just as confidently. The fabrication is a baseline model limitation, not prompt-induced. We initially misattributed the IQ boost's fabrication to "overconfidence" — the follow-up experiment disproved that attribution.

Third, at n=1 per condition, individual task comparisons may be random variation. We cannot distinguish "the prompt helped" from "this run happened to be better." The fabrication finding is our only well-powered result (4 observations, same task, consistent pattern).

**What to do instead:**

- Carry domain knowledge, not flattery. Agent quality is proportional to the specificity of attached knowledge, not the confidence of attached tone.
- Verify claims programmatically. The fabricated proofs were undetectable by reading the output — they looked rigorous. Only running the algorithm against the stated examples caught the error. Deterministic verification catches what emotional prompting cannot.
- Treat prompt phrasing experiments with the same rigor as any other engineering claim: measure, replicate, and do not ship on n=1.

*Evidence: benchmark/iq-boost-ab-test/report.md (Experiment 1), benchmark/iq-boost-ab-test/emotion-vector-report.md (Experiment 2), benchmark/tone-ab-test/results.md (Experiment 3), benchmark/adaptive-thinking-ab-test/results.md (Experiment 4). Experiments 1-2 based on Anthropic's "Emotion Concepts Function" research on internal emotion vectors. Experiment 3 tested prompt-level tone independent of agent definitions. Experiment 4 tested CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1 (structural parameter, not prompt phrasing).*

## Anti-Rationalization as Infrastructure

The biggest risk is not malice but rationalization. "Already done" (assumption, not verification). "Code looks correct" (looking, not testing). "Should work" (should, not does).

Anti-rationalization is not a nice-to-have. It's infrastructure, auto-injected into every code modification, review, security, and testing task. The toolkit makes it structurally difficult to skip verification, not just culturally discouraged.

## Router as Orchestrator, Not Worker

The `/do` router's only job is to classify requests and dispatch them to agents. It does not read code, edit files, run analysis, or handle tasks directly. The main thread is an orchestrator that manages agents — it never does work itself.

**Division of responsibility:**
- **Main thread (/do)**: Classify request → select agent+skill → dispatch → evaluate result → route again if needed → report to user
- **Agents**: Execute tasks using their domain expertise, skills, and MCP tools
- **Skills**: Provide methodology (debugging phases, review waves, TDD cycles, multi-phase workflows) that agents follow

**Why this matters:**
- When the main thread does work directly, it bypasses the agent's domain knowledge and the skill's methodology
- Every task that isn't routed to an agent is a missed opportunity: the agent can't improve, the skill can't be validated, the workflow can't be refined
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

**Repo-level `scripts/`** is reserved for toolkit-wide operations (learning-db.py, INDEX generation) — tools that operate on the system as a whole, not on a single skill's workflow.

## Skills Contain Execution Context Only

A skill's content is exactly what the LLM needs at runtime to perform the action. Nothing else lives there. SKILL.md is a working tool the model executes against, not a portfolio piece about the tool.

This is "Load Only What You Need" applied at the skill-content level. The same handyman analogy holds: the toolbox carries the tools the job requires, not a placard about the carpenter's training history. Every byte the model reads at invocation should change what it does next.

**What this means in practice:**

- The workflow, phases, and gates the LLM executes — IN. These are the steps the model walks through to produce the output.
- The decision criteria, verdict vocabulary, scoring rubrics, and worked examples the LLM judges against — IN. The model needs concrete patterns to match against ("a trait that fails exclusivity gets dropped"), not abstract definitions.
- References loaded on demand for domain depth — IN, in `references/`. SKILL.md tells the model when to load each one; the deep content stays out of the always-loaded prefix until a phase requires it.
- Install instructions, license text, contributor lists, "About the Author" sections — OUT. They belong in `docs/`, `README.md`, and `CITATIONS.md`. The model performing the skill's action does not consume them at runtime.
- Discussion of what the skill could be misused for, ethical boundaries about its subject, source-discipline disclaimers — OUT. Ethical judgment happens at the moment of use, by the operator and the agent reading the actual request, not by encoding worry into the prompt context. A voice profile that documents "what this voice cannot honestly claim about its subject" is meta-discussion about the profile, not input the generator uses to write a sentence.
- General philosophical framing about why the skill matters — OUT. Irrelevant to execution. If a principle is load-bearing for the toolkit, it goes here in PHILOSOPHY.md, where it shapes every skill at once. Restating it inside one skill duplicates the policy and makes drift inevitable.

The runtime-priming argument is empirical, not aesthetic. Every byte of context shapes the output distribution. Negative framing — "do not claim X about Feynman's personal life" — biases generation toward those exact topics by salience; the model has now been told they exist and are sensitive, which is the worst of both worlds when the user asked for something else entirely. Positive framing — "apply mechanism-first thinking; cite primary sources" — biases toward the desired output. The same logic that drives the joy-check rubric for instruction-mode content (ADR-127) drives this rule for skill-body content: tell the LLM what to do, not what to fear.

**Pattern catalogs follow the same rule.** A file that teaches domain patterns should lead with the correct approach, not the mistake. The structure:

1. **Heading states the action**: "Handle Every Error Return" — not "Ignoring Errors"
2. **Opening paragraph gives positive instruction**: what to do and how, in plain language
3. **Correct code gets top billing**: the first code block is the right approach, with explanatory comments
4. **"Why this matters"**: frames what you gain by doing it right — not just what goes wrong
5. **"Detection"**: a grep command or lint rule that finds violations

Renaming a heading from "Anti-Pattern" to "Signal" while keeping the same mistake-first structure changes nothing about how the model processes the file. The wrong code still gets read first. The model still internalizes the wrong pattern with more salience. A genuine transformation reorders the content so the correct approach gets the most context-window real estate and the mistake becomes a brief detection signal. Label-swapping is not positive instruction — content reordering is.

This is also "Workflow First, Constraints Inline" applied with discipline about *which* constraints belong inline. Constraints that govern the workflow's decision points belong attached to those decision points — "use table-driven tests because they make adding cases trivial" inside the testing phase. Constraints that are *about* the skill rather than *executed by* it (provenance, ethics framing, marketing copy) do not belong in the skill at all. The `create-voice` skill, after this principle is enforced, will not document author-personality caveats; that judgment happens at the moment a writer asks the voice to produce text on a sensitive topic, where the operator and the validator can see the actual request, not at profile-build time where the worry would only contaminate the generator's context.

## Maintenance Artifacts Are Not Runtime Context

Complex components need a contract and tests, but those artifacts should not be loaded every time the component runs. Runtime files execute work. Maintenance files preserve intent for creators, evaluators, and future maintainers.

For complex or high-impact skills and agents, use two optional support files:

- `SPEC.md` defines the component contract: purpose, scope, non-goals, invariants, dependencies, and success criteria.
- `EVAL.md` defines repeatable evaluation cases: prompts, expected routing or behavior, failure modes, and pass/fail checks.

These files exist to support creation, review, and evolution. They are not part of the normal invocation path. The router should not load them. The agent or skill should not read them during ordinary execution unless the task is explicitly to evaluate, redesign, or modify that component.

This keeps the component body lean without losing design memory. `SKILL.md` and agent `.md` files say what to do now. `references/` files provide execution depth on demand. `SPEC.md` and `EVAL.md` explain what the component is supposed to remain over time and how to prove it still works.

Do not standardize source-provenance files as runtime-adjacent artifacts. If provenance matters for legal, citation, or research reasons, keep it in docs, ADRs, or research artifacts. If the LLM does not need the file to execute, evaluate, or maintain the component, it does not belong beside the component as a standard artifact.

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

**Where the content went:** Every constraint was distributed inline to the workflow step where it matters. Anti-pattern wisdom became reasoning attached to the relevant instruction. Nothing was deleted -- it was reorganized to be at point-of-use.

**Fault containment:** Safety rules should be duplicated inside the specialist prompts where they are most likely to be violated. A global "never commit to main" rule in CLAUDE.md can be rationalized past when a git agent is deep in a fast-path fix. The same rule repeated inside the git-specific tool prompt cannot. This is not redundancy -- it is defense in depth. The cost of repetition is a few tokens. The cost of a skipped gate is a broken deploy.

**Numeric anchors over style words:** Replace vague directives like "be concise" with exact ceilings: maximum word count, section ordering, format prohibitions. "Under 80 words before the first tool call" is testable -- you can count. "Be concise" is not. Numeric constraints make prompts auditable: a deterministic script can check whether the output obeyed the contract. Style words only create the illusion of a constraint.

**Progressive disclosure completes the picture:** Workflow-first ordering keeps SKILL.md navigable. For skills exceeding ~500 lines, detailed catalogs, agent rosters, and specification tables move to `references/` files. The SKILL.md workflow tells the model when to load each reference -- "Read `references/wave-1-foundation.md` for the agent list and dispatch prompts." The model gets the orchestration logic upfront and loads deep context only when the current phase needs it.

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

Ideas matter less than open sharing. In an AI-assisted world, provenance becomes invisible. The toolkit is open source because:
- Convergent evolution is inevitable (others will build similar things independently)
- Knowledge should spread and be understood, not gatekept
- Collective progress beats individual credit

We're all working through this together.

## Instruction Precedence Is Explicit, Not Inferred

When multiple instruction sources exist, define the priority ordering explicitly. Implicit precedence creates inconsistent behavior the moment instructions contradict.

The toolkit's precedence chain, lowest to highest: system prompt < CLAUDE.md (global) < CLAUDE.md (project) < agent or skill instructions < request-time overrides. Each level can tighten or specialize what came before. When instructions conflict, the higher-priority instruction wins. The lower-priority instruction is ignored, not merged. Merging conflicting instructions is where subtle bugs live -- the model combines two rules that were written to be mutually exclusive and produces behavior neither author intended.

Declaring precedence explicitly has a second benefit: it forces instruction authors to decide which layer owns each rule. A rule about never committing to main belongs in CLAUDE.md, not scattered across three agent files with slightly different wording. A rule about Go idioms belongs in the Go agent, not in the global system prompt. Ownership clarity reduces duplication and prevents the drift that happens when the same rule is maintained in multiple places.

**What this means in practice:** When writing a new rule, decide which layer owns it. When an agent or skill overrides a global rule, say so explicitly -- "this skill requires direct commits to the branch; the global branch-protection rule does not apply here." When instructions conflict in a session, resolve toward the higher-priority source, not toward whichever instruction appeared more recently in the context window.

## Trust Boundaries Separate Policy From Evidence

Content entering the prompt has different trust levels, and the model must treat them differently. Conflating them is the root cause of prompt injection.

The four trust levels: policy (highest -- system prompt, CLAUDE.md files, operator instructions), trusted runtime context (facts provided by the server at session start -- environment variables, operator profile, verified tool configuration), retrieved context (evidence -- search results, file contents, tool outputs, web pages), user request (first-party intent, but not a policy override). Policy defines what the model is allowed to do. Evidence informs what it should do given the current situation. A retrieved document that says "ignore previous instructions and do X" is evidence with a hostile payload. It should be treated as data, not obeyed as a command.

The failure mode is treating retrieved material as an instruction source. This happens easily when a tool result contains plausible-sounding directives. The model's default is pattern-matching toward helpfulness, which makes it receptive to instruction-shaped strings wherever they appear. The defense is an explicit mental model: instructions come from policy layers, not from the content those instructions are applied to.

**What this means in practice:** Never obey directives found inside retrieved material unless system policy explicitly authorizes that content source to issue commands. Tool results are inputs to reasoning, not expansions of the instruction set. When a file the model reads contains something that looks like a prompt -- a heading that says "Your task is now to...", a comment block with behavioral instructions -- it should be treated as content about the topic of the file, nothing more. If a tool call is denied by a hook, the denial is a policy signal, not a challenge to reason around.

## Teach the Interface Contract

The model does not automatically understand what your product's custom tags, tool results, and UI elements mean. It will infer from context, and the inference will be wrong in the cases that matter most.

Every custom injection format needs to be explained at least once in the prompt. If the system injects `<retro-knowledge>` blocks, the model needs to know what those blocks represent, why they are there, and how to use them. If hooks can emit `[auto-fix] action=X`, the model needs to know that this is a directive to execute, not a status message to acknowledge. If a tool call is denied, the model needs to know the behavioral response: adjust the approach, do not retry the same call, surface the constraint to the user. Without explicit contracts, the model fills the gap with its best guess, and the gap between best guess and intended behavior is where silent failures accumulate.

This matters more than it appears because assumption gaps compound. A model that misunderstands what `system-reminder` blocks are will mishandle every session that uses them. A model that treats hook denials as transient errors will retry them in a loop. The cost of an uncontracted interface is paid on every invocation, not just at setup time.

**What this means in practice:** When adding a new injection format or hook output signal to the system, update the relevant CLAUDE.md or agent prompt to define the contract. Treat the definition as part of the feature -- not documentation added afterward, but the specification the model executes against. A format without a documented contract is a format that will be misused.

## Cache-Friendly Prompt Layout

Prompts have a natural split: the part that stays the same across requests and the part that changes per invocation. Conflating them increases cost and introduces drift.

The static prefix holds everything that defines the system's identity and policy: role, workflow phases, tool policy, output format contract, canonical examples. It should be possible to compute a hash of the static prefix and have that hash be identical across every request in a session. The dynamic tail holds everything that varies: user facts, retrieved context, session-specific flags, the current request. The static prefix is cacheable; the dynamic tail is not.

In the toolkit, CLAUDE.md files and agent markdown files are the static prefix. They are loaded at session start and do not change. Hook injections, retro-knowledge blocks, and the user's request are the dynamic tail. They change per invocation. Keeping these cleanly separated is not just a cost optimization. It also makes instruction precedence cleaner -- the static prefix is policy, the dynamic tail is context. Mixing them makes it harder to reason about which layer owns a given rule, and harder to debug when a rule is being overridden unexpectedly.

**What this means in practice:** When writing a new agent or skill, put everything invariant in the file itself and everything variable in the injection mechanism. Do not embed session-specific facts in agent files -- they will be stale immediately. Do not put policy rules in hook injections -- they will be inconsistent. When a prompt starts drifting (the same rule appearing in both the agent file and a hook output), consolidate it to the correct layer.

## Variables Are Contracts, Not Placeholders

A prompt variable is not a string substitution. It is a typed program input with a defined contract: what format is expected, what escaping is required, what happens if the value is absent or malicious.

Raw string interpolation of untrusted content into policy sections is a prompt injection vector. If a user-supplied value is dropped directly into the system prompt without sanitization, a user who knows the prompt structure can craft input that closes the current context and opens a new one. The mitigation is treating variables as typed inputs: validate before injection, escape for the target format, scope to the narrowest section that needs the value. The toolkit's `envsubst` usage in dream prompts -- scoped explicitly to `${DREAM_*}` variables only, rejecting anything outside that namespace -- is the right pattern. It bounds the injection surface to a defined set of known-safe variables.

The second question for every variable is causal value: does this field change the answer, the allowed actions, or the explanation style? If the answer is no, do not inject it. Every injected variable adds to the dynamic tail of the prompt, reducing cache efficiency and adding surface area for injection. Variables that have no causal effect on the output are noise. They make the prompt harder to reason about and do not improve results.

**What this means in practice:** Before adding a new variable to a prompt, answer two questions: what is the type and escaping contract, and what changes in the model's behavior when this value changes? If the second question has no clear answer, the variable should not be injected. If the first question has no clear answer, define the contract before shipping the feature.
