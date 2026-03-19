---
name: codebase-analyzer
description: |
  Statistical rule discovery through measurement of Go codebases: Count
  patterns, derive confidence-scored rules, produce Style Vector fingerprint.
  Use when analyzing codebase conventions, extracting implicit coding rules,
  profiling a repo before onboarding or PR automation. Use for "analyze
  codebase", "find coding patterns", "what conventions does this repo use",
  "extract rules", or "codebase DNA". Do NOT use for code review, bug
  fixes, refactoring, or performance optimization.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
context: fork
---

# Codebase Analyzer Skill

## Operator Context

This skill operates as an operator for statistical codebase analysis, configuring Claude's behavior for measurement-based rule discovery from Go codebases. It implements a **Measure, Don't Read** methodology -- Python scripts count patterns to avoid LLM training bias override, then statistics are interpreted to derive confidence-scored rules.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution. Project instructions override default behaviors.
- **Over-Engineering Prevention**: Scripts perform pure statistical measurement only. No feature additions beyond counting patterns. No speculative metrics or flexibility that was not requested.
- **Measurement-Only Analysis**: Scripts count and measure; NEVER interpret or judge code quality during data collection phase. The LLM is a calculator, not a judge.
- **No Training Bias**: Analysis MUST avoid LLM interpretation of "good" vs "bad" patterns during measurement. What IS in the code is the local standard.
- **Confidence Gating**: Only derive rules from patterns with >70% consistency. Below that threshold, report statistics without creating rules.
- **Separate Measurement from Interpretation**: Run scripts first (mechanical), then interpret statistics second (analytical). Never combine these steps.

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show complete statistics rather than describing them. Be concise but informative.
- **Temporary File Cleanup**: Analysis scripts do not create temporary files (single-pass processing). Any debug outputs or iteration files should be removed at completion.
- **Verbose Output**: Display summary statistics to stderr, full JSON to stdout or file.
- **Confidence Thresholds**: HIGH (>85%), MEDIUM (70-85%), below 70% not extracted as rule.
- **Vendor Filtering**: Automatically skip vendor/, testdata/, and generated code to avoid polluting statistics with external patterns.

### Optional Behaviors (OFF unless enabled)
- **Cross-Repository Analysis**: Compare patterns across multiple repos (requires explicit request).
- **Historical Tracking**: Re-analyze same repo over time to track pattern evolution (requires explicit request).
- **Custom Metric Addition**: Add new measurement categories beyond the 100 standard metrics (requires explicit request).

## What This Skill CAN Do
- Extract implicit coding rules through statistical analysis of Go codebases
- Measure 100 metrics across 25 categories using Python scripts
- Derive confidence-scored rules from pattern frequency data
- Produce a 10-dimensional Style Vector quality fingerprint (0-100 scores)
- Discover shadow constitution rules (linter suppressions teams accept)
- Compare patterns across multiple repositories for team-wide standards

## What This Skill CANNOT Do
- Judge code quality subjectively (measures patterns, not "good" vs "bad")
- Analyze non-Go codebases (scripts are Go-specific)
- Derive rules from codebases with fewer than 50 Go files (insufficient sample)
- Replace code review or linting (produces rules, not enforcement)
- Skip measurement and rely on LLM "reading" the code

---

## Instructions

### Phase 1: CONFIGURE (Do NOT proceed without validated target)

**Goal**: Validate target and select analyzer variant.

**Step 1: Validate the target**
- Confirm path points to a Go repository root with .go files
- Check for standard structure (cmd/, internal/, pkg/)
- Verify sufficient file count (50+ files for meaningful rules, 100+ ideal)

**Step 2: Select cartographer variant**

| Variant | Script | Metrics | Use When |
|---------|--------|---------|----------|
| Omni (recommended) | `cartographer_omni.py` (not yet implemented) | 100 across 25 categories | Full codebase profiling |
| Basic | `cartographer.py` (not yet implemented) | ~15 categories | Quick pattern overview |
| Ultimate | `cartographer_ultimate.py` | 6 focused categories | Performance pattern detection |

