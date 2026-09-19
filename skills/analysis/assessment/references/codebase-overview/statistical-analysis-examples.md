# Codebase Analyzer: Real-World Examples

**Note**: This skill was formerly called "code-cartographer". Update any saved commands to use the current name.

## Example 1: Analyzing a Go Service

### Scenario
You want to understand the error handling standards in a Go service before submitting a PR.

### Command
```bash
cd ~/.claude/skills/codebase-analyzer
python3 ~/.claude/scripts/analyzer.py ~/repos/api-server --output analysis_data/api_server_analysis.json
```

### Output Summary
```
================================================================================
CODEBASE ANALYSIS SUMMARY
================================================================================

📦 Repository: api-server
📄 Files analyzed: 127
📏 Total lines: 15,432

🎯 Derived Rules: 5

  [HIGH] All errors must be wrapped using fmt.Errorf with %w verb
  Evidence: 89% consistency across 176 error checks

  [HIGH] Constructors must use New{Type} naming pattern
  Evidence: 94% of 36 constructors follow this pattern

  [HIGH] context.Context must be the first parameter
  Evidence: 98% consistency across 91 functions

  [HIGH] Prefer guard clauses (early returns) over else blocks
  Evidence: 5.2x more guard clauses than else blocks

  [HIGH] Error variables must be named 'err', not 'e' or 'error'
  Evidence: 96% consistency across 234 error variables

================================================================================
```

### Interpretation

1. **Error Handling**: 89% use `fmt.Errorf("while X: %w", err)`
   - **Action**: Always wrap errors with context
   - **Bad**: `return err`
   - **Good**: `return fmt.Errorf("while loading config: %w", err)`

2. **Constructor Naming**: 94% use `New{Type}`
   - **Action**: Name your constructor `NewAuditHandler`, not `CreateAuditHandler`

3. **Context Parameters**: 98% put context first
   - **Bad**: `func Process(id string, ctx context.Context)`
   - **Good**: `func Process(ctx context.Context, id string)`

4. **Control Flow**: 5.2x more guard clauses than else blocks
   - **Bad**: `if x { doStuff() } else { return err }`
   - **Good**: `if !x { return err }; doStuff()`

5. **Error Variables**: 96% use `err`
   - **Bad**: `e := loadConfig()`
   - **Good**: `err := loadConfig()`

### Cross-Reference with PR Miner

```bash
# Check if reviewers also mention error wrapping
cd ~/.claude/skills/pr-workflow
grep -i "while.*%w" mined_data/senior-reviewer_go_all_2025-11-20.json
```

**Result**: pr-workflow (miner) shows Senior commenting "use fmt.Errorf with %w" in multiple PRs.

**Conclusion**: Both explicit (pr-workflow (miner)) and implicit (codebase-analyzer) evidence confirm this rule.

---

## Example 2: Comparing Team Repos (Multi-Repo Analysis)

### Scenario
You're new to the team and want to understand team-wide patterns across api-server, metrics-service, and registry-service.

### Commands
```bash
cd ~/.claude/skills/codebase-analyzer

# Analyze each repo
python3 ~/.claude/scripts/analyzer.py ~/repos/api-server --output analysis_data/api-server.json
python3 ~/.claude/scripts/analyzer.py ~/repos/metrics-service --output analysis_data/metrics-service.json
python3 ~/.claude/scripts/analyzer.py ~/repos/registry-service --output analysis_data/registry-service.json
```

### Comparison Analysis

**api-server Results**:
- Error wrapping: 89% use fmt.Errorf %w
- Constructor prefix: 94% use New_
- Test framework: 85% standard testing

**metrics-service Results**:
- Error wrapping: 91% use fmt.Errorf %w
- Constructor prefix: 97% use New_
- Test framework: 92% standard testing

**registry-service Results**:
- Error wrapping: 87% use fmt.Errorf %w
- Constructor prefix: 89% use New_
- Test framework: 78% standard testing

### Team-Wide Rules Discovered

1. **Error Wrapping** (87-91% across all repos)
   - **Team Standard**: Always use `fmt.Errorf("while X: %w", err)`
   - **Confidence**: HIGH (consistent across all 3 repos)

2. **Constructor Naming** (89-97% across all repos)
   - **Team Standard**: Use `New{Type}` pattern
   - **Confidence**: HIGH

3. **Testing Framework** (78-92% across all repos)
   - **Team Standard**: Prefer standard testing over testify
   - **Confidence**: MEDIUM-HIGH (some variation)

### Action Items

1. **Update team CLAUDE.md** with these rules
2. **Create team-wide golangci-lint config** enforcing these patterns
3. **Onboarding docs**: Point new developers to these statistics

---

## Example 3: Discovering Modern Go Adoption

