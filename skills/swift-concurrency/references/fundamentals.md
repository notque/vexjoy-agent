---
name: swift-concurrency-fundamentals
description: "async/await basics, Task and Task.detached patterns, Sendable/@Sendable protocol."
type: reference
---

# Swift Concurrency Fundamentals

## async/await

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

## Task and Task.detached

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
