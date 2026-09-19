---
name: toolkit
description: "Toolkit management: create and evaluate skills and agents, manage routing tables, generate Claude.md."
user-invocable: true
agent: toolkit-governance-engineer
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Agent
  - Task
  - Skill
routing:
  force_route: true
  not_for: "application code (use workflow), code review (use review)"
  triggers:
    - "create skill"
    - "create agent"
    - "scaffold skill"
    - "scaffold agent"
    - "new skill"
    - "new agent"
    - "skill template"
    - "agent template"
    - "eval skill"
    - "evaluate agent"
    - "benchmark skill"
    - "benchmark agents"
    - "compare agents"
    - "A/B test agents"
    - "optimize description"
    - "evolve toolkit"
    - "toolkit evolution"
    - "self-improve"
    - "update routing tables"
    - "routing maintenance"
    - "generate claude.md"
    - "create claude.md"
    - "compose skills"
    - "bake-off"
    - "skill quality"
  category: meta-tooling
  pairs_with:
    - review
    - workflow
---

# Toolkit

Nine modes covering the full toolkit lifecycle: creating, evaluating, and
improving skills and agents; maintaining routing tables; generating CLAUDE.md;
composing multi-skill DAGs; and running the evolution loop. Classify the request
and follow the matching section.

## Mode Selection

| Mode | Signals | Section |
|------|---------|---------|
| **Skill Creator** | create skill, scaffold skill, new skill, build a skill | Create Skill |
| **Agent Creator** | create agent, scaffold agent, new agent | Create Agent |
| **Skill Eval** | eval skill, benchmark skill, improve skill, bake-off | Evaluate Skill |
| **Agent Comparison** | compare agents, A/B test agents, benchmark agents | Compare Agents |
| **Agent Evaluation** | evaluate agent quality, audit agent, grade agent | Evaluate Agent |
| **Skill Composer** | compose skills, DAG orchestration, skill pipeline | Compose Skills |
| **Routing Tables** | update routing tables, sync routing, routing drift | Update Routing |
| **Toolkit Evolution** | evolve toolkit, self-improve, discover gaps | Evolve Toolkit |
| **Generate CLAUDE.md** | generate claude.md, create claude.md, init | Generate CLAUDE.md |

---

## Create Skill

Phases: **INTENT -> DRAFT -> TEST -> EVAL -> IMPROVE**

1. **Capture intent.** What should the skill do? When should it trigger? What output? Are outputs objectively verifiable (code, data) or subjective (writing, design)?
2. **Duplicate check.** Run `grep -i "<domain>" skills/*/SKILL.md` to check existing coverage. If an umbrella skill covers the domain, add a reference file instead.
3. **Write SKILL.md.** Follow `references/skill-creator/skill-template.md` for frontmatter structure. Apply Dense-Complete Writing standard. Frontmatter must include: name, description, routing (triggers, not_for, category, pairs_with), allowed-tools.
4. **Create test prompts.** 3 should-trigger, 2 should-not-trigger, 2 near-miss prompts. Save as `EVAL.md`.
5. **Run eval loop.** Execute test prompts with the skill loaded. Grade results. Iterate on the SKILL.md until eval passes.
6. **Register.** Run `python3 scripts/generate-skill-index.py` to update routing.

Load `references/skill-creator.md` for the full workflow. Deep references in `references/skill-creator/` cover progressive disclosure, artifact schemas, complexity tiers, error catalog, enrichment workflow, and more.

Scripts: `scripts/skill-creator/`

---

## Create Agent

Phases: **DISCOVER -> DESIGN -> SCAFFOLD -> REGISTER -> VALIDATE**

1. **Discover.** Check for domain overlap: `grep -i "<domain>" agents/*.md`. If an existing agent covers the domain, add a `references/` file instead.
2. **Design.** Decide role type (reviewer/engineer/orchestrator), allowed tools, complexity, triggers (3-6 specific phrases), pairs_with (verify each exists), reference files, description (intent verb + domain + boundary clause), activation cases.
3. **Scaffold.** Write the agent file using `references/agent-creator/agent-frontmatter-template.md`. Follow `docs/PHILOSOPHY.md` for operator context structure.
4. **Register.** Run `python3 scripts/generate-agent-index.py`.
5. **Validate.** Run `python3 scripts/validate-references.py` to check reference file integrity. Test activation with the 3+2+2 prompt set.

