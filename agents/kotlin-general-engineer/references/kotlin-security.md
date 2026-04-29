# Kotlin Secure Implementation Patterns

Secure-by-default patterns for Kotlin JVM and Android applications. Each section shows what correct code looks like and why it matters. Load this reference when the task involves security, auth, injection, deserialization, WebView, content providers, or any vulnerability-related code.

---

## Disable Jackson Default Typing

Configure Jackson's `ObjectMapper` without default typing enabled. Use explicit `@JsonTypeInfo` with a closed allowlist of subtypes when polymorphic deserialization is genuinely needed.

```kotlin
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.registerKotlinModule

// Correct: no default typing, Kotlin module for data class support
val mapper = ObjectMapper().registerKotlinModule()

// When polymorphic deserialization is needed, use sealed classes
@JsonTypeInfo(use = JsonTypeInfo.Id.NAME, property = "type")
@JsonSubTypes(
    JsonSubTypes.Type(Circle::class, name = "circle"),
    JsonSubTypes.Type(Rectangle::class, name = "rectangle"),
)
sealed interface Shape

data class Circle(val radius: Double) : Shape
data class Rectangle(val width: Double, val height: Double) : Shape
```

**Why this matters**: `ObjectMapper.enableDefaultTyping()` or `@JsonTypeInfo(use = Id.CLASS)` allows the attacker to specify the deserialized class. Known gadget chains (C3P0, Spring, Hibernate) enable RCE. Log4Shell (CVE-2021-44228) and Spring4Shell (CVE-2022-22965) exploited similar class-loading paths. Jackson's documented recommendation is to avoid default typing entirely.

**Detection**:
```bash
rg -n 'enableDefaultTyping|activateDefaultTyping|Id\.CLASS' . --type kotlin
rg -n 'JsonTypeInfo' . --type kotlin
```

---

## Validate Android Intent Extras

Use explicit intents for internal component communication. Validate all extras from implicit intents or deep links before use.

```kotlin
// Correct: explicit intent for internal navigation
val intent = Intent(context, TargetActivity::class.java).apply {
    putExtra("orderId", orderId)
}
startActivity(intent)

// Correct: validate extras from external sources
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)

    // Validate intent source when receiving from external apps
    val orderId = intent.getStringExtra("orderId")
        ?: return finish()  // Missing required extra

    // Validate format before use
    if (!orderId.matches(Regex("^[a-f0-9-]{36}$"))) {
        return finish()  // Invalid format
    }

    loadOrder(orderId)
}
```

**Why this matters**: Implicit intents and deep links deliver attacker-controlled data. Extras can contain unexpected types (bundle-unparceling attacks), missing values (null pointer), or malicious strings (SQL injection through content providers, path traversal through file URIs). Explicit intents limit the recipient to your own components.

**Detection**:
```bash
rg -n 'getStringExtra|getIntExtra|getParcelableExtra' . --type kotlin
rg -n 'Intent\(.*ACTION' . --type kotlin
```

---

## Configure WebView Security Defaults

Disable JavaScript by default. Enable it only for trusted content with explicit URL allowlists.

```kotlin
import android.webkit.WebView
import android.webkit.WebViewClient

// Correct: secure WebView configuration
webView.apply {
    settings.javaScriptEnabled = false  // Default; enable only when needed
    settings.allowFileAccess = false
    settings.allowContentAccess = false
    settings.domStorageEnabled = false

    // Override URL loading to enforce allowlist
    webViewClient = object : WebViewClient() {
        private val allowedHosts = setOf("app.example.com", "help.example.com")

        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            return request.url.host !in allowedHosts  // Block navigation to unknown hosts
        }
    }
}

// When JavaScript IS needed for trusted content
webView.settings.javaScriptEnabled = true
// NEVER add JavaScript interfaces that expose sensitive operations
// webView.addJavascriptInterface(...)  // Avoid unless strictly necessary
```

