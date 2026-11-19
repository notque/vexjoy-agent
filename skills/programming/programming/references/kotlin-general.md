---
description: "General Kotlin development on JVM, Android, and Multiplatform: features, coroutines, debugging, code quality. Kotlin 1.9+/2.0 rules, platform detection, gradle gates."
type: reference
---

# General Kotlin Development

Rules for idiomatic, production-ready Kotlin on JVM and Android, following
Kotlin 1.9+/2.0 conventions. Use for writing and debugging Kotlin features.
For coroutine or Flow patterns in isolation, or Kotlin test writing, the
`kotlin/` references are enough (see the Kotlin table in `SKILL.md`).

Not for: Go goroutine work (load `golang-general.md`).

## Expertise areas

- **Language:** Kotlin 2.0 features, null safety, extension functions, scope
  functions, sealed classes, data classes, value classes, context receivers,
  explicit API mode.
- **Coroutines and Flow:** structured concurrency, coroutine builders,
  dispatcher selection, Flow operators, StateFlow, SharedFlow, `runTest`.
- **Android:** ViewModel, StateFlow/SharedFlow for UI state, Room with
  coroutines, Hilt/Koin DI, Jetpack Compose.
- **Backend:** Ktor application structure, routing DSL, content negotiation,
  Ktor Auth with JWT, Exposed ORM DSL, Koin DI.
- **Build and tooling:** Gradle Kotlin DSL (`build.gradle.kts`), version
  catalogs, detekt, ktfmt/ktlint, Kover.
- **Testing:** Kotest (StringSpec/FunSpec/BehaviorSpec), MockK, `runTest` from
  `kotlinx-coroutines-test`, Kotest property-based testing, Kover reports.
- **Multiplatform:** common code, `expect`/`actual`, shared business logic for
  JVM + Android.

| Domain | Key technologies |
|--------|-----------------|
| Null safety | `?.`, `?:`, `require()`, `checkNotNull()`, `let`, platform type boundaries |
| Coroutines | `launch`, `async`, `withContext`, `Flow`, `StateFlow`, `Dispatchers.IO/Default/Main` |
| Type hierarchies | Sealed classes/interfaces, data classes, value classes, enums |
| Backend | Ktor routing DSL, Ktor Auth JWT, Exposed DSL, Koin modules |
| Android | ViewModel, StateFlow, Room, Jetpack Compose, Hilt/Koin |
| Testing | Kotest, MockK, `runTest`, Kover, property-based testing |
| Tooling | Gradle Kotlin DSL, detekt, ktfmt, ktlint, version catalogs |

## Baseline practices

- `val` over `var`; `var` only when mutation is genuinely required.
- Immutable collection types (`List`, `Map`, `Set`) in signatures; return
  `listOf()`, `mapOf()`, `setOf()`.
- `data class` with `copy()` for immutable updates instead of mutating fields.
- Expression bodies for single-expression functions
  (`fun greet(name: String) = "Hello, $name"`).
- Trailing commas in multiline declarations (Kotlin 1.4+).
- Explicit nullability annotations at Java interop boundaries.
- Scope functions: `let` for nullable transforms, `apply` for object
  initialization, `also` for side effects, `run` for scoped computation. Keep
  them flat (one per expression).
- `?.`, `?:`, `require()`, or `checkNotNull()` instead of any `!!`.
- Sealed classes/interfaces for exhaustive hierarchies; list every case in
  `when` explicitly.

## Review priorities

1. Null safety: no `!!`, proper Java interop boundary handling
2. Coroutines: structured concurrency, no blocking on non-IO dispatchers
3. Immutability: `val` over `var`, immutable collections
4. Exhaustive type handling: sealed-class `when` without `else`
5. Security: parameterized queries, secrets via environment, JWT validation
6. Testing: `runTest`, MockK, Kotest
7. Clarity: scope function use, expression bodies, readable flow chains

## Platform detection

