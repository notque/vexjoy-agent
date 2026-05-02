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

## Output style directive (applies to every generated skill/agent)

Generated SKILL.md and agent bodies: dense informational text, maximize signal.

- No motivational framing, pep talk, or "this will help you..."
- No repeated restatement of the same constraint
- Prefer tables, numbered phases, bullet lists over paragraphs
- Every sentence must carry information the model acts on
- "Why" stays short, attached to its rule -- one clause, not a paragraph

This governs outputs of this skill, not this file's own prose.

The process:

- Decide what the skill should do
- Write a draft
- Create test prompts, run claude-with-the-skill on them
- Evaluate results (agent reviewers + optional human review)
- Improve based on evaluation
- Repeat until the skill demonstrably helps

Meet the user where they are. "I want to make a skill for X" -> help narrow scope, draft, test, eval. Already have a draft -> go straight to testing.

---

## Creating a skill

### Capture intent

Understand what the user wants. If the current conversation contains a workflow worth capturing, extract:

1. What should this skill enable Claude to do?
2. When should it trigger? (phrases, contexts)
3. Expected output?
4. Are outputs objectively verifiable (code, data, structured files) or subjective (writing quality, design)? Verifiable -> test cases. Subjective -> human review.

### Duplicate Domain Check

Mandatory before creating any new skill.

**Step 1**: Search for existing domain coverage.
```bash
grep -i "<domain-keyword>" skills/INDEX.json
ls skills/ | grep "<domain-prefix>"
```

**Step 2**: If domain skill exists and new scope is a sub-concern, add as reference file on existing skill.

Correct: `skills/perses/references/plugins.md`
Wrong: `skills/perses-plugin-creator/SKILL.md`

**Step 3**: If no domain skill exists and domain has multiple sub-concerns, create with `references/` from the start.

**One domain = one skill + many reference files.**

Proceed only if no existing skill covers the domain, or user explicitly confirms after reviewing overlap.

### Research

Read `docs/PHILOSOPHY.md` before writing any component -- it contains binding architectural decisions governing agent knowledge, skill workflow structure, reference organization, and content framing.

Read CLAUDE.md. Project conventions override defaults.

### Write the SKILL.md

**Skill structure:**

```
skill-name/
├── SKILL.md              # Required -- the workflow
├── SPEC.md               # Optional -- contract for complex/high-impact skills
├── EVAL.md               # Optional -- repeatable eval cases
├── scripts/              # Deterministic CLI tools
├── agents/               # Subagent prompts (internal to skill)
├── references/           # Deep context loaded on demand
└── assets/               # Templates, viewers, static files
```

**Maintenance artifacts** -- For Complex, security-sensitive, router-facing, PR/release, or frequently-iterated skills, create `SPEC.md` and `EVAL.md`:

- `SPEC.md`: purpose, scope, non-goals, invariants, dependencies, success criteria
- `EVAL.md`: representative prompts, expected behavior, failure modes, pass/fail checks

Do not create `SOURCES.md`. Provenance belongs in docs/ADRs/citations. Maintenance artifacts are not runtime context -- SKILL.md should not load `SPEC.md`/`EVAL.md` during ordinary execution.

**Frontmatter** -- name, description, routing metadata. Description caps: 60 chars (non-invocable), 120 chars (user-invocable). No "Use when:", "Use for:", or "Example:" in description.

**`user_invocable` default is `false`.** Emit explicitly:

```yaml
user_invocable: false  # default -- router-dispatched
```

Flipping to `true` requires justification comment naming trigger phrases and why `/do` dispatch is insufficient:

```yaml
user_invocable: true  # justification: users type "/pr-workflow" directly;
                      # /do dispatch bypassed because user is scoped to PR lifecycle.
```

No justification = leave `false`.

> See `references/skill-template.md` for complete frontmatter template.

**Frontmatter validation (mandatory post-write gate):**

```bash
python3 scripts/validate-skill-frontmatter.py skills/<skill-name>/SKILL.md
```

Scaffold not complete until exit 0. Catches: broken YAML, name/directory mismatch, missing routing/triggers/category, top-level `pairs_with`, `force_routing` typo.

**Body** -- workflow first:

1. Brief overview (2-3 sentences)
2. Instructions / workflow phases
3. Reference material (commands, guides, schemas)
4. Error handling (cause/solution pairs)
5. References to bundled files

Constraints inline within workflow steps. Explain reasoning -- "Run with `-race` because race conditions are silent until production" generalizes; "ALWAYS run with -race" does not.

**Do-pair validation** -- After writing anti-pattern blocks:
```bash
python3 scripts/validate-references.py --check-do-framing
```
Every anti-pattern needs a paired "Do instead". Blocks without one: annotate `<!-- no-pair-required: reason -->`. Ship only after exit 0.

**Triple-validation verdicts** -- When the skill documents patterns (mental models, heuristics, phrase fingerprints, code conventions), every pattern block carries a verdict: **KEEP**, **FOOTNOTE**, or **DROP**.

