# Swift Secure Implementation Patterns

Secure-by-default patterns for Swift iOS, macOS, and server-side. Load when task involves security, auth, Keychain, ATS, WebView, biometrics, deep links, or vulnerabilities.

---

## Store Sensitive Data in Keychain Services

Use Keychain Services for tokens, passwords, API keys, and cryptographic keys. Set `kSecAttrAccessible` to the most restrictive level appropriate for the use case.

```swift
import Security

enum KeychainError: Error {
    case duplicateItem, itemNotFound, unexpectedStatus(OSStatus)
}

func saveToKeychain(key: String, data: Data, accessibility: CFString = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly) throws {
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrAccount as String: key,
        kSecValueData as String: data,
        kSecAttrAccessible as String: accessibility,
    ]

    let status = SecItemAdd(query as CFDictionary, nil)
    switch status {
    case errSecSuccess: return
    case errSecDuplicateItem:
        // Update existing item
        let update: [String: Any] = [kSecValueData as String: data]
        let updateStatus = SecItemUpdate(query as CFDictionary, update as CFDictionary)
        guard updateStatus == errSecSuccess else {
            throw KeychainError.unexpectedStatus(updateStatus)
        }
    default:
        throw KeychainError.unexpectedStatus(status)
    }
}

func loadFromKeychain(key: String) throws -> Data {
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrAccount as String: key,
        kSecReturnData as String: true,
        kSecMatchLimit as String: kSecMatchLimitOne,
    ]

    var result: AnyObject?
    let status = SecItemCopyMatching(query as CFDictionary, &result)
    guard status == errSecSuccess, let data = result as? Data else {
        throw KeychainError.itemNotFound
    }
    return data
}
```

**Accessibility levels** (most restrictive to least):
- `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` — available only while unlocked, no backup migration
- `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` — available after first unlock, no backup migration (recommended default)
- `kSecAttrAccessibleWhenUnlocked` — available while unlocked, migrates with backups

**Why this matters**: `UserDefaults` is a plist readable on jailbroken devices and in unencrypted backups. Keychain is encrypted with device key; `ThisDeviceOnly` items don't migrate or appear in backups.

**Detection**:
```bash
rg -n 'UserDefaults.*token\|UserDefaults.*password\|UserDefaults.*secret\|UserDefaults.*key' . --type swift
rg -n 'SecItemAdd\|SecItemCopyMatching\|kSecClass' . --type swift
```

---

## Justify Every ATS Exception

Keep ATS enabled. Document each exception with technical reason why HTTPS cannot be used.

```xml
<!-- Info.plist — minimal exceptions with justification -->
<key>NSAppTransportSecurity</key>
<dict>
    <!-- ATS is ON by default; only add exceptions that are technically necessary -->
    <key>NSExceptionDomains</key>
    <dict>
        <key>legacy-api.partner.com</key>
        <dict>
            <!-- Partner API does not support TLS 1.2; migration scheduled Q3 -->
            <key>NSExceptionMinimumTLSVersion</key>
            <string>TLSv1.0</string>
            <key>NSExceptionAllowsInsecureHTTPLoads</key>
            <true/>
        </dict>
    </dict>
</dict>
```

```swift
// Never do this in production:
// NSAllowsArbitraryLoads = true  // Disables ATS entirely
```

**Why this matters**: `NSAllowsArbitraryLoads = true` disables all transport security, enabling MITM attacks. App Store may reject blanket ATS exceptions.

**Detection**:
```bash
rg -n 'NSAllowsArbitraryLoads' . --type xml
rg -n 'NSExceptionDomains|NSAppTransportSecurity' . --type xml
```

---

## Prefer Universal Links Over Custom URL Schemes

Use universal links for deep linking. If custom URL schemes necessary, validate all parameters.

