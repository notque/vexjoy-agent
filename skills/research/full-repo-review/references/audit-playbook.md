# Audit Playbook

Structured checklists for full-repo review. Each category lists specific patterns to look for and the evidence required to confirm a finding. Findings without evidence are speculation, not findings.

Integrates with `score-component.py` grades: F and D grades (< 60) map to CRITICAL severity, C grade (60-74) maps to HIGH. Each category names a primary reviewer role; overlap is intentional — independent confirmation strengthens findings. See "Reviewer Role Cross-Reference" for how roles map to `parallel-code-review` and to comprehensive-review wave lenses.

---

## How to Use

The orchestrator loads this playbook and pastes the relevant category checklists — plus each component's `score-component.py` score and grade — into every review agent's prompt (agents run in fresh context and cannot load it themselves). Each agent then, for each category it owns:

1. Check every pattern in the "Look for" list against the file under review.
2. Record a finding only when evidence exists (file path, line number, concrete observation).
3. Assign severity per the category's severity guide.
4. Cross-reference the `score-component.py` scores in the prompt — structural issues the script already flagged need confirmation, not rediscovery.

---

## Category 1: Correctness

**Primary reviewer**: Business Logic

**Look for**:

| Pattern | Evidence required |
|---|---|
| Off-by-one in loops, slices, ranges | Line number + boundary values that trigger the error |
| Nil/null dereference on optional returns | Call site that skips the nil check + the function signature |
| Race condition on shared state | Two goroutines/threads accessing the same variable without synchronization; name both access points |
| Unchecked error return | `file:line` where error is discarded + what failure it masks |
| Type coercion that loses precision | The two types involved + a value that would be truncated |
| Dead code path (unreachable branch) | The condition that is always true/false + why |
| Incorrect boolean logic (swapped AND/OR, missing negation) | The expression + an input that produces wrong output |

**Severity guide**: Data loss or silent wrong answer = CRITICAL. Logic error with limited blast radius = HIGH. Unreachable code = MEDIUM.

---

## Category 2: Security

**Primary reviewer**: Security

**Defer to the `security-review` skill for comprehensive security audits.** This category catches surface-level security issues during a repo-wide sweep; it does not replace the dedicated 25-pattern regex scanner + 40-class LLM taxonomy in `security-review`.

**Look for**:

| Pattern | Evidence required |
|---|---|
| Hardcoded secrets, API keys, tokens | `file:line` + the literal or pattern matched |
| SQL/command injection (unsanitized input in query/exec) | The input source + the query/command it flows into |
| Missing authentication on a route/endpoint | The route definition + absence of auth middleware |
| Overly broad file permissions (world-writable, 777) | The chmod/permission call + the file it affects |
| Secrets in logs, error messages, or client responses | `file:line` + the variable being logged |

**Severity guide**: Exploitable vulnerability = CRITICAL. Missing defense-in-depth = HIGH. Hardening opportunity = MEDIUM.

**Boundary**: Findings requiring deep threat modeling (attack trees, trust boundary analysis, cryptographic protocol review) belong in `security-review`, not here.

---

## Category 3: Performance

**Primary reviewer**: Architecture

**Look for**:

| Pattern | Evidence required |
|---|---|
| N+1 query pattern (loop issuing one query per item) | The loop + the query inside it + the collection size if known |
| Unbounded collection growth (append without cap or eviction) | The data structure + the growth path + absence of bounds |
| Blocking call on hot path (synchronous I/O in request handler) | The call + the path it blocks |
| Redundant computation (same value computed multiple times) | Both computation sites + the shared input |
| Missing index on frequently queried column | The query + the table + absence of index in schema |
| Large allocation in tight loop | The allocation + loop bounds |

**Severity guide**: Measurable latency/memory impact on production path = HIGH. Theoretical concern without load evidence = MEDIUM. Micro-optimization = LOW.

---

## Category 4: Test Coverage

**Primary reviewer**: Business Logic

**Look for**:

| Pattern | Evidence required |
|---|---|
| Public function with zero test coverage | Function signature + grep confirming no test calls it |
| Test that asserts nothing (no assertion, only prints) | `file:line` of the test + absence of assert/expect |
| Test that mocks the thing it tests (tautological) | The mock setup + the assertion that checks the mock |
| Missing edge-case test (boundary values, empty inputs, errors) | The function's contract + the untested boundary |
| Flaky test indicators (sleep, time-dependent, order-dependent) | The timing call or shared state + the test name |
| Test file without corresponding source file (orphaned) | The test path + the missing source path |

**Severity guide**: Core business logic untested = HIGH. Utility/helper untested = MEDIUM. Missing edge case on tested function = LOW.

---

## Category 5: Tech Debt

**Primary reviewer**: Architecture

**Look for**:

