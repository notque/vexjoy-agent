# Progressive Disclosure Model

How to structure skills so they load fast when Claude considers them and deliver
full depth when Claude executes them.

---

## The Core Model

```
SKILL.md            ← always loaded when Claude considers invoking the skill
references/         ← loaded on demand as the skill executes
scripts/            ← deterministic CLI tools, called from SKILL.md phases
agents/             ← specialized subagent prompts, dispatched from SKILL.md
```

**SKILL.md** is the routing target. It stays lean so it loads fast, then reads
reference files on demand as phases execute.

**`references/`** holds deep content: checklists, rubrics, templates, patterns,
agent dispatch prompts, scoring systems, example collections. Loaded only when
the skill is actually running and reaches the phase that needs them.

**`scripts/`** holds deterministic CLI tools. If an operation is repeatable and
doesn't require LLM judgment, it should be a Python script — not inline
instructions that the model reinvents each run.

**`agents/`** holds specialized subagent prompts for skills that dispatch
parallel reviewers, graders, or domain specialists. Each agent file contains
the full prompt for one specialized role.

---

## The Economics

| Moment | What loads | Token cost |
|--------|------------|------------|
| Claude considers invoking the skill | SKILL.md only | Low (300–400 lines) |
| Skill executes Phase 1 | SKILL.md + Phase 1 reference | Medium |
| Skill executes all phases | SKILL.md + all referenced files | Full depth |

A 300-line SKILL.md with 5 reference files totaling 800 lines costs **300 tokens
to consider** and **1100 tokens when executing**. A 1100-line SKILL.md costs
1100 tokens on every routing decision, whether or not the skill gets invoked.

This is the key asymmetry. Keep SKILL.md lean.

---

## Size Gates

| SKILL.md length | Action |
|-----------------|--------|
| Under 400 lines | Fine — no extraction needed |
| 400–500 lines | Consider extracting if there are obvious deep-content sections |
| Over 500 lines | Should extract detailed catalogs to `references/` |
| Over 700 lines | Must extract — SKILL.md is carrying reference content |

After writing a SKILL.md, check its length. If it exceeds 500 lines, identify
the heaviest sections (checklists, rubrics, pattern catalogs, agent prompts,
example collections) and move them to `references/`.

---

## What to Extract to `references/`

**Extract these** — they are deep content that only matters when the skill runs:

- Detailed checklists and rubrics (e.g., severity classification tables, joy-check
  rubric, grading criteria)
- Agent dispatch prompts (e.g., the 10 specialist prompts in `sapcc-review`, wave
  agent prompts in `comprehensive-review`)
- Report and output templates (e.g., the structured markdown template for
  `sapcc-review` findings)
- Domain-specific pattern catalogs (e.g., Go anti-patterns with before/after
  examples, common error patterns)
- Validation criteria and scoring systems
- Example collections (realistic input/output pairs, prompt examples)
- Phase-specific deep guides (e.g., "how to run the voice extraction phase")

**Keep in SKILL.md** — these guide routing and orchestration:

- Frontmatter (name, description, routing — never extracted)
- Brief overview (2-3 sentences)
- Phase/step structure with gates
- One-line pointers to reference files ("See `references/X.md` for...")
- Error handling (cause/solution pairs for common failures)
- Brief examples showing trigger context

---

## Real Examples from This Toolkit

These skills were built following this model. Use them as reference.

| Skill | SKILL.md | `references/` | Total | What's in references |
|-------|----------|----------------|-------|----------------------|
| `comprehensive-review` | 564 lines | 765 lines (5 files) | 1329 | Wave-specific agent prompts per wave |
| `create-voice` | 444 lines | 426 lines (4 files) | 870 | Phase-specific deep guides |
| `pr-pipeline` | 417 lines | 365 lines (4 files) | 782 | Checklist, templates, loop details |
| `sapcc-review` | 269 lines | 323 lines (2 files) | 592 | 10 agent dispatch prompts, report template |
| `systematic-code-review` | 301 lines | 252 lines (3 files) | 553 | Severity rules, Go patterns, feedback guide |
| `voice-writer` | 307 lines | 462 lines (6 files) | 769 | Rubrics, checklists, joy-check criteria, schemas |

