---
name: skill-creator
description: "Create and iteratively improve skills through eval-driven validation."
routing:
  triggers:
    - create skill
    - new skill
    - skill template
    - skill design
    - test skill
    - improve skill
    - optimize description
    - skill eval
  pairs_with:
    - agent-evaluation
    - verification-before-completion
  complexity: Complex
  category: meta
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
  - Glob
  - Grep
  - Agent
---

# Skill Creator

Create skills and iteratively improve them through measurement.

The process:

- Decide what the skill should do and how it should work
- Write a draft of the skill
- Create test prompts and run claude-with-the-skill on them
- Evaluate the results -- both with agent reviewers and optionally human review
- Improve the skill based on what the evaluation reveals
- Repeat until the skill demonstrably helps

Figure out where the user is in this process and help them progress. If they say
"I want to make a skill for X", help narrow scope, write a draft, write test cases,
and run the eval loop. If they already have a draft, go straight to testing.

---

## Creating a skill

### Capture intent

Start by understanding what the user wants. The current conversation might already
contain a workflow worth capturing ("turn this into a skill"). If so, extract:

1. What should this skill enable Claude to do?
2. When should this skill trigger? (what user phrases, what contexts)
3. What is the expected output?
4. Are the outputs objectively verifiable (code, data transforms, structured files)
   or subjective (writing quality, design aesthetics)? Objectively verifiable outputs
   benefit from test cases. Subjective outputs are better evaluated by human review.

### Duplicate Domain Check

Before creating any new skill, check whether an existing umbrella skill already
covers this domain. This is mandatory -- skipping it leads to system prompt bloat
and routing degradation.

**Step 1**: Search for existing domain coverage.
```bash
grep -i "<domain-keyword>" skills/INDEX.json
ls skills/ | grep "<domain-prefix>"
```

**Step 2**: If a domain skill exists, determine whether the new skill's scope is a
sub-concern of the existing skill. Sub-concerns MUST be added as reference files
on the existing skill, not created as separate skills.

Pattern (correct): `skills/perses/references/plugins.md`
Anti-pattern (wrong): `skills/perses-plugin-creator/SKILL.md`

**Step 3**: If no domain skill exists and the domain has multiple sub-concerns,
create the skill with a `references/` directory from the start.

**One domain = one skill + many reference files. Never create multiple skills for
the same domain.**

Only proceed to writing a new SKILL.md if no existing skill covers the domain, or
if the user explicitly confirms creating a new skill after reviewing the overlap.

### Research

Read the repository CLAUDE.md before writing anything. Project conventions override
default patterns.

### Write the SKILL.md

Based on the user interview, create the skill directory and write the SKILL.md.

**Skill structure:**

```
skill-name/
├── SKILL.md              # Required -- the workflow
├── scripts/              # Deterministic CLI tools the skill invokes
├── agents/               # Subagent prompts used only by this skill
├── references/           # Deep context loaded on demand
└── assets/               # Templates, viewers, static files
```

**Frontmatter** -- name, description, routing metadata. Description caps: 60 chars max for non-invocable skills, 120 chars for user-invocable. No "Use when:", "Use for:", or "Example:" in the description. The `/do` router has its own routing tables.

> See `references/skill-template.md` for the complete frontmatter template with all fields and valid values.

The description is the primary triggering mechanism. Claude tends to undertrigger skills -- be explicit about trigger contexts. Include "Use for" with concrete phrases users would say.

**Body** -- workflow first, then context:

1. Brief overview (2-3 sentences: what this does and how)
2. Instructions / workflow phases (the actual methodology)
3. Reference material (commands, guides, schemas)
4. Error handling (cause/solution pairs for common failures)
5. References to bundled files

Constraints belong inline within the workflow step where they apply. Explain the reasoning behind constraints -- "Run with `-race` because race conditions are silent until production" generalizes; "ALWAYS run with -race" does not.

**Do-pair validation** -- After writing any anti-pattern blocks, run:
```bash
python3 scripts/validate-references.py --check-do-framing
```
Every anti-pattern block must have a paired "Do instead" counterpart. Blocks
without one fail the check. If a prohibition genuinely has no correct alternative,
annotate it with `<!-- no-pair-required: reason -->` to pass validation without
a "Do instead" block. Ship the skill only after this check exits 0.

**Progressive disclosure** -- SKILL.md is the routing target, not the reference
library. It stays lean so it loads fast when Claude considers invoking it, then
reads `references/` on demand as phases execute. See
`references/progressive-disclosure.md` for the full model, economics, and
extraction decision tree.

Key rules:
- SKILL.md: brief overview, phase structure with gates, one-line pointers to
  reference files, error handling
- `references/`: checklists, rubrics, agent dispatch prompts, report templates,
  pattern catalogs, example collections -- anything only needed at execution time
- If SKILL.md exceeds **500 lines** after writing, extract detailed content to
  `references/` before proceeding
