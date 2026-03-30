---
name: skill-creator
description: |
  Create new skills and iteratively improve them through eval-driven validation.
  Draft a skill, test it against real prompts, review the outputs, improve based
  on measured results, repeat. Use when creating new skills, improving existing
  skills, testing skill quality, or optimizing descriptions for triggering accuracy.
  Use for "create skill", "new skill", "test skill", "improve skill", "optimize
  description", "skill eval", "turn this into a skill". Do NOT use for agent
  creation (this skill also handles agents) or hook development (use
  hook-development-engineer).
version: 2.0.0
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
- Evaluate the results — both with agent reviewers and optionally human review
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

### Research

Check for existing skills that overlap — run `grep -r "trigger-keyword" skills/*/SKILL.md`
to avoid duplicating what already exists. If a similar skill exists, offer to improve
it rather than create a new one.

Read the repository CLAUDE.md before writing anything. Project conventions override
default patterns.

### Write the SKILL.md

Based on the user interview, create the skill directory and write the SKILL.md.

**Skill structure:**

```
skill-name/
├── SKILL.md              # Required — the workflow
├── scripts/              # Deterministic CLI tools the skill invokes
├── agents/               # Subagent prompts used only by this skill
├── references/           # Deep context loaded on demand
└── assets/               # Templates, viewers, static files
```

**Frontmatter** — name, description, routing metadata:

```yaml
---
name: skill-slug-name
description: |
  [What it does — 1-2 sentences]. Use when [trigger conditions].
  Use for "[phrase 1]", "[phrase 2]". Do NOT use for [exclusions].
version: 1.0.0
routing:
  triggers:
    - keyword1
    - keyword2
  pairs_with:
    - related-skill
  complexity: Simple | Medium | Complex
  category: language | infrastructure | review | meta | content
allowed-tools:
  - Read
  - Write
  - Bash
---
```

The description is the primary triggering mechanism. Claude tends to undertrigger
skills — not activating them when they would help. Combat this by being explicit
about trigger contexts. Include "Use for" with concrete phrases users would say.

**Body** — workflow first, then context:

1. Brief overview (2-3 sentences: what this does and how)
2. Instructions / workflow phases (the actual methodology)
3. Reference material (commands, guides, schemas)
4. Error handling (cause/solution pairs for common failures)
5. References to bundled files

Constraints belong inline within the workflow step where they apply, not in a
separate section. If a constraint matters during Phase 2, put it in Phase 2 —
not in a preamble the model reads 200 lines before it reaches Phase 2.

Explain the reasoning behind constraints rather than issuing bare imperatives.
"Run with `-race` because race conditions are silent until production" is more
effective than "ALWAYS run with -race" because the model can generalize the
reasoning to situations the skill author didn't anticipate.

**Progressive disclosure** — SKILL.md is the routing target, not the reference
library. It stays lean so it loads fast when Claude considers invoking it, then
reads `references/` on demand as phases execute. See
`references/progressive-disclosure.md` for the full model, economics, and
extraction decision tree.

Key rules:
- SKILL.md: brief overview, phase structure with gates, one-line pointers to
  reference files, error handling
- `references/`: checklists, rubrics, agent dispatch prompts, report templates,
  pattern catalogs, example collections — anything only needed at execution time
- If SKILL.md exceeds **500 lines** after writing, extract detailed content to
  `references/` before proceeding
- If SKILL.md exceeds **700 lines**, extraction is mandatory — it is carrying
  reference content that should not be loaded on every routing decision

**Maximizing skill effectiveness:**

| More of this → better skill | Why |
|-----------------------------|-----|
| Rich `references/` content | Depth available at execution; zero cost at routing time |
| Deterministic `scripts/` | Consistency, token savings, independent testability |
| Bundled `agents/` prompts | Specialized dispatch without routing system overhead |

The most effective complex skills in this toolkit (`comprehensive-review`,
`sapcc-review`, `voice-writer`) have SKILL.md under 600 lines and put all
operational depth in `references/` and `agents/`. See
`references/progressive-disclosure.md` for the real numbers.

### Bundled scripts

Extract deterministic, repeatable operations into `scripts/*.py` CLI tools with
argparse interfaces. Scripts save tokens (the model doesn't reinvent the wheel
each invocation), ensure consistency across runs, and can be tested independently.

Pattern: `scripts/` for deterministic ops, SKILL.md for LLM-orchestrated workflow.

### Bundled agents

For skills that spawn subagents with specialized roles, bundle agent prompts in
`agents/`. These are not registered in the routing system — they are internal to
the skill's workflow.

| Scenario | Approach |
|----------|----------|
| Agent used only by this skill | Bundle in `agents/` |
| Agent shared across skills | Keep in repo `agents/` directory |
| Agent needs routing metadata | Keep in repo `agents/` directory |

---

## Testing the skill

This is the core of the eval loop. Do not stop after writing — test the skill
against real prompts and measure whether it actually helps.

