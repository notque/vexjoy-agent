# Kotlin Security & Testing Reference

Security rules, pattern corrections, and test tooling for Kotlin feature work.
Full secure-implementation patterns (Exposed and Room parameterized queries,
Ktor JWT with algorithm pinning, Keystore, WebView, content providers) live in
[kotlin-security.md](kotlin-security.md). Kotest styles, MockK basics, and
coroutine testing live in [../kotlin/kotlin-testing.md](../kotlin/kotlin-testing.md).

## Security

### Secrets via Environment Variables

```kotlin
// BAD -- hardcoded secret
val jwtSecret = "super-secret-key-do-not-share"

// GOOD -- environment variable with fail-fast on missing
val jwtSecret: String = System.getenv("JWT_SECRET")
    ?: throw IllegalStateException("JWT_SECRET environment variable must be set")

// GOOD -- using requireNotNull for cleaner message
val dbPassword: String = requireNotNull(System.getenv("DB_PASSWORD")) {
    "DB_PASSWORD environment variable must be set before starting the application"
}
```

### Parameterized Queries and JWT

- SQL: Exposed DSL or explicit `?` parameters only, never string interpolation.
  Examples and detection commands: kotlin-security.md, "Use Parameterized
  Queries With Exposed and Room".
- Ktor JWT: read secret, issuer, and audience from the environment with
  `requireNotNull`, and in `validate` require audience, issuer, AND subject.
  Example: kotlin-security.md, "Configure Ktor JWT Auth With Algorithm Pinning".

### Null Safety as a Security Property

`!!` on externally-sourced data (HTTP params, DB results, env vars) is a security vulnerability — converts compile-time safety into runtime NPE triggerable by adversarial input. Treat as critical defect.

---

## Pattern Corrections

| Pattern | Why It's Wrong | Detection | Fix |
|---------|---------------|-----------|-----|
| `!!` operator | Bypasses null safety; runtime NPE | `grep -rn '!!' src/` | Use `?.`, `?:`, `require()`, `checkNotNull()` |
| Nested scope functions | Unreadable, hard to debug; `this` ambiguity | Code review | Extract intermediate `val`s; use single scope function per expression |
| `var` when `val` works | Accidental mutation, harder to reason about | detekt: `VarCouldBeVal` | Declare `val`; use `copy()` for updates |
| `MutableList`/`MutableMap` in signatures | Exposes mutation capability beyond intent | Code review | Use `List`/`Map`; return immutable copy if needed |
| `GlobalScope.launch` | Uncancellable; leaks coroutines at shutdown | `grep -rn 'GlobalScope' src/` | Use `viewModelScope`, `lifecycleScope`, or explicit scope |
| Blocking call without `Dispatchers.IO` | Starves coroutine thread pool; hangs | Code review | Wrap in `withContext(Dispatchers.IO) { ... }` |
| Platform type passthrough | Silently nullable; NPE at arbitrary call site | Code review; detekt | Annotate at Java boundary or guard with `?:` |
| String interpolation in SQL | SQL injection | grep for `exec(` with string interpolation | Use Exposed DSL or explicit `?` parameters |
| Hardcoded secrets | Credential leak | grep for `password =` string literals | `System.getenv()` with `requireNotNull()` |
| `else` on sealed `when` | Hides missing cases for new subtypes | Code review | Remove `else`; let compiler enforce exhaustiveness |
| Java-style getters/setters | Verbose; ignores Kotlin property syntax | Code review | Use Kotlin properties directly |

---

## Testing

### Kotest Styles

Choose a style per context (StringSpec for simple flat tests, FunSpec for
grouping related tests, BehaviorSpec for Given/When/Then scenarios) and keep it
consistent within a module. Examples: kotlin-testing.md, "Kotest Styles".

### MockK Extras

Beyond `every`/`verify`/`slot`/`coEvery` (see kotlin-testing.md, "MockK"):

```kotlin
// Stub a miss as well as a hit
every { repo.findById(99L) } returns null

// After verifying, assert no other calls happened
verify(exactly = 1) { repo.save(any()) }
confirmVerified(repo)

// Suspend functions -- coVerify pairs with coEvery
coVerify { repo.findByIdSuspend(1L) }
```

### Kover Coverage

```bash
# Generate HTML report
./gradlew koverHtmlReport

# Verify minimum coverage thresholds (configured in build.gradle.kts)
./gradlew koverVerify

# Run tests with coverage
./gradlew test koverHtmlReport
```

Configure coverage thresholds in `build.gradle.kts`:

```kotlin
koverReport {
    verify {
        rule {
            bound {
                minValue = 80
                metric = MetricType.LINE
                aggregation = AggregationType.COVERED_PERCENTAGE
            }
        }
    }
}
```