Load `references/agent-creator.md` for full phases. Deep references in `references/agent-creator/` cover design patterns, frontmatter template, eval design.

---

## Evaluate Skill

Three evaluation types: **trigger testing**, **A/B benchmark**, and **bake-off**.

1. **Trigger test.** Run each EVAL.md prompt. Grade: did the skill activate? Did it produce correct output?
2. **A/B benchmark.** Compare skill variants on the same prompts. Measure: accuracy, token usage, user satisfaction. Load `references/skill-eval/schemas.md` for grading schemas.
3. **Bake-off.** Head-to-head comparison of two skill variants. Load `references/skill-eval/bake-off-methodology.md`.
4. **Self-improve loop.** After eval, identify weaknesses, modify the SKILL.md, re-eval. Load `references/skill-eval/self-improve-loop.md`.

Load `references/skill-eval.md` for the full methodology.

---

## Compare Agents

Controlled benchmarks comparing agent variants on identical tasks.

1. **Select variants.** Identify the agents to compare (2-4 variants).
2. **Design benchmark.** Load `references/agent-comparison/benchmark-tasks.md`. Select 5-10 representative tasks covering the agent's domain.
3. **Execute.** Run each task with each variant. Collect: output quality, token usage, tool calls, time.
4. **Grade.** Apply rubric from `references/agent-comparison/grading-rubric.md`. Score each dimension.
5. **Report.** Use `references/agent-comparison/report-template.md`. Include: methodology, per-task scores, aggregate rankings, cost analysis, recommendation.
6. **Optimize.** Load `references/agent-comparison/optimize-phase.md` to improve the winning variant further.

Load `references/agent-comparison.md` for the full methodology.

---

## Evaluate Agent

Static structural and standards-compliance grading with a 90-point deterministic scorer.

1. **Read the agent file.** Extract frontmatter, body sections, reference files.
2. **Score.** Apply rubric from `references/agent-evaluation/scoring-rubric.md`. Categories: identity (15 pts), expertise (20 pts), routing (15 pts), references (15 pts), workflow (15 pts), standards (10 pts).
3. **Report.** Use `references/agent-evaluation/report-templates.md`. Include: per-category scores, specific findings, improvement recommendations.
4. **Batch mode.** For multiple agents: `references/agent-evaluation/batch-evaluation.md`.

Load `references/agent-evaluation.md` for the full methodology.

---

## Compose Skills

DAG-based multi-skill orchestration with dependency resolution.

1. **Define the DAG.** List skills in execution order. Identify dependencies (skill B needs output from skill A).
2. **Check compatibility.** Load `references/skill-composer/compatibility-matrix.md`. Verify input/output contracts between skills.
3. **Build the pipeline.** Load `references/skill-composer/composition-patterns.md` for orchestration patterns (serial, parallel, fan-out, conditional).
4. **Execute.** Run skills in DAG order. Pass outputs between skills via the defined contracts.
5. **Validate.** Check all skills completed. Verify final output meets the composite goal.

Load `references/skill-composer.md` for the full methodology. See `references/skill-composer/examples.md` for worked examples.

Scripts: `scripts/skill-composer/`

---

## Update Routing

5-phase pipeline: SCAN -> EXTRACT -> GENERATE -> UPDATE -> VERIFY.

1. **SCAN.** Run `python3 scripts/generate-skill-index.py` to discover all skills and agents.
2. **EXTRACT.** Parse frontmatter from each SKILL.md and agent file. Extract triggers, description, category, complexity.
3. **GENERATE.** Build `skills/INDEX.json` and `agents/INDEX.json`.
4. **UPDATE.** Write index files. PostToolUse hooks auto-regenerate on individual edits; this covers bulk changes and drift.
5. **VERIFY.** Compare generated index against discovered files. Report missing entries, conflicts, or stale entries.

