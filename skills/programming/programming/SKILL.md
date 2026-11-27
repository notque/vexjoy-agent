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
| Go | `references/golang-general.md` | `references/language-quick-rules.md#go` |
| Python | `references/python-general.md` | — |
| OpenStack Python (Nova, Neutron, Cinder, Oslo) | `references/python-openstack.md` | — |
| Rust | `references/rust-general.md` | — |
| Kotlin | `references/kotlin-general.md` | `references/language-quick-rules.md#kotlin` |
| PHP | `references/php-general.md` | `references/language-quick-rules.md#php` |
| Swift | `references/swift-general.md` | `references/language-quick-rules.md#swift` |
| TypeScript type check (read-only) | `references/language-quick-rules.md#typescript-read-only-type-check` | — |
| TypeScript debugging (races, async, type errors, leaks, production errors) | `references/typescript-debugging.md` | — |
| TypeScript frontend architecture | `frontend` skill | — |
| MCP local-docs server (TypeScript or Go) | `references/mcp-local-docs.md` | — |
| Node.js backend APIs (Express, Next.js API routes, auth, webhooks, uploads, jobs) | `references/nodejs-api.md` | — |

If the request spans multiple languages, apply each relevant reference. Per-language quick rules and checklists live in `references/language-quick-rules.md`.

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