### Create test prompts

Write 2-3 realistic test prompts — the kind of thing a real user would say. Rich,
detailed, specific. Not abstract one-liners.

Bad: `"Format this data"`
Good: `"I have a CSV in ~/downloads/q4-sales.csv with revenue in column C and costs
in column D. Add a profit margin percentage column and highlight rows where margin
is below 10%."`

Share prompts with the user for review before running them.

Save test cases to `evals/evals.json` in the workspace (not in the skill directory —
eval data is ephemeral):

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "name": "descriptive-name",
      "prompt": "The realistic user prompt",
      "assertions": []
    }
  ]
}
```

### Run test prompts

For each test case, spawn two subagents in the same turn — one with the skill
loaded, one without (baseline). Launch everything at once so it finishes together.

**With-skill run:** Tell the subagent to read the skill's SKILL.md first, then
execute the task. Save outputs to the workspace.

**Baseline run:** Same prompt, no skill loaded. Save to a separate directory.

Organize results by iteration:

```
skill-workspace/
├── evals/evals.json
├── iteration-1/
│   ├── eval-descriptive-name/
│   │   ├── with_skill/outputs/
│   │   ├── without_skill/outputs/
│   │   └── grading.json
│   └── benchmark.json
└── iteration-2/
    └── ...
```

### Evaluate results

Evaluation has three tiers, applied in order:

**Tier 1: Deterministic checks** — run automatically where applicable:
- Does the code compile? (`go build`, `tsc --noEmit`, `python -m py_compile`)
- Do tests pass? (`go test -race`, `pytest`, `vitest`)
- Does the linter pass? (`go vet`, `ruff`, `biome`)

**Tier 2: Agent blind review** — dispatch using `agents/comparator.md`:
- Comparator receives both outputs labeled "Output 1" / "Output 2"
- It does NOT know which is the skill version
- Scores on relevant dimensions, picks a winner with reasoning
- Save results to `blind_comparison.json`

**Tier 3: Human review (optional)** — generate the comparison viewer:
```bash
python3 scripts/eval_compare.py path/to/workspace
open path/to/workspace/compare_report.html
```

The viewer shows outputs side by side with blind labels, agent review panels,
deterministic check results, winner picker, feedback textarea, and a
skip-to-results option. Human reviews are optional — agent reviews are sufficient
for iteration.

### Draft assertions

While test runs are in progress, draft quantitative assertions for objective
criteria. Good assertions are discriminating — they fail when the skill doesn't
help and pass when it does. Non-discriminating assertions ("file exists") provide
false confidence.

Run the grader (`agents/grader.md`) to evaluate assertions against outputs:
- PASS requires genuine substance, not surface compliance
- The grader also critiques the assertions themselves — flagging ones that would
  pass regardless of skill quality

Aggregate results with `scripts/aggregate_benchmark.py` to get pass rates,
timing, and token usage with mean/stddev across runs.

---

## Improving the skill

This is the iterative heart of the process.

**Generalize from feedback.** Skills will be used across many prompts, not just
test cases. If a fix only helps the test case but wouldn't generalize, it's
overfitting. Try different approaches rather than fiddly adjustments.

**Keep instructions lean.** Read the execution transcripts, not just the final
outputs. If the skill causes the model to waste time on unproductive work, remove
those instructions. Instructions that don't pull their weight hurt more than they
help — they consume attention budget without producing value.

**Explain the reasoning.** Motivation-based instructions generalize better than
rigid imperatives. "Prefer table-driven tests because they make adding cases
trivial and the input-output relationship explicit" works better than "MUST use
table-driven tests" because the model understands when the pattern applies and
when it doesn't.

**Extract repeated work.** Read the transcripts from test runs. If all subagents
independently wrote similar helper scripts or took the same multi-step approach,
bundle that script in `scripts/`. One shared implementation beats N independent
reinventions.

### The iteration loop

1. Apply improvements to the skill
2. Rerun all test cases into `iteration-<N+1>/`, including baselines
3. Generate the comparison viewer with `--previous-workspace` pointing at the
   prior iteration
4. Review — agent or human
5. Repeat until results plateau or the user is satisfied

Stop iterating when:
- Feedback is empty (outputs look good)
- Pass rates aren't improving between iterations
- The user says they're satisfied

---

## Description optimization

The description field determines whether Claude activates the skill. After the
skill is working well, optimize the description for triggering accuracy.

Generate 20 eval queries — 10 that should trigger, 10 that should not. The
should-not queries are the most important: they should be near-misses from
adjacent domains, not obviously irrelevant queries.

Run the optimization loop:
```bash
python3 scripts/optimize_description.py \
  --skill-path path/to/skill \
  --eval-set evals/trigger-eval.json \
  --max-iterations 5