- If SKILL.md exceeds **700 lines**, extraction is mandatory -- it is carrying
  reference content that should not be loaded on every routing decision

The most effective complex skills (`sapcc-review`, `voice-writer`) keep SKILL.md under 600 lines and put operational depth in `references/` and `agents/`. Rich `references/` content adds depth at zero routing cost; deterministic `scripts/` ensure consistency; bundled `agents/` prompts enable specialized dispatch without routing overhead.

> See `references/progressive-disclosure.md` for the real numbers and extraction decision tree.

### Bundled scripts

Extract deterministic, repeatable operations into `scripts/*.py` CLI tools with
argparse interfaces. Scripts save tokens (the model doesn't reinvent the wheel
each invocation), ensure consistency across runs, and can be tested independently.

Pattern: `scripts/` for deterministic ops, SKILL.md for LLM-orchestrated workflow.

### Bundled agents

For skills that spawn subagents with specialized roles, bundle agent prompts in
`agents/`. These are not registered in the routing system -- they are internal to
the skill's workflow.

| Scenario | Approach |
|----------|----------|
| Agent used only by this skill | Bundle in `agents/` |
| Agent shared across skills | Keep in repo `agents/` directory |
| Agent needs routing metadata | Keep in repo `agents/` directory |

---

## Testing the skill

This is the core of the eval loop. Do not stop after writing -- test the skill
against real prompts and measure whether it actually helps.

### Create test prompts

Write 2-3 realistic test prompts -- the kind of thing a real user would say. Rich,
detailed, specific. Not abstract one-liners.

Bad: `"Format this data"`
Good: `"I have a CSV in ~/downloads/q4-sales.csv with revenue in column C and costs
in column D. Add a profit margin percentage column and highlight rows where margin
is below 10%."`

Share prompts with the user for review before running them.

> See `references/bundled-components.md` for the evals.json format and workspace directory layout.

### Run test prompts

For each test case, spawn two subagents in the same turn -- one with the skill
loaded, one without (baseline). Launch everything at once so it finishes together.

**With-skill run:** Tell the subagent to read the skill's SKILL.md first, then
execute the task. Save outputs to the workspace.

**Baseline run:** Same prompt, no skill loaded. Save to a separate directory.

### Evaluate results

Evaluation has three tiers, applied in order:

**Tier 1: Deterministic checks** -- run automatically where applicable:
- Does the code compile? (`go build`, `tsc --noEmit`, `python -m py_compile`)
- Do tests pass? (`go test -race`, `pytest`, `vitest`)
- Does the linter pass? (`go vet`, `ruff`, `biome`)

**Tier 2: Agent blind review** -- dispatch using `agents/comparator.md`:
- Comparator receives both outputs labeled "Output 1" / "Output 2"
- It does NOT know which is the skill version
- Scores on relevant dimensions, picks a winner with reasoning
- Save results to `blind_comparison.json`

**Tier 3: Human review (optional)** -- generate the comparison viewer:
```bash
python3 scripts/eval_compare.py path/to/workspace
open path/to/workspace/compare_report.html
```

The viewer shows outputs side by side with blind labels, agent review panels,
deterministic check results, winner picker, feedback textarea, and a
skip-to-results option. Human reviews are optional -- agent reviews are sufficient
for iteration.

### Draft assertions

While test runs are in progress, draft quantitative assertions for objective
criteria. Good assertions are discriminating -- they fail when the skill doesn't
help and pass when it does. Non-discriminating assertions ("file exists") provide
false confidence.

Run the grader (`agents/grader.md`) to evaluate assertions against outputs:
- PASS requires genuine substance, not surface compliance
- The grader also critiques the assertions themselves -- flagging ones that would
  pass regardless of skill quality

Aggregate results with `scripts/aggregate_benchmark.py` to get pass rates,
timing, and token usage with mean/stddev across runs.

---

## Improving the skill

This is the iterative heart of the process.

**Generalize from feedback.** If a fix only helps the test case but wouldn't generalize, it's overfitting. Try different approaches rather than fiddly adjustments.

**Keep instructions lean.** Read execution transcripts, not just final outputs. Remove instructions that cause the model to waste time -- they consume attention budget without producing value.

**Explain the reasoning.** Motivation-based instructions generalize better than bare imperatives. "Prefer X because Y" lets the model apply the principle to situations the skill author didn't anticipate.

**Extract repeated work.** If all subagents independently wrote similar helper scripts, bundle that script in `scripts/`. One shared implementation beats N independent reinventions.

### The iteration loop

1. Apply improvements to the skill
2. Rerun all test cases into `iteration-<N+1>/`, including baselines
3. Generate the comparison viewer with `--previous-workspace` pointing at the
   prior iteration
4. Review -- agent or human
5. Repeat until results plateau or the user is satisfied

Stop iterating when:
- Feedback is empty (outputs look good)
- Pass rates aren't improving between iterations
- The user says they're satisfied

---

## Description optimization

