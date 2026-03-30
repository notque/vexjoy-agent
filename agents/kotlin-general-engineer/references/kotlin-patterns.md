# Kotlin Patterns Reference

Deep reference for null safety, coroutines/Flow, sealed classes/enums/data classes, and Koin DI.

---

## Null Safety

Kotlin's type system distinguishes nullable (`T?`) from non-nullable (`T`) at compile time. The `!!` operator circumvents this guarantee — replace all occurrences with safe alternatives in production code.

### Safe Alternatives to `!!`

| Situation | Instead of `!!` | Use |
|-----------|----------------|-----|
| Value might be null, provide default | `value!!` | `value ?: defaultValue` |
| Null means skip/return | `value!!.doSomething()` | `value?.doSomething()` |
| Null is a programming error | `value!!` | `requireNotNull(value) { "value must not be null: reason" }` |
| Null check in initialization | `lateinit var x: T; x!!` | `checkNotNull(x) { "x not initialized" }` |
| Nullable transform chain | `list.find { ... }!!.name` | `list.find { ... }?.name ?: throw NoSuchElementException(...)` |

```kotlin
// BAD -- bypasses null safety
val account = accountRepository.findById(id)!!
val label = config["display_name"]!!

// GOOD -- explicit, descriptive failure
val account = accountRepository.findById(id)
    ?: throw AccountNotFoundException("Account $id not found")
val label = requireNotNull(config["display_name"]) {
    "display_name must be present in config"
}
```

### Java Interop Boundaries

Platform types (returned from Java with unknown nullability) must be annotated or guarded at the boundary -- always handle explicitly:

```kotlin
// BAD -- platform type passes through silently
fun getHeader(request: HttpServletRequest): String {
    return request.getHeader("X-Request-Id") // String! -- platform type
}

// GOOD -- explicit boundary handling
fun getHeader(request: HttpServletRequest): String? {
    return request.getHeader("X-Request-Id") // explicitly nullable
}

// GOOD -- assert non-null with context
fun getRequiredHeader(request: HttpServletRequest): String {
    return requireNotNull(request.getHeader("X-Request-Id")) {
        "X-Request-Id header is required"
    }
}
```

**Detection**: `grep -rn '!!' src/` -- any match is a violation requiring immediate review.

---

## Coroutines and Flow

### Structured Concurrency

Always launch coroutines within a structured scope. Use `viewModelScope`, `lifecycleScope`, or explicit scopes instead of `GlobalScope` in production code.

```kotlin
// BAD -- GlobalScope leaks coroutines
GlobalScope.launch { fetchData() }

// GOOD -- scoped to ViewModel lifecycle
class ProductViewModel(private val repository: ProductRepository) : ViewModel() {
    fun loadProducts() {
        viewModelScope.launch {
            _state.value = repository.getProducts()
        }
    }
}

// GOOD -- scoped in Ktor
fun Application.configureRouting() {
    routing {
        get("/products") {
            val products = coroutineScope {
                async { productService.getAll() }.await()
            }
            call.respond(products)
        }
    }
}
```

### Dispatcher Selection

| Task Type | Dispatcher | Reason |
|-----------|-----------|--------|
| CPU-intensive computation | `Dispatchers.Default` | Thread pool sized to CPU cores |
| Blocking I/O (JDBC, file) | `Dispatchers.IO` | Expandable thread pool for blocking |
| Android UI updates | `Dispatchers.Main` | Main thread only |
| Ktor request handling | Ktor manages dispatcher | Use `withContext(Dispatchers.IO)` for blocking calls |

```kotlin
// BAD -- blocking JDBC call on Default dispatcher starves CPU threads
suspend fun fetchRecord(id: Long): DbRecord = withContext(Dispatchers.Default) {
    database.find(id) // blocking JDBC
}

// GOOD -- blocking call on IO dispatcher
suspend fun fetchRecord(id: Long): DbRecord = withContext(Dispatchers.IO) {
    database.find(id)
}
```

### Flow Patterns

```kotlin
// StateFlow for UI state with debounced search
class SearchViewModel(private val repo: ProductRepository) : ViewModel() {
    private val _query = MutableStateFlow("")
    val results: StateFlow<List<Product>> = _query
        .debounce(300)
        .distinctUntilChanged()
        .flatMapLatest { query -> repo.search(query) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    fun onQueryChanged(query: String) { _query.value = query }
}
```