Load `references/routing-table-updater.md` for full phases. Deep references in `references/routing-table-updater/` cover routing format, extraction patterns, conflict resolution, batch mode.

---

## Evolve Toolkit

7-phase pipeline: DISCOVER -> DIAGNOSE -> PROPOSE -> CRITIQUE -> BUILD -> VALIDATE -> EVOLVE.

1. **DISCOVER.** Audit recent sessions for routing failures, skill gaps, agent weaknesses, user friction.
2. **DIAGNOSE.** Load `references/toolkit-evolution/diagnose-scripts.md`. Run gap analysis scripts. Identify patterns.
3. **PROPOSE.** Generate 3-5 improvement proposals with expected impact, effort, risk.
4. **CRITIQUE.** Apply multi-perspective review to proposals.
5. **BUILD.** Implement the approved proposals using the appropriate mode above (create skill, create agent, etc.).
6. **VALIDATE.** Run evals on new/changed components.
7. **EVOLVE.** Update evolution history at `references/toolkit-evolution/evolution-history.md`.

Load `references/toolkit-evolution.md` for the full pipeline.

---

## Generate CLAUDE.md

4-phase pipeline: SCAN -> DETECT -> GENERATE -> VALIDATE.

1. **SCAN.** Check for existing CLAUDE.md. If present, write to `CLAUDE.md.generated` for comparison. Detect language, framework, build system from repo files.
2. **DETECT.** Identify domain enrichment opportunities. Load `references/generate-claudemd/examples-and-errors.md` for language-specific patterns.
3. **GENERATE.** Load template from `references/generate-claudemd/CLAUDEMD_TEMPLATE.md`. Fill sections: overview, commands, architecture, conventions, testing, deployment.
4. **VALIDATE.** Run all documented commands. Verify paths exist. Check for secrets in output.

Optional modes: subdirectory CLAUDE.md for monorepos; minimal mode (overview + commands + architecture only).

---

## Deep References

Load when the task needs detailed schemas, templates, or methodology.

| Mode | Key References |
|------|---------------|
| Skill Creator | `references/skill-creator.md`, `references/skill-creator/{skill-template,progressive-disclosure,complexity-tiers,error-catalog,enrichment-workflow}.md` |
| Agent Creator | `references/agent-creator.md`, `references/agent-creator/{agent-design-patterns,agent-frontmatter-template,agent-eval-design}.md` |
| Skill Eval | `references/skill-eval.md`, `references/skill-eval/{schemas,self-improve-loop,bake-off-methodology}.md` |
| Agent Comparison | `references/agent-comparison.md`, `references/agent-comparison/{methodology,grading-rubric,benchmark-tasks,report-template,optimize-phase}.md` |
| Agent Evaluation | `references/agent-evaluation.md`, `references/agent-evaluation/{scoring-rubric,report-templates,batch-evaluation}.md` |
| Skill Composer | `references/skill-composer.md`, `references/skill-composer/{compatibility-matrix,composition-patterns,skill-patterns,examples}.md` |
| Routing Tables | `references/routing-table-updater.md`, `references/routing-table-updater/{routing-format,extraction-patterns,conflict-resolution,examples}.md` |
| Toolkit Evolution | `references/toolkit-evolution.md`, `references/toolkit-evolution/{diagnose-scripts,evolution-history,evolve-preferred-patterns}.md` |
| Generate CLAUDE.md | `references/generate-claudemd.md`, `references/generate-claudemd/{CLAUDEMD_TEMPLATE,examples-and-errors}.md` |

## Scripts and Agents

| Mode | Scripts | Agents |
|------|---------|--------|
| Skill Creator | `scripts/skill-creator/` | `agents/skill-creator/` |
| Skill Composer | `scripts/skill-composer/` | -- |
| Skill Eval | -- | `agents/skill-eval/` |
| Routing Tables | `scripts/routing-table-updater/` | -- |
| Agent Comparison | `scripts/agent-comparison/` | -- |