After the skill works well, optimize the description for triggering accuracy.

> See `references/bundled-components.md` for the full optimization loop: eval query format, train/test split, `optimize_description.py` usage, and overfitting guards.

---

## Enriching existing skills

Use this mode when a skill already exists but produces shallow, generic output -- it
has thin `references/`, no `scripts/`, and passes an eval by luck rather than
by containing domain knowledge that changes behavior.

Indicators this mode is appropriate:
- `references/` has fewer than 2 files, or none at all
- No `scripts/` directory
- Eval outputs look plausible but lack domain idioms, concrete examples, or
  checklists specific to the skill's domain
- The skill passes a test because the model already knows the domain, not because
  the skill contributes anything

### The enrichment loop

Six phases: AUDIT (measure current depth), RESEARCH (find gaps), ENRICH (add reference content), TEST (A/B vs baseline), EVALUATE (blind comparator), PUBLISH (branch + PR). Max 3 iterations before escalating to the user. Each retry uses a different research angle: iteration 1 = official docs, iteration 2 = common mistakes, iteration 3 = advanced patterns.

> See `references/enrichment-workflow.md` for the full phase-by-phase checklist, scoring details, retry logic, and exact commit/PR flow.

---

## Bundled agents and scripts

> See `references/bundled-components.md` for the full list of bundled agents (`grader.md`, `comparator.md`, `analyzer.md`), bundled scripts, workspace layout, and evals.json format.

---

## Reference files

- `references/progressive-disclosure.md` -- The disclosure model: economics, size
  gates, what to extract, real examples from the toolkit, script and agent patterns
- `references/skill-template.md` -- Complete SKILL.md template with all sections
- `references/artifact-schemas.md` -- JSON schemas for eval artifacts (evals.json,
  grading.json, benchmark.json, comparison.json, timing.json, metrics.json)
- `references/complexity-tiers.md` -- Skill examples by complexity tier
- `references/workflow-patterns.md` -- Reusable phase structures and gate patterns
- `references/error-catalog.md` -- Common skill creation errors with solutions
- `references/enrichment-workflow.md` -- Deep reference for the enrichment loop:
  AUDIT checklist, RESEARCH strategy, ENRICH structuring, TEST/EVALUATE/PUBLISH phases,
  and retry logic in detail
- `references/domain-research-targets.md` -- Lookup table: given a skill's domain,
  which primary sources, secondary sources, and extraction targets to use during RESEARCH
- `references/bundled-components.md` -- Bundled agents, scripts, workspace layout,
  evals.json format, and description optimization procedure

---

## Error handling

### Skill doesn't trigger when it should
Cause: Description is too vague or missing trigger phrases
Solution: Add explicit "Use for" phrases matching what users actually say.
Test with `scripts/optimize_description.py`.

### Test run produces empty output
Cause: The `claude -p` subprocess didn't load the skill, or the skill path is wrong
Solution: Verify the skill directory contains SKILL.md (exact case). Check
the `--skill-path` argument points to the directory, not the file.

### Grading results show all-pass regardless of skill
Cause: Assertions are non-discriminating (e.g., "file exists")
Solution: Write assertions that test behavior, not structure. The grader's
eval critique section flags these -- read it.

### Iteration loop doesn't converge
Cause: Changes are overfitting to test cases rather than improving the skill
Solution: Expand the test set with more diverse prompts. Focus improvements
on understanding WHY outputs differ, not on patching specific failures.

### Description optimization overfits to train set
Cause: Test set is too small or train/test queries are too similar
Solution: Ensure should-trigger and should-not-trigger queries are realistic
near-misses, not obviously different. The 60/40 split guards against this,
but only if the queries are well-designed.

## Reference Loading Table

<!-- Auto-generated by scripts/inject_reference_loading_tables.py -->

| Signal | Load These Files | Why |
|---|---|---|
| implementation patterns | `anti-patterns.md` | Loads detailed guidance from `anti-patterns.md`. |
| tasks related to this reference | `artifact-schemas.md` | Loads detailed guidance from `artifact-schemas.md`. |
| tasks related to this reference | `bundled-components.md` | Loads detailed guidance from `bundled-components.md`. |
| tasks related to this reference | `complexity-tiers.md` | Loads detailed guidance from `complexity-tiers.md`. |
| tasks related to this reference | `domain-research-targets.md` | Loads detailed guidance from `domain-research-targets.md`. |
| workflow steps | `enrichment-workflow.md` | Loads detailed guidance from `enrichment-workflow.md`. |
| errors | `error-catalog.md` | Loads detailed guidance from `error-catalog.md`. |
| tasks related to this reference | `progressive-disclosure.md` | Loads detailed guidance from `progressive-disclosure.md`. |
| tasks related to this reference | `skill-template.md` | Loads detailed guidance from `skill-template.md`. |
| workflow steps, implementation patterns | `workflow-patterns.md` | Loads detailed guidance from `workflow-patterns.md`. |