```

This splits queries 60/40 train/test, evaluates the current description (3 runs
per query for reliability), proposes improvements based on failures, and selects
the best description by test-set score to avoid overfitting.

---

## Enriching existing skills

Use this mode when a skill already exists but produces shallow, generic output — it
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

Six phases, max 3 iterations before escalating to the user:

**AUDIT** — measure the skill's current depth before changing anything.
Count `references/`, `scripts/`, `agents/` files. Run the skill against 2-3
realistic prompts. Save outputs to `enrichment-workspace/baseline/`.
See `references/enrichment-workflow.md` → AUDIT phase for the exact checklist.

**RESEARCH** — find domain knowledge the skill is missing.
Read the skill's SKILL.md and existing references to identify gaps. Search for
best practices, pattern catalogs with before/after examples, common mistakes,
and validation criteria. Where to look depends on the skill's domain — consult
`references/domain-research-targets.md` for a lookup table of primary and
secondary sources per domain.

**ENRICH** — add the research as reference content.
Create new files in the skill's `references/` directory. Add deterministic
`scripts/` where operations are repeatable. Update SKILL.md only with one-line
pointers to the new references — keep the orchestrator lean. Focus on content
that changes behavior: concrete examples beat abstract advice.
See `references/enrichment-workflow.md` → ENRICH phase for structuring guidance.

**TEST** — A/B test the enriched skill against baseline.
Write 2-3 realistic prompts that exercise the skill's domain. Use
`scripts/run_eval.py` to run enriched vs baseline on the same prompts. Both
runs use identical inputs. Save outputs to `enrichment-workspace/iteration-N/`.

**EVALUATE** — dispatch blind comparators on each test prompt.
Use `agents/comparator.md` (already bundled in this skill). Comparator scores on
depth, accuracy, actionability, and domain idioms without knowing which version
is which. If enriched wins 2/3 or better → PUBLISH. If tie or loss → run
`agents/analyzer.md` to understand why, then RETRY with a different research angle.
See `references/enrichment-workflow.md` → EVALUATE phase for scoring details.

**PUBLISH** — commit validated improvements.
Create branch `feat/enrich-{skill-name}`, commit references + scripts + SKILL.md
pointer updates, push, create PR. See `references/enrichment-workflow.md` →
PUBLISH phase for the exact commit/PR flow.

### Retry logic

Each retry uses a different research angle to avoid retreading the same ground:

| Iteration | Research angle |
|-----------|---------------|
| 1 | Official docs + canonical best practices |
| 2 | Common mistakes + anti-patterns (what goes wrong) |
| 3 | Advanced patterns + edge cases (what experts know) |

After 3 failed iterations, report to the user: summarize what was tried, what the
evaluator found lacking, and ask whether to try a different approach or accept the
current state.

---

## Bundled agents

The `agents/` directory contains prompts for specialized subagents used by this
skill. Read them when you need to spawn the relevant subagent.

- `agents/grader.md` — Evaluate assertions against outputs with cited evidence
- `agents/comparator.md` — Blind A/B comparison of two outputs
- `agents/analyzer.md` — Post-hoc analysis of why one version beat another

---

## Bundled scripts

- `scripts/run_eval.py` — Execute a skill against a test prompt via `claude -p`
- `scripts/aggregate_benchmark.py` — Compute pass rate statistics across runs
- `scripts/optimize_description.py` — Train/test description optimization loop
- `scripts/package_results.py` — Consolidate iteration artifacts into a report
- `scripts/eval_compare.py` — Generate blind comparison HTML viewer

---

## Reference files

- `references/progressive-disclosure.md` — The disclosure model: economics, size
  gates, what to extract, real examples from the toolkit, script and agent patterns
- `references/skill-template.md` — Complete SKILL.md template with all sections
- `references/artifact-schemas.md` — JSON schemas for eval artifacts (evals.json,
  grading.json, benchmark.json, comparison.json, timing.json, metrics.json)
- `references/complexity-tiers.md` — Skill examples by complexity tier
- `references/workflow-patterns.md` — Reusable phase structures and gate patterns
- `references/error-catalog.md` — Common skill creation errors with solutions
- `references/enrichment-workflow.md` — Deep reference for the enrichment loop:
  AUDIT checklist, RESEARCH strategy, ENRICH structuring, TEST/EVALUATE/PUBLISH phases,
  and retry logic in detail
- `references/domain-research-targets.md` — Lookup table: given a skill's domain,
  which primary sources, secondary sources, and extraction targets to use during RESEARCH

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
eval critique section flags these — read it.

### Iteration loop doesn't converge
Cause: Changes are overfitting to test cases rather than improving the skill
Solution: Expand the test set with more diverse prompts. Focus improvements
on understanding WHY outputs differ, not on patching specific failures.

### Description optimization overfits to train set
Cause: Test set is too small or train/test queries are too similar
Solution: Ensure should-trigger and should-not-trigger queries are realistic
near-misses, not obviously different. The 60/40 split guards against this,
but only if the queries are well-designed.