**Step 3: Verify environment**
- Python 3.7+ available
- No external dependencies needed (uses only Python standard library)
- Output directories exist or can be created

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

**Gate**: Target directory exists, contains 50+ Go files, variant selected. Proceed only when gate passes.

### Phase 2: MEASURE (Do NOT interpret during this phase)

**Goal**: Run statistical analysis scripts. Pure measurement -- no interpretation yet.

**Step 1: Execute the cartographer**

```bash
# TODO: scripts/cartographer_omni.py not yet implemented
# Manual alternative: use grep/find to count patterns across Go files
# Example: count error wrapping patterns
grep -rn 'fmt.Errorf.*%w' ~/repos/my-project --include="*.go" | wc -l
# Example: count constructor patterns
grep -rn 'func New' ~/repos/my-project --include="*.go" | wc -l
```

**Step 2: Verify output integrity**
- Confirm JSON output is valid and complete
- Check file count matches expectations (no vendor pollution)
- Verify all three lenses produced data
- Confirm derived_rules section exists in output

**Step 3: Check for data quality issues**
- File count suspiciously high? Vendor code may be included
- File count suspiciously low? Subdirectories may be missed
- All percentages near 50%? May indicate mixed codebase or insufficient data

```
===============================================================
 PHASE 2: MEASURE
===============================================================

 Script Executed: [cartographer_omni.py (not yet implemented — use manual pattern counting)]
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

**Gate**: Script completed without errors, JSON output is valid, file count is reasonable. Proceed only when gate passes.

### Phase 3: INTERPRET (Now the LLM analyzes)

**Goal**: Derive rules from statistics. This is where LLM interpretation happens -- AFTER measurement is complete.

**Step 1: Review the three lenses**

| Lens | Question | Measures |
|------|----------|----------|
| Consistency (Frequency) | "How often do they use X?" | Imports, test frameworks, logging, modern features |
| Signature (Structure) | "How do they name/structure things?" | Constructors, receivers, parameter order, variables |
| Idiom (Implementation) | "How do they implement patterns?" | Error handling, control flow, context usage, defer |

For detailed lens explanations, see `references/three-lenses.md`.

**Step 2: Extract rules by confidence**

| Confidence | Threshold | Action | Example |
|------------|-----------|--------|---------|
| HIGH | >85% consistency | Extract as enforceable rule | "96% use err not e" -> MUST use err |
| MEDIUM | 70-85% consistency | Extract as recommendation | "78% guard clauses" -> SHOULD prefer guards |
| Below 70% | Not extracted | Report as observation only | "55% single-letter receivers" -> No rule |

**Step 3: Review Style Vector** (Omni only)
- 10 composite scores (0-100): Consistency, Modernization, Safety, Idiomaticity, Documentation, Testing Maturity, Architecture, Performance, Observability, Production Readiness
- Identify strengths (scores >75) and gaps (scores <50)
- Note shadow constitution entries (accepted linter suppressions)

**Step 4: Cross-reference lenses**
- Pattern confirmed across multiple lenses = higher confidence
- Pattern in one lens only = standard confidence
- Contradictions between lenses = investigate further

**Gate**: Rules extracted with evidence and confidence levels. Style Vector reviewed. Proceed only when gate passes.

### Phase 4: DELIVER (Do NOT mark complete without artifacts)

**Goal**: Produce actionable output artifacts.

**Step 1: Save statistical report**
```
cartography_data/{repo_name}_cartography.json
```

**Step 2: Generate derived rules document**
```
derived_rules/{repo_name}_rules.md
```

Format each rule as:
```markdown
## Rule: [Statement]
**Confidence**: HIGH/MEDIUM
**Evidence**: [X% consistency across N occurrences]
**Category**: [error_handling | naming | control_flow | architecture | ...]
**Lens**: [Consistency | Signature | Idiom | Multiple]
```

**Step 3: Summarize Style Vector** (Omni only)

```markdown
## Style Vector Summary
| Dimension | Score | Assessment |
|-----------|-------|------------|
| Consistency | [0-100] | [Strength/Gap/Neutral] |
| Modernization | [0-100] | [Strength/Gap/Neutral] |
| ... | ... | ... |
```

**Step 4: Recommend next steps**
- Compare with pr-miner data if available (explicit vs implicit rules)
- Suggest CLAUDE.md updates for high-confidence rules
- Identify golangci-lint rules that could enforce discovered patterns
- Suggest quarterly re-analysis schedule

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

**Gate**: JSON report saved, rules document generated, next steps documented. Analysis complete.

---

## Complementary Skills

| Skill | Extracts | Combined Value |
|-------|----------|----------------|
| pr-miner | Explicit rules (what people argue about in reviews) | Agreement = HIGH confidence; Silence + consistency = implicit rule |
| codebase-analyzer | Implicit rules (what they actually do) | pr-miner says X but code does Y = rule not followed |

### Reconciliation Matrix

| pr-miner | codebase-analyzer | Conclusion |
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

---

## Anti-Patterns

### Anti-Pattern 1: LLM Reading Instead of Script Measuring
**What**: Using Claude to "read the codebase and find patterns" instead of running cartographer scripts
**Why wrong**: LLM applies training bias -- reports what "should be" instead of what IS. When the LLM sees `return err` it reports "not wrapping errors properly" even if that IS the local standard.
**Do instead**: Run the cartographer script first (measurement), then interpret the statistics (analysis). Two separate steps, never combined.

### Anti-Pattern 2: Rules from Low-Confidence Patterns
**What**: Creating enforceable rules from patterns below 70% consistency (e.g., "45% use fmt.Errorf with %w" becomes "All errors must use fmt.Errorf")
**Why wrong**: Forces consistency where the team has not achieved it organically. Causes false positives in reviews. Team may be transitioning between patterns.
**Do instead**: Only derive rules from HIGH confidence (>85%). For 70-85%, suggest "consider standardizing." Below 70%, report as observation only.

### Anti-Pattern 3: Analyzing Insufficient Sample Size
**What**: Running analysis on a repo with <50 Go files and treating results as definitive patterns
**Why wrong**: Small sample size produces high variance. Patterns that appear consistent at 20 files may be coincidence. Cannot distinguish signal from noise.
**Do instead**: Require 50+ files minimum. For small repos, combine analysis across multiple team repos. For monorepos, analyze the full tree.

### Anti-Pattern 4: One-Time Analysis Without Follow-Up
**What**: Analyzing once, extracting rules, never re-running as the codebase evolves
**Why wrong**: Coding patterns evolve with team growth and new Go versions. One-time snapshot becomes stale within months. Cannot measure impact of standardization efforts.
**Do instead**: Re-analyze quarterly. Compare Style Vector scores over time. Track pattern adoption (e.g., "Did Modernization score improve after Go 1.21 adoption?").

### Anti-Pattern 5: Mixing Measurement and Interpretation
**What**: Having the LLM "read" code files and count patterns manually instead of running the deterministic Python scripts
**Why wrong**: LLM counting is unreliable at scale -- misses files, double-counts, applies inconsistent criteria. Python scripts produce deterministic, reproducible results across runs.
**Do instead**: ALWAYS run the cartographer script for measurement (Phase 2). The LLM's role begins at interpretation (Phase 3), working from the script's JSON output.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I can read the code and find patterns" | Reading applies training bias; measures what "should be" not what IS | Run cartographer scripts for measurement |
| "Small repo is fine for analysis" | <50 files produces unreliable statistics | Combine repos or accept limited confidence |
| "This 55% pattern should be a rule" | Below 70% is noise, not signal | Only extract rules above confidence threshold |
| "Analysis was done last year, still valid" | Patterns evolve with team and language | Re-analyze quarterly |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/three-lenses.md`: Detailed explanation of the three analysis lenses
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Real-world analysis examples and workflows
- `${CLAUDE_SKILL_DIR}/references/metrics-catalog.md`: Complete 100-metric catalog across 25 categories

### Prerequisites
- Python 3.7+
- Go codebase to analyze (50+ files recommended)
- No external dependencies (uses only Python standard library)
