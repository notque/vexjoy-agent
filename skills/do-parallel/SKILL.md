---
name: do-parallel
description: |
  Spawn 10 independent parallel agents to analyze source material from
  distinct perspectives, synthesize findings, and apply improvements to
  a target agent or skill. Use when source material is complex and
  multi-angle extraction reveals patterns that single-threaded analysis misses.
  Use for "parallel analysis", "multi-perspective", or "deep extraction".
  Do NOT use for routine improvements or simple source material.
version: 2.0.0
user-invocable: false
argument-hint: "<target-name> <source-path>"
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
routing:
  triggers:
    - "parallel analysis"
    - "multi-perspective"
    - "10 perspectives"
  category: meta-tooling
---

# Parallel Multi-Perspective Analysis

$ARGUMENTS - Target agent/skill name + source material file path

---

## Operator Context

This skill operates as an operator for intensive multi-perspective analysis, configuring Claude's behavior for true parallel independence across 10 analytical agents. It implements the **Fan-Out / Fan-In** architectural pattern -- dispatch independent agents in parallel, collect results, synthesize into unified recommendations -- with **Domain Intelligence** embedded in each perspective's focus constraints.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution
- **Over-Engineering Prevention**: Apply only Priority 1 and Priority 2 synthesized rules. Do not invent improvements beyond what the source material supports. No speculative enhancements.
- **True Parallel Independence**: All 10 Task invocations MUST be in a single message. Each agent receives ONLY its assigned perspective with zero cross-contamination. All 10 agents are read-only analysts — scope overlap checking (`scripts/check-scope-overlap.py`) is not required since agents produce analysis artifacts, not code modifications.
- **Artifact Persistence**: Save synthesis document and completion report to files. Context is ephemeral; artifacts persist.
- **Source Material Assessment**: Validate source material has sufficient depth before spawning agents. Thin material (under 500 words) should use inline analysis instead.
- **Validate Inputs First**: Verify target agent/skill exists and source material is readable before spawning any agents.
- **No Behavior Changes**: Synthesized rules ADD depth. They NEVER remove or significantly alter existing working patterns in the target.

### Default Behaviors (ON unless disabled)
- **10 Perspectives**: Use all 10 analytical frameworks (see `references/perspective-prompts.md`)
- **Priority-Based Application**: Apply Must-Have rules first, then Should-Have. Skip Nice-to-Have unless user requests.
- **Synthesis Before Application**: Collect all 10 reports and synthesize before making any changes to the target.
- **Completion Report**: Generate detailed report showing impact, changes, and perspective contributions.
- **Graceful Degradation**: If agents time out, proceed with available results (3+ of 10 sufficient).
- **Git Commit**: Commit improvements with descriptive message after application.

### Optional Behaviors (OFF unless enabled)
- **Reduced Perspectives**: Use 5 perspectives instead of 10 for faster completion
- **Dry Run Mode**: Generate synthesis without applying changes to target
- **Compare Mode**: Analyze two sources and extract differences

## What This Skill CAN Do
- Extract comprehensive insights from complex source material through 10 independent lenses
- Synthesize cross-perspective patterns into prioritized improvement recommendations
- Apply synthesized rules to enhance an existing agent or skill
- Produce detailed reports showing which perspectives contributed to each improvement
- Detect patterns that single-threaded analysis misses due to cognitive anchoring

## What This Skill CANNOT Do
- Replace inline analysis for simple or straightforward material (use `/do-perspectives` for single-target improvements)
- Generate value from poor source material (marketing fluff, auto-generated docs, under 500 words)
- Guarantee all 10 agents complete (network/timeout issues may reduce count)
- Skip the synthesis phase and apply raw per-perspective rules directly

---

## Instructions

### Phase 1: VALIDATE INPUTS

**Goal**: Confirm target exists and source material is suitable before spawning agents.

**Step 1: Parse arguments**
- Extract target agent/skill name (first argument)
- Extract source material path (second argument)
- If either argument is missing, report usage: `/do-parallel <target-name> <source-path>`

**Step 2: Validate target**

