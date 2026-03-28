# Instruction Rubric — Positive Framing for LLM Instructions

This rubric applies to agent, skill, and pipeline markdown files — instructions read by LLMs, not humans. The principle: state the desired action, not the forbidden one. An LLM needs to know what TO DO, not what to avoid.

## Positive Instruction Framing Rubric

Every instruction should tell the reader what action to take. Prohibitions define a boundary without specifying where to go; positive framing gives a clear action target.

| Dimension | Positive (PASS) | Negative (FAIL) |
|-----------|----------------|----------------|
| **Action framing** | "Route all code modifications to domain agents" | "NEVER edit code directly" |
| **Specific instruction** | "Stage files by name: `git add specific-file.py`" | "do NOT use git add -A" |
| **Table headings** | "Preferred Patterns", "Hard Gate Patterns" | "Anti-Patterns", "FORBIDDEN Patterns" |
| **Safety boundaries** | "Create feature branches for all changes" | "Never commit to main" |
| **Error handling** | "exit 0 on errors to keep tools available" | "must NEVER block tools" |
| **Double negatives** | "Run validation before marking complete" | "Don't skip validation" |
| **Section organization** | "What to do" tables showing correct approach | "What NOT to do" tables showing prohibited approach |

## Patterns to Flag

### Primary patterns (always flag when used as instructions)

| Pattern | Regex | Example |
|---------|-------|---------|
| NEVER (caps) | `\bNEVER\b` | "NEVER edit code directly" |
| do NOT / Do NOT | `\b[Dd]o NOT\b` | "Do NOT use git add -A" |
| must NOT | `\bmust NOT\b` | "must NOT block tools" |
| FORBIDDEN | `\bFORBIDDEN\b` | "FORBIDDEN Patterns" |
| Don't (instruction start) | `^-?\s*Don't\b` | "Don't mock the database" |
| Avoid (as heading/instruction) | `^\s*#{1,6}.*Avoid\|^-?\s*Avoid\b` | "### Patterns to Avoid" |
| Anti-Pattern (in headings) | `^\s*#{1,6}.*[Aa]nti-[Pp]attern` | "### Common Anti-Patterns" |

### Contextual exceptions (allow these)

These are PASS even though they contain negative words:

- **Subordinate negatives attached to positive instructions**: "Credentials stay in .env files, never in code" — the primary instruction is positive ("stay in .env files"), the "never" is a subordinate boundary clarification
- **Code examples showing bad patterns**: `// NEVER` in a code comment demonstrating what SQL injection looks like — this is illustrative, not instructional
- **Writing samples and user dialogue**: "Don't do this!" in an example of how users speak — this is quoted content
- **Technical terms**: "Copula Avoidance" is a proper term for an AI writing pattern — the word "Avoidance" is part of the term, not a prohibition
- **File path references**: `references/anti-patterns.md` — this is a filename, not an instruction
- **Descriptive text about behavior**: "tests do not cover edge cases" — this describes a state, not an instruction

## Rewrite Rules

When flagging a negative pattern, suggest a specific positive rewrite:

| Negative Pattern | Positive Rewrite Strategy |
|-----------------|--------------------------|
| Prohibition ("NEVER X") | State the action: "Do Y instead" |
| Warning ("do NOT use X") | Give the specific alternative: "Use Y: `example`" |
| Anti-pattern table | Invert to pattern table: show what to do, not what to avoid |
| Fear-based ("must NEVER block") | State the outcome: "exit 0 to keep available" |
| Double negative ("Don't skip") | Direct instruction: "Run before marking complete" |
| "Avoid" heading | Replace with "Preferred" or "Recommended" |
| "Anti-Pattern" heading | Replace with "Preferred Patterns" or "Patterns to Detect and Fix" |

## Scoring

| Score | Label | Meaning |
|-------|-------|---------|
| 80-100 | **POSITIVE** | Instructions frame through desired actions |
| 50-79 | **MIXED** | Some instructions are positive, some are prohibition-based |
| 30-49 | **NEGATIVE-LEANING** | Most instructions tell what to avoid rather than what to do |
| 0-29 | **PROHIBITION-HEAVY** | Instructions are primarily "don't do X" framing |

**Pass criteria**: Score >= 60 AND no primary negative patterns in instructional context.

## Principles

1. **State the desired action, not the forbidden one** — The LLM needs to know what TO DO
2. **Preserve safety intent** — "Never commit to main" becomes "Create feature branches for all changes" — same protection, positive framing
3. **Replace anti-pattern tables with pattern tables** — Show "What to do instead", not "What NOT to do"
4. **Keep the WHY** — "because X" explanations stay unchanged; only the framing changes
5. **Subordinate negatives are fine** — "Credentials stay in .env files, never in code" is PASS because the positive instruction leads

## Examples

### Example 1: Router Instructions

**NEGATIVE (FAIL):**
```markdown
**What the main thread NEVER does:** Read code files, edit files, run tests,
write docs, handle ANY Simple+ task directly.
```

**POSITIVE (PASS):**
```markdown
**The main thread delegates to agents:** code reading (Explore agent), file
edits (domain agents), test runs (agent with skill), documentation
(technical-documentation-engineer), all Simple+ tasks.
```

**Why the second works:** Tells the LLM exactly where each task type goes instead of listing what's forbidden.

### Example 2: Safety Boundaries

**NEGATIVE (FAIL):**
```markdown
Route to agents that create branches; never allow direct main/master commits,
because main branch commits affect everyone.
```

**POSITIVE (PASS):**
```markdown
Route to agents that create feature branches for all commits, because main
branch commits affect everyone.
```

**Why the second works:** Same safety boundary, but the instruction says what to create (feature branches) rather than what to prevent (main commits).

### Example 3: Section Headings

**NEGATIVE (FAIL):**
```markdown
## Anti-Patterns
### FORBIDDEN Patterns (HARD GATE)
| Pattern | Why FORBIDDEN |
```

**POSITIVE (PASS):**
```markdown
## Preferred Patterns
### Hard Gate Patterns
| Pattern | Why Blocked |
```

**Why the second works:** "Preferred Patterns" tells the reader what to aim for. "Hard Gate Patterns" preserves the enforcement without the fear framing.

### Example 4: Subordinate Negative (PASS)

```markdown
Credentials stay in .env files, never in code or logs.
```

This is PASS — the primary instruction is positive ("stay in .env files") and the "never" is a subordinate boundary that clarifies the positive instruction. The reader knows both what to do AND the boundary.
