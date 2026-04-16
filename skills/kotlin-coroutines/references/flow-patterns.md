---
name: flow-patterns
description: "Kotlin Flow patterns: cold streams, StateFlow, SharedFlow comparison and usage."
level: 2
---

# Kotlin Flow Patterns

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

## StateFlow vs SharedFlow

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

### StateFlow vs SharedFlow Decision Matrix

| Property | `StateFlow` | `SharedFlow` |
|----------|-------------|--------------|
| Initial value | Required | Not required |
| Replay | Always 1 (latest) | Configurable (0..N) |
| Equality | Conflates duplicate values | Emits all values |
| Use case | Current state | Event streams |