```bash
# For agents
ls agents/{target_name}.md

# For skills
ls skills/{target_name}/SKILL.md
```

- Determine if target is an agent or skill based on which path exists
- Read target file to understand current state, capture line count
- If target does not exist in either location, stop and report error

**Step 3: Validate source material**

```markdown
## Source Material Assessment

File: [path]
Word count: [N] words
Quality indicators:
- [ ] Contains concrete examples (not just abstract claims)
- [ ] Has systematic structure (sections, progression)
- [ ] Demonstrates expertise (technical depth, nuanced explanations)
- [ ] Sufficient length (500+ words minimum)

Assessment: SUITABLE / UNSUITABLE
```

- Read source file, confirm it is non-empty
- If material fails 2+ quality indicators, recommend inline analysis instead and ask user to confirm

**Gate**: Target exists and is readable. Source material is present and substantive. Proceed only when gate passes.

### Phase 2: MULTI-PERSPECTIVE ANALYSIS (TRUE PARALLEL)

**Goal**: Spawn 10 independent agents to analyze source material from distinct frameworks.

**Step 1: Launch all 10 agents in a SINGLE message**

Each agent receives:
1. The FULL source material
2. ONE assigned perspective (from `references/perspective-prompts.md`)
3. The target name for contextualized recommendations
4. Instructions to produce 200-500 words of focused analysis

The 10 perspectives are:
1. Structural Analysis
2. Clarity and Precision
3. Technical Explanation Patterns
4. Audience Assumption Patterns
5. Evidence and Citation Strategy
6. Narrative Progression
7. Paragraph and Sentence Architecture
8. Header and Signposting Strategy
9. Complexity Management
10. Limitation and Nuance Handling

**Step 2: Collect results with timeout awareness**

Wait for all agents to complete. Monitor using this decision tree:

```
Agent running > 5 minutes?
    |
    +-- YES --> Check progress (non-blocking)
    |           |
    |           +-- Making progress? --> Wait 2 more minutes
    |           |
    |           +-- Stuck on web fetch? --> Mark as timed out, proceed
    |
    +-- NO --> Continue waiting
```

**Step 3: Assess completeness**

| Agents Completed | Action |
|------------------|--------|
| 8-10 of 10 | Full pipeline, excellent coverage |
| 5-7 of 10 | Proceed, note gaps in report |
| 3-4 of 10 | Proceed with caution, synthesis will be thinner |
| 1-2 of 10 | Abort parallel approach, fall back to inline analysis |
| 0 of 10 | Critical failure, investigate cause |

**Gate**: At least 3 of 10 perspectives have returned results. Proceed only when gate passes.

### Phase 3: SYNTHESIZE

**Goal**: Merge 10 independent analyses into prioritized, unified recommendations.

**Step 1: Create cross-reference matrix**

For each rule extracted by any perspective, track which perspectives identified it:

```markdown
| Rule | Struct | Clarity | Tech | Audience | Evidence | Narrative | Para | Header | Complex | Nuance | Count |
|------|--------|---------|------|----------|----------|-----------|------|--------|---------|--------|-------|
| [Rule A] | X | X | | X | | X | | | X | | 5 |
| [Rule B] | | | X | | X | | X | X | | X | 4 |
```

**Step 2: Identify common themes**
- Patterns appearing in 4+ perspectives are high-confidence findings
- Patterns appearing in 7+ perspectives are near-certain insights
- Group related rules into themes (e.g., "Progressive Disclosure" may appear in Audience, Complexity, and Structure)

**Step 3: Extract unique insights**
- Single-perspective findings that are high-value despite low frequency
- These often represent the unique value of parallel independence
- Example: Only Narrative Progression spots a "hook-payoff" pattern that would strengthen an agent's introduction section

**Step 4: Prioritize rules**

