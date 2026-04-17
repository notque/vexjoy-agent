# Skill Template

Complete SKILL.md template with all required sections.

## YAML Frontmatter

```yaml
---
name: skill-slug-name
description: |
  [WHAT it does — 1-2 sentences]. [WHEN to use it — trigger phrases users
  would actually say]. Use when user says "[phrase 1]", "[phrase 2]", or
  "[phrase 3]". Do NOT use for [exclusion if needed].
# Optional fields:
# allowed-tools: [Read, Write, Bash, Grep, Glob]
# compatibility: "Requires Python 3.10+, network access for API calls"
# user-invocable: false
# agent: golang-general-engineer
# model: sonnet
routing:
  triggers:
    - keyword1
    - keyword2
  pairs_with:
    - related-skill
  complexity: Simple | Medium | Medium-Complex | Complex
  category: language | infrastructure | review | meta | content
---
```

**Description Formula**: `[WHAT] + [WHEN] + [capabilities] + [negative triggers if needed]`

**Max length**: 1024 characters (Anthropic enforced limit)

**Triggering note**: Claude tends to "undertrigger" skills — not invoking them when they'd be helpful. To combat this, make descriptions slightly assertive. Instead of just stating what the skill does, explicitly list trigger contexts. Example: "Make sure to use this skill whenever the user mentions X, Y, or Z, even if they don't explicitly ask for it."

**Good descriptions**:
```yaml
# Specific with trigger phrases
description: |
  Analyzes Figma design files and generates developer handoff documentation.
  Use when user uploads .fig files, asks for "design specs", "component
  documentation", or "design-to-code handoff".

# Clear scope with negative trigger
description: |
  Advanced data analysis for CSV files. Use for statistical modeling,
  regression, clustering. Do NOT use for simple data exploration
  (use data-viz skill instead).
```

**Bad descriptions**:
```yaml
# Too vague — won't trigger
description: Helps with projects.

# Missing triggers — Claude can't determine when to load
description: Creates sophisticated multi-page documentation systems.

# Too broad — will overtrigger on everything
description: Processes documents.
```

### Verifying Description Triggering

After writing a description, mentally test it against 3-5 prompts:
- 2-3 prompts that **should** trigger the skill (including indirect/casual phrasing)
- 2-3 prompts that **should not** trigger (near-misses from adjacent domains)

If the description wouldn't clearly match the should-trigger prompts, it's too vague. If it would match the should-not-trigger prompts, add negative triggers.

For important skills, consider creating a small eval set:
```json
[
  {"query": "realistic user prompt here", "should_trigger": true},
  {"query": "similar but wrong domain prompt", "should_trigger": false}
]
```
Use realistic prompts with detail (file paths, context, casual phrasing) — not abstract one-liners. Test edge cases where the skill competes with adjacent skills.

## Audience Awareness

Consider who will use the skill. Claude Code users range from experienced engineers to people new to terminals. Adjust terminology accordingly:

| Audience Signal | Approach |
|-----------------|----------|
| User writes code, uses CLI fluently | Technical terms fine (assertions, JSON schemas, middleware) |
| User follows tutorials, asks about basics | Briefly define technical terms on first use |
| No clear signal | Default to clear language, define terms that aren't universally known |

In skill instructions, explain jargon if the skill might serve a broad audience. For domain-specific skills (go-patterns, kubernetes-helm), assume domain competence.

## File Structure

```
.claude/skills/[skill-name]/
├── SKILL.md           # Manifest (YAML + instructions) - REQUIRED, exact case
├── scripts/           # Deterministic operations
│   ├── main.py       # Primary script
│   └── validate.py   # Testing/validation
├── references/        # Static context (anti-rot)
│   └── examples.md   # Usage examples
└── assets/            # Templates, fonts, icons used in output
    └── template.md   # Output templates
```

### Critical Naming Rules

| Rule | Correct | Incorrect |
|------|---------|-----------|
| SKILL.md must be exact (case-sensitive) | `SKILL.md` | `SKILL.MD`, `skill.md`, `Skill.md` |
| Folder name: kebab-case only | `deploy-pipeline` | `Deploy Pipeline`, `deploy_pipeline`, `DeployPipeline` |
| Name field must match folder | `name: deploy-pipeline` | Mismatched name/folder |
| No README.md inside skill folder | All docs in `SKILL.md` or `references/` | `README.md` inside skill folder |

### Security Rules

| Rule | Reason |
|------|--------|
| **No XML angle brackets (`<` `>`) in frontmatter** | Frontmatter appears in Claude's system prompt; could inject instructions |
| **No "claude" or "anthropic" in skill name** | Reserved namespace |
| **No code execution in YAML** | Safe YAML parsing enforced |
| **No secrets in frontmatter or SKILL.md** | Skills are shared; secrets go in environment variables |

### Bundled Agents (Optional)

For Complex+ skills that spawn subagents with specialized roles, agent prompts can be bundled inside the skill:

```
skill-name/
├── SKILL.md
├── agents/          # Purpose-built agent prompts for this skill
│   ├── grader.md    # Evaluates outputs against criteria
│   └── analyzer.md  # Post-hoc analysis of results
├── scripts/
└── references/
```

**When to bundle agents vs use repo-level agents:**

| Scenario | Approach |
|----------|----------|
| Agent is only used by this skill | Bundle in `agents/` — keeps skill self-contained |
| Agent is shared across skills | Keep in repo `agents/` directory — avoid duplication |
| Agent needs routing metadata | Keep in repo `agents/` — routing requires top-level registration |

