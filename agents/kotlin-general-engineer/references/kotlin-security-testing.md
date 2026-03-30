# Kotlin Security & Testing Reference

Deep reference for security patterns, pattern corrections, and testing methodology.

---

## Security

### Secrets via Environment Variables

Load secrets from environment variables; keep them out of committed config files.

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

### Exposed DSL -- Parameterized Queries Only

Use parameterized queries for all user-controlled values in database queries.

```kotlin
// BAD -- SQL injection via string interpolation
fun findByEmail(email: String): AppUser? {
    return transaction {
        exec("SELECT * FROM users WHERE email = '\$email'") { rs -> parseRow(rs) } // NEVER
    }
}

// GOOD -- Exposed DSL uses parameterized queries automatically
fun findByEmail(email: String): AppUser? = transaction {
    Users.select { Users.email eq email }
        .singleOrNull()
        ?.let { row -> Users.toAppUser(row) }
}

// GOOD -- if raw SQL is necessary, use explicit parameters
fun findByDomain(domain: String): List<AppUser> = transaction {
    exec("SELECT * FROM users WHERE email LIKE ?", listOf(stringParam("%@\$domain"))) { rs ->
        generateSequence { if (rs.next()) toAppUser(rs) else null }.toList()
    }
}
```

### Ktor JWT Authentication

```kotlin
fun Application.configureSecurity() {
    val secret = requireNotNull(System.getenv("JWT_SECRET")) { "JWT_SECRET must be set" }
    val issuer = requireNotNull(System.getenv("JWT_ISSUER")) { "JWT_ISSUER must be set" }
    val audience = requireNotNull(System.getenv("JWT_AUDIENCE")) { "JWT_AUDIENCE must be set" }

    authentication {
        jwt("auth-jwt") {
            realm = "MyApp"
            verifier(
                JWT.require(Algorithm.HMAC256(secret))
                    .withIssuer(issuer)
                    .withAudience(audience)
                    .build()
            )
            validate { credential ->
                // Validate audience, issuer, AND subject -- all three required
                if (credential.payload.audience.contains(audience) &&
                    credential.payload.issuer == issuer &&
                    credential.payload.subject != null
                ) {
                    JWTPrincipal(credential.payload)
                } else {
                    null // authentication fails
                }
            }
        }
    }
}
```

### Null Safety as a Security Property

The `!!` operator is not just a style violation -- it is a security vulnerability. It converts a compile-time null safety guarantee into a runtime `NullPointerException`, which can be triggered by adversarial input that causes a null to propagate from an external source. Treat any `!!` touching externally-sourced data (HTTP params, DB results, environment vars) as a critical defect.

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

Choose the style that fits the context and keep it consistent within a module:

```kotlin
// StringSpec -- simple, flat tests
class UserValidatorTest : StringSpec({
    "should reject email without @ symbol" {
        val validator = UserValidator()
        validator.validate("notanemail") shouldBe ValidationResult.Invalid("Invalid email format")
    }
})

// FunSpec -- grouping related tests
class OrderServiceTest : FunSpec({
    val mockRepo = mockk<OrderRepository>()
    val service = OrderService(mockRepo)

    test("create order persists to repository") {
        every { mockRepo.save(any()) } returns Unit
        service.createOrder(orderRequest)
        verify(exactly = 1) { mockRepo.save(any()) }
    }
})

// BehaviorSpec -- Given/When/Then for complex scenarios
class PaymentProcessorTest : BehaviorSpec({
    Given("a valid payment request") {
        val processor = PaymentProcessor(mockk())
        When("the card is authorized") {
            Then("the order status transitions to PAID") { }
        }
    }
})
```

### MockK

```kotlin
// Mock and stub
val repo = mockk<AccountRepository>()
every { repo.findById(1L) } returns AppUser(id = UserId(1L), name = "Alice", email = "alice@example.com")
every { repo.findById(99L) } returns null

// Capture arguments
val slot = slot<AppUser>()
every { repo.save(capture(slot)) } returns Unit
service.createUser("Bob")
assertEquals("Bob", slot.captured.name)

// Verify interactions
verify(exactly = 1) { repo.save(any()) }
confirmVerified(repo)

// Suspend functions -- use coEvery/coVerify for suspend functions
coEvery { repo.findByIdSuspend(1L) } returns AppUser(id = UserId(1L), name = "Alice", email = "alice@example.com")
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