### Scenario
You want to know if the team is adopting modern Go 1.21+ features (slices, maps, min/max).

### Command
```bash
python3 ~/.claude/scripts/analyzer.py ~/repos/your-project
```

### Relevant Output Section
```json
"modern_go_adoption": {
  "slices_package": 23,
  "maps_package": 12,
  "min_max_builtin": 5,
  "clear_builtin": 2
}
```

### Interpretation

**Total files**: 127
**Slices package**: Used in 23 files (18%)
**Maps package**: Used in 12 files (9%)

**Insight**: The team IS adopting modern Go features, but not universally.

### Action Items

1. **Refactoring opportunity**: Replace custom deduplication with `slices.Compact`
2. **Code review focus**: Suggest modern alternatives during reviews
3. **Training**: Share examples of slices/maps package usage

---

## Example 4: Validating a New Pattern

### Scenario
You want to introduce a new error handling pattern and first check what the codebase currently does.

### Question
"Should we use `github.com/pkg/errors` for error wrapping?"

### Analysis
```bash
python3 ~/.claude/scripts/analyzer.py ~/repos/your-project
```

### Check Import Statistics
```json
"top_dependencies": {
  "fmt": 127,
  "context": 89,
  "github.com/your-org/go-libs/logg": 45,
  ...
  // Note: github.com/pkg/errors is NOT in top 20
}
```

### Check Error Patterns
```json
"error_handling": {
  "fmt_errorf_with_w": 156,
  "fmt_errorf_without_w": 12,
  "pkg_errors_wrap": 0,     // ← ZERO usage
  "return_raw_err": 8
}
```

### Conclusion
**Answer**: NO, don't introduce pkg/errors
- **Current pattern**: 89% use stdlib `fmt.Errorf` with `%w`
- **pkg/errors usage**: 0%
- **Reason**: Team already standardized on Go 1.13+ error wrapping

**Better approach**: Continue using `fmt.Errorf("while X: %w", err)`

---

## Example 5: Reconciling Inconsistencies

### Scenario
You notice reviewers sometimes ask for different things. Let's check what the code actually does.

### PR Comments Observed
- PR #234: "Please use testify for assertions"
- PR #189: "Prefer standard testing over testify"
- PR #256: "Either is fine"

### Analysis
```bash
python3 ~/.claude/scripts/analyzer.py ~/repos/your-project
```

### Results
```json
"test_libraries": {
  "standard_testing": 67,
  "testify": 12
},
"test_framework_percentages": {
  "standard_testing": 84.8,
  "testify": 15.2
}
```

### Interpretation
**Actual practice**: 85% of test files use standard testing

**Reviewer comments**: Mixed signals (some say testify, some say standard)

**Reality**: The codebase has ALREADY standardized on standard testing, even if reviewers don't consistently articulate it.

### Action Items

1. **Clarify team standard**: Document "prefer standard testing" in CLAUDE.md
2. **Reviewer alignment**: Share these statistics with reviewers
3. **New PRs**: Use standard testing, point to statistics if questioned

---

## Example 6: Tracking Pattern Evolution

### Scenario
Re-analyze the codebase quarterly to see how patterns evolve over time.

### Initial Analysis (Q1 2025)
```bash
python3 ~/.claude/scripts/analyzer.py ~/repos/your-project --output analysis_data/project_2025_q1.json
```

**Results**:
- slices package: 5 files (4%)
- min/max builtin: 1 file (0.8%)

### Follow-Up Analysis (Q4 2025)
```bash
python3 ~/.claude/scripts/analyzer.py ~/repos/your-project --output analysis_data/project_2025_q4.json
```

**Results**:
- slices package: 45 files (35%)
- min/max builtin: 23 files (18%)

### Interpretation
**Trend**: Rapid adoption of modern Go features
- **Q1**: 4% use slices package
- **Q4**: 35% use slices package
- **Growth**: 8.75x increase in 9 months

**Insight**: Team is actively modernizing codebase

**Action**: Update onboarding docs to emphasize modern Go patterns

---

## Example 7: Debugging Style Violations

### Scenario
golangci-lint fails on your PR with "receiver name should be consistent". You want to understand the actual convention.

### Command
```bash
python3 ~/.claude/scripts/analyzer.py ~/repos/your-project
```

### Relevant Output
```json
"receiver_naming": {
  "d": 45,
  "s": 23,
  "c": 18,
  "h": 12,
  "db": 2,
  "ctx": 1
}
```

### Interpretation

**Pattern**: Single-letter receivers strongly preferred
- `d`: 45 occurrences (likely for "Database", "Driver", etc.)
- `s`: 23 occurrences (likely for "Service", "Store", etc.)
- `db`: Only 2 occurrences (multi-letter is rare)

**Rule**: Use single letter matching type's first letter

### Your Code Fix

