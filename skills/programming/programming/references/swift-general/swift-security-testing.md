# Swift Security & Testing

## Security

### Keychain vs. UserDefaults

| Data Category | Storage | Reason |
|---------------|---------|--------|
| API tokens, OAuth tokens | **Keychain** | Encrypted at rest; protected by device passcode / Secure Enclave |
| Passwords, private keys | **Keychain** | Never stored in plaintext |
| User preferences (theme, language) | UserDefaults | Non-sensitive; loss is acceptable |
| Feature flags | UserDefaults | Non-sensitive |
| JWT refresh tokens | **Keychain** | Credential — same as token |
| Device-specific identifiers | UserDefaults or Keychain depending on sensitivity | Evaluate case by case |

**Detection trigger**: Any `UserDefaults` call with a key string containing `token`, `password`, `key`, `secret`, `credential`, or `auth` is a security violation requiring Keychain migration.

Keychain wrapper code, `kSecAttrAccessible` levels, and detection commands: [swift-security.md](swift-security.md), "Store Sensitive Data in Keychain Services" and "UserDefaults vs Keychain".

### App Transport Security (ATS)

- ATS is enabled by default — keep it enabled
- `NSAllowsArbitraryLoads: true` in Info.plist requires documented justification (e.g., streaming media exemption per Apple documentation)
- Use `NSExceptionDomains` for specific domains that require exceptions; keep ATS bypasses scoped to individual domains
- All production endpoints must use HTTPS with valid certificates
- Info.plist example and detection: swift-security.md, "Justify Every ATS Exception"

### Certificate Pinning

For endpoints handling financial, healthcare, or authentication data, implement certificate or public key pinning via `URLSessionDelegate`.

Use the SPKI-hash `PinningDelegate` in [swift-security.md](swift-security.md), "Certificate Pinning for Sensitive Connections": evaluate trust with `SecTrustEvaluateWithError` before comparing hashes, and always ship a backup pin for key rotation.

### Secret Management

| Source | Rule |
|--------|------|
| API keys in source files | **Hard boundary** — decompilation extracts them trivially |
| API keys in Info.plist | **Hard boundary** — same decompilation risk |
| Build-time secrets | Use `.xcconfig` files excluded from version control; read via `Bundle.main.infoDictionary` |
| CI/CD secrets | Environment variables injected at build time; keep out of version control |
| Runtime secrets | Fetched from server after authentication; stored in Keychain |

### Input Validation

Validate all data from external sources before use:

```swift
// URL from deep link or pasteboard — never force-unwrap
guard let url = URL(string: rawString), url.scheme == "https" else {
    logger.warning("Rejected invalid URL: \(rawString, privacy: .private)")
    return
}

// API response data — always decode into typed models, never assume structure
let decoder = JSONDecoder()
decoder.keyDecodingStrategy = .convertFromSnakeCase
let response = try decoder.decode(APIResponse.self, from: data)
```

---

## Testing

### Swift Testing over XCTest for New Code

Use `import Testing` for all new test files. Migrate XCTest suites to Swift Testing only when explicitly requested.

| Feature | Swift Testing | XCTest |
|---------|--------------|--------|
| Test declaration | `@Test func name()` | `func testName()` |
| Assertion | `#expect(condition)` | `XCTAssertTrue(condition)` |
| Parameterized tests | `@Test(arguments: [...])` | Manual loop or subclassing |
| Expected failure | `@Test(.disabled("reason"))` | `XCTSkip` |
| Test tags | `@Test(.tags(.performance))` | None built-in |

```swift
import Testing
@testable import MyApp

@Suite("UserRepository")
struct UserRepositoryTests {
    let sut: UserRepository
    let mockClient: MockHTTPClient

    init() {
        mockClient = MockHTTPClient()
        sut = UserRepository(client: mockClient)
    }

    @Test("fetch returns decoded user on success")
    func fetchSuccess() async throws {
        mockClient.stubbedData = try JSONEncoder().encode(User.fixture)
        let user = try await sut.fetchUser(id: User.fixture.id)
        #expect(user.id == User.fixture.id)
        #expect(user.displayName == User.fixture.displayName)
    }

    @Test("fetch throws on network failure", arguments: [
        URLError(.notConnectedToInternet),
        URLError(.timedOut)
    ])
    func fetchNetworkFailure(error: URLError) async {
        mockClient.errorToThrow = error
        await #expect(throws: FetchError.self) {
            try await sut.fetchUser(id: UUID())
        }
    }
}
```

More examples (XCTest, async tests, UI tests, protocol mocks): [../swift/swift-testing.md](../swift/swift-testing.md).

### Fresh-Instance Isolation

- Instantiate the system-under-test in `init()`, not as a static shared property
- Tear down resources in `deinit`
- No shared mutable state between tests — each `@Suite` instance is independent

### Coverage

```bash
swift test --enable-code-coverage
# View report:
xcrun llvm-cov report .build/debug/<product>.xctest/Contents/MacOS/<product> \
    -instr-profile .build/debug/codecov/default.profdata
```

---

## Patterns to Detect and Fix

| Pattern | Consequence | Detection |
|-------------|-------------|-----------|
| `var` where `let` suffices | Unnecessary mutation surface; potential data races | Compiler warning; SwiftLint `prefer_let` rule |
| `class` where `struct` suffices | Reference semantics risk; thread-safety burden | Review: does any property need shared mutable state? |
| `print()` in production code | No log level filtering; no subsystem/category tagging; lost in console noise | `grep -rn 'print(' Sources/` |
| Force-unwrap `!` on external data | Crash on unexpected input from API, deep link, or pasteboard | SwiftLint `force_unwrapping` rule; code review |
| `UserDefaults` for credentials | Credential accessible in unencrypted preferences plist | `grep -rn 'UserDefaults' Sources/` + key inspection |
| `NSAllowsArbitraryLoads: true` | ATS bypass; App Store rejection risk; MITM exposure | `grep -rn 'NSAllowsArbitraryLoads' .` |
| Hardcoded secrets in source | Trivially extracted by decompilation | `grep -rn 'apiKey\|secret\|password\|token' Sources/` |
| `Task {}` when `async let` applies | Escaped scope; implicit cancellation loss; harder error propagation | Review: is the task count known at call site? |
| XCTest for new test files | Misses parameterized tests, tags, structured error checking | Check import: `import XCTest` in new files |
| `@unchecked Sendable` without proof | False Sendable claim; silent data race | Review: document the thread-safety mechanism in a comment |
| Secrets in tracked `.xcconfig` | Secrets in version history | `.gitignore` should exclude `*.xcconfig` for secret configs |
