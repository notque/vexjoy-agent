---
name: programming
description: "Language rules, workflows, and tooling: Go, Python, Rust, Kotlin, Swift, PHP, TypeScript type checks and debugging, OpenStack Python, MCP local-docs servers, Node.js backend APIs."
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
  not_for: "go used as a verb (go ahead, go fix this); rust used as an adjective (rust-colored, rusty); C++ ownership patterns; WebAssembly-only tasks without Rust source; using existing MCP tools or servers (only building local-docs MCP servers); general debugging (use debugging); TypeScript components, state, build config, React Native, or Core Web Vitals (use frontend); SQLite and Peewee ORM (use data); writing documentation content (use writing). When a dedicated language skill exists (php, swift, kotlin), prefer it over this umbrella"
  triggers:
    # Highest signal first: the routing manifest shows only the first 5 triggers not already in the description
    - golang
    - pytest
    - cargo
    - oslo
    - "typescript debug"
    # Node.js backend APIs
    - node.js
    - nodejs
    - express
    - "express router"
    - "node api"
    - "node backend"
    - "rest api"
    - webhook
    # Go
    - .go
    - ".go files"
    - go test
    - "*_test.go"
    - "go mod"
    - gofmt
    - gopls
    - goroutine
    - channel
    - "go channel"
    - sync.Mutex
    - context.Context
    - Go code review
    - Go lint
    - sapcc
    - make check
    # Python
    - python
    - ".py files"
    - pip
    - "pip install"
    - asyncio
    - fastapi
    - django
    - flask
    # OpenStack
    - openstack
    - neutron
    - nova
    - cinder
    - tempest
    - oslo.config
    - oslo.messaging
    # Rust
    - rust
    - ".rs files"
    - "cargo fmt"
    - clippy
    - "borrow checker"
    - lifetime
    - "rust lifetime"
    - rust-analyzer
    - rustfmt
    # Kotlin
    - kotlin
    - coroutine
    - ktor
    - koin
    - "kotlin coroutines"
    - "kotlin Flow"
    - StateFlow
    - "suspend function"
    - "suspend fun"
    - "kotlin testing"
    - kotest
    - mockk
    - gradle-kts
    - detekt
    - ktlint
    - ktfmt
    - "android kotlin"
    - kotlin-multiplatform
    # PHP
    - php
    - laravel
    - symfony
    - composer
    - artisan
    - eloquent
    - blade
    - twig
    - pest
    - doctrine
    - php-cs-fixer
    - psalm
    - ".php files"
    - "php quality"
    - "php code review"
    - "PSR standards"
    - psr-12
    - phpstan
    - phpunit
    # Swift
    - swift
    - ios
    - macos
    - spm
    - swiftui
    - uikit
    - appkit
    - xcode
    - watchos
    - tvos
    - visionos
    - vapor
    - swift-package-manager
    - swiftlint
    - swiftformat
    - "swift concurrency"
    - "swift async await"
    - "Swift Actor"
    - "swift sendable"
    - swift-combine
    - swiftdata
    - coredata
    - XCTest
    # TypeScript
    - "TypeScript check"
    - "tsc noEmit"
    - "tsc errors"
    - "async bug"
    - "race condition"
    - "type error"
    - "production error"
    - "memory leak"
    # MCP local docs
    - MCP
    - "MCP docs server"
    - "docs server"
    - "documentation server"
    - hugo
    - "hugo docs"
  category: language
  pairs_with:
    - code-quality
    - testing
    - review
    - workflow
    - debugging
    - frontend
---
# Programming

Language rules, workflows, and tooling. Identify the language or domain, load
the matching reference, then follow it and any deep references it names. Every
listed reference replaces a retired specialist agent: load it in the main
thread. When dispatch pays (parallel fan-out, a long lane), send a
`general-purpose` worker told to load this skill and that reference.

## Language Routing

| Language or domain | Load first | Section |
|----------|-------|---------|
| Go | `references/golang-general.md` | Go |
| Python | `references/python-general.md` | — |
| OpenStack Python (Nova, Neutron, Cinder, Oslo) | `references/python-openstack.md` | — |
| Rust | `references/rust-general.md` | — |
| Kotlin | `references/kotlin-general.md` | Kotlin |
| PHP | `references/php-general.md` | PHP |
| Swift | `references/swift-general.md` | Swift |
| TypeScript type check (read-only) | — | TypeScript |
| TypeScript debugging (races, async, type errors, leaks, production errors) | `references/typescript-debugging.md` | — |
| TypeScript frontend architecture | `frontend` skill | — |
| MCP local-docs server (TypeScript or Go) | `references/mcp-local-docs.md` | — |
| Node.js backend APIs (Express, Next.js API routes, auth, webhooks, uploads, jobs) | `references/nodejs-api.md` | — |

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
| Any Go feature, debugging, review, or performance work; go.mod version, gopls | `references/golang-general.md` |
| Writing or editing Go code: doc comments, `wg.Go`, synctest, HTTP shutdown, uuid, pre-handoff checklist | `references/golang-general/go-modern-code.md` |
| Go 1.18–1.27 idioms, `requires go1.N`, errors.AsType, omitzero | `references/golang-general/go-version-idioms.md` |
| gopls MCP order, GOMODCACHE source check, stale binary, deadcode, render-time output | `references/golang-general/go-verification-workflow.md` |
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
| Any Kotlin feature or debugging work; Ktor, Koin, Android, KMP, detekt, gradle gates | `references/kotlin-general.md` |
| `!!`, null safety, Java interop, sealed classes, Koin DI, StateFlow debounce | `references/kotlin-general/kotlin-patterns.md` |
| Secrets via env, pattern corrections, MockK extras, Kover | `references/kotlin-general/kotlin-security-testing.md` |
| Security, auth, Jackson typing, WebView, content provider, Keystore, Ktor JWT | `references/kotlin-general/kotlin-security.md` |
| Scopes, cancellation, dispatchers, exception handling | `references/kotlin/concurrency-patterns.md` |
| JUnit 5, Kotest, MockK, runTest | `references/kotlin/kotlin-testing.md` |

