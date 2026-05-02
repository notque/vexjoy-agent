# Kotlin Secure Implementation Patterns

Secure-by-default patterns for Kotlin JVM and Android. Load for security, auth, injection, deserialization, WebView, content providers.

---

## Disable Jackson Default Typing

No default typing. Use explicit `@JsonTypeInfo` with closed subtype allowlist when polymorphic deser is needed.

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

**Why**: `enableDefaultTyping()` lets attackers specify deserialized class. Known RCE gadget chains (C3P0, Spring). CVE-2021-44228, CVE-2022-22965.

**Detection**:
```bash
rg -n 'enableDefaultTyping|activateDefaultTyping|Id\.CLASS' . --type kotlin
rg -n 'JsonTypeInfo' . --type kotlin
```

---

## Validate Android Intent Extras

Explicit intents for internal communication. Validate all extras from implicit intents/deep links.

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

**Why**: Implicit intents deliver attacker-controlled data — unexpected types, missing values, malicious strings.

**Detection**:
```bash
rg -n 'getStringExtra|getIntExtra|getParcelableExtra' . --type kotlin
rg -n 'Intent\(.*ACTION' . --type kotlin
```

---

## Configure WebView Security Defaults

Disable JS by default. Enable only for trusted content with URL allowlists.

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

**Why**: Unrestricted JS + navigation = arbitrary code execution. `addJavascriptInterface` exposes Kotlin methods. `allowFileAccess` enables local file reads.

**Detection**:
```bash
rg -n 'javaScriptEnabled\s*=\s*true|addJavascriptInterface' . --type kotlin
rg -n 'allowFileAccess\s*=\s*true|allowContentAccess\s*=\s*true' . --type kotlin
```

---

## Prevent Content Provider Path Traversal

Validate paths with `canonicalFile` + `startsWith` containment check.

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

**Why**: URI path segments with `../` escape the intended directory. `canonicalFile` resolves traversal; `startsWith` enforces containment.

**Detection**:
```bash
rg -n 'openFile|ContentProvider' . --type kotlin
rg -n 'canonicalFile|canonicalPath' . --type kotlin
```

---

## Handle Coroutine Exceptions Without Swallowing Security Failures

Structured concurrency preserves exception propagation. Never silently catch security exceptions.

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

**Why**: Silently catching exceptions swallows auth failures. `catch (e: Exception) { /* ignored */ }` around auth = bypass.

**Detection**:
```bash
rg -n 'catch.*Exception.*\{' . --type kotlin | rg -v 'log|throw|rethrow'
rg -n 'CoroutineExceptionHandler' . --type kotlin
```

---

## Use Parameterized Queries With Exposed and Room

Parameterized APIs only. Never interpolate into SQL.

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

**Why**: String interpolation in SQL = injection. Exposed DSL and Room parameterize automatically. Raw SQL requires `?` placeholders.

**Detection**:
```bash
rg -n 'exec\(.*\$|exec\(.*\+|exec\(.*format' . --type kotlin
rg -n '@Query.*\$\{' . --type kotlin
```

---

## Store Secrets in Android Keystore

Use Keystore for crypto keys and credentials. Never SharedPreferences, Room, or hardcoded strings.

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

**Why**: SharedPreferences = world-readable on rooted devices. Hardcoded strings extractable from APK. Keystore uses hardware-backed TEE/StrongBox.

**Detection**:
```bash
rg -n 'SharedPreferences.*password|SharedPreferences.*token|SharedPreferences.*secret' . --type kotlin
rg -n 'KeyStore\.getInstance\("AndroidKeyStore"\)' . --type kotlin
rg -n 'putString.*password|putString.*token|putString.*key' . --type kotlin
```

---

## Configure Ktor JWT Auth With Algorithm Pinning

Pin algorithm, verify claims, short-lived tokens.

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

**Why**: Without algorithm pinning, algorithm confusion attacks succeed. CVE-2022-23540, CVE-2022-29217 (`alg: none`, RS-to-HS confusion).

**Detection**:
```bash
rg -n 'JWT\.require|jwt\b.*verify|Algorithm\.' . --type kotlin
rg -n 'System\.getenv.*JWT|System\.getenv.*SECRET' . --type kotlin
```
