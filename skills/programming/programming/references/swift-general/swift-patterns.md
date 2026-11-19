# Swift Patterns

## Immutability

### `let` vs. `var` Rules

| Rule | Rationale |
|------|-----------|
| Always declare as `let` first | If the compiler accepts it, it is immutable — keep it |
| Change to `var` only when compiler requires it | The compiler is the source of truth, not habit |
| Never pre-emptively declare `var` in case it changes | That change may never come; premature mutability creates data-race surface area |
| Use `mutating func` in structs for controlled mutation | Keeps value semantics; each mutation is explicit at call sites |

```swift
// Wrong — var when let suffices
var name = "Alice"
print(name)  // never reassigned

// Correct
let name = "Alice"
print(name)
```

### `struct` vs. `class` Decision Matrix

| Use `struct` when... | Use `class` when... |
|----------------------|---------------------|
| Data is copied between contexts (DTO, model, config) | Identity matters — two references must point to the same object |
| Thread-safety via value semantics is desired | Objective-C interoperability requires `NSObject` subclassing |
| No subclassing is needed | Reference sharing is an intentional design decision (e.g., shared cache) |
| All stored properties are value types or `Sendable` | Lifecycle management via `deinit` is required |
| SwiftUI view models that do not need `ObservableObject` | `ObservableObject` / `@Published` Combine integration |

```swift
// Prefer struct for DTOs
struct UserProfile: Sendable {
    let id: UUID
    let displayName: String
    let email: String
}

// class only when identity semantics are needed
final class ImageCache {
    static let shared = ImageCache()  // single shared instance
    private var storage: [URL: UIImage] = [:]
    private init() {}
}
```

---

## Concurrency

### Core Principles

Swift 6 strict concurrency treats data races as compile-time errors. Every type crossing actor isolation boundaries must be `Sendable`.

### Actor Isolation

```swift
// Use actors for shared mutable state — not DispatchQueue or locks
actor DownloadManager {
    private var activeTasks: [URL: Task<Data, Error>] = [:]

    func fetch(_ url: URL) async throws -> Data {
        if let existing = activeTasks[url] {
            return try await existing.value
        }
        let task = Task { try await URLSession.shared.data(from: url).0 }
        activeTasks[url] = task
        defer { activeTasks.removeValue(forKey: url) }
        return try await task.value
    }
}
```

### Sendable Requirements

- Value types (`struct`, `enum`) that contain only `Sendable` properties are automatically `Sendable`
- Add `@unchecked Sendable` only with documented proof of manual thread-safety; it is a last resort
- Pass `Sendable` closures across actor boundaries; non-`Sendable` closures must stay on the originating actor

### Structured vs. Unstructured Concurrency

| Pattern | Use When |
|---------|----------|
| `async let` | Fixed number of independent operations with known result types |
| `TaskGroup` / `withThrowingTaskGroup` | Dynamic number of concurrent operations |
| `Task {}` | Background work not in an async context (UI event handlers, Combine sinks) |
| Prefer `async let` / `TaskGroup` over naked `Task {}` when applicable | Unstructured tasks escape scope, making cancellation and error propagation harder |

```swift
// Prefer async let for fixed parallel fetches
async let profile = fetchProfile(userID)
async let posts = fetchPosts(userID)
let (p, feed) = try await (profile, posts)

// Use TaskGroup for dynamic concurrency
let results = try await withThrowingTaskGroup(of: Item.self) { group in
    for id in ids {
        group.addTask { try await fetchItem(id) }
    }
    return try await group.reduce(into: []) { $0.append($1) }
}
```

### Typed Throws (Swift 6+)

```swift
enum FetchError: Error {
    case networkUnavailable
    case decodingFailed(underlying: Error)
}

func fetchUser(id: UUID) async throws(FetchError) -> User {
    guard NetworkMonitor.isAvailable else { throw .networkUnavailable }
    do {
        let data = try await urlSession.data(from: endpoint(id)).0
        return try JSONDecoder().decode(User.self, from: data)
    } catch {
        throw .decodingFailed(underlying: error)
    }
}
```

---

## Protocol-Oriented Design

### Small Focused Protocols

Define protocols around a single capability. Conformers implement only what they need.

```swift
// Wrong — fat protocol
protocol DataService {
    func fetch() async throws -> [Item]
    func save(_ item: Item) async throws
    func delete(_ id: UUID) async throws
    func export() -> Data
}

// Correct — segregated protocols
protocol ItemFetcher { func fetch() async throws -> [Item] }
protocol ItemWriter { func save(_ item: Item) async throws; func delete(_ id: UUID) async throws }
protocol DataExporter { func export() -> Data }
```

### Protocol Extensions for Shared Defaults

```swift
protocol Loggable {
    var logger: Logger { get }
}

extension Loggable {
    var logger: Logger {
        Logger(subsystem: Bundle.main.bundleIdentifier ?? "app", category: String(describing: Self.self))
    }
}
```

### Dependency Injection via Protocol with Default Parameter

Production code uses the real implementation by default; tests inject a mock without any additional configuration in the production call sites.

```swift
protocol HTTPClient: Sendable {
    func data(for request: URLRequest) async throws -> (Data, URLResponse)
}

extension URLSession: HTTPClient {}  // URLSession already matches the protocol

struct UserRepository {
    private let client: any HTTPClient

    // Default parameter means production callers never see the seam
    init(client: any HTTPClient = URLSession.shared) {
        self.client = client
    }
}

// In tests:
struct MockHTTPClient: HTTPClient {
    var stubbedData: Data = Data()
    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        (stubbedData, URLResponse())
    }
}
```

---

## State Modeling

### `LoadState<T>` Enum Pattern

Model async data loading states with an enum rather than multiple optionals.

```swift
enum LoadState<T: Sendable>: Sendable {
    case idle
    case loading
    case loaded(T)
    case failed(Error)
}

@Observable
final class ProfileViewModel {
    private(set) var state: LoadState<UserProfile> = .idle

    func load(userID: UUID) async {
        state = .loading
        do {
            let profile = try await repository.fetchProfile(userID)
            state = .loaded(profile)
        } catch {
            state = .failed(error)
        }
    }
}
```

```swift
// SwiftUI view consuming LoadState
switch viewModel.state {
case .idle: Color.clear
case .loading: ProgressView()
case .loaded(let profile): ProfileContentView(profile: profile)
case .failed(let error): ErrorView(error: error, retry: { await viewModel.load(userID: id) })
}
```