```markdown
## Priority Rules for [Target]

### Must-Have (Priority 1)
Rules present in 7+ perspectives OR critical impact:
1. [Rule] - Found in: [list of perspectives]
2. [Rule] - Found in: [list of perspectives]

### Should-Have (Priority 2)
Rules present in 4-6 perspectives OR high impact:
1. [Rule] - Found in: [list of perspectives]
2. [Rule] - Found in: [list of perspectives]

### Nice-to-Have (Priority 3)
Rules present in 1-3 perspectives OR moderate impact:
1. [Rule] - Found in: [perspective]
2. [Rule] - Found in: [perspective]
```

**Step 5: Save synthesis document**
- Write to `skills/do-parallel/artifacts/synthesis-{target}-{date}.md`
- Include the cross-reference matrix, themes, and prioritized rules
- This artifact persists for future reference and can inform later analyses

**Gate**: Synthesis document exists with at least 3 Must-Have and 3 Should-Have rules. Proceed only when gate passes.

### Phase 4: APPLY

**Goal**: Improve the target agent/skill using synthesized recommendations.

**Step 1: Read current target state**

```markdown
## Before State

Target: [name]
Type: [agent/skill]
Lines: [N]
Sections: [list of H2/H3 sections]
Version: [current version]
```

**Step 2: Plan application**

Map each Priority 1 and Priority 2 rule to a specific location in the target:

```markdown
## Application Plan

| Rule | Action | Target Section | Risk |
|------|--------|----------------|------|
| [Rule 1] | Add subsection | Operator Context | LOW |
| [Rule 2] | Enhance existing | Instructions Phase 2 | LOW |
| [Rule 3] | Add new section | After Anti-Patterns | MEDIUM |
```

**Step 3: Apply Priority 1 rules**
- Add or enhance sections based on Must-Have recommendations
- Preserve all existing working patterns
- After each rule application, verify target file is still valid markdown

**Step 4: Apply Priority 2 rules**
- Add Should-Have enhancements where they integrate naturally
- Do NOT force rules that conflict with existing patterns
- If a Should-Have rule conflicts with an existing pattern, document the conflict in the report and skip

**Step 5: Commit changes**
- Create descriptive git commit explaining what was improved and from what source
- Bump version if target is a skill (e.g., 1.0.0 to 1.1.0)

**Gate**: Target file has been modified. Changes preserve existing behavior. Before/after diff shows additions only (no deletions of existing content). Proceed only when gate passes.

### Phase 5: VERIFY AND REPORT

**Goal**: Confirm improvements are sound and document the full analysis.

**Step 1: Verify target integrity**

```markdown
## Integrity Check

YAML frontmatter valid: [YES/NO]
Sections preserved: [list any missing sections]
Before lines: [N]
After lines: [M]
Net change: +[M-N] lines

Verification:
- [ ] All original H2 sections still present
- [ ] All original H3 sections still present
- [ ] No content was deleted (only additions)
- [ ] Markdown renders correctly
```

If any check fails, revert the problematic change and re-apply.

**Step 2: Generate completion report**

Use template from `references/perspective-prompts.md`. The report MUST include:
- Per-perspective key insights (one sentence each)
- Cross-reference showing which perspectives contributed to each improvement
- Before/after comparison (line counts, section counts)
- Recommendations for future improvements

**Step 3: Save completion report**
- Write to `skills/do-parallel/artifacts/report-{target}-{date}.md`
- Present summary to user in conversation

**Step 4: Present results**

```markdown
## Parallel Analysis Complete

Target: [name]
Source: [source path]
Perspectives completed: [N] of 10
Rules extracted: [total across all perspectives]
Rules applied: [Priority 1 count] Must-Have + [Priority 2 count] Should-Have
Lines added: +[count]
New sections: [count]

Full report: skills/do-parallel/artifacts/report-{target}-{date}.md
Synthesis: skills/do-parallel/artifacts/synthesis-{target}-{date}.md
```

**Gate**: Completion report exists. Target file is valid. All phases documented.

---

## Examples