```swift
// Correct: universal link handling with validation
func application(_ application: UIApplication,
                 continue userActivity: NSUserActivity,
                 restorationHandler: @escaping ([UIUserActivityRestoring]?) -> Void) -> Bool {
    guard userActivity.activityType == NSUserActivityTypeBrowsingWeb,
          let url = userActivity.webpageURL,
          let components = URLComponents(url: url, resolvingAgainstBaseURL: true) else {
        return false
    }

    // Validate the host is your domain (universal links guarantee this, but defense-in-depth)
    guard components.host == "app.example.com" else { return false }

    // Validate path and parameters before routing
    switch components.path {
    case "/order":
        guard let orderId = components.queryItems?.first(where: { $0.name == "id" })?.value,
              orderId.range(of: #"^[a-f0-9-]{36}$"#, options: .regularExpression) != nil else {
            return false
        }
        navigateToOrder(orderId)
    default:
        return false
    }
    return true
}
```

```swift
// If custom URL schemes are used, validate everything
func application(_ app: UIApplication, open url: URL, options: [UIApplication.OpenURLOptionsKey: Any]) -> Bool {
    guard url.scheme == "myapp",
          let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
        return false
    }

    // Validate each parameter individually
    let action = components.host ?? ""
    guard ["order", "profile", "settings"].contains(action) else { return false }

    // Never pass URL parameters directly to SQL, file paths, or web views
    // ...
}
```

**Why this matters**: Any app can register the same custom scheme and intercept your deep links. Universal links use associated domains verification to cryptographically bind URLs to your app.

**Detection**:
```bash
rg -n 'CFBundleURLSchemes|openURL|open url' . --type swift
rg -n 'NSUserActivityTypeBrowsingWeb|universalLinks' . --type swift
```

---

## Configure WKWebView Security

Disable JS for untrusted content. Restrict navigation to allowed domains. Never use `UIWebView`.

```swift
import WebKit

// Correct: secure WKWebView configuration
let config = WKWebViewConfiguration()
let prefs = WKWebpagePreferences()
prefs.allowsContentJavaScript = false  // Disable JS by default
config.defaultWebpagePreferences = prefs

// Restrict content to HTTPS
config.websiteDataStore = .nonPersistent()  // No persistent cookies/storage

let webView = WKWebView(frame: .zero, configuration: config)

// Navigation delegate for URL allowlist
class SecureNavigationDelegate: NSObject, WKNavigationDelegate {
    private let allowedHosts: Set<String> = ["help.example.com", "docs.example.com"]

    func webView(_ webView: WKWebView,
                 decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url,
              let host = url.host,
              allowedHosts.contains(host),
              url.scheme == "https" else {
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }
}
```

**Why this matters**: JS enabled + unrestricted navigation lets loaded pages execute JavaScript. Combined with `WKScriptMessageHandler`, exposes native functionality to untrusted content.

**Detection**:
```bash
rg -n 'allowsContentJavaScript\s*=\s*true|javaScriptEnabled\s*=\s*true' . --type swift
rg -n 'WKWebView|UIWebView' . --type swift
rg -n 'addScriptMessageHandler|evaluateJavaScript' . --type swift
```

---

## Combine Biometrics With Server-Side Verification

Never rely solely on `LocalAuthentication`. Use biometrics to unlock a Keychain-stored credential, then verify server-side.

```swift
import LocalAuthentication

func authenticateAndFetch() async throws -> UserData {
    let context = LAContext()
    var error: NSError?

    guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
        throw AuthError.biometricsUnavailable
    }

    let success = try await context.evaluatePolicy(
        .deviceOwnerAuthenticationWithBiometrics,
        localizedReason: "Authenticate to access your account"
    )

    guard success else { throw AuthError.biometricsFailed }

    // Biometrics unlocks a Keychain-stored token — the real credential
    let tokenData = try loadFromKeychain(key: "auth_token")
    let token = String(data: tokenData, encoding: .utf8)!

    // Server verifies the token — biometrics alone is not auth
    let request = URLRequest(url: URL(string: "https://api.example.com/me")!)
    // ...add token to Authorization header, make request
}
```

**Why this matters**: `evaluatePolicy` returns a local boolean hookable on jailbroken devices to always return `true`. Biometrics gates access to a Keychain token; the server verifies the token.

