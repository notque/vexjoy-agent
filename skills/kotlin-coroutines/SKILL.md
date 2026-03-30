---
name: kotlin-coroutines
description: "Kotlin structured concurrency, Flow, and Channel patterns."
version: 1.0.0
user-invocable: false
context: fork
agent: kotlin-general-engineer
---

# Kotlin Coroutines Patterns

## Structured Concurrency

Every coroutine must belong to a scope. The scope defines the lifetime -- when the scope is cancelled, all its children are cancelled. Tie every coroutine to a scope.

```kotlin
import kotlinx.coroutines.*

// coroutineScope suspends until ALL children complete.
// If any child fails, all siblings are cancelled.
suspend fun fetchDashboard(): Dashboard = coroutineScope {
    val user = async { userService.getUser() }
    val orders = async { orderService.getRecent() }
    val notifications = async { notificationService.getUnread() }

    Dashboard(
        user = user.await(),
        orders = orders.await(),
        notifications = notifications.await()
    )
}

// supervisorScope lets children fail independently.
// One child's failure does NOT cancel siblings.
suspend fun refreshCaches(): List<Result<Unit>> = supervisorScope {
    val jobs = listOf("users", "products", "inventory").map { cache ->
        async {
            runCatching { cacheService.refresh(cache) }
        }
    }
    jobs.awaitAll()
}
```

### coroutineScope vs supervisorScope

| Behavior | `coroutineScope` | `supervisorScope` |
|----------|------------------|-------------------|
| Child failure | Cancels all siblings | Siblings continue |
| Use when | All results required | Partial success acceptable |
| Exception | Rethrown from scope | Must handle per-child |

## Cancellation

Coroutines use cooperative cancellation. Long-running work must check `isActive` or call suspending functions that respect cancellation.

```kotlin
suspend fun processLargeFile(file: File) = coroutineScope {
    file.useLines { lines ->
        lines.forEach { line ->
            // Check cancellation between iterations
            ensureActive()
            processLine(line)
        }
    }
}

// CPU-bound loops MUST check isActive — they won't suspend naturally
suspend fun computeHash(data: ByteArray): String = withContext(Dispatchers.Default) {
    var hash = 0L
    for (i in data.indices) {
        if (!isActive) break  // Respect cancellation
        hash = hash * 31 + data[i]
    }
    hash.toString(16)
}
```

### NonCancellable for Cleanup

When you need to run suspending cleanup code after cancellation, use `NonCancellable`.

```kotlin
suspend fun transferFunds(from: Account, to: Account, amount: BigDecimal) {
    try {
        from.debit(amount)
        to.credit(amount)
    } finally {
        // After cancellation, the coroutine is in a "cancelling" state.
        // Suspending calls would throw CancellationException — unless
        // we switch to NonCancellable.
        withContext(NonCancellable) {
            auditLog.record("Transfer attempted: $amount from ${from.id} to ${to.id}")
        }
    }
}
```

## Flow: Cold Asynchronous Streams

Flow is cold -- it does not produce values until collected. Each collector gets its own execution of the flow body.

```kotlin
import kotlinx.coroutines.flow.*

// Producing a flow
fun searchResults(query: String): Flow<SearchResult> = flow {
    val page1 = api.search(query, page = 1)
    emit(page1)

    if (page1.hasMore) {
        val page2 = api.search(query, page = 2)
        emit(page2)
    }
}

// Operators: transform, filter, combine
fun processedResults(query: String): Flow<DisplayItem> =
    searchResults(query)
        .filter { it.results.isNotEmpty() }
        .map { page -> page.results.map { it.toDisplayItem() } }
        .flatMapConcat { items -> items.asFlow() }
        .onEach { item -> analytics.trackImpression(item.id) }

// Terminal operator — triggers collection
suspend fun displayResults(query: String) {
    processedResults(query).collect { item ->
        ui.render(item)
    }
}
```

### StateFlow vs SharedFlow

```kotlin
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.channels.BufferOverflow

// StateFlow: holds a SINGLE current value, replays latest to new collectors.
// Use for UI state, configuration, or anything with a "current" value.
class CounterViewModel : ViewModel() {
    private val _count = MutableStateFlow(0)
    val count = _count.asStateFlow()

    fun increment() {
        _count.value++
    }
}

// SharedFlow: event stream with configurable replay.
// Use for one-shot events (navigation, toasts, errors).
class EventBus {
    private val _events = MutableSharedFlow<AppEvent>(
        replay = 0,           // Skip replaying old events to new subscribers
        extraBufferCapacity = 64,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    val events = _events.asSharedFlow()

    suspend fun emit(event: AppEvent) {
        _events.emit(event)
    }
}
```

| Property | `StateFlow` | `SharedFlow` |
|----------|-------------|--------------|
| Initial value | Required | Not required |
| Replay | Always 1 (latest) | Configurable (0..N) |
| Equality | Conflates duplicate values | Emits all values |
| Use case | Current state | Event streams |

## Channels: Hot Communication Primitives

Channels are hot -- they exist independently of consumers. Use them for producer-consumer patterns and inter-coroutine communication.

