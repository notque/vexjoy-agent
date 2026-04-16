---
name: anti-patterns
description: "Kotlin coroutine anti-patterns: GlobalScope, unstructured launch, CancellationException swallowing."
level: 2
---

# Kotlin Coroutine Anti-Patterns

## GlobalScope: Fire-and-Forget Leak

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

GlobalScope has no lifecycle, no cancellation, and no structured concurrency. Pass a scope from your application framework instead.

## Unstructured launch Without Join

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

## Catching CancellationException

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

Always rethrow CancellationException. Catching `Exception` broadly swallows the cancellation signal, preventing the coroutine tree from shutting down properly.