### Testing Coroutines

Always use `runTest` from `kotlinx-coroutines-test` instead of `runBlocking` in tests.

```kotlin
// BAD -- runBlocking in tests masks timing issues
@Test
fun `should return products`() = runBlocking {
    val result = viewModel.loadProducts()
    assertEquals(expected, result)
}

// GOOD -- runTest with TestDispatcher provides virtual time control
@Test
fun `should debounce search queries`() = runTest {
    val vm = SearchViewModel(fakeRepo)
    vm.onQueryChanged("ki")
    advanceTimeBy(200) // under debounce threshold
    assertEquals(emptyList(), vm.results.value)
    advanceTimeBy(200) // crosses 300ms threshold
    assertEquals(listOf(product), vm.results.value)
}
```

---

## Sealed Classes, Enums, and Data Classes

### Decision Matrix

| Need | Use | Reason |
|------|-----|--------|
| Fixed set of named constants, no data | `enum class` | Serializable, ordinal, `values()`, simple |
| Fixed set of states, each with different data | `sealed class` / `sealed interface` | Exhaustive `when`, each subtype carries its own fields |
| Named constant with associated behavior | `enum class` with abstract function | Enum entries can override |
| Pure value/record type with structural equality | `data class` | `copy()`, `equals()`, `hashCode()`, destructuring |
| Inline wrapper to avoid primitive confusion | `@JvmInline value class` | Zero-overhead at runtime |
| Open hierarchy for external extension | `abstract class` or `interface` | Sealed prevents external subclassing |

```kotlin
// Use enum for simple constants
enum class Direction { NORTH, SOUTH, EAST, WEST }

// Use sealed class when variants carry different data
sealed class LoadResult<out T> {
    data class Success<T>(val value: T) : LoadResult<T>()
    data class Failure(val error: Throwable) : LoadResult<Nothing>()
    data object Loading : LoadResult<Nothing>()
}

// Use data class for records
data class UserId(val value: Long)
data class AppUser(val id: UserId, val name: String, val email: String)

// Use value class to avoid primitive confusion
@JvmInline
value class OrderId(val value: Long)
```

### Exhaustive `when` -- List All Cases on Sealed Types

```kotlin
// BAD -- else suppresses exhaustiveness check; new subtypes silently fall through
fun describeResult(result: LoadResult<AppUser>): String = when (result) {
    is LoadResult.Success -> result.value.name
    is LoadResult.Failure -> result.error.message ?: "error"
    else -> "loading" // hides future subtypes
}

// GOOD -- no else; compiler enforces all cases
fun describeResult(result: LoadResult<AppUser>): String = when (result) {
    is LoadResult.Success -> result.value.name
    is LoadResult.Failure -> result.error.message ?: "error"
    is LoadResult.Loading -> "loading"
}
```

### Extension Functions Over Inheritance

Prefer extension functions to add behavior without modifying the original class:

```kotlin
// Instead of subclassing or utility class
fun String.toSlug(): String = lowercase().replace(Regex("[^a-z0-9]+"), "-").trim('-')

fun AppUser.displayName(): String = "${firstName.trim()} ${lastName.trim()}"

// Scope function selection
val config = ServerConfig().apply {   // apply: configure object, returns receiver
    port = 8080
    host = "0.0.0.0"
}

val transformed = nullableValue?.let {  // let: transform nullable, returns lambda result
    process(it)
}

val logged = value.also {               // also: side effect, returns original value
    logger.info("Processing: $it")
}
```

---

## Koin Dependency Injection

Use Koin in Ktor projects and Android projects where Hilt is not already established.

```kotlin
// Module definition -- prefer interface bindings
val appModule = module {
    single<UserRepository> { DatabaseUserRepository(get()) }
    single<ProductService> { ProductServiceImpl(get(), get()) }
    factory<OrderProcessor> { OrderProcessorImpl(get()) } // new instance each time
}

// Ktor integration
fun Application.configureDI() {
    install(Koin) {
        modules(appModule)
    }
}

fun Route.userRoutes() {
    val userService: UserService by inject()
    // ...
}

// Android -- ViewModel injection
val androidModule = module {
    viewModel { SearchViewModel(get()) }
}
```