**Before**:
```go
func (database *Database) Query(ctx context.Context) error {
```

**After**:
```go
func (d *Database) Query(ctx context.Context) error {
```

---

## Example 8: Combined pr-workflow (miner) + codebase-analyzer Workflow

### Complete Analysis Workflow

**Step 1**: Mine PR reviews (explicit rules)
```bash
cd ~/.claude/skills/pr-workflow
./venv/bin/python3 scripts/miner.py your-org/your-repo \
  mined_data/project_reviews.json \
  --limit 100 --all-comments
```

**Step 2**: Analyze codebase (implicit rules)
```bash
cd ~/.claude/skills/codebase-analyzer
python3 ~/.claude/scripts/analyzer.py ~/repos/your-project \
  --output analysis_data/project_stats.json
```

**Step 3**: Reconcile the findings

| Pattern | pr-workflow (miner) says | codebase-analyzer shows | Conclusion |
|---------|---------------|-------------------------|------------|
| Error wrapping | "Use fmt.Errorf %w" (12 comments) | 89% use fmt.Errorf %w | ✅ Confirmed rule |
| Guard clauses | "Prefer early returns" (8 comments) | 5.2x more guards than else | ✅ Confirmed rule |
| Receiver naming | (No comments found) | 96% single-letter | 📊 Implicit rule |
| Test framework | Mixed signals | 85% standard testing | ⚠️  Inconsistent messaging |

**Step 4**: Update documentation

Create `~/repos/your-project/CODING_STANDARDS.md`:

```markdown
# Project Coding Standards

## Error Handling ✅ HIGH CONFIDENCE
**Rule**: All errors must be wrapped with fmt.Errorf("while X: %w", err)
**Evidence**:
- 89% of codebase follows this (codebase-analyzer)
- 12 PR review comments enforcing this (pr-workflow (miner))

## Control Flow ✅ HIGH CONFIDENCE
**Rule**: Prefer guard clauses (early returns) over else blocks
**Evidence**:
- 5.2x more guard clauses than else blocks (codebase-analyzer)
- 8 PR review comments requesting this (pr-workflow (miner))

## Receiver Naming ✅ MEDIUM CONFIDENCE
**Rule**: Use single-letter receivers matching type's first letter
**Evidence**:
- 96% of receivers are single-letter (codebase-analyzer)
- No explicit PR comments (implicit convention)

## Test Framework ⚠️  NEEDS CLARIFICATION
**Current practice**: 85% use standard testing
**PR comments**: Mixed signals (some say testify, some say standard)
**Action**: Team should align on standard testing as official standard
```

---

## Example 9: New Team Member Onboarding

### Scenario
New developer joins the team. Instead of vague "read the code", give them concrete statistics.

### Onboarding Script
```bash
#!/bin/bash
# Welcome to the team!
# This script generates your coding standards cheat sheet.

cd ~/.claude/skills/codebase-analyzer

echo "Analyzing api-server..."
python3 ~/.claude/scripts/analyzer.py ~/repos/api-server --output /tmp/api-server.json

echo "Analyzing metrics-service..."
python3 ~/.claude/scripts/analyzer.py ~/repos/metrics-service --output /tmp/metrics-service.json

echo ""
echo "=============================="
echo "TEAM CODING STANDARDS"
echo "=============================="
echo ""
echo "Based on statistical analysis of 250+ Go files:"
echo ""
echo "1. Error Handling:"
echo "   ✓ Always wrap: fmt.Errorf(\"while X: %w\", err)"
echo "   ✓ Always use 'err' not 'e'"
echo "   ✓ 89% consistency across codebase"
echo ""
echo "2. Function Patterns:"
echo "   ✓ Constructors: New{Type} pattern"
echo "   ✓ Context: Always first parameter"
echo "   ✓ Guard clauses: 5x more common than else"
echo ""
echo "3. Testing:"
echo "   ✓ Use standard testing package"
echo "   ✓ 85% of tests use standard testing"
echo ""
echo "See /tmp/api-server.json for full statistics"
```

### Result
New developer has concrete, evidence-based standards from day one.

---

## Summary

These examples demonstrate:

1. **Single repo analysis**: Understand local patterns
2. **Multi-repo comparison**: Find team-wide standards
3. **Pattern discovery**: Find implicit conventions
4. **Validation**: Check before introducing new patterns
5. **Reconciliation**: Resolve conflicting guidance
6. **Evolution tracking**: Monitor pattern changes over time
7. **Debugging**: Understand specific style requirements
8. **Combined workflow**: pr-workflow (miner) + codebase-analyzer
9. **Onboarding**: Give new developers concrete standards

**Key Insight**: Statistics don't lie. When code shows 89% consistency, that IS the standard, regardless of what anyone remembers or thinks.