**Detection**:
```bash
rg -n 'LAContext|evaluatePolicy|canEvaluatePolicy' . --type swift
rg -n 'deviceOwnerAuthentication' . --type swift
```

---

## Certificate Pinning for Sensitive Connections

Pin certificates or public keys for auth, payment, and personal data APIs.

```swift
import CryptoKit

class PinningDelegate: NSObject, URLSessionDelegate {
    // SHA-256 hash of the server's Subject Public Key Info (SPKI)
    private let pinnedHashes: Set<String> = [
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",  // Primary
        "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=",  // Backup
    ]

    func urlSession(_ session: URLSession,
                    didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust,
              SecTrustEvaluateWithError(serverTrust, nil),
              let certificate = SecTrustGetCertificateAtIndex(serverTrust, 0) else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }

        let serverKey = SecCertificateCopyKey(certificate)!
        let serverKeyData = SecKeyCopyExternalRepresentation(serverKey, nil)! as Data
        let serverHash = Data(SHA256.hash(data: serverKeyData)).base64EncodedString()

        if pinnedHashes.contains(serverHash) {
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
        } else {
            completionHandler(.cancelAuthenticationChallenge, nil)
        }
    }
}
```

**Why this matters**: Without pinning, any trusted CA can issue a certificate for your domain. Always include a backup pin for key rotation.

**Detection**:
```bash
rg -n 'didReceive challenge|URLAuthenticationChallenge|SecTrust' . --type swift
rg -n 'pinnedCertificates\|pinnedPublicKeys\|certificatePinner' . --type swift
```

---

## UserDefaults vs Keychain

Store tokens, keys, credentials in Keychain. Reserve UserDefaults for non-sensitive preferences.

```swift
// Correct: UserDefaults for preferences only
UserDefaults.standard.set("dark", forKey: "theme")
UserDefaults.standard.set(true, forKey: "onboardingComplete")
UserDefaults.standard.set("en", forKey: "preferredLanguage")

// WRONG — these belong in Keychain:
// UserDefaults.standard.set(authToken, forKey: "token")     // ← Keychain
// UserDefaults.standard.set(apiKey, forKey: "apiKey")       // ← Keychain
// UserDefaults.standard.set(sessionId, forKey: "session")   // ← Keychain
```

**Why this matters**: UserDefaults is unencrypted plist — readable on jailbroken devices, in plaintext backups, trivially extracted. Keychain is encrypted with device passcode.

**Detection**:
```bash
rg -n 'UserDefaults.*set.*token\|UserDefaults.*set.*password\|UserDefaults.*set.*secret\|UserDefaults.*set.*key\|UserDefaults.*set.*credential' . --type swift
```

---

## Validate Deep Link Parameters

Validate all parameters before use in navigation, API calls, or database queries.

```swift
// Correct: validate and sanitize deep link parameters
struct DeepLinkRouter {
    enum Route {
        case order(id: String)
        case profile(username: String)
        case unknown
    }

    static func route(from url: URL) -> Route {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            return .unknown
        }

        switch components.path {
        case "/order":
            guard let id = components.queryItems?.first(where: { $0.name == "id" })?.value,
                  id.count == 36,
                  id.range(of: #"^[a-f0-9-]{36}$"#, options: .regularExpression) != nil else {
                return .unknown
            }
            return .order(id: id)

        case "/profile":
            guard let username = components.queryItems?.first(where: { $0.name == "user" })?.value,
                  username.count <= 30,
                  username.range(of: #"^[a-zA-Z0-9_]+$"#, options: .regularExpression) != nil else {
                return .unknown
            }
            return .profile(username: username)

        default:
            return .unknown
        }
    }
}
```

**Why this matters**: Deep link parameters are attacker-controlled. Direct use in SQL, file paths, or WebView URLs enables injection/traversal attacks. Typed enum with validation constrains to expected formats.

**Detection**:
```bash
rg -n 'openURL\|open url\|application.*open.*url' . --type swift
rg -n 'URLComponents.*queryItems' . --type swift
```
