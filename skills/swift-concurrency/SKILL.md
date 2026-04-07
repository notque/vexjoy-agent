---
name: swift-concurrency
description: "Swift concurrency: async/await, Actor, Task, Sendable patterns."
version: 1.0.0
user-invocable: false
context: fork
agent: swift-general-engineer
routing:
  triggers:
    - "swift concurrency"
    - "swift async await"
    - "Swift Actor"
    - "Swift Task group"
  category: swift
---

# Swift Structured Concurrency

## async/await Fundamentals

Mark functions that perform asynchronous work with `async`. Use `throws` alongside `async` for fallible operations. Call async functions with `await`.

```swift
func fetchUser(id: String) async throws -> User {
    let url = URL(string: "https://api.example.com/users/\(id)")!
    let (data, response) = try await URLSession.shared.data(from: url)

    guard let httpResponse = response as? HTTPURLResponse,
          httpResponse.statusCode == 200 else {
        throw APIError.invalidResponse
    }

    return try JSONDecoder().decode(User.self, from: data)
}

// Calling from a synchronous context
Task {
    do {
        let user = try await fetchUser(id: "42")
        print(user.name)
    } catch {
        print("Failed: \(error)")
    }
}
```

### Task and Task.detached

`Task { }` creates unstructured work that inherits the current actor context. `Task.detached` creates work with no inherited context -- use it sparingly.

```swift
// Inherits current actor isolation (e.g., @MainActor)
Task {
    let data = try await fetchData()
    updateUI(with: data) // safe on MainActor if caller was MainActor
}

// No inherited context -- runs on a cooperative thread pool
Task.detached(priority: .background) {
    let report = await generateReport()
    await MainActor.run {
        displayReport(report)
    }
}
```

## Actor Isolation

Actors protect mutable state from data races. Only one task can execute on an actor at a time.

```swift
actor BankAccount {
    private var balance: Decimal

    init(initialBalance: Decimal) {
        self.balance = initialBalance
    }

    func deposit(_ amount: Decimal) {
        balance += amount
    }

    func withdraw(_ amount: Decimal) throws {
        guard balance >= amount else {
            throw BankError.insufficientFunds
        }
        balance -= amount
    }

    func getBalance() -> Decimal {
        balance
    }
}

// All access is async from outside the actor
let account = BankAccount(initialBalance: 1000)
try await account.withdraw(200)
let balance = await account.getBalance()
```

### @MainActor

Use `@MainActor` to confine work to the main thread, required for all UI updates.

```swift
@MainActor
final class ProfileViewModel: ObservableObject {
    @Published var user: User?
    @Published var isLoading = false

    private let service: UserService

    init(service: UserService) {
        self.service = service
    }

    func loadProfile() async {
        isLoading = true
        defer { isLoading = false }

        do {
            user = try await service.fetchCurrentUser()
        } catch {
            print("Load failed: \(error)")
        }
    }
}
```

### nonisolated

Use `nonisolated` to opt specific methods out of actor isolation when they only read immutable state or perform no state access.

```swift
actor CacheManager {
    let maxSize: Int
    private var entries: [String: Data] = [:]

    init(maxSize: Int) {
        self.maxSize = maxSize
    }

    // No await needed to call this -- it reads only a let property
    nonisolated func description() -> String {
        "CacheManager(maxSize: \(maxSize))"
    }

    func store(_ data: Data, forKey key: String) {
        entries[key] = data
    }
}
```

## Sendable and @Sendable

The `Sendable` protocol marks types safe to transfer across concurrency domains. The compiler enforces this at build time with strict concurrency checking.

```swift
// Value types are implicitly Sendable
struct Coordinate: Sendable {
    let latitude: Double
    let longitude: Double
}

// Classes must be final with only immutable stored properties
final class Configuration: Sendable {
    let apiKey: String
    let baseURL: URL

    init(apiKey: String, baseURL: URL) {
        self.apiKey = apiKey
        self.baseURL = baseURL
    }
}

// @Sendable closures cannot capture mutable state
func process(items: [Item], transform: @Sendable (Item) -> Result) async {
    await withTaskGroup(of: Result.self) { group in
        for item in items {
            group.addTask {
                transform(item)
            }
        }
    }
}
```

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

## Common Anti-Patterns

### Blocking the Main Actor

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

### Unstructured Tasks Leaking

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

### Actor Reentrancy Hazard

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

## Key Conventions

- **Prefer structured concurrency** -- use `TaskGroup` over loose `Task { }` whenever possible; structured tasks propagate cancellation and errors automatically.
- **Mark types Sendable** -- enable strict concurrency checking (`-strict-concurrency=complete`) and resolve all warnings before they become errors in Swift 6.
- **Use actors for shared mutable state** -- avoid manual locks; actors provide compiler-verified safety.
- **Cancel what you create** -- every `Task` stored in a property should have a corresponding cancellation path.
- **Minimize @MainActor surface** -- isolate only the UI layer; keep business logic and networking off the main actor.
