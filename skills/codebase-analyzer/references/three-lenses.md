# The Three Lenses: A Statistical Approach to Code Analysis

**Note**: This skill was formerly called "code-cartographer". References to that name in examples refer to this skill.

## The Problem: Training Bias Override

When an LLM "reads" code, it applies its training data expectations:

```go
// What the code actually says:
if err != nil {
    return err
}

// What LLM's training says:
// "Errors should be wrapped with context"

// What LLM reports:
// "❌ Not wrapping errors properly - should use fmt.Errorf"

// What's actually true:
// ✅ This IS their local standard for this codebase
```

The LLM can't distinguish between:
- "What the training corpus considers best practice"
- "What this specific codebase actually does"

## The Solution: Measure, Don't Read

Instead of asking "What does this code do?" ask "How many times does X appear?"

**Don't ask**: "Does this code wrap errors?"
**Do ask**: "Count: fmt.Errorf with %w vs without vs raw return"

The LLM doesn't judge. It just counts. Then it reports the statistics.

## Why Three Lenses?

A single statistical view isn't enough. Three complementary perspectives give the full picture:

### Lens 1: Consistency (Frequency)
**What it measures**: "How often do they use X?"
**Why it matters**: Frequency reveals dependencies and tool preferences

#### What Gets Counted:
- **Imports**: Which packages appear most (reveals ecosystem choices)
- **Test frameworks**: testify vs standard testing vs ginkgo (reveals testing culture)
- **Logging libraries**: Which logger, which log levels (reveals debugging approach)
- **Modern features**: slices package, maps package, min/max (reveals Go version adoption)

#### Example Insights:
```
Import frequency:
  github.com/your-org/go-libs/logg: 45 files
  → Rule: "Use org-libs/logg for all logging"

Test framework usage:
  standard_testing: 84.8%
  testify: 15.2%
  → Rule: "Prefer standard testing, avoid testify"

Modern Go features:
  slices package: 23 files
  maps package: 12 files
  → Rule: "Adopt modern Go 1.21+ features"
```

### Lens 2: Signature (Structure)
**What it measures**: "How do they name/structure things?"
**Why it matters**: Naming reveals conventions and cognitive patterns

#### What Gets Counted:
- **Function prefixes**: Get, Set, New, Create, Make, Handle, Process
- **Constructor patterns**: New{Type} vs Create{Type} vs Make{Type}
- **Receiver names**: Single letter (d, s, c) vs full words
- **Parameter order**: context first vs context later
- **Variable naming**: err vs e, ctx vs context

#### Example Insights:
```
Constructor patterns:
  New_prefix: 94.4%
  Create_prefix: 5.6%
  → Rule: "Constructors must use New{Type} pattern"

Receiver naming:
  d: 45 occurrences
  s: 23 occurrences
  db: 2 occurrences
  → Rule: "Use single-letter receivers, type's first letter"

Error variable naming:
  err: 96%
  e: 3%
  error: 1%
  → Rule: "Error variables must be named 'err'"
```

### Lens 3: Idiom (Implementation)
**What it measures**: "How do they implement patterns?"
**Why it matters**: Implementation reveals actual coding philosophy

#### What Gets Counted:
- **Error handling**: fmt.Errorf %w vs errors.Wrap vs raw return
- **Control flow**: Guard clauses vs else blocks
- **Resource management**: defer close, unlock, rollback
- **Nil checks**: != nil vs == nil frequency
- **Context usage**: First parameter position consistency

#### Example Insights:
```
Error handling:
  fmt_errorf_with_w: 89%
  fmt_errorf_without_w: 6%
  return_raw_err: 5%
  → Rule: "All errors must be wrapped with fmt.Errorf and %w"

Control flow:
  guard_clauses: 234
  else_blocks: 45
  ratio: 5.2x
  → Rule: "Prefer guard clauses over else blocks"

Defer patterns:
  defer_close: 67
  defer_unlock: 23
  defer_rollback: 5
  → Rule: "Always defer resource cleanup"
```

## How the Lenses Work Together

Each lens reveals different aspects of the same codebase:

### Example: Error Handling

**Lens 1 (Consistency)**:
- Import frequency shows `fmt` in 98% of files
- No imports of `github.com/pkg/errors`
- **Insight**: Team doesn't use pkg/errors

**Lens 2 (Signature)**:
- Error variable name: 96% use `err`
- **Insight**: Standard naming convention

**Lens 3 (Idiom)**:
- Error wrapping: 89% use `fmt.Errorf` with `%w`
- **Insight**: Go 1.13+ error wrapping is standard

**Combined Rule**:
```
Error Handling Standard:
1. Use 'err' for error variables (96% consistency)
2. Wrap errors with fmt.Errorf("while X: %w", err) (89% consistency)
3. Don't use github.com/pkg/errors (0% usage)

Confidence: HIGH
Evidence: Consistent across all three lenses
```

### Example: Constructor Patterns

