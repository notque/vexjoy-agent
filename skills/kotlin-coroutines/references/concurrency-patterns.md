---
name: concurrency-patterns
description: "Kotlin structured concurrency: coroutineScope, supervisorScope, cancellation, dispatchers, exception handling."
level: 2
---

# Kotlin Concurrency Patterns

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
