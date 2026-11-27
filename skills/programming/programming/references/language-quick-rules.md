# Language Quick Rules: Go, Kotlin, PHP, Swift, and TypeScript

Concise per-language rules and workflows extracted from `programming/SKILL.md`. Load the section matching your active language alongside its deep reference.

## Go

### Style Precedence
1. Target repository's explicit rules and compatibility constraints.
2. Google Go Style Guide canonical rules.
3. Google Go Style Decisions normative guidance.
4. Google Go Style Best Practices non-canonical recommendations.
5. Task-specific deep references under `references/go/`.

Prefer local consistency where the Google guide allows judgment; keep existing code style intact without cause.

### Workflow
Classify the task, load the matching reference, and follow its gates:
- **Testing:** table-driven tests with subtests, test helpers, mock injection (`go test ./...`; `references/go/testing.md`).
- **Concurrency:** goroutine lifecycle, sync primitives, context propagation (`go test -race`; `references/go/concurrency.md`).
- **Error handling:** `%w` wrapping, sentinels, `errors.Is`/`errors.As` (`references/go/error-handling.md`).
- **Code review:** `references/go/code-review.md`; **SAPCC repos:** `references/go/sapcc-conventions.md`; **Quality gate:** `make check` + `references/go/quality-gate.md`.

### Expert Review Patterns
- Keep implementation types unexported; export interfaces and constructors.
- Remove only the returned batch in `commit()` to prevent batch+callback races.
- Extract helpers when reused or hiding complex details.
- Place `defer f.Close()` after the error check.
- Use Go 1.22+ per-iteration loop variables directly (omit legacy `i := i`).
- Pre-initialize Prometheus counters with `.Add(0)` for known label combinations.
- Share test bodies across interface implementations via `testWithEachBackingStore()`.

### Scripts
`scripts/gen-table-test.sh`, `scripts/bench-compare.sh`, `scripts/check-errors.sh`, `scripts/check-interface-compliance.sh`, `scripts/check-sapcc-*.sh`, `scripts/quality_checker.py`, `scripts/validate.py`, `scripts/sync-google-style-guide.py`.

---

## Kotlin

### Core Rules
1. Enforce structured concurrency: every coroutine runs inside a parent scope defining its lifetime (pass scopes from the framework rather than `GlobalScope`).
2. Inject `CoroutineDispatcher` for deterministic testing and threading control.
3. Catch specific exception types and always rethrow `CancellationException`.
4. Prefer `Flow` over `Channel`; reserve `Channel` for producer-consumer and inter-coroutine communication.
5. Use `supervisorScope` for independent sibling tasks that tolerate partial failures.

### Stream Selection
- `Flow` (cold, no replay): async sequences, API pagination, transform chains (`filter`/`map`/`flatMapConcat`/`collect`).
- `StateFlow` (hot, replays latest): UI state with initial value; conflates duplicates.
- `SharedFlow` (hot, configurable replay): one-shot events (navigation, toasts, errors).
- `Channel` (hot, no replay): producer-consumer (`produce`) and fan-in/fan-out pipelines.

Classify into concurrency, Flow, Channels, or testing, load the matching deep reference under `references/kotlin/`, and apply its templates.

---

## PHP

- Start every PHP file with `declare(strict_types=1)` and follow PSR-12 (4-space indent, one class per file, explicit member visibility, K&R braces for control structures, Allman for classes/methods).
- **Laravel:** Eloquent scopes (`scopeActive`), Collection pipelines over raw loops, Service Container interface binding and contextual `when()->needs()->give()`.
- **Symfony:** `#[Autowire]` constructor injection and `#[AsEventListener]` over XML config.
- **Verify:** `./vendor/bin/phpunit` (coverage: `XDEBUG_MODE=coverage ./vendor/bin/phpunit --coverage-text --coverage-min=80`).

---

## Swift

- **Concurrency:** Prefer `TaskGroup` over unstructured `Task {}`; conform shared types to `Sendable` with `-strict-concurrency=complete`; isolate mutable state in `actor`s; restrict `@MainActor` to UI and mark `let`-only readers `nonisolated`; cancel every stored `Task`.
- **Testing:** Arrange-Act-Assert, one concept per test, descriptive names (`testFetchUser_withExpiredToken_throwsAuthError`); prefer Swift Testing (`@Test`, `#expect`, parameterized `arguments:`) on Swift 5.9+, XCTest for UI/legacy targets.
- **Verify:** `swift test --enable-code-coverage` and `swift build` with strict concurrency enabled.

---

## TypeScript (Read-Only Type Check)

Keep check-only runs strictly read-only (leave code, config, and dependencies untouched):
1. Locate `tsconfig.json` (in monorepos, target affected packages or aggregate check; report and stop if absent).
2. Confirm local TypeScript installation (avoid implicit npx downloads).
3. Run `npx tsc --noEmit 2>&1` (or `--project path/to/tsconfig.json`; use `npm exec tsc -- --noEmit` if `npx` is absent). Capture exit code and group diagnostics with `file:line:column`, `TS####`, and message.
4. Keep `--skipLibCheck` and `--strict` matched to config/request; omit `--incremental` on read-only checks to avoid writing build-info files. Full JS/TS order: lint -> type-check -> tests.