**Lens 1 (Consistency)**:
- Constructor count: 36 across codebase
- **Insight**: Moderate use of constructors

**Lens 2 (Signature)**:
- New_prefix: 94.4%
- Create_prefix: 5.6%
- **Insight**: Strong preference for New{Type}

**Lens 3 (Idiom)**:
- (Not directly measured here, but could track initialization patterns)

**Combined Rule**:
```
Constructor Standard:
1. Always use New{Type} pattern (94% consistency)
2. Avoid Create{Type} (only 6% usage)

Confidence: HIGH
Evidence: Strong statistical preference in naming
```

## Confidence Scoring

Rules are derived when statistical evidence is strong:

### HIGH Confidence (>85%)
**Meaning**: Extremely consistent pattern
**Action**: Enforce this as a hard rule
**Example**: 96% use `err` not `e` → "MUST use err"

### MEDIUM Confidence (70-85%)
**Meaning**: Strong preference, some exceptions
**Action**: Prefer this pattern, accept exceptions with justification
**Example**: 78% use guard clauses → "SHOULD prefer guard clauses"

### LOW Confidence (<70%)
**Meaning**: No clear pattern
**Action**: Don't create a rule
**Example**: 55% use single-letter receivers → No rule

## Avoiding False Positives

### Pattern: Vendor Code
**Problem**: Vendor directories skew statistics
**Solution**: Filter out vendor/, .git/, node_modules/

### Pattern: Generated Code
**Problem**: Generated code may have different style
**Solution**: Could add --exclude-generated flag

### Pattern: Legacy Code
**Problem**: Old code may not reflect current standards
**Solution**: Could add --since flag to analyze only recent files

### Pattern: Test Code
**Problem**: Test code may have different patterns
**Solution**: Separate analysis for _test.go files (tracked separately)

## Reconciling with PR Miner

### Scenario 1: Agreement (Both Say Same Thing)
**pr-workflow (miner)**: "Please wrap errors with fmt.Errorf %w"
**code-cartographer**: 89% use fmt.Errorf with %w
**Conclusion**: HIGH confidence rule - both explicit and practiced

### Scenario 2: PR Miner Silent, Code Consistent
**pr-workflow (miner)**: No comments about receiver naming
**code-cartographer**: 94% use single-letter receivers
**Conclusion**: Implicit rule - nobody argues because everyone agrees

### Scenario 3: PR Miner Says X, Code Does Y
**pr-workflow (miner)**: "Should use testify for tests"
**code-cartographer**: 85% use standard testing
**Conclusion**: Rule stated but not followed - needs enforcement OR rule is outdated

### Scenario 4: Both Inconsistent
**pr-workflow (miner)**: Mixed comments about logging
**code-cartographer**: 45% use logg.Info, 40% use log.Info, 15% other
**Conclusion**: No clear standard - opportunity to establish one

## Practical Example: Go Project Analysis

Let's walk through a real analysis:

### Step 1: Run Cartographer
```bash
# TODO: scripts/cartographer.py not yet implemented
# Use manual grep/find pattern counting as described in SKILL.md
```

### Step 2: Review Statistics

**Lens 1 Results**:
```json
"top_dependencies": {
  "github.com/your-org/go-libs/logg": 45,
  "github.com/go-openapi/runtime": 23,
  "context": 89
}
```
**Insight**: Heavy use of org-libs/logg and OpenAPI

**Lens 2 Results**:
```json
"constructor_patterns": {
  "New_prefix": 34,
  "Create_prefix": 2
}
```
**Insight**: Strong New{Type} preference

**Lens 3 Results**:
```json
"error_handling": {
  "fmt_errorf_with_w": 156,
  "fmt_errorf_without_w": 12,
  "return_raw_err": 8
}
```
**Insight**: Consistent error wrapping

### Step 3: Derived Rules
```json
"derived_rules": [
  {
    "rule": "All errors must be wrapped using fmt.Errorf with %w verb",
    "evidence": "89% consistency across 176 error checks",
    "confidence": "HIGH"
  },
  {
    "rule": "Constructors must use New{Type} naming pattern",
    "evidence": "94% of 36 constructors follow this pattern",
    "confidence": "HIGH"
  }
]
```

### Step 4: Cross-Reference with PR Miner
```bash
# Check what reviewers actually said
grep -i "error" pr_miner_data/project_reviews.json | grep -i "wrap"
```

If pr-workflow (miner) also shows error wrapping comments → **Rule confirmed**
If pr-workflow (miner) is silent → **Implicit rule discovered**

## Summary

The three lenses work together to build a complete picture:

1. **Lens 1 (Consistency)**: What tools and libraries they prefer
2. **Lens 2 (Signature)**: How they name and structure things
3. **Lens 3 (Idiom)**: How they implement patterns

Measuring instead of reading avoids training bias and reveals the rules that actually govern the codebase.

**Key Principle**: Let the statistics speak. The LLM is just a calculator, not a judge.
