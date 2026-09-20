---
name: programming
description: "Language-specific patterns and tooling: Go, Kotlin, PHP, Swift, TypeScript."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
routing:
  force_route: true
  not_for: "Python (agents handle directly), general debugging (use debugging). When a dedicated language skill exists (php, swift, kotlin), prefer it over this umbrella"
  triggers:
    # Go
    - .go
    - go test
    - "*_test.go"
    - goroutine
    - sync.Mutex
    - context.Context
    - Go code review
    - Go lint
    - sapcc
    - make check
    # Kotlin
    - "kotlin coroutines"
    - "kotlin Flow"
    - "suspend function"
    - "kotlin testing"
    - kotest
    # PHP
    - "php quality"
    - "php code review"
    - "PSR standards"
    - phpstan
    - phpunit
    # Swift
    - "swift concurrency"
    - "swift async await"
    - "Swift Actor"
    - XCTest
    # TypeScript
    - "TypeScript check"
    - "tsc noEmit"
    - "tsc errors"
  category: language
  pairs_with:
    - golang-general-engineer
    - kotlin-general-engineer
    - php-general-engineer
    - swift-general-engineer
    - typescript-frontend-engineer
---

# Programming

Language-specific patterns and tooling for Go, Kotlin, PHP, Swift, and
TypeScript. Identify the language, load matching deep references, follow the
language section.

## Language Routing

| Language | Agent | Section |
|----------|-------|---------|
| Go | golang-general-engineer | Go |
| Kotlin | kotlin-general-engineer | Kotlin |
| PHP | php-general-engineer | PHP |
| Swift | swift-general-engineer | Swift |
| TypeScript | typescript-frontend-engineer | TypeScript |

If the request spans multiple languages, apply each relevant section.

---

## Go

### Style Precedence

1. Target repository's explicit rules and compatibility constraints.
2. Google Go Style Guide canonical rules.
3. Google Go Style Decisions normative guidance.
4. Google Go Style Best Practices non-canonical recommendations.
5. Task-specific deep references below.

Prefer local consistency only where the Google guide allows judgment. Do not
restyle existing code without cause.

### Workflow

1. Classify the task: testing, concurrency, error handling, code review, SAPCC conventions, or quality gate.
2. Load the matching deep reference.
3. Follow the reference's phases, gates, and completion criteria.

For **testing**: table-driven tests with subtests, test helpers, mock injection. Run `go test ./...`. Load `references/go/testing.md`.
For **concurrency**: goroutine lifecycle, sync primitives, context propagation, race detection. Run `go test -race`. Load `references/go/concurrency.md`.
For **error handling**: wrapping with `%w`, sentinel errors, `errors.Is`/`errors.As`, custom error types. Load `references/go/error-handling.md`.
For **code review**: review checklist, common comments, interface compliance. Load `references/go/code-review.md`.
For **SAPCC repos**: org conventions -- go-bits patterns, auth ordering, JSON strictness, endpoint identification. Load `references/go/sapcc-conventions.md`.
For **quality gate**: run `make check` or equivalent. Load `references/go/quality-gate.md`.

### Expert Review Patterns

Beyond linting -- patterns from real code reviews that automated tools miss:

- **Type export design**: keep implementation types unexported; export only interfaces and constructors.
- **Batch+callback races**: `commit()` should remove only the specific batch returned, not all items.
- **Function extraction**: extract only if reused elsewhere or hides complex details.
- **Defer timing**: place `defer f.Close()` after the error check, not before.
- **Go 1.22+ loop variables**: remove `i := i` reassignment and closure parameter passing -- each iteration has its own variable since 1.22.
- **Prometheus metrics**: pre-initialize counters with `.Add(0)` for all known label combinations.
- **Test dedup**: use `testWithEachBackingStore()` pattern to share test bodies across interface implementations.

### Scripts