```kotlin
import kotlinx.coroutines.channels.*

// Producer-consumer with produce builder
fun CoroutineScope.produceNumbers(): ReceiveChannel<Int> = produce {
    var n = 1
    while (true) {
        send(n++)
        delay(100)
    }
}

// Fan-out: multiple coroutines consuming from one channel
suspend fun fanOut() = coroutineScope {
    val channel = produceNumbers()

    repeat(3) { workerId ->
        launch {
            for (number in channel) {
                println("Worker $workerId processing $number")
            }
        }
    }
}

// Fan-in: multiple producers writing to one channel
suspend fun fanIn() = coroutineScope {
    val channel = Channel<String>()

    launch { repeat(5) { channel.send("Source A: $it"); delay(100) } }
    launch { repeat(5) { channel.send("Source B: $it"); delay(150) } }

    // Collect all from both sources
    repeat(10) {
        println(channel.receive())
    }
    channel.close()
}
```

## Exception Handling

Exceptions in coroutines propagate up the scope hierarchy. Uncaught exceptions cancel the parent scope.

```kotlin
// CoroutineExceptionHandler — last resort for uncaught exceptions in launch.
// Only works with launch (NOT async). Only at root scope level.
val handler = CoroutineExceptionHandler { _, exception ->
    logger.error("Uncaught coroutine exception", exception)
    metrics.incrementCounter("coroutine.unhandled_exception")
}

val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default + handler)

scope.launch {
    // If this throws, handler catches it instead of crashing
    riskyOperation()
}

// For async, exceptions surface at await()
val deferred = scope.async {
    riskyOperation() // Exception stored, not thrown yet
}
try {
    deferred.await() // Exception thrown HERE
} catch (e: Exception) {
    handleError(e)
}
```

### try-catch in Coroutines

```kotlin
// Wrap individual operations, not the entire coroutine
suspend fun fetchWithFallback(): Data {
    return try {
        remoteApi.fetch()
    } catch (e: IOException) {
        logger.warn("Remote fetch failed, using cache", e)
        localCache.get()
    }
}

// Always rethrow CancellationException — it breaks structured concurrency
suspend fun badExample() {
    try {
        someWork()
    } catch (e: Exception) {
        // Before: This catches CancellationException too!
        // The coroutine won't cancel properly.
    }
}

suspend fun goodExample() {
    try {
        someWork()
    } catch (e: CancellationException) {
        throw e // Always rethrow
    } catch (e: Exception) {
        handleError(e)
    }
}
```

## Dispatchers

| Dispatcher | Thread Pool | Use For |
|------------|------------|---------|
| `Dispatchers.Default` | Shared, sized to CPU cores | CPU-bound work (parsing, sorting) |
| `Dispatchers.IO` | Elastic, up to 64 threads | Blocking I/O (file, network, JDBC) |
| `Dispatchers.Main` | Single UI thread | UI updates (Android, Swing) |
| `Dispatchers.Unconfined` | Caller's thread (until first suspend) | Testing only; avoid in production |

```kotlin
// Switch dispatcher for blocking calls
suspend fun readConfig(): Config = withContext(Dispatchers.IO) {
    val text = File("config.json").readText() // Blocking call on IO pool
    Json.decodeFromString(text)
}

// Custom dispatcher for limited parallelism
val dbDispatcher = Dispatchers.IO.limitedParallelism(4)

suspend fun queryDatabase(): List<Row> = withContext(dbDispatcher) {
    connection.executeQuery("SELECT * FROM orders")
}
```

## Preferred Patterns

### GlobalScope: Fire-and-Forget Leak

```kotlin
// Before: No lifecycle management, lives until process dies
fun handleRequest(request: Request) {
    GlobalScope.launch {
        auditService.log(request) // If this hangs, it leaks forever
    }
}

// After: Use a scoped coroutine tied to the component lifecycle
class RequestHandler(private val scope: CoroutineScope) {
    fun handleRequest(request: Request) {
        scope.launch {
            auditService.log(request)
        }
    }
}
```

### Unstructured launch Without Join

```kotlin
// After: coroutineScope waits for all children
suspend fun processAll(items: List<Item>) = coroutineScope {
    items.forEach { item ->
        launch { process(item) } // These run concurrently
    }
    // coroutineScope suspends until all children complete
}

// Before: Using a detached scope means no waiting
fun processAllBroken(items: List<Item>) {
    val scope = CoroutineScope(Dispatchers.Default)
    items.forEach { item ->
        scope.launch { process(item) } // No one awaits these!
    }
    // Function returns immediately, work may remain incomplete
}
```

### Catching CancellationException

```kotlin
// Before: Swallowing cancellation breaks the entire coroutine tree
try {
    longRunningWork()
} catch (e: Exception) { /* swallows CancellationException */ }

// After: Explicit rethrow
try {
    longRunningWork()
} catch (e: CancellationException) {
    throw e
} catch (e: Exception) {
    recover(e)
}
```

## Key Principles

1. **Structured concurrency is non-negotiable** -- every coroutine must have a parent scope that defines its lifetime.
2. **Inject dispatchers** -- accept `CoroutineDispatcher` as a parameter so callers (and tests) can control threading.
3. **Always rethrow CancellationException** -- rethrow it immediately or use specific exception types instead of catching `Exception`. Use specific exception types.
4. **Prefer Flow over Channel** -- Flow is cold, composable, and handles backpressure. Channels are lower-level; reach for them only when Flow cannot express the pattern.
5. **Use supervisorScope for partial failure tolerance** -- when independent tasks should not cancel each other, wrap them in supervisorScope.
6. **Use scoped coroutines instead of GlobalScope** -- it has no lifecycle, no cancellation, and no structured concurrency. Pass a scope from your application framework instead.