| Pattern | Evidence required |
|---|---|
| TODO/FIXME/HACK comments older than 6 months | `file:line` + `git log` date of the comment |
| Duplicated logic across 3+ files | The duplicated block + all file locations |
| Deprecated API usage (language or library) | The deprecated call + the recommended replacement |
| Inconsistent patterns for the same operation | Two+ examples of the same operation done differently |
| Overly complex function (cyclomatic complexity, deep nesting) | The function + nesting depth or branch count |
| Dead dependencies (imported but unused) | The import + grep confirming no usage |

**Severity guide**: Deprecated API with removal timeline = HIGH. Duplication causing maintenance risk = MEDIUM. Cosmetic inconsistency = LOW.

---

## Category 6: Dependencies

**Primary reviewer**: Security

**Look for**:

| Pattern | Evidence required |
|---|---|
| Known vulnerability in pinned version | The package + version + CVE or advisory ID |
| Unpinned dependency (floating version) | The dependency spec + the lockfile state |
| Abandoned dependency (no commits in 12+ months) | The package name + last commit date |
| Unnecessary dependency (functionality available in stdlib) | The import + the stdlib equivalent |
| Version conflict between direct and transitive deps | The two version specs + the conflict |
| License incompatibility | The dependency license + the project license |

**Severity guide**: Known CVE = CRITICAL. Abandoned with no alternative = HIGH. Unpinned = MEDIUM. Unnecessary = LOW.

---

## Category 7: Developer Experience

**Primary reviewer**: Architecture

**Look for**:

| Pattern | Evidence required |
|---|---|
| Missing or wrong setup instructions (README, CONTRIBUTING) | The instruction + what actually happens when followed |
| Unclear error messages (codes without context, raw stack traces) | The error output + what the user needs to know instead |
| Inconsistent naming (mixed camelCase/snake_case in same layer) | Two+ examples from the same package/module |
| Missing type annotations on public interfaces | The function signature + the language's annotation convention |
| Complex build/run steps not scripted | The manual steps required + absence of script |
| Missing CLAUDE.md or stale project conventions | The convention + evidence it no longer matches code |

**Severity guide**: Setup instructions that fail = HIGH. Naming inconsistency = MEDIUM. Missing optional annotations = LOW.

---

## Category 8: Documentation

**Primary reviewer**: Business Logic

**Look for**:

| Pattern | Evidence required |
|---|---|
| Stale docstring (describes old behavior) | The docstring + the current code that contradicts it |
| Missing docstring on public API | The function/class + its public visibility |
| README that does not match current project state | The README claim + the actual state |
| Commented-out code without explanation | `file:line` + absence of explanatory comment |
| Architecture doc that references deleted components | The reference + the missing component |

**Severity guide**: Actively misleading docs = HIGH. Missing docs on public API = MEDIUM. Missing docs on internal code = LOW.

---

## Mapping to score-component.py

Grade bands come from `score-component.py` (A 90-100, B 75-89, C 60-74, D 40-59, F 0-39):

| Grade | Score | Severity in report | Action |
|---|---|---|---|
| F | 0-39 | CRITICAL | Fix immediately; structural deficiency |
| D | 40-59 | CRITICAL | Fix immediately; structural deficiency |
| C | 60-74 | HIGH | Fix this sprint |
| B | 75-89 | (informational) | Note in health scores table |
| A | 90-100 | (informational) | Note in health scores table |

Wave agents use this mapping to avoid double-counting: if `score-component.py` already flagged a structural issue (missing error handling section, broken frontmatter), the reviewer confirms and cites the score rather than writing a new finding from scratch.

---

## Reviewer Role Cross-Reference

When review runs via `parallel-code-review`, its three roles map to audit categories:

| Reviewer | Primary categories | Secondary (cross-check) |
|---|---|---|
| Security | Security, Dependencies | Correctness (injection paths) |
| Business Logic | Correctness, Test Coverage, Documentation | Tech Debt (stale TODOs) |
| Architecture | Performance, Tech Debt, Developer Experience | Test Coverage (structural gaps) |

When review runs via comprehensive-review waves (the full-repo-review path), the orchestrator maps categories to wave lenses:

| Wave lens | Categories |
|---|---|
| security | Security, Dependencies |
| business-logic, silent-failures | Correctness |
| test-analyzer | Test Coverage |
| quality, type-design, language-specialist | Tech Debt |
| comment-analyzer, docs-validator | Documentation |
| newcomer, docs-validator | Developer Experience |
| architecture reviewer | Performance, Tech Debt |
| Wave 2 deep-dive agents | Re-check the same categories as their Wave 1 counterpart lens, at depth |

Each reviewer covers its primary categories exhaustively and its secondary categories opportunistically. This division prevents both gaps and redundant deep-dives.
