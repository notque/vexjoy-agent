---
name: reference-enrichment
description: "Analyze agent/skill reference depth and generate missing domain-specific reference files."
version: 1.0.0
user-invocable: true
argument-hint: "<agent-or-skill-name>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - Agent
routing:
  triggers:
    - "enrich references"
    - "improve reference depth"
    - "generate references"
    - "add reference files"
    - "reference enrichment"
  category: meta-tooling
  complexity: medium
  pairs_with:
    - verification-before-completion
---

# Reference Enrichment Skill

Enrich an agent or skill's reference files from Level 0-1 to Level 2-3. The pipeline runs five
phases with explicit gates because each phase feeds the next — starting Phase 3 without Phase 2
research produces filler, not depth.

## Workflow

### Phase 1: DISCOVER

**Goal**: Identify which sub-domains are missing reference coverage.

1. Run the gap analyzer: `python3 skills/reference-enrichment/scripts/gap-analyzer.py --agent {name}`
   (or `--skill {name}`)
2. Read the component's .md file to understand its stated purpose, triggers, and domain claims
3. Read any existing reference files to map current coverage
4. Compare stated domains against covered domains to identify gaps

Output format:
```
DISCOVER: {name}
  Current level: {0-3}
  Existing references: [{filenames}]
  Stated domains: [{domains from description and body}]
  Gaps: [{sub-domains with no reference coverage}]
  Recommended files: [{filename} → {why}]
```

**Gate**: Gap report exists with at least one identified gap. If no gaps exist (Level 3 already),
report and stop — over-generating creates noise, not signal.

---

### Phase 2: RESEARCH

**Goal**: Compile concrete, domain-specific content for each gap.

For each identified gap:
1. Read existing Level 3 reference files in this repo as exemplars — golang-general-engineer's
   references/ is the benchmark: version-specific patterns, grep commands, error-fix mappings
2. Identify: version-specific patterns (what changed in version X.Y), common anti-patterns with
   detection commands (`grep -rn "pattern" --include="*.ext"`), error-fix mappings
   (error message → root cause → fix), project-specific conventions visible in the codebase

Dispatch up to 5 parallel research agents — one per sub-domain gap — because sequential research
bottlenecks the pipeline. Each agent receives: the sub-domain, the component's .md as context,
and a path to an exemplar Level 3 reference file.

**Gate**: Each gap has at least 10 concrete findings (version numbers, function names, grep
patterns, code examples). Generic advice ("follow best practices") does not count toward this gate.

---

### Phase 3: COMPILE

**Goal**: Assemble research into structured reference files.

For each gap, create one reference file following `references/reference-file-template.md`:
- One file per major sub-domain (not one monolithic file) because focused files are faster to
  load and easier to update as language versions change
- Max 500 lines per file (CLAUDE.md standard) — split into sub-topics if content exceeds this
- Include: overview paragraph, pattern table with version ranges, anti-pattern table with
  detection commands, error-fix mappings where applicable
- Match the tone of existing Level 3 references: direct, concrete, no hedging

Write files to: `agents/{name}/references/` or `skills/{name}/references/`

**Gate**: Each generated file is between 80-500 lines. Run
`scripts/validate-references.py --agent {name}` if it exists.

---

### Phase 4: VALIDATE

**Goal**: Confirm the reference files meet Level 2+ depth before integrating.

**Tier 1 (Deterministic):**
```bash
python3 scripts/audit-reference-depth.py --agent {name} --json
```
Verify the `level` field is 2 or 3 in the output. If still Level 1, the files are too
generic — return to Phase 2 for the weak sub-domain.

**Tier 2 (LLM self-assessment):**
Read each generated file and apply the rubric from `references/quality-rubric.md`. Ask: would
a reviewer using only this file produce Level 3 quality output? Concrete test: pick one
anti-pattern from the file — does it include a grep command to detect it?

**Gate**: Both tiers pass. If Tier 2 fails for a specific sub-domain, loop back to Phase 2 for
that gap only (not all gaps). Maximum 2 loops per gap before flagging for manual enrichment.

---

### Phase 5: INTEGRATE

**Goal**: Wire the new references into the component so they are actually loaded.

1. Read the component's .md file
2. Add or update a loading table in the body — pattern from `skills/do/references/repo-architecture.md`:
   ```
   | Task type | Load |
   |-----------|------|
   | {task}    | `references/{file}.md` |
   ```
3. Write the updated .md file
4. Run validation:
   ```bash
   python3 scripts/validate-references.py --agent {name}
   python3 -m pytest scripts/tests/test_reference_loading.py -k {name} -v
   ```
5. Stage all changes: `git add agents/{name}/ skills/{name}/`

**Gate**: Validation passes. Changes staged. Report the level change (was: N, now: M) and list
each new file with its line count.

---

## Reference Material

Load when the task type matches:

| Task type | Load |
|-----------|------|
| Understanding Level 0-3 criteria | `references/quality-rubric.md` |
| Creating new reference files | `references/reference-file-template.md` |

---

## Error Handling

**Gap analyzer fails**: The component may not exist in expected paths. Check both `agents/` and
`skills/` directories, and `~/.claude/agents/` for deployed copies.

**Phase 2 gate fails** (fewer than 10 concrete findings): The domain may be too narrow or already
well-documented upstream. Flag and suggest manual enrichment with project-specific production
incidents rather than generic docs research.

**Phase 4 Tier 1 still Level 1 after compile**: The files are too short or too generic. Read one
file, apply the rubric directly, identify the weakest section, and target Phase 2 research at
that section specifically.

**validate-references.py not found**: Script may not exist for this component. Skip that check,
proceed with `audit-reference-depth.py` as the sole Tier 1 gate.