| Task | Script |
|------|--------|
| Generate table test | `scripts/gen-table-test.sh` |
| Benchmark compare | `scripts/bench-compare.sh` |
| Check errors | `scripts/check-errors.sh` |
| Interface compliance | `scripts/check-interface-compliance.sh` |
| SAPCC checks | `scripts/check-sapcc-*.sh` |
| Quality checker | `scripts/quality_checker.py`, `scripts/validate.py` |
| Google style sync | `scripts/sync-google-style-guide.py` |

---

## Kotlin

### Core Rules

1. **Structured concurrency is non-negotiable.** Every coroutine must have a parent scope that defines its lifetime.
2. **Inject dispatchers.** Accept `CoroutineDispatcher` as a parameter so callers and tests control threading.
3. **Always rethrow CancellationException.** Catch specific exception types, not broad `Exception`.
4. **Prefer Flow over Channel.** Flow is cold, composable, handles backpressure. Use Channels only for producer-consumer and inter-coroutine communication.
5. **Use supervisorScope for partial failure tolerance.** Independent tasks that should not cancel each other.
6. **No GlobalScope.** Pass a scope from the application framework.

### Stream Type Selection

| Type | Temperature | Replay | Use Case |
|------|-------------|--------|----------|
| `Flow` | Cold | None | Async sequences, API pagination, transform chains |
| `StateFlow` | Hot | Latest (1) | UI state with current value; conflates duplicates |
| `SharedFlow` | Hot | Configurable | One-shot events: navigation, toasts, errors |
| `Channel` | Hot | None | Producer-consumer, fan-in/fan-out inter-coroutine communication |

**Flow**: cold -- each collector gets its own execution. Chain with `filter`, `map`, `flatMapConcat`. Terminate with `collect`.
**StateFlow**: requires initial value, always replays latest to new collectors. Use for UI state.
**SharedFlow**: configurable replay, emits all values (no conflation). Use for event streams.
**Channel**: hot communication primitive. Use `produce` builder for producer-consumer. Fan-out: multiple coroutines consuming one channel. Fan-in: multiple producers writing to one channel.

### Workflow

1. Classify into concurrency, Flow, Channels, or testing.
2. Load matching deep reference.
3. Apply patterns from the reference as templates.

---

## PHP

### Core Rules

- Every PHP file must begin with `declare(strict_types=1)`.
- Follow PSR-12: 4-space indentation, no trailing whitespace, one class per file, visibility on all members, opening braces same line for control structures, next line for classes and methods.

### Framework Idioms

**Laravel**: Eloquent scopes for reusable query constraints (`scopeActive`). Collection methods over raw loops (`collect()->filter()->map()->sort()`). Service Container for interface-to-implementation binding. Contextual binding with `when()->needs()->give()`.

**Symfony**: DI with `#[Autowire]` attributes for constructor injection. `#[AsEventListener]` for event dispatch. Rely on autowiring over XML config.

### Workflow

1. **Assess.** Classify: code review, type system, framework patterns, tooling setup, or test writing. Load matching deep reference.
2. **Execute.** For quality reviews: check strict_types, PSR-12, modern features, framework idioms, tooling. For testing: PHPUnit `TestCase` with `test` prefix, `@dataProvider` for table-driven, `createStub()` for returns, `createMock()` for interactions, `parent::setUp()` first in every setUp.
3. **Verify.** Run `./vendor/bin/phpunit`. For coverage: `XDEBUG_MODE=coverage ./vendor/bin/phpunit --coverage-text --coverage-min=80`.

---

## Swift

### Core Rules

**Concurrency:**
- Prefer structured concurrency: `TaskGroup` over loose `Task { }`.
- Mark types `Sendable`. Enable `-strict-concurrency=complete`.
- Use actors for shared mutable state instead of manual locks. All access from outside is async.
- `@MainActor` for UI layer only. Use `nonisolated` for methods that only read `let` properties.
- Cancel what you create: every stored `Task` needs a cancellation path.

