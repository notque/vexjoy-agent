---
name: reference-enrichment
description: "Analyze agent/skill reference depth and generate missing domain-specific reference files."
user-invocable: true
argument-hint: "<agent-or-skill-name> [--decompose]"
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
    - "decompose skill"
    - "extract references"
    - "slim down skill"
    - "skill too long"
    - "move content to references"
  category: meta-tooling
  complexity: medium
  pairs_with:
    - verification-before-completion
---

# Reference Enrichment Skill

Enrich agent/skill reference files from Level 0-2 to Level 3+, or decompose bloated body files by extracting domain content into references. Each phase feeds the next -- starting Phase 3 without Phase 2 research produces filler.

## Workflow

### Phase 0: DECOMPOSE

**Goal**: Extract domain-heavy content from a bloated SKILL.md or agent body into reference files.

**When**: Component body exceeds ~500 lines and contains catalogs, code examples, specification tables, or agent rosters that belong in `references/`.

**Trigger**: `--decompose` argument, or request matches "decompose", "extract references", "slim down", "too long", "move to references".

1. Detect extractable content:
   ```bash
   python3 scripts/detect-decomposition-targets.py --skill {name}
   ```
   (or `--agent {name}`)

2. No extractable blocks found => report "nothing to decompose" and stop.

3. Snapshot: `cp {path} /tmp/decomp-before-{name}.md`

4. For each extractable block:
   a. Read the content block and surrounding context
   b. Determine reference filename:
      - Use detection script's suggestion as starting point
      - If related reference exists, MERGE into it
      - Convention: `references/{topic}.md` (lowercase, hyphens)
   c. Create/update reference file per `references/reference-file-template.md`
   d. Remove content from body (MOVE, not copy)
   e. Add loading table entry mapping signals to new reference

5. Body must retain: YAML frontmatter, brief overview, phase workflow, loading table, error handling, references section.

6. Validate:
   ```bash
   python3 scripts/validate-decomposition.py \
       --before /tmp/decomp-before-{name}.md \
       --after {path} \
       --refs {refs_dir}/
   ```

7. Validation FAILS => restore from snapshot and report failure.

8. Validation PASSES => run structural checks:
   ```bash
   python3 scripts/validate-references.py --skill {name}  # or --agent {name}
   python3 scripts/audit-reference-depth.py --skill {name} --verbose  # or --agent {name}
   ```

**Gate**: Validation passes. Body line count reduced. All extracted content exists in references. Loading table entries exist for new references.

---

### Phase 1: DISCOVER

**Goal**: Identify sub-domains missing reference coverage.

1. Run gap analyzer: `python3 skills/reference-enrichment/scripts/gap-analyzer.py --agent {name}` (or `--skill {name}`)
2. Read the component's .md to understand purpose, triggers, and domain claims
3. Read existing references to map current coverage
4. Compare stated vs covered domains

Output:
```
DISCOVER: {name}
  Current level: {0-3}
  Existing references: [{filenames}]
  Stated domains: [{domains from description and body}]
  Gaps: [{sub-domains with no reference coverage}]
  Recommended files: [{filename} -> {why}]
```

**Gate**: Gap report with at least one gap. No gaps (Level 3 already) => report and stop.

---

### Phase 2: RESEARCH

**Goal**: Compile concrete, domain-specific content per gap.

For each gap:
1. Read existing Level 3 references as exemplars (benchmark: golang-general-engineer's references/)
2. Identify: version-specific patterns, anti-patterns with detection commands (`grep -rn "pattern" --include="*.ext"`), error-fix mappings, project-specific conventions

Dispatch up to 5 parallel research agents (one per gap). Each receives: sub-domain, component .md, path to exemplar Level 3 reference.

**Gate**: Each gap has at least 10 concrete findings (version numbers, function names, grep patterns, code examples). Generic advice does not count.

---

### Phase 3: COMPILE

**Goal**: Assemble research into structured reference files.

Per gap, create one file following `references/reference-file-template.md`:
- One file per sub-domain (not monolithic)
- Max 500 lines per file -- split if exceeded
- Include: overview paragraph, pattern table with version ranges, anti-pattern table with detection commands, error-fix mappings
- Match tone of existing Level 3 references: direct, concrete, no hedging

**Do-pairing rule (mandatory):** Every anti-pattern must include a "Do instead" counterpart. If research lacks enough info for a concrete positive counterpart, omit the anti-pattern entirely. Bare negative blocks fail structural validation. For genuine absolutes with no alternative, annotate `<!-- no-pair-required: reason -->`.

Write to: `agents/{name}/references/` or `skills/{name}/references/`

**Gate**: Each file is 80-500 lines. Both checks exit 0:
```bash
python3 scripts/validate-references.py --agent {name}
python3 scripts/validate-references.py --check-do-framing
```

---

### Phase 4: VALIDATE

**Goal**: Confirm Level 3+ depth before integrating.

**Tier 1 (Deterministic):**
```bash
python3 scripts/audit-reference-depth.py --agent {name} --json
```
Verify `level` is 3. Below 3 => return to Phase 2 for weak sub-domain.

**Tier 2 (LLM self-assessment):**
Read each file against `references/quality-rubric.md`. Test: pick one anti-pattern -- does it include a grep detection command?

**Gate**: Both tiers pass. Tier 2 fails for a sub-domain => loop to Phase 2 for that gap only. Max 2 loops per gap before flagging for manual enrichment.

---

### Phase 5: INTEGRATE

**Goal**: Wire new references into the component so they load.

1. Read the component's .md
2. Add/update loading table:
   ```
   | Task type | Load |
   |-----------|------|
   | {task}    | `references/{file}.md` |
   ```
3. Write updated .md
4. Validate:
   ```bash
   python3 scripts/validate-references.py --agent {name}
   python3 -m pytest scripts/tests/test_reference_loading.py -k {name} -v
   ```
5. Stage: `git add agents/{name}/ skills/{name}/`

**Gate**: Validation passes. Changes staged. Report level change (was: N, now: M) and list each new file with line count.

---

## Reference Material

| Task type | Load |
|-----------|------|
| Understanding Level 0-3 criteria | `references/quality-rubric.md` |
| Creating new reference files | `references/reference-file-template.md` |
| Decomposing bloated components | Run `python3 scripts/detect-decomposition-targets.py --skill {name}` first |

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `quality-rubric.md` | Loads detailed guidance from `quality-rubric.md`. |
| tasks related to this reference | `reference-file-template.md` | Loads detailed guidance from `reference-file-template.md`. |

## Error Handling

**Gap analyzer fails**: Component may not exist at expected paths. Check `agents/`, `skills/`, and `~/.claude/agents/`.

**Phase 2 gate fails** (fewer than 10 findings): Domain may be too narrow or well-documented upstream. Flag and suggest manual enrichment with project-specific production incidents.

**Phase 4 Tier 1 still below Level 3**: Files too short or generic. Read one file, apply rubric, identify weakest section, target Phase 2 at that section.

**validate-references.py not found**: Skip that check, use `audit-reference-depth.py` as sole Tier 1 gate.

**Decomposition validation fails**: Content lost during extraction. Restore from `/tmp/decomp-before-{name}.md`. Check each extracted block appears in a reference file. Common cause: partially extracted code block or table split across body and reference.