**Why this matters**: `javaScriptEnabled = true` with unrestricted navigation allows any loaded page to execute JavaScript in the WebView's context. `addJavascriptInterface` exposes Kotlin methods to JavaScript; pre-API-17, all public methods were accessible. `allowFileAccess = true` lets JavaScript read local files via `file://` URIs.

**Detection**:
```bash
rg -n 'javaScriptEnabled\s*=\s*true|addJavascriptInterface' . --type kotlin
rg -n 'allowFileAccess\s*=\s*true|allowContentAccess\s*=\s*true' . --type kotlin
```

---

## Prevent Content Provider Path Traversal

Validate requested paths in content providers. Use `ParcelFileDescriptor` with path containment checks.

```kotlin
import android.content.ContentProvider
import android.os.ParcelFileDescriptor
import java.io.File

class SecureFileProvider : ContentProvider() {
    private val baseDir by lazy {
        File(context!!.filesDir, "shared").also { it.mkdirs() }
    }

    override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor? {
        val requestedPath = uri.lastPathSegment
            ?: throw SecurityException("missing path")

        // Resolve and verify containment
        val target = File(baseDir, requestedPath).canonicalFile
        if (!target.path.startsWith(baseDir.canonicalPath + File.separator)) {
            throw SecurityException("path traversal attempt: $requestedPath")
        }

        if (!target.exists()) {
            throw FileNotFoundException("file not found")
        }

        return ParcelFileDescriptor.open(target, ParcelFileDescriptor.MODE_READ_ONLY)
    }
}
```

**Why this matters**: Content providers that serve files based on URI path segments are vulnerable to `../` traversal. `File(baseDir, "../../../data/data/com.app/databases/secrets.db")` escapes the intended directory. `canonicalFile` resolves symlinks and `..` sequences; the `startsWith` check enforces containment.

**Detection**:
```bash
rg -n 'openFile|ContentProvider' . --type kotlin
rg -n 'canonicalFile|canonicalPath' . --type kotlin
```

---

## Handle Coroutine Exceptions Without Swallowing Security Failures

Use structured concurrency with `supervisorScope` or `CoroutineExceptionHandler` that logs and re-throws security-relevant exceptions.

```kotlin
import kotlinx.coroutines.*

// Correct: structured concurrency preserves exception propagation
suspend fun processSecureRequest(request: Request): Response =
    coroutineScope {  // Cancels all children if any fails
        val authResult = async { verifyAuth(request) }
        val data = async { fetchData(request) }

        // Auth failure propagates and cancels data fetch
        val user = authResult.await()
        val result = data.await()
        Response(user, result)
    }

// Correct: supervisor scope for independent operations with logging
suspend fun batchProcess(items: List<Item>) = supervisorScope {
    items.map { item ->
        async {
            try {
                processItem(item)
            } catch (e: SecurityException) {
                // Log security exceptions, do not swallow
                logger.error("Security violation processing item ${item.id}", e)
                throw e  // Re-throw to fail the job
            }
        }
    }.awaitAll()
}
```

**Why this matters**: Catching and silently ignoring exceptions in coroutines can swallow auth failures, permission denials, and security constraint violations. A `try { verifyAuth() } catch (e: Exception) { /* ignored */ }` around auth code effectively bypasses authentication. Structured concurrency ensures parent scopes see child failures.

**Detection**:
```bash
rg -n 'catch.*Exception.*\{' . --type kotlin | rg -v 'log|throw|rethrow'
rg -n 'CoroutineExceptionHandler' . --type kotlin
```

---

## Use Parameterized Queries With Exposed and Room

Pass user input through parameterized query APIs. Never interpolate into SQL strings.

```kotlin
// Correct: Exposed DSL (parameterized by default)
import org.jetbrains.exposed.sql.*

val invoices = Invoices
    .select { (Invoices.customerId eq customerId) and (Invoices.orgId eq orgId) }
    .map { it.toInvoice() }

// Correct: Exposed raw SQL with parameters
val results = TransactionManager.current().exec(
    "SELECT * FROM invoices WHERE customer_id = ?",
    listOf(customerId),
) { rs -> /* map results */ }

// Correct: Room DAO with parameterized query
@Dao
interface InvoiceDao {
    @Query("SELECT * FROM invoices WHERE customer_id = :customerId AND org_id = :orgId")
    suspend fun getByCustomer(customerId: String, orgId: String): List<Invoice>

    // Room enforces parameterized queries at compile time via annotation processing
}
```

