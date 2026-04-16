---
name: swift-concurrency-anti-patterns
description: "Common concurrency mistakes: blocking MainActor, task leaking, actor reentrancy."
type: reference
---

# Common Anti-Patterns

## Blocking the Main Actor

Never perform synchronous blocking work on `@MainActor`. Offload heavy computation to a detached task or a background actor.

```swift
// BAD -- blocks the main thread
@MainActor
func loadData() {
    let data = heavySyncComputation() // UI freezes
    self.items = data
}

// GOOD -- offload and return to main actor for UI update
@MainActor
func loadData() async {
    let data = await Task.detached(priority: .userInitiated) {
        heavySyncComputation()
    }.value
    self.items = data
}
```

## Unstructured Tasks Leaking

Creating `Task { }` without storing or cancelling it leads to leaked work that outlives its logical scope.

```swift
// BAD -- task leaks if view disappears
func viewDidAppear() {
    Task {
        while true {
            await pollServer()
            try await Task.sleep(for: .seconds(30))
        }
    }
}

// GOOD -- store and cancel on disappear
private var pollingTask: Task<Void, Never>?

func viewDidAppear() {
    pollingTask = Task {
        while !Task.isCancelled {
            await pollServer()
            try? await Task.sleep(for: .seconds(30))
        }
    }
}

func viewDidDisappear() {
    pollingTask?.cancel()
    pollingTask = nil
}
```

## Actor Reentrancy Hazard

Awaiting inside an actor method yields the actor, allowing other callers to mutate state before your method resumes. Always re-validate state after an `await`.

```swift
actor ImageCache {
    private var cache: [URL: UIImage] = [:]
    private var inFlight: [URL: Task<UIImage, Error>] = [:]

    func image(for url: URL) async throws -> UIImage {
        // Check cache first
        if let cached = cache[url] { return cached }

        // Deduplicate in-flight requests
        if let existing = inFlight[url] {
            return try await existing.value
        }

        let task = Task {
            let (data, _) = try await URLSession.shared.data(from: url)
            guard let image = UIImage(data: data) else {
                throw ImageError.decodingFailed
            }
            return image
        }

        inFlight[url] = task

        let image = try await task.value

        // Re-check: another caller may have populated cache while we awaited
        cache[url] = image
        inFlight[url] = nil

        return image
    }
}
```
