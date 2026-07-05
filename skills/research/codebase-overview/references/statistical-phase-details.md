# Codebase Analyzer: Phase Details

Detailed phase banners, reconciliation matrix, worked examples, and error
handling for the codebase-analyzer skill.

---

## Phase Banners

### Phase 1: CONFIGURE banner

```
===============================================================
 PHASE 1: CONFIGURE
===============================================================

 Target Repository:
   - Path: [/path/to/repo]
   - Go Files: [N files found]
   - Structure: [cmd/ | internal/ | pkg/ | flat]

 Variant Selected: [Omni | Basic | Ultimate]
 Reason: [why this variant]

 Validation:
   - [ ] Path exists and contains .go files
   - [ ] File count >= 50 (actual: N)
   - [ ] Python 3.7+ available
   - [ ] Output directory writable

 CONFIGURE complete. Proceeding to MEASURE...
===============================================================
```

### Phase 2: MEASURE banner

```
===============================================================
 PHASE 2: MEASURE
===============================================================

 Script Executed: [cartographer_omni.py]
 Target: [/path/to/repo]

 Results:
   - Files analyzed: [N]
   - Total lines: [N]
   - Categories measured: [N of 25]
   - Derived rules: [N auto-extracted]

 Data Quality:
   - [ ] JSON output valid
   - [ ] File count reasonable (no vendor pollution)
   - [ ] All three lenses have data
   - [ ] No unexpected zeros in major categories

 Output saved to: [path/to/output.json]

 MEASURE complete. Proceeding to INTERPRET...
===============================================================
```

### Phase 4: DELIVER banner

```
===============================================================
 PHASE 4: DELIVER
===============================================================

 Artifacts:
   - [ ] JSON report: [path]
   - [ ] Rules document: [path]
   - [ ] Style Vector summary: [included in rules doc]

 Results Summary:
   - HIGH confidence rules: [N]
   - MEDIUM confidence rules: [N]
   - Observations (below threshold): [N]
   - Style Vector overall: [strong/mixed/weak]

 Next Steps:
   1. [Specific recommendation]
   2. [Specific recommendation]
   3. [Specific recommendation]

 DELIVER complete. Analysis finished.
===============================================================
```

## Rule Format (Phase 4)

Format each rule as:
```markdown
## Rule: [Statement]
**Confidence**: HIGH/MEDIUM
**Evidence**: [X% consistency across N occurrences]
**Category**: [error_handling | naming | control_flow | architecture | ...]
**Lens**: [Consistency | Signature | Idiom | Multiple]
```

## Style Vector Summary (Phase 4, Omni only)

```markdown
## Style Vector Summary
| Dimension | Score | Assessment |
|-----------|-------|------------|
| Consistency | [0-100] | [Strength/Gap/Neutral] |
| Modernization | [0-100] | [Strength/Gap/Neutral] |
| ... | ... | ... |
```

---

## Complementary Skills

| Skill | Extracts | Combined Value |
|-------|----------|----------------|
| pr-workflow (miner) | Explicit rules (what people argue about in reviews) | Agreement = HIGH confidence; Silence + consistency = implicit rule |
| codebase-analyzer | Implicit rules (what they actually do) | pr-workflow (miner) says X but code does Y = rule not followed |

### Reconciliation Matrix

| pr-workflow (miner) | codebase-analyzer | Conclusion |
|----------|-------------------|------------|
| Says X | Shows X at >85% | Confirmed rule (both explicit and practiced) |
| Silent | Shows X at >85% | Implicit rule (nobody argues because everyone agrees) |
| Says X | Shows Y at >85% | Rule stated but not followed (needs enforcement or is outdated) |
| Mixed signals | Inconsistent | No standard yet (opportunity to establish one) |

---

## Examples

### Example 1: Single Repository Analysis
User says: "What conventions does this repo follow?"
Actions:
1. Validate target has 100+ Go files (CONFIGURE)
2. Run pattern counting against the repo (MEASURE)
3. Extract rules from statistics: error wrapping 89%, guard clauses 5.2x, New{Type} 94% (INTERPRET)
4. Save JSON report and rules document (DELIVER)
Result: 30+ rules extracted with confidence levels, Style Vector produced

### Example 2: Team-Wide Standards Discovery
User says: "Find our team's coding patterns across all services"
Actions:
1. Validate all target repos, confirm 50+ files each (CONFIGURE)
2. Run cartographer on each repo separately (MEASURE)
3. Cross-reference patterns: error wrapping 87-91% across all repos = team standard (INTERPRET)
4. Produce team-wide rules document with per-repo breakdowns (DELIVER)
Result: Team-wide standards with cross-repo evidence

### Example 3: Onboarding New Developer
User says: "I just joined the team, what coding patterns should I follow?"
Actions:
1. Identify main team repos, validate Go file counts (CONFIGURE)
2. Run omni-cartographer on primary service (MEASURE)
3. Extract top 10 HIGH confidence rules as onboarding checklist (INTERPRET)
4. Produce concise rules doc focusing on error handling, naming, and control flow (DELIVER)
Result: Evidence-based onboarding guide with concrete examples from actual codebase

---

## Error Handling

### Error: "No Go files found"
Cause: Path does not point to a Go repository root, or .go files are in subdirectories not being scanned
Solution:
1. Verify path points to repository root with `ls *.go` or `find . -name "*.go" | head`
2. If Go files are nested, point to parent directory
3. Confirm vendor/ is not the only directory containing Go files

### Error: "No rules derived"
Cause: Codebase too small (<50 files) or patterns genuinely inconsistent
Solution:
1. Check file count -- if <50, combine analysis across multiple repos from same team
2. If >50 files but no rules, team genuinely lacks consistent patterns
3. Lower threshold to 60% to find emerging patterns (note reduced confidence)

### Error: "Statistics dominated by vendor/generated code"
Cause: Vendor directory or generated files not filtered, polluting pattern data
Solution:
1. Verify scripts are filtering vendor/, testdata/, and _test files for core patterns
2. If non-standard structure, analyze specific directories manually
3. Check for generated code markers (Code generated by...) and exclude those files
