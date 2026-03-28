---
name: do-parallel
description: |
  Spawn 10 independent parallel agents to analyze source material from
  distinct perspectives, synthesize findings, and apply improvements to
  a target agent or skill. Use when source material is complex and
  multi-angle extraction reveals patterns that single-threaded analysis misses.
  Use for "parallel analysis", "multi-perspective", or "deep extraction".
  Route to other skills for routine improvements or simple source material.
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

This skill implements Fan-Out / Fan-In: dispatch 10 independent agents in parallel, collect results, synthesize into unified recommendations, and apply improvements to a target agent or skill. The primary value comes from cross-perspective pattern detection that single-threaded analysis misses due to cognitive anchoring.

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

Read and follow repository CLAUDE.md before proceeding. Then assess the source:

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
- Material under 500 words lacks sufficient depth for 10-angle extraction -- recommend inline analysis instead and ask user to confirm
- If material fails 2+ quality indicators, recommend inline analysis (`/do-perspectives` for single-target improvements) and ask user to confirm

**Gate**: Target exists and is readable. Source material is present and substantive. Proceed only when gate passes.

### Phase 2: MULTI-PERSPECTIVE ANALYSIS (TRUE PARALLEL)

**Goal**: Spawn 10 independent agents to analyze source material from distinct frameworks.

**Step 1: Launch all 10 agents in a SINGLE message**

All 10 Task invocations MUST appear in one message to achieve true parallelism. Each agent is a read-only analyst receiving ONLY its assigned perspective with zero cross-contamination between agents.

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

**Optional**: Use 5 perspectives instead of 10 for faster completion if user requests reduced mode.

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

Not all 10 agents are guaranteed to complete (network/timeout issues may reduce count). Degrade gracefully:

| Agents Completed | Action |
|------------------|--------|
| 8-10 of 10 | Full pipeline, excellent coverage |
| 5-7 of 10 | Proceed, note gaps in report |
| 3-4 of 10 | Proceed with caution, synthesis will be thinner |
| 1-2 of 10 | Abort parallel approach, fall back to inline analysis |
| 0 of 10 | Critical failure, investigate cause |

**Gate**: At least 3 of 10 perspectives have returned results. Proceed only when gate passes.

### Phase 3: SYNTHESIZE

**Goal**: Merge all independent analyses into prioritized, unified recommendations. Always collect ALL reports and synthesize before touching the target -- applying per-perspective rules one at a time misses cross-cutting themes and introduces contradictions.

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

Apply only Priority 1 and Priority 2 rules. Limit improvements to what the source material supports -- no speculative enhancements.

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

Priority 3 rules are documented but NOT applied unless the user explicitly requests them. Applying all 30-50 extracted rules without filtering leads to target bloat and conflicts with existing patterns.

**Step 5: Save synthesis document**
- Write to `skills/do-parallel/artifacts/synthesis-{target}-{date}.md`
- Include the cross-reference matrix, themes, and prioritized rules
- This artifact persists for future reference and can inform later analyses (context is ephemeral; artifacts persist)

**Optional**: In dry run mode, stop here and present the synthesis without applying changes.

**Gate**: Synthesis document exists with at least 3 Must-Have and 3 Should-Have rules. Proceed only when gate passes.

### Phase 4: APPLY

**Goal**: Improve the target agent/skill using synthesized recommendations. Synthesized rules ADD depth -- they preserve existing working patterns in the target.

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
| [Rule 3] | Add new section | After Preferred Patterns | MEDIUM |
```

**Step 3: Apply Priority 1 rules**
- Add or enhance sections based on Must-Have recommendations
- Preserve all existing working patterns -- additions only
- After each rule application, verify target file is still valid markdown

**Step 4: Apply Priority 2 rules**
- Add Should-Have enhancements where they integrate naturally
- If a Should-Have rule conflicts with an existing pattern, document the conflict in the report and skip it

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

## References

- `${CLAUDE_SKILL_DIR}/references/perspective-prompts.md`: All 10 perspective templates, synthesis format, completion report template, and source material guidance