### Example 1: Improve Agent from Article
User says: `/do-parallel technical-journalist-writer expert-writing-guide.md`
Actions:
1. Validate target agent exists, read source article (VALIDATE)
2. Spawn 10 agents analyzing article from 10 perspectives (ANALYZE)
3. Synthesize: 5 Must-Have rules, 7 Should-Have rules (SYNTHESIZE)
4. Apply Priority 1 and 2 rules to agent file (APPLY)
5. Generate report showing +180 lines added (VERIFY)
Result: Agent enhanced with synthesized writing patterns from 10 independent analyses

### Example 2: Improve Skill from Documentation
User says: `/do-parallel systematic-debugging postgres-debugging-guide.md`
Actions:
1. Validate skill exists, assess documentation quality (VALIDATE)
2. Launch 10 parallel analyses of PostgreSQL debugging patterns (ANALYZE)
3. Synthesize database-specific debugging rules (SYNTHESIZE)
4. Add new patterns to debugging skill references (APPLY)
5. Report: 8 of 10 perspectives contributed new rules (VERIFY)
Result: Debugging skill gains domain-specific PostgreSQL patterns

---

## Error Handling

### Error: "Target Agent/Skill Not Found"
Cause: Name mismatch or typo in first argument
Solution:
1. List available agents with `ls agents/*.md`
2. List available skills with `ls skills/*/SKILL.md`
3. Retry with exact name matching repository

### Error: "Source Material Too Short or Empty"
Cause: File path wrong, file empty, or material lacks depth
Solution:
1. Verify file path is absolute and file exists
2. If material is under 500 words, it likely lacks sufficient patterns
3. Consider using inline analysis instead of parallel (similar value for thin material)

### Error: "Agents Timing Out"
Cause: Source material too large, network issues, or agent stuck on web fetch
Solution:
1. Check if source exceeds 10,000 words (reduce or split)
2. After 5 minutes, check agent progress with non-blocking query
3. Proceed with completed perspectives if 3+ have returned
4. See graceful degradation table in Phase 2, Step 3

### Error: "Synthesis Has Insufficient Rules"
Cause: Source material lacked depth, or perspectives returned shallow analysis
Solution:
1. Review agent outputs for quality (are they 200-500 words with concrete patterns?)
2. If most outputs are thin, the source material is unsuitable for parallel analysis
3. Consider switching to inline analysis with a focused prompt
4. Report to user: "Source material did not yield sufficient patterns for 10-perspective analysis"

---

## Anti-Patterns

### Anti-Pattern 1: Using Parallel for Simple Material
**What it looks like**: Running 10 agents on a 200-word README
**Why wrong**: No depth to analyze from 10 angles. Simple material yields the same insights from a single reading.
**Do instead**: Use `/do-perspectives` for single-target improvements or simpler inline analysis. Reserve do-parallel for complex, hard-to-grasp material.

### Anti-Pattern 2: Applying All Rules Without Prioritization
**What it looks like**: Dumping all 30-50 extracted rules into the target without filtering
**Why wrong**: Low-frequency rules may conflict with existing patterns. Quantity overwhelms quality. Target becomes bloated.
**Do instead**: Apply Priority 1 first, then Priority 2. Skip Priority 3 unless explicitly requested.

### Anti-Pattern 3: Skipping Synthesis Phase
**What it looks like**: Reading each agent report and applying rules one perspective at a time
**Why wrong**: Cross-perspective patterns are the primary value. Applying per-perspective rules misses common themes and introduces contradictions.
**Do instead**: Always collect all reports, identify common themes, then create unified recommendations before touching the target.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Pipeline Architecture](../shared-patterns/pipeline-architecture.md) - Phase-gated pipeline design
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition rules

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Source is simple, 10 perspectives overkill" | Simple source = use inline analysis instead | Check material depth in Phase 1, downgrade if thin |
| "3 perspectives returned, close enough" | 3 is minimum for synthesis, not ideal | Wait for timeout threshold, then proceed with available |
| "I can synthesize as I go" | Per-perspective application misses cross-cutting themes | Complete all collection before ANY synthesis |
| "Existing patterns in target are outdated" | Existing patterns may work; new rules ADD, never replace | Preserve all existing content, add depth only |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/perspective-prompts.md`: All 10 perspective templates, synthesis format, completion report template, and source material guidance