| Platform | Primary stack | Build |
|----------|---------------|-------|
| JVM backend | Ktor + Koin + Exposed | `build.gradle.kts` with version catalog |
| Android | ViewModel + StateFlow + Room + Compose | Android Gradle Plugin, `build.gradle.kts` |
| Multiplatform | Common + `expect`/`actual` per target | KMP Gradle plugin |

Detect the platform from context. When unclear, ask before assuming Android vs.
backend.

**Version detection:** read `build.gradle.kts` or `settings.gradle.kts` for the
`kotlin()` plugin version before generating code. Use only features available
in that version.

## Hard rules

- **Read the file before editing.** Never edit a file you have not read in this
  session.
- **Run tests, build, and lint before reporting completion:** `./gradlew test`,
  `./gradlew detekt`, `./gradlew compileKotlin`. Show their actual output, not
  "tests pass".
- **Feature branch, never main.** If on main, create a branch before committing.
- **Verify dependencies exist before importing them.** Check `build.gradle.kts`
  or the version catalog first.
- **Replace every `!!`.** Non-negotiable: use `?.`, `?:`, `require()`, or
  `checkNotNull()`. After editing a `.kt` file, run `grep -n '!!' <file>` and fix
  every hit. If the codebase uses `!!` widely, report it as a systemic issue.
- **Explicit nullability at Java boundaries.** Guard every platform type.
- **Immutable-first collections** in parameters and return types unless
  mutation is part of the contract.
- **`val` by default.**
- **Parameterized queries only:** Exposed DSL or `?` placeholders for all
  user-controlled values in raw SQL.
- **Secrets via environment:** `System.getenv()` with an explicit
  `IllegalStateException` (or `requireNotNull`) when missing.
- **Detekt before completion:** run `./gradlew detekt` and resolve warnings.
- **Version-aware code** per the detected Kotlin version.

## Defaults (on unless disabled)

- Show commands and output rather than describing them; concise summaries; no
  self-congratulation.
- Run `./gradlew test` (or the Kotest runner) after changes; show full output.
- Run `./gradlew detekt` after changes.
- Run `./gradlew compileKotlin` after edits (faster than a full build). If it
  reports `error:`, review the output before proceeding.
- Format edited `.kt`/`.kts` files with `ktfmt` or `ktlint --format`.

## Off unless requested

- Aggressive refactoring beyond the immediate task.
- New Gradle dependencies.
- Micro-optimizations (inline functions, reified generics) before profiling.

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| Jetpack Compose screen layout, hierarchy, spacing, type, color, states (load first; Material conventions win over web defaults) | [ui-design-judgment.md](../../../shared-patterns/ui-design-judgment.md), then `ui-design-recipes.md` and `ui-design-examples.md` in the same folder | Design defaults with reasons and the look-then-fix loop |
| null safety, `!!`, Java interop, viewModelScope, Ktor scope, StateFlow debounce, sealed classes, enums, data classes, Koin | [kotlin-patterns.md](kotlin-general/kotlin-patterns.md) | Null safety alternatives, coroutines/Flow (structured concurrency, dispatchers, StateFlow, `runTest`), sealed/enum/data classes, Koin DI |
| secrets via env, Ktor JWT claims, pattern corrections, detekt rule, confirmVerified, Kover coverage | [kotlin-security-testing.md](kotlin-general/kotlin-security-testing.md) | Secrets, null safety as a security property, pattern-corrections table, MockK extras, Kover |
| Security, auth, injection, deserialization, WebView, content provider, Keystore, or any vulnerability-related code | [kotlin-security.md](kotlin-general/kotlin-security.md) | Secure implementation patterns for Kotlin JVM and Android, with detection commands |
| Scopes, cancellation, dispatchers, exception handling | [concurrency-patterns.md](kotlin/concurrency-patterns.md) | Structured concurrency deep reference |
| JUnit 5, Kotest, MockK, runTest | [kotlin-testing.md](kotlin/kotlin-testing.md) | Kotlin testing deep reference |

## Related skills

- `workflow` for multi-phase tasks, feature builds, and planning.
- `testing` for TDD, E2E, and verification.
- `review` for code review.
