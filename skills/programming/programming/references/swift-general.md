---
description: "General Swift development for iOS, macOS, watchOS, tvOS, visionOS, and server-side Swift: Swift 6 strict concurrency, Apple API Design Guidelines, App Store security, build/test gates."
type: reference
---

# General Swift Development

Rules for idiomatic, production-ready Swift following the Swift 6 concurrency
model, Apple API Design Guidelines, and App Store security requirements. Use for
full Swift development. For concurrency patterns or test writing in isolation,
the `swift/` references are enough (see the Swift table in `SKILL.md`).

## Expertise areas

- **Swift 6 strict concurrency:** actor isolation, `Sendable` conformance,
  structured concurrency (`async let`, `TaskGroup`), typed throws, data-race
  avoidance.
- **Protocol-oriented design:** small focused protocols, protocol extensions for
  shared defaults, associated types, DI via protocol with a default parameter.
- **Apple platforms:** SwiftUI, UIKit, AppKit, Combine, SwiftData, CoreData
  across iOS, macOS, watchOS, tvOS, visionOS.
- **Server-side Swift:** Vapor routing/middleware, async-await and
  EventLoopFuture interop, no UIKit on server targets.
- **Toolchain:** SwiftFormat, SwiftLint, `swift build` type-checking, Swift
  Package Manager.
- **Testing:** Swift Testing (`import Testing`, `@Test`, `#expect`),
  parameterized tests with `arguments:`, protocol-based mock injection,
  fresh-instance isolation.
- **Security:** Keychain Services, App Transport Security, certificate pinning,
  input validation for API, deep link, and pasteboard data.
- **Immutability:** `let` over `var`, `struct` over `class`, value types for
  DTOs and models.

## Environment assumptions

| Assumption | Value |
|------------|-------|
| Swift version | 6.0+ (strict concurrency checking enabled) |
| Xcode | 16+ (`swift-format` available alongside SwiftFormat) |
| Target platforms | iOS 17+, macOS 14+, watchOS 10+, tvOS 17+, visionOS 1+ (check Package.swift / project settings) |
| Testing framework | Swift Testing for new tests; XCTest for existing suites that have not migrated |
| Concurrency model | `async`/`await` + actors; Combine only for existing code unless Combine is a stated requirement |
| Server-side | Vapor 4+ with async-await; Hummingbird 2+ |

## Hard rules

- **Read the file before editing.** Never edit a file you have not read in this
  session.
- **Run tests and build before reporting completion:** `swift test` and
  `swift build`. Show the actual output, not "tests pass".
- **Feature branch, never main.** If on main, create a branch before committing.
- **Verify dependencies exist before importing them.** Check `Package.swift`
  first.
- **Format every edited `.swift` file:** `swiftformat .` or
  `swift-format format --recursive .`, then `swiftlint lint`, then
  `swift build` to type-check.
- **`let` by default;** `var` only when the compiler requires it.
- **`struct` by default;** `class` only when identity or reference semantics
  are genuinely needed.
- **No `print()` in production code** (test files excepted). Use
  `os.Logger(subsystem: Bundle.main.bundleIdentifier ?? "app", category: "subsystem")`.
  After an edit, grep the non-test file for `print(`.
- **No credentials in UserDefaults.** After an edit, check any `UserDefaults`
  call whose key contains `token`, `password`, `key`, `secret`, `credential`,
  or `auth`; move it to Keychain Services.
- **Safe unwrapping on external data.** `guard let` / `if let` for all API,
  deep link, and pasteboard data. `URL(string:)!`, `data!`, and other force
  unwraps are hard boundaries.
- **Version-aware code.** Detect the minimum deployment target from project
  settings and use only APIs available there.

## Defaults (on unless disabled)

- Run `swift test --enable-code-coverage` after changes; show full output.
- Run `swiftlint lint` after edits; fix all errors, review warnings.
- `///` doc comments on all public functions, types, and properties.

## Off unless requested

- Aggressive refactoring beyond the immediate task.
- Migrating XCTest suites to Swift Testing.
- New SPM dependencies.
- Instruments profiling and micro-optimizations before a bottleneck is confirmed.

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| SwiftUI or UIKit screen layout, hierarchy, spacing, type, color, states (load first; Apple Human Interface Guidelines win over web defaults) | [ui-design-judgment.md](../../../shared-patterns/ui-design-judgment.md), then `ui-design-recipes.md` and `ui-design-examples.md` in the same folder | Design defaults with reasons and the look-then-fix loop |
| immutability, actors, Sendable, async let, typed throws, protocol-oriented design, state modeling | [swift-patterns.md](swift-general/swift-patterns.md) | Core Swift idiom and concurrency patterns |
| secret management, xcconfig, input validation, Swift Testing vs XCTest, fresh-instance isolation, llvm-cov, failure-mode detection | [swift-security-testing.md](swift-general/swift-security-testing.md) | Secret and input rules, test methodology, failure-mode detection table |
| security, auth, Keychain, ATS, WebView, biometrics, certificate pinning, deep links, or any vulnerability-related code | [swift-security.md](swift-general/swift-security.md) | Secure implementation patterns for iOS, macOS, and server-side, with detection commands |
| TaskGroup, AsyncSequence, AsyncStream, cancellation | [task-patterns.md](swift/task-patterns.md) | Task deep reference |
| Blocking MainActor, leaking tasks, actor reentrancy | [preferred-patterns.md](swift/preferred-patterns.md) | Concurrency pitfalls |
| XCTest, Swift Testing, async tests, UI tests | [swift-testing.md](swift/swift-testing.md) | Testing deep reference |

## Related skills

- `workflow` for multi-phase tasks, feature builds, and planning.
- `testing` for TDD, E2E, and verification.
- `review` for code review.
