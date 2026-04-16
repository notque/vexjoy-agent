---
name: swift-actor-isolation
description: "Actor isolation, @MainActor, nonisolated patterns with code examples."
type: reference
---

# Actor Isolation

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

## @MainActor

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

## nonisolated

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