Rubric (recurrence, generative power, exclusivity) at `skills/create-voice/references/extraction-validation.md`. Load on demand.

Accepted verdict markers (priority order):
1. `**Verdict**: KEEP` / `FOOTNOTE` / `DROP` in block body
2. Inline tag on H3: `### M1: Mechanism-first (KEEP)`
3. Blanket tag on H2: `## Mental Models (KEEP-verdict)` (per-block overrides blanket)

Each KEEP/FOOTNOTE pattern needs one-line evidence covering three checks ("appears in X and Y; predicts Z; distinguishes from W"). Verdict without evidence fails gate.

**Phase gate:**
```bash
python3 scripts/check-skill-verdicts.py skills/<your-skill>/SKILL.md
```

Walks H3 sections under pattern-related H2s. Exits non-zero on missing/DROP verdicts. Pure workflow skills exit 0 trivially.

**Progressive disclosure** -- SKILL.md is the routing target, not the reference library.

Key rules:
- SKILL.md: brief overview, phase structure with gates, one-line pointers to references, error handling
- `references/`: checklists, rubrics, agent prompts, templates, pattern catalogs
- Over **500 lines**: extract detailed content to `references/`
- Over **700 lines**: extraction mandatory

> See `references/progressive-disclosure.md` for economics and extraction decision tree.

### Bundled scripts

Extract deterministic operations into `scripts/*.py` with argparse. Saves tokens, ensures consistency, testable independently.

### Bundled agents

Bundle subagent prompts in `agents/` for skill-internal use (not registered in routing).

| Scenario | Approach |
|----------|----------|
| Agent used only by this skill | Bundle in `agents/` |
| Agent shared across skills | Keep in repo `agents/` |
| Agent needs routing metadata | Keep in repo `agents/` |

### Agent creation standard

Read `docs/PHILOSOPHY.md` first. Apply same maintenance-artifact rules:

```
agents/
├── {agent-name}.md
└── {agent-name}/
    ├── SPEC.md            # Optional
    ├── EVAL.md            # Optional
    └── references/
```

Use `SPEC.md`/`EVAL.md` for complex, high-impact, security-sensitive, router-facing, or frequently-tuned agents. Do not create `SOURCES.md`.

### Path placeholder convention (per ADR-201)

Paths matching `/tmp/...`, `/home/<author>/...`, `~/<user>/...`, `/Users/<author>/...`, `/private/var/folders/...` in published reference docs MUST be either angle-bracket placeholders or labelled author-harness.

**Placeholder (preferred):**
```markdown
Place outputs at `<your-output-dir>/assets/<slug>/final.png`.
```

**Labelled harness (only when path has documentary value):**
```markdown
> **Author's local validation harness, replace before use:** `/tmp/sprite-demo/...`
```

Integration-target paths (`~/road-to-aew`, `~/deeproute`) stay literal when the skill explicitly targets that project.

**Enforcement:**
```bash
grep -rnE '(/tmp/[a-z][a-z0-9_-]+|/home/[a-z][a-z0-9_-]+|/Users/[a-z][a-z0-9_-]+)' \
  skills/<your-skill>/SKILL.md skills/<your-skill>/references/*.md 2>/dev/null \
  | grep -v '<your-' \
  | grep -v "Author's local validation harness"
```

### Post-scaffold: register in routing table + INDEX.json (mandatory)

**Step 1: Routing table entry.** Add to `skills/do/references/routing-tables.md`. Verify:
```bash
python3 scripts/check-routing-drift.py
```

**Step 2: INDEX.json.** Regenerate:
```bash
python3 scripts/generate-skill-index.py
```

Scaffold not complete until routing table has entry AND INDEX.json reflects new skill. Diff both before staging.

### Post-scaffold: joy-check + do-pair validation

**Joy-check** (framing):
```bash
python3 scripts/validate-references.py --check-do-framing
```

For prose-heavy references, prefer full `joy-check` skill.

**Do-pair validation** (structural). Same command. Ship only after exit 0.

---

## Testing the skill

Core of the eval loop. Do not stop after writing -- test against real prompts.

### Create test prompts

2-3 realistic, detailed prompts. Not abstract one-liners.

Bad: `"Format this data"`
Good: `"I have a CSV in ~/downloads/q4-sales.csv with revenue in column C and costs in column D. Add a profit margin percentage column and highlight rows where margin is below 10%."`

Share prompts with user before running.

> See `references/bundled-components.md` for evals.json format and workspace layout.

### Run test prompts

Spawn two subagents per test case (same turn): one with skill loaded, one without (baseline).

**With-skill**: Read SKILL.md first, execute task, save outputs.
**Baseline**: Same prompt, no skill, separate directory.

### Evaluate results

**Tier 1: Deterministic** -- compile, test, lint where applicable.

**Tier 2: Agent blind review** -- dispatch `agents/comparator.md`. Outputs labeled "Output 1"/"Output 2" (blind). Scores dimensions, picks winner with reasoning.