Notice that the most complex skills (`comprehensive-review`, `sapcc-review`) have
the *smallest* SKILL.md-to-total ratios. All their operational depth lives in
`references/` and `agents/`, loaded only when the skill executes.

### Pattern: Agent Dispatch Prompts in `agents/`

`sapcc-review` dispatches 10 parallel domain-specialist agents. Their prompts
live in `agents/` (one file per specialist). SKILL.md says:

```
Spawn 10 parallel subagents, each loaded with their agent prompt from agents/:
- agents/error-handling-reviewer.md
- agents/api-contracts-reviewer.md
...
```

SKILL.md stays at 269 lines. The 10 agent prompts are only loaded when the
skill actually runs.

### Pattern: Wave Prompts in `references/`

`comprehensive-review` runs 4 waves of parallel review. Each wave's agent
prompts are in a separate reference file (`references/wave1-agents.md`, etc.).
SKILL.md describes the structure; the actual prompts are loaded per-wave.

### Pattern: Checklist Extraction

`pr-pipeline` has a pre-PR checklist that would bulk out SKILL.md. It lives in
`references/pre-pr-checklist.md`. SKILL.md says: "Before creating the PR, work
through `references/pre-pr-checklist.md`."

---

## Deterministic Script Principle

If an operation is repeatable and doesn't require LLM judgment, it **should** be
a Python CLI script in `scripts/`, not inline instructions that the model
reinvents on each invocation.

Scripts:
- Save tokens — the model calls a script rather than reasoning through the same
  steps from scratch each time
- Ensure consistency — the same input produces the same output every run
- Can be tested independently — unit tests for scripts, not for model reasoning
- Are version-controlled and reviewable — changes are explicit diffs
- Have predictable outputs — scripts fail deterministically; model reasoning fails
  silently

**Good candidates for scripts:**
- Validation (voice validation, format checking, lint)
- Metric extraction (line counts, token counts, benchmark aggregation)
- Template rendering (fill a report template with data)
- Link checking, path resolution, file discovery
- Format conversion (CSV to JSON, markdown to HTML)
- API calls with structured output (GitHub, linear, Slack)

**Keep as SKILL.md instructions** — things that require judgment:
- Deciding what to review and how deeply
- Interpreting ambiguous outputs
- Adapting approach to context

The right split: `scripts/` for mechanical operations, SKILL.md for orchestration
and judgment.

---

## Bundled Agents

For skills that dispatch subagents with specialized roles, bundle agent prompts
in `agents/`. These are not registered in the routing system — they are internal
to the skill's workflow, loaded only when the skill dispatches them.

```
skill-name/
├── SKILL.md
├── agents/
│   ├── security-reviewer.md    # Prompt for the security specialist
│   ├── arch-reviewer.md        # Prompt for the architecture specialist
│   └── grader.md               # Prompt for output grading
├── scripts/
└── references/
```

SKILL.md references them with a dispatch instruction:
```
Spawn a subagent using the prompt in agents/security-reviewer.md.
Pass it: the diff, the package list, and the Wave 1 findings.
```

When to bundle vs. use repo-level agents:

| Scenario | Where |
|----------|-------|
| Agent only used by this skill | Bundle in `agents/` |
| Agent shared across multiple skills | Repo `agents/` directory |
| Agent needs to appear in routing | Repo `agents/` directory |

---

## Applying This Model When Creating a New Skill

1. **Write SKILL.md first** — get the workflow right without worrying about length
2. **Check length** — if over 500 lines, identify extraction candidates
3. **Extract** — move checklists, rubrics, agent prompts, templates to `references/`
4. **Replace with pointers** — each extracted section becomes one line in SKILL.md:
   `"See references/X.md for the full checklist."`
5. **Identify deterministic operations** — anything the model would reinvent each
   run is a script candidate; write `scripts/X.py` and replace with a `Run:` line
6. **Identify specialized roles** — if the skill dispatches agents with distinct
   expertise, write their prompts in `agents/` and reference from SKILL.md

The result: a lean SKILL.md that orchestrates, and a rich `references/` + `scripts/`
+ `agents/` that delivers depth on demand.
