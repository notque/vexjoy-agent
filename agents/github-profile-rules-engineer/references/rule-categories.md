<!--
scope: github-profile-rules-engineer
version: 1.0.0
date: 2026-04-05
purpose: Taxonomy of programming rule types extracted from GitHub profiles
level: 3 (detection commands, confidence scoring, output format)
-->

# Rule Categories — GitHub Profile Rules Engineer

Taxonomy of rule types this agent extracts, with detection signals, confidence thresholds, and output format.

---

## Confidence Scoring

Every rule must carry a confidence level based on cross-repo corroboration.

| Confidence | Threshold | Meaning |
|------------|-----------|---------|
| **high** | 3+ repos, 5+ matching files | Pattern is consistent enough to include in CLAUDE.md |
| **medium** | 2 repos OR 1 repo with 5+ files showing the pattern | Worth noting; qualify with context |
| **low** | 1 repo, 1–4 files | Tentative; require developer confirmation before acting |
| **insufficient** | Single file, no corroboration | Drop the rule — it's noise, not signal |

PR review comments override code signals: a pattern the developer *requested* in review is stronger than one they merely wrote once.

---

## Rule Output Format

```
Rule: {imperative statement of the convention}
Evidence: {repo}/{file}:{line} | {repo2}/{file2}:{line2}
Confidence: high | medium | low
Applies when: {language / context / project type}
Source type: authored-code | pr-review-comment | both
```

Example:

```
Rule: Use snake_case for all module-level constants, not SCREAMING_SNAKE_CASE
Evidence: myuser/api-server/config.py:14 | myuser/data-pipeline/settings.py:8
Confidence: high
Applies when: Python, any project type
Source type: pr-review-comment
```

---

## Category 1: Naming Conventions

**What to look for:**
- Variable, function, class, and file naming patterns across multiple repos
- Abbreviation habits (e.g., `mgr` vs `manager`, `ctx` vs `context`)
- Prefix/suffix patterns (`_internal`, `I` for interfaces, `Impl`)
- Test file naming (`test_foo.py` vs `foo_test.go` vs `foo.spec.ts`)

**High-confidence signal:** Same naming style applied consistently in 3+ repos across 10+ identifiers.

**Detection approach:**
```
# Grep for class definitions to detect naming style
grep -r "^class " --include="*.py" | head -50
grep -r "^func " --include="*.go" | head -50
grep -r "export (function|const|class) " --include="*.ts" | head -50
```

**Anti-pattern:** Detecting Go `camelCase` and inferring a preference — Go mandates it. Only extract naming patterns that deviate from or supplement language defaults.

---

## Category 2: Style Preferences

**What to look for:**
- Line length (check for long lines vs. aggressive wrapping)
- Comment style (inline vs. block, JSDoc vs. plain text)
- Blank line usage between functions/methods
- Import ordering (stdlib first? grouped? aliased?)
- Trailing comma presence in multi-line literals

**High-confidence signal:** Consistent style across files in 3+ repos with no `.editorconfig` or formatter config that would enforce it.

**Detection approach:**
```
# Check for formatter configs that would override personal style
find . -name ".editorconfig" -o -name ".prettierrc" -o -name "pyproject.toml" | head -10

# If formatter config exists, lower confidence on style rules — formatter, not preference
```

**Anti-pattern:** Extracting style rules when a formatter config (`.prettierrc`, `gofmt`, `black`) is present. The formatter owns style; the developer's preference is only visible where the formatter has gaps.

---

## Category 3: Architectural Patterns

**What to look for:**
- Folder structure (feature-based vs. layer-based, domain separation)
- Service/handler split patterns
- Config injection style (env vars, config structs, dependency injection containers)
- Interface granularity (many small interfaces vs. few large ones)
- Error wrapping strategy (context added at each layer vs. root-only)

**High-confidence signal:** Same structural pattern reproduced independently in 3+ repos of similar type (e.g., 3 API servers all using the same handler/service/repository split).

**Detection approach:**
```
# Inspect top-level directory structure across repos
GET /repos/{owner}/{repo}/contents/
# Look for repeated patterns: cmd/, internal/, pkg/ (Go); src/features/ vs src/components/ (TS)
```

**Anti-pattern:** Treating framework scaffolding as developer preference. A `pages/` directory in Next.js or `app/controllers/` in Rails is framework-mandated, not a personal choice.

---

## Category 4: Testing Habits

**What to look for:**
- Test coverage breadth (unit only, integration tests present, e2e tests present)
- Assertion library choices (built-in vs. third-party)
- Test data strategy (fixtures, factories, inline literals)
- Mock/stub approach (manual mocks, mock libraries, dependency injection)
- Test naming convention (describe/it, TestXxx, test_should_xxx)