Bundled agents are referenced from SKILL.md: "Spawn a subagent using the prompt in `agents/grader.md`". They don't appear in the routing system — they're internal to the skill's workflow.

## Instructions Section

Constraints belong **inline** within the workflow step where they apply, not in a
separate `## Operator Context` block. If a constraint matters during Phase 2, put
it in Phase 2 — not in a preamble 200 lines above where the model encounters it.
Explain the reasoning alongside each constraint (see "Motivation over Mandate" below).

```markdown
## Instructions

### Overview

[2-3 sentences: what this skill does and how it works end-to-end]

### Phase 1: [First Phase Name]

[What to do here — goal and actions]

Run: `python3 ~/.claude/scripts/main.py --input {input_file}`
Expect: [Specific output format]

Gate: [Condition that must be true before moving to Phase 2]
— because [reason the gate exists]

### Phase 2: [Second Phase Name]

[What to do here]

Constraint: [Domain-specific rule that applies HERE]
— because [why this matters in this context]

> If SKILL.md exceeds 500 lines: extract detailed content to `references/`
> and add a one-liner here: "See `references/X.md` for the full [checklist/rubric/template]."

### Phase 3: [Output Phase]

[Produce the output artifact]

## Error Handling

**Error: "[Error message]"**
- Cause: [Why it happens]
- Solution: [How to fix]

## Reference Files
- `references/examples.md`: [Purpose — loaded only when this skill executes]
- `references/checklist.md`: [Phase 2 checklist — deep content extracted from SKILL.md]
```

### Best Practices for Instructions

| Rule | Why |
|------|-----|
| **Be specific and actionable** | `Run python scripts/validate.py --input {file}` beats "validate the data" |
| **Put critical instructions at the top** | Use `## Critical` or `## Important` headers |
| **Use bullet points and numbered lists** | Structured content is followed more reliably than paragraphs |
| **Use code over language for validation** | Code is deterministic; language interpretation isn't |
| **Reference bundled resources clearly** | "Before writing queries, consult `references/api-patterns.md`" |
| **Include error handling** | Common errors with cause/solution format |
| **Repeat key points if needed** | Critical instructions may need reinforcement |
| **Explain the why, not just the what** | See "Motivation over Mandate" below |

### Motivation over Mandate

LLMs follow instructions better when they understand the reasoning behind them. For every constraint or rule in a skill, prefer explaining **why** it matters alongside the directive.

**Yellow flag**: If you find yourself writing `ALWAYS` or `NEVER` in all caps without explanation, reframe it. Add the reasoning so the model understands the importance and can generalize correctly to edge cases.

| Pattern | Less Effective | More Effective |
|---------|---------------|----------------|
| Constraint | `NEVER use console.log in production code` | `Avoid console.log in production — it blocks the event loop on high-throughput paths and leaks internal state to browser devtools` |
| Requirement | `ALWAYS validate inputs before processing` | `Validate inputs before processing because malformed data at this boundary propagates silently through 3 downstream services` |
| Gate | `MUST pass lint before committing` | `Pass lint before committing — the CI will reject it anyway, and fixing lint after commit creates noisy fix-lint commits in the PR` |

This doesn't mean abandoning imperative constraints — gates, anti-rationalization tables, and blocker criteria still serve an important purpose as safety nets. The principle is: **explain the why AND enforce the gate**. Motivation makes the model follow willingly; gates catch the cases where it doesn't.

Think of it as two layers:
1. **Motivation** (soft): Explain why something matters so the model internalizes the intent
2. **Gate** (hard): Verify the outcome so failures are caught regardless of intent

## Shared Patterns Integration

All skills should reference appropriate shared patterns:

```markdown
## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transitions (for workflow skills)

### Domain-Specific Anti-Rationalization

See [anti-rationalization-core.md](../shared-patterns/anti-rationalization-core.md) for universal patterns.

Additional for this skill:

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| [domain-specific-1] | [reason] | [action] |
| [domain-specific-2] | [reason] | [action] |
```

**Pattern Selection Guide:**

| Skill Type | Include These Patterns |
|------------|----------------------|
| Implementation | anti-rationalization-core, verification-checklist, gate-enforcement |
| Review/Analysis | anti-rationalization-core, anti-rationalization-review, severity-classification |
| Testing | anti-rationalization-core, anti-rationalization-testing |
| Security | anti-rationalization-core, anti-rationalization-security |
| Workflow | gate-enforcement, pressure-resistance, execution-report-format |

## Anti-Patterns Section (Medium+)

For skills with significant complexity, include 3-6 anti-patterns.

**Do-pairing rule (mandatory):** Every anti-pattern block must include a "Do instead" counterpart that shows the correct approach. A bare negative ("don't do X") encodes no actionable knowledge. The positive counterpart is the actual learning. If a genuine absolute prohibition has no correct alternative (e.g., "never commit secrets"), annotate it with `<!-- no-pair-required: absolute prohibition, no safe alternative -->` to pass structural validation.

Validation gate: `python3 scripts/validate-references.py --check-do-framing` rejects anti-pattern blocks without a paired "Do instead" or `<!-- no-pair-required: ... -->` annotation.

```markdown
### Anti-Pattern 1: [Pattern Name]

**What it looks like:**
[Example of misuse]

**Why wrong:** [Consequence]

**Do instead:** [Correct approach — this field is mandatory]
```