**Why this matters**: `exec("SELECT * FROM invoices WHERE id = '$userInput'")` allows SQL injection. Exposed's DSL and Room's annotation processor parameterize queries automatically. Raw SQL escape hatches require explicit `?` placeholders with separate parameter lists.

**Detection**:
```bash
rg -n 'exec\(.*\$|exec\(.*\+|exec\(.*format' . --type kotlin
rg -n '@Query.*\$\{' . --type kotlin
```

---

## Store Secrets in Android Keystore

Use the Android Keystore system for cryptographic keys and sensitive credentials. Never store secrets in SharedPreferences, room databases, or hardcoded strings.

```kotlin
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator

// Correct: generate and store a key in Android Keystore
fun getOrCreateKey(alias: String): SecretKey {
    val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }

    keyStore.getKey(alias, null)?.let { return it as SecretKey }

    val keyGenerator = KeyGenerator.getInstance(
        KeyProperties.KEY_ALGORITHM_AES,
        "AndroidKeyStore"
    )
    keyGenerator.init(
        KeyGenParameterSpec.Builder(alias,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build()
    )
    return keyGenerator.generateKey()
}

// Correct: encrypt sensitive data before storage
fun encryptForStorage(plaintext: ByteArray, key: SecretKey): Pair<ByteArray, ByteArray> {
    val cipher = Cipher.getInstance("AES/GCM/NoPadding")
    cipher.init(Cipher.ENCRYPT_MODE, key)
    return cipher.iv to cipher.doFinal(plaintext)
}
```

**Why this matters**: SharedPreferences stores data in a world-readable XML file on rooted devices. Hardcoded strings are extractable via `strings` on the APK. Android Keystore stores keys in hardware-backed storage (TEE/StrongBox) where the key material never leaves the secure environment.

**Detection**:
```bash
rg -n 'SharedPreferences.*password|SharedPreferences.*token|SharedPreferences.*secret' . --type kotlin
rg -n 'KeyStore\.getInstance\("AndroidKeyStore"\)' . --type kotlin
rg -n 'putString.*password|putString.*token|putString.*key' . --type kotlin
```

---

## Configure Ktor JWT Auth With Algorithm Pinning

Pin the JWT algorithm, verify standard claims, and use short-lived tokens with the Ktor auth plugin.

```kotlin
import io.ktor.server.auth.*
import io.ktor.server.auth.jwt.*
import com.auth0.jwt.JWT
import com.auth0.jwt.algorithms.Algorithm

fun Application.configureAuth() {
    val jwtSecret = System.getenv("JWT_SECRET")
        ?: throw IllegalStateException("JWT_SECRET not configured")

    install(Authentication) {
        jwt("auth") {
            verifier(JWT.require(Algorithm.HMAC256(jwtSecret))
                .withAudience("api.example.com")
                .withIssuer("auth.example.com")
                .build()
            )
            validate { credential ->
                if (credential.payload.audience.contains("api.example.com")) {
                    JWTPrincipal(credential.payload)
                } else {
                    null
                }
            }
        }
    }
}
```

**Why this matters**: JWT verification without algorithm pinning allows algorithm confusion attacks. CVE-2022-23540 (jsonwebtoken) and CVE-2022-29217 (PyJWT) allowed `alg: none` or RS-to-HS key confusion. Always use `JWT.require(Algorithm.HMAC256(...))` or the equivalent for RS256, which pins the algorithm at verification time.

**Detection**:
```bash
rg -n 'JWT\.require|jwt\b.*verify|Algorithm\.' . --type kotlin
rg -n 'System\.getenv.*JWT|System\.getenv.*SECRET' . --type kotlin
```