**Testing:**
- One assertion per concept. Arrange-Act-Assert structure.
- Name tests descriptively: `testFetchUser_withExpiredToken_throwsAuthError`.
- Prefer Swift Testing (`@Test`, `#expect`) for Swift 5.9+. Fall back to XCTest for older targets or UI tests.
- Parameterized tests with `arguments:`. Protocol-based mock injection.

### Workflow

1. **Assess.** Classify: concurrency patterns, concurrency mistakes, test writing, or full concurrency review. Load matching deep reference.
2. **Execute.** For concurrency: verify structured concurrency, check Sendable conformance, validate actor isolation boundaries, confirm cancellation paths. For testing: Swift Testing for new code on 5.9+, XCTest for UI tests.
3. **Verify.** Run `swift test --enable-code-coverage` and `swift build`. Confirm strict concurrency checking passes.

---

## TypeScript

Read-only type validation. Do not fix code, change configuration, or install
dependencies for a check-only request.

### Run

1. Locate `tsconfig.json` (check `src/`, `app/`, `packages/`). In a monorepo, use the affected package or the repo's aggregate check. If no config exists, report and stop.
2. Confirm TypeScript is installed locally. Do not allow implicit npx download.
3. Run `npx tsc --noEmit 2>&1` (or `--project path/to/tsconfig.json`). Capture exit code. Zero = pass; nonzero = type errors or tool failure (report which).
4. Report status and error count. Group diagnostics by file and line, retaining `file:line:column`, `TS####`, and the message.

### Recovery

- **TypeScript missing:** suggest `npm install typescript --save-dev`.
- **npx missing:** use `npm exec tsc -- --noEmit`.
- **Multiple configs:** list checked and omitted packages. A single-package pass is not a whole-repository pass.
- **`--skipLibCheck`:** use only when configured or requested.
- **`--strict`:** enable only when configured or requested.
- **`--incremental`:** avoid for read-only checks (writes build-info cache).

For the full JS/TS check sequence: lint first, type-check next, then run tests.

---

## Deep References

Load only the references matching the task. Multiple may apply (e.g., a concurrency
PR review loads both code-review and concurrency references).

### Go

| Signal | Reference |
|--------|-----------|
| Tests, table-driven, helpers, mocks | `references/go/testing.md` + sub-refs in `testing/` |
| Goroutines, channels, sync, race conditions | `references/go/concurrency.md` + `concurrency/concurrency-patterns.md` |
| Error wrapping, sentinels, errors.Is/As | `references/go/error-handling.md` + `error-handling/patterns.md` |
| Code smells, bad patterns | `references/go/preferred-patterns.md` + `preferred-patterns/code-examples.md` |
| Code review process | `references/go/code-review.md` + `code-review/common-review-comments.md` |
| SAPCC repos, go-bits | `references/go/sapcc-conventions.md` + sub-refs in `sapcc-conventions/` |
| make check, linting | `references/go/quality-gate.md` + sub-refs in `quality-gate/` |
| Google style decisions | `references/go/google-style-guide/` (pinned upstream) |

### Kotlin

| Signal | Reference |
|--------|-----------|
| Scopes, cancellation, dispatchers, exception handling | `references/kotlin/concurrency-patterns.md` |
| JUnit 5, Kotest, MockK, runTest | `references/kotlin/kotlin-testing.md` |

### PHP

| Signal | Reference |
|--------|-----------|
| Union/intersection types, enums, readonly, match | `references/php/modern-php-features.md` |
| PHP-CS-Fixer, PHPStan, Psalm, Rector | `references/php/quality-tools.md` |
| PHPUnit, data providers, mocks, stubs | `references/php/testing-patterns.md` |

### Swift

| Signal | Reference |
|--------|-----------|
| TaskGroup, AsyncSequence, AsyncStream, cancellation | `references/swift/task-patterns.md` |
| XCTest, Swift Testing, async tests, UI tests | `references/swift/swift-testing.md` |