### PHP

| Signal | Reference |
|--------|-----------|
| Any PHP feature or debugging work; Laravel, Symfony, Doctrine | `references/php-general.md` |
| Hard gates, detection greps, prepared statements, mass assignment, sessions, PHPUnit vs Pest, factories | `references/php-general/php-conventions.md` |
| Union/intersection types, enums, readonly, match | `references/php/modern-php-features.md` |
| PHP-CS-Fixer, Pint, PHPStan, Psalm tiers; post-edit checks | `references/php-general/php-behaviors.md` |
| PHPUnit, data providers, mocks, stubs | `references/php/testing-patterns.md` |

### Swift

| Signal | Reference |
|--------|-----------|
| Any Swift feature work; SwiftUI, UIKit, Vapor, SPM, SwiftLint, deployment targets | `references/swift-general.md` |
| Immutability, actors, Sendable, async let, typed throws, protocol-oriented design, state modeling | `references/swift-general/swift-patterns.md` |
| Secret management, input validation, Swift Testing vs XCTest, coverage, failure-mode table | `references/swift-general/swift-security-testing.md` |
| Keychain, ATS, WKWebView, biometrics, certificate pinning, deep links | `references/swift-general/swift-security.md` |
| Concurrency pitfalls: blocking MainActor, leaking tasks, actor reentrancy | `references/swift/preferred-patterns.md` |
| TaskGroup, AsyncSequence, AsyncStream, cancellation | `references/swift/task-patterns.md` |
| XCTest, Swift Testing, async tests, UI tests | `references/swift/swift-testing.md` |

### Python

| Signal | Reference |
|--------|-----------|
| Any Python feature, debugging, review, or performance work; requires-python, ruff, mypy, pytest gates | `references/python-general.md` |
| Writing or editing Python code, `pyproject.toml`, pre-handoff checklist | `references/python-general/python-modern-code.md` |
| Flask, Jinja, gunicorn, CSRF exempt, static 403, session cookies | `references/python-general/flask-jinja-webapp.md` |
| Host incidents, Peewee E712, venv/uv, stdin JSON CLIs, tarfile, yaml.load, pickle, SSRF | `references/python-general/python-local-gates.md` |

### OpenStack Python

| Signal | Reference |
|--------|-----------|
| Nova, Neutron, Cinder, Keystone, Tempest, tox gates, eventlet, i18n | `references/python-openstack.md` |
| oslo.config, oslo.log, oslo.messaging, oslo.db, oslo.policy | `references/python-openstack/oslo-patterns.md` + `openstack-patterns.md` |
| H-series hacking rules, `tox -e pep8`, import order | `references/python-openstack/hacking-rules.md` + `error-handling.md` |
| RPC version negotiation, `version_cap`, rolling upgrades | `references/python-openstack/rpc-versioning.md` |
| Failure modes, blockers, output template, scope | `references/python-openstack/preferred-patterns.md` + `output-format.md` |

### Rust

| Signal | Reference |
|--------|-----------|
| Any Rust feature, debugging, review, or performance work; edition, MSRV, rust-analyzer | `references/rust-general.md` |
| Writing or editing Rust code, pre-handoff checklist | `references/rust-general/rust-modern-code.md` |
| Rust 1.56–1.85 idioms, let-else, gen blocks, MSRV errors | `references/rust-general/rust-version-idioms.md` |
| cargo check/clippy order, crate source, stale binary, udeps/machete | `references/rust-general/rust-verification-workflow.md` |

### TypeScript debugging

| Signal | Reference |
|--------|-----------|
| Race conditions, async bugs, type errors, production errors, memory leaks | `references/typescript-debugging.md` |
| Race conditions, TS2322/TS2345, production runtime errors, source maps | `references/typescript-debugging/debugging-workflows.md` |
| Floating promises, waterfalls, git bisect, memory leaks, debugging checklist | `references/typescript-debugging/debugging-workflows-async-memory.md` |

### MCP local-docs servers

| Signal | Reference |
|--------|-----------|
| Building an MCP docs server, Hugo front matter, indexing budget, docs:// URIs | `references/mcp-local-docs.md` |
| Server scaffolding (TypeScript DocsServer class, Go DocsServer struct) | `references/mcp-local-docs/server-templates.md` |
| Tool registration, SDK patterns | `references/mcp-local-docs/mcp-patterns.md` |
| Front matter failures, URI issues, shortcode bugs, detection commands | `references/mcp-local-docs/mcp-preferred-patterns.md` |
| Async file I/O, EMFILE, slow indexing | `references/mcp-local-docs/typescript-async-patterns.md` |
