---
name: swift-testing
description: "Swift testing: XCTest, Swift Testing framework, async patterns."
user-invocable: false
context: fork
agent: swift-general-engineer
routing:
  triggers:
    - "swift testing"
    - "XCTest"
    - "Swift Testing framework"
    - "async test swift"
  category: swift
  pairs_with:
    - swift-concurrency
    - test-driven-development
---

# Swift Testing Patterns

## XCTest Basics

`XCTestCase` subclass with `setUp`/`tearDown` lifecycle:

```swift
import XCTest
@testable import MyApp

final class UserServiceTests: XCTestCase {
    var sut: UserService!
    var mockStore: MockUserStore!

    override func setUp() {
        super.setUp()
        mockStore = MockUserStore()
        sut = UserService(store: mockStore)
    }

    override func tearDown() {
        sut = nil
        mockStore = nil
        super.tearDown()
    }

    func testFetchUser_withValidID_returnsUser() {
        mockStore.stubbedUser = User(id: "1", name: "Alice")
        let user = sut.fetchUser(id: "1")
        XCTAssertNotNil(user)
        XCTAssertEqual(user?.name, "Alice")
    }

    func testFetchUser_withInvalidID_returnsNil() {
        mockStore.stubbedUser = nil
        let user = sut.fetchUser(id: "unknown")
        XCTAssertNil(user)
    }
}
```

## Swift Testing Framework (Swift 5.9+)

Macro-driven: `@Test` for tests, `#expect` for assertions, `@Suite` for grouping.

```swift
import Testing
@testable import MyApp

@Suite("User Service")
struct UserServiceTests {
    let mockStore = MockUserStore()

    @Test("fetches user by valid ID")
    func fetchValidUser() {
        mockStore.stubbedUser = User(id: "1", name: "Alice")
        let service = UserService(store: mockStore)
        let user = service.fetchUser(id: "1")
        #expect(user?.name == "Alice")
    }

    @Test("returns nil for unknown ID")
    func fetchUnknownUser() {
        mockStore.stubbedUser = nil
        let service = UserService(store: mockStore)
        #expect(service.fetchUser(id: "unknown") == nil)
    }
}
```

### Parameterized Tests

```swift
@Test("validates email formats", arguments: [
    ("alice@example.com", true),
    ("bob@", false),
    ("", false),
    ("valid+tag@sub.domain.com", true),
])
func emailValidation(email: String, isValid: Bool) {
    #expect(EmailValidator.isValid(email) == isValid)
}
```

## Async Testing

### XCTest async

```swift
func testFetchProfile_async() async throws {
    let service = ProfileService(client: MockHTTPClient())
    let profile = try await service.fetchProfile(userID: "1")
    XCTAssertEqual(profile.name, "Alice")
}

// Callback-based APIs
func testFetchProfile_callback() {
    let expectation = expectation(description: "Profile fetched")
    let service = ProfileService(client: MockHTTPClient())

    service.fetchProfile(userID: "1") { result in
        switch result {
        case .success(let profile):
            XCTAssertEqual(profile.name, "Alice")
        case .failure(let error):
            XCTFail("Unexpected error: \(error)")
        }
        expectation.fulfill()
    }
    waitForExpectations(timeout: 5)
}
```

### Swift Testing async

```swift
@Test("fetches profile asynchronously")
func fetchProfileAsync() async throws {
    let service = ProfileService(client: MockHTTPClient())
    let profile = try await service.fetchProfile(userID: "1")
    #expect(profile.name == "Alice")
}
```

## UI Testing

Use `XCUIApplication`. Prefer accessibility identifiers over text matching.

```swift
final class LoginUITests: XCTestCase {
    let app = XCUIApplication()

    override func setUp() {
        super.setUp()
        continueAfterFailure = false
        app.launchArguments = ["--uitesting"]
        app.launch()
    }

    func testSuccessfulLogin() {
        let emailField = app.textFields["login.emailField"]
        let passwordField = app.secureTextFields["login.passwordField"]
        let loginButton = app.buttons["login.submitButton"]

        emailField.tap()
        emailField.typeText("alice@example.com")
        passwordField.tap()
        passwordField.typeText("password123")
        loginButton.tap()

        let welcomeLabel = app.staticTexts["home.welcomeLabel"]
        XCTAssertTrue(welcomeLabel.waitForExistence(timeout: 5))
        XCTAssertEqual(welcomeLabel.label, "Welcome, Alice")
    }
}
```

Set identifiers in production code:
```swift
emailTextField.accessibilityIdentifier = "login.emailField"
passwordTextField.accessibilityIdentifier = "login.passwordField"
submitButton.accessibilityIdentifier = "login.submitButton"
```

## Protocol-Based Mocking

Define dependencies as protocols, mock in tests:

```swift
protocol HTTPClient {
    func data(from url: URL) async throws -> (Data, URLResponse)
}

struct URLSessionHTTPClient: HTTPClient {
    let session: URLSession
    func data(from url: URL) async throws -> (Data, URLResponse) {
        try await session.data(from: url)
    }
}

final class MockHTTPClient: HTTPClient {
    var stubbedData: Data = Data()
    var stubbedResponse: URLResponse = HTTPURLResponse()
    var capturedURLs: [URL] = []

    func data(from url: URL) async throws -> (Data, URLResponse) {
        capturedURLs.append(url)
        return (stubbedData, stubbedResponse)
    }
}
```

### Dependency Injection

```swift
final class ProfileService {
    private let client: HTTPClient
    init(client: HTTPClient) { self.client = client }

    func fetchProfile(userID: String) async throws -> Profile {
        let url = URL(string: "https://api.example.com/users/\(userID)")!
        let (data, _) = try await client.data(from: url)
        return try JSONDecoder().decode(Profile.self, from: data)
    }
}
```

## Key Conventions

- **One assertion per concept** -- multiple assertions OK if verifying same logical behavior
- **Arrange-Act-Assert** -- setup, execution, verification in every test
- **Descriptive names** -- `testFetchUser_withExpiredToken_throwsAuthError` not `testFetch2`
- **Prefer Swift Testing for new code** -- `@Test`/`#expect` for Swift 5.9+; XCTest for older targets or UI tests
- **Test independence** -- each test runnable in isolation with self-contained state