**High-confidence signal:** Consistent testing approach across 3+ repos with test suites.

**Detection approach:**
```
# List test files
GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1
# Filter: path ends with _test.go, .test.ts, _spec.rb, test_*.py

# Sample test file contents for assertion and mock patterns
GET /repos/{owner}/{repo}/contents/{test_file_path}
```

**Anti-pattern:** Extracting testing rules from test files alone — test code often follows different conventions from production code. Verify that rules extracted from tests are explicitly requested in PR reviews before treating them as general preferences.

---

## Category 5: Error Handling Patterns

**What to look for:**
- Error wrapping depth (how much context added per layer)
- Custom error types vs. standard errors
- Panic usage policy (Go), exception specificity (Python/JS)
- Logging at error site vs. propagating for caller to log
- Error message format (lowercase, sentence-ended, code-prefixed)

**High-confidence signal:** Same error wrapping or message format pattern in 5+ files across 2+ repos.

**Detection approach:**
```
# Search for error creation and wrapping patterns
grep -r "fmt.Errorf\|errors.New\|errors.Wrap" --include="*.go" | head -30
grep -r "raise\|except\|ValueError\|RuntimeError" --include="*.py" | head -30
grep -r "throw new\|catch\s*(" --include="*.ts" | head -30
```

---

## Category 6: Documentation Style

**What to look for:**
- README completeness and structure (badges, setup, usage, contributing)
- Inline comment density (heavy narration vs. sparse)
- Function/method docstring presence and format
- TODO/FIXME/HACK comment habits
- Changelog presence and format

**High-confidence signal:** Consistent README structure across 3+ repos (same sections, same ordering).

**Detection approach:**
```
# Fetch README content
GET /repos/{owner}/{repo}/readme
# Decoded content will show structure

# Check docstring presence in sampled source files
```

**Anti-pattern:** Inferring documentation preferences from repos with contributing guidelines that mandate a style (e.g., a company open-source template). Only extract rules from personal projects where the developer made the documentation choices themselves.

---

## Category 7: Dependency Preferences

**What to look for:**
- Preferred HTTP client libraries
- Test framework choices (jest vs. vitest, pytest vs. unittest)
- ORM/database access patterns (raw SQL, query builder, ORM)
- Logging library choices
- Dependency minimalism (few deps vs. many utility packages)

**High-confidence signal:** Same dependency appearing in 3+ repos' `go.mod`, `package.json`, `requirements.txt`, or `Cargo.toml`.

**Detection approach:**
```
# Fetch dependency manifests
GET /repos/{owner}/{repo}/contents/package.json
GET /repos/{owner}/{repo}/contents/go.mod
GET /repos/{owner}/{repo}/contents/requirements.txt
# Decode base64 content, tally repeated dependencies
```

**Anti-pattern:** Treating transitive dependencies as preferences. Only direct dependencies in the manifest reflect deliberate choices.

---

## Anti-Pattern Catalog

| Anti-Pattern | Description | Detection | Mitigation |
|--------------|-------------|-----------|------------|
| **Framework bleed** | Extracting framework conventions as developer rules | Pattern appears only in framework dirs (`controllers/`, `pages/`) | Verify pattern appears outside framework scaffolding |
| **Test-only rules** | Rules from test code that don't apply to production | Pattern found only in `*_test.*` files | Cross-reference with production code before including |
| **Boilerplate extraction** | Treating generated/template code as preference | Files named `template`, `scaffold`, `generated`, `_auto` | Skip files with these markers |
| **Single-project overfitting** | 20 rules from one repo with unique constraints | All evidence cites the same repo | Require 2+ repos for medium confidence, 3+ for high |
| **Formatter displacement** | Extracting style rules that a formatter enforces | `.prettierrc`, `black`, `gofmt`, `rustfmt` present | Mark affected style rules as `formatter-controlled`, do not emit |
| **Star-biased sampling** | Analyzing only the most-starred repos | Most-starred may be old or showcase work, not daily style | Sort by `pushed_at`, not stars |

---

## Detection Commands Reference

Use these grep patterns on extracted rule output to validate rule quality before emitting:

```bash
# Rules missing evidence citation
grep -E "^Rule:" output.md | grep -v "Evidence:"

# Rules with only single-repo evidence
grep -E "Evidence: [^|]+" output.md | grep -v "|"

# Rules with no confidence level
grep -E "^Rule:" output.md -A4 | grep -v "Confidence:"

# Low-confidence rules (review before including)
grep -B1 "Confidence: low" output.md

# Rules sourced from test files only — verify before keeping
grep "Evidence:.*test" output.md | grep -v "Source type: pr-review"
```