**Tier 3: Human review (optional)**:
```bash
python3 scripts/eval_compare.py path/to/workspace
open path/to/workspace/compare_report.html
```

Side-by-side viewer with blind labels, review panels, deterministic results, winner picker, feedback textarea.

### Draft assertions

Draft quantitative assertions for objective criteria. Good assertions discriminate -- fail without skill, pass with it.

Run grader (`agents/grader.md`): PASS requires substance, not surface compliance. Grader critiques assertions too.

Aggregate with `scripts/aggregate_benchmark.py` for pass rates, timing, token usage.

---

## Improving the skill

**Generalize from feedback.** If a fix only helps the test case, it's overfitting. Try different approaches.

**Keep instructions lean.** Read transcripts, not just outputs. Remove instructions that waste attention.

**Explain reasoning.** "Prefer X because Y" generalizes better than bare "ALWAYS X".

**Extract repeated work.** If all subagents wrote similar helpers, bundle in `scripts/`.

### The iteration loop

1. Apply improvements
2. Rerun all test cases into `iteration-<N+1>/` with baselines
3. Generate comparison viewer with `--previous-workspace`
4. Review (agent or human)
5. Repeat until plateau or user satisfied

Stop when: feedback empty, pass rates not improving, user satisfied.

---

## Description optimization

After the skill works, optimize description for triggering accuracy.

> See `references/bundled-components.md` for the optimization loop: eval queries, train/test split, `optimize_description.py`, overfitting guards.

---

## Enriching existing skills

Use when a skill exists but produces shallow output -- thin `references/`, no `scripts/`, passes eval by luck.

Indicators: <2 reference files, no scripts, outputs lack domain idioms, skill passes because model already knows domain.

### The enrichment loop

Six phases: AUDIT, RESEARCH, ENRICH, TEST, EVALUATE, PUBLISH. Max 3 iterations. Each retry uses different angle: iteration 1 = official docs, 2 = common mistakes, 3 = advanced patterns.

> See `references/enrichment-workflow.md` for full checklist, scoring, retry logic, commit/PR flow.

---

## Bundled agents and scripts

> See `references/bundled-components.md` for agents (`grader.md`, `comparator.md`, `analyzer.md`), scripts, workspace layout, evals.json format.

---

## Reference files

- `references/progressive-disclosure.md` -- Disclosure model, economics, size gates, extraction examples
- `references/skill-template.md` -- Complete SKILL.md template
- `references/artifact-schemas.md` -- JSON schemas for eval artifacts
- `references/complexity-tiers.md` -- Skill examples by complexity tier
- `references/workflow-patterns.md` -- Reusable phase structures and gate patterns
- `references/error-catalog.md` -- Common skill creation errors with solutions
- `references/enrichment-workflow.md` -- Enrichment loop: AUDIT through PUBLISH
- `references/domain-research-targets.md` -- Lookup table: domain -> primary/secondary sources
- `references/bundled-components.md` -- Agents, scripts, workspace layout, evals.json, description optimization

---

## Error handling

### Skill doesn't trigger
Cause: Description too vague or missing trigger phrases.
Solution: Add explicit trigger phrases matching user language. Test with `scripts/optimize_description.py`.

### Test run produces empty output
Cause: `claude -p` didn't load skill, or path wrong.
Solution: Verify SKILL.md exists (exact case). Check `--skill-path` points to directory, not file.

### All-pass grading regardless of skill
Cause: Non-discriminating assertions (e.g., "file exists").
Solution: Test behavior, not structure. Read grader's eval critique section.

### Iteration loop doesn't converge
Cause: Overfitting to test cases.
Solution: Expand test set. Focus on understanding WHY outputs differ.

### Description optimization overfits
Cause: Test set too small or train/test queries too similar.
Solution: Ensure should-trigger and should-not-trigger queries are realistic near-misses. 60/40 split guards against this only if queries are well-designed.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| implementation patterns | `preferred-patterns.md` | Loads detailed guidance from `preferred-patterns.md`. |
| tasks related to this reference | `artifact-schemas.md` | Loads detailed guidance from `artifact-schemas.md`. |
| tasks related to this reference | `bundled-components.md` | Loads detailed guidance from `bundled-components.md`. |
| tasks related to this reference | `complexity-tiers.md` | Loads detailed guidance from `complexity-tiers.md`. |
| tasks related to this reference | `domain-research-targets.md` | Loads detailed guidance from `domain-research-targets.md`. |
| workflow steps | `enrichment-workflow.md` | Loads detailed guidance from `enrichment-workflow.md`. |
| errors | `error-catalog.md` | Loads detailed guidance from `error-catalog.md`. |
| tasks related to this reference | `progressive-disclosure.md` | Loads detailed guidance from `progressive-disclosure.md`. |
| tasks related to this reference | `skill-template.md` | Loads detailed guidance from `skill-template.md`. |
| workflow steps, implementation patterns | `workflow-patterns.md` | Loads detailed guidance from `workflow-patterns.md`. |
