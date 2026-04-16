---
name: swift-task-patterns
description: "TaskGroup, AsyncSequence, AsyncStream, and cancellation patterns."
type: reference
---

# Task Patterns

## TaskGroup for Parallel Work

Use `withTaskGroup` or `withThrowingTaskGroup` to fan out work and collect results.

```swift
func fetchAllProfiles(ids: [String]) async throws -> [Profile] {
    try await withThrowingTaskGroup(of: Profile.self) { group in
        for id in ids {
            group.addTask {
                try await fetchProfile(id: id)
            }
        }

        var profiles: [Profile] = []
        for try await profile in group {
            profiles.append(profile)
        }
        return profiles
    }
}
```

### Rate-Limited Concurrency

Limit concurrency manually when hitting external services:

```swift
func fetchWithLimit(ids: [String], maxConcurrent: Int = 5) async throws -> [Profile] {
    try await withThrowingTaskGroup(of: Profile.self) { group in
        var iterator = ids.makeIterator()
        var profiles: [Profile] = []

        // Seed the group with initial batch
        for _ in 0..<min(maxConcurrent, ids.count) {
            if let id = iterator.next() {
                group.addTask { try await fetchProfile(id: id) }
            }
        }

        // As each completes, add the next
        for try await profile in group {
            profiles.append(profile)
            if let id = iterator.next() {
                group.addTask { try await fetchProfile(id: id) }
            }
        }

        return profiles
    }
}
```

## AsyncSequence and AsyncStream

`AsyncSequence` is the async counterpart to `Sequence`. Use `AsyncStream` to bridge callback-based APIs into structured concurrency.

```swift
// Consuming an AsyncSequence
func processNotifications() async {
    for await notification in NotificationCenter.default.notifications(named: .userDidUpdate) {
        guard let user = notification.userInfo?["user"] as? User else { continue }
        await handleUserUpdate(user)
    }
}

// Creating an AsyncStream from a delegate/callback pattern
func locationUpdates() -> AsyncStream<CLLocation> {
    AsyncStream { continuation in
        let delegate = LocationDelegate(
            onUpdate: { location in
                continuation.yield(location)
            },
            onFinish: {
                continuation.finish()
            }
        )
        // Store delegate to keep it alive
        continuation.onTermination = { _ in
            delegate.stopUpdating()
        }
        delegate.startUpdating()
    }
}

// Consuming the stream
Task {
    for await location in locationUpdates() {
        print("Lat: \(location.coordinate.latitude)")
    }
}
```

## Cancellation

Structured concurrency propagates cancellation automatically through task hierarchies. Check for cancellation in long-running work.

```swift
func processLargeDataset(_ items: [DataItem]) async throws -> [Result] {
    var results: [Result] = []

    for item in items {
        // Throws CancellationError if the task was cancelled
        try Task.checkCancellation()

        let result = await process(item)
        results.append(result)
    }

    return results
}

// Alternative: check without throwing
func processWithGracefulCancel(_ items: [DataItem]) async -> [Result] {
    var results: [Result] = []

    for item in items {
        if Task.isCancelled {
            break // stop early, return partial results
        }
        let result = await process(item)
        results.append(result)
    }

    return results
}

// Cancelling a task
let task = Task {
    try await processLargeDataset(hugeList)
}

// Later, if the user navigates away
task.cancel()
```
