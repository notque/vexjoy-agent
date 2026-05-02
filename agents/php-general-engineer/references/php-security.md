# PHP Secure Implementation Patterns

Secure-by-default patterns for PHP 8.2+. Load when the task involves security, auth, injection, XSS, CSRF, deserialization, session management, or any vulnerability-related code.

---

## Use Strict Comparisons and strict_types

Declare `strict_types=1` in every file. Use `===` for all comparisons, especially security-critical ones.

```php
<?php
declare(strict_types=1);

function verifyApiKey(string $provided, string $expected): bool {
    return hash_equals($expected, $provided);  // Timing-safe
}

function isAdmin(mixed $role): bool {
    return $role === 'admin';  // "0" !== 0, null !== false
}
```

PHP's `==` performs type juggling: `"0e1234" == "0e5678"` is `true` (both coerce to float 0). In auth contexts, this can bypass password verification via magic hash collisions.

**Detection**:
```bash
rg -n '\$.*==\s' . --type php | rg -v '===' | rg -i 'password\|token\|hash\|key\|secret\|admin\|role'
```

---

## Use json_decode Instead of unserialize for Untrusted Input

```php
$data = json_decode($requestBody, associative: true, flags: JSON_THROW_ON_ERROR);

// When unserialize is needed for internal data:
$data = unserialize($cacheValue, ['allowed_classes' => [DateTime::class, Money::class]]);
```

`unserialize($user_data)` executes magic methods (`__wakeup`, `__destruct`) producing RCE through gadget chains. `json_decode` cannot instantiate objects.

**Detection**:
```bash
rg -n 'unserialize\(' . --type php | rg -v 'allowed_classes'
```

---

## Use PDO Prepared Statements for All Database Access

```php
// PDO
$stmt = $pdo->prepare('SELECT * FROM users WHERE email = :email AND org_id = :org_id');
$stmt->execute(['email' => $email, 'org_id' => $orgId]);

// Eloquent
$invoices = Invoice::where('customer_id', $customerId)->where('org_id', $orgId)->get();

// Doctrine QueryBuilder
$qb->select('u')->from(User::class, 'u')->where('u.email = :email')->setParameter('email', $email);
```

Prepared statements separate SQL structure from data at the driver level.

**Detection**:
```bash
rg -n 'query\(.*\$|exec\(.*\$' . --type php | rg -i 'select\|insert\|update\|delete'
rg -n 'DB::raw\(.*\$' . --type php
```

---

## Prevent File Inclusion With User Input

Never pass user input to `include`/`require`. Use allowlists:

```php
$allowedPages = ['home', 'about', 'contact', 'pricing'];
$page = $_GET['page'] ?? 'home';
if (!in_array($page, $allowedPages, strict: true)) { $page = 'home'; }
require __DIR__ . '/templates/' . $page . '.php';
```

`include($_GET['page'])` allows LFI (`?page=../../etc/passwd`) and with `allow_url_include=On`, RFI.

**Detection**:
```bash
rg -n 'include.*\$_|require.*\$_' . --type php
```

---

## Use password_hash With Strong Algorithms

```php
function hashPassword(string $password): string {
    return password_hash($password, PASSWORD_ARGON2ID, [
        'memory_cost' => 65536, 'time_cost' => 4, 'threads' => 3,
    ]);
}

function verifyPassword(string $password, string $hash): bool {
    return password_verify($password, $hash);
}

function rehashIfNeeded(string $password, string $hash): ?string {
    if (password_needs_rehash($hash, PASSWORD_ARGON2ID)) { return hashPassword($password); }
    return null;
}
```

`md5`/`sha256` are fast hashes for integrity, not passwords. GPUs compute billions/sec. `PASSWORD_ARGON2ID` is memory-hard and time-hard. `PASSWORD_BCRYPT` has 72-byte limit but is a supported fallback.

**Detection**:
```bash
rg -n 'md5\(.*password\|sha1\(.*password' . --type php
```

---

## Regenerate Session ID on Auth State Changes

```php
ini_set('session.cookie_httponly', '1');
ini_set('session.cookie_secure', '1');
ini_set('session.cookie_samesite', 'Lax');
ini_set('session.use_strict_mode', '1');
ini_set('session.use_only_cookies', '1');

function loginUser(User $user): void {
    session_regenerate_id(true);  // true = delete old session
    $_SESSION['user_id'] = $user->id;
}

function logout(): void {
    $_SESSION = [];
    session_regenerate_id(true);
    session_destroy();
}

// Laravel: $request->session()->regenerate();
```

Without regeneration, pre-login session ID capture (XSS, sniffing, fixation) retains access after authentication.

**Detection**:
```bash
rg -n 'session_regenerate_id' . --type php
rg -n 'session\.cookie_httponly\|session\.cookie_secure' . --type php
```

---

## Escape Output With htmlspecialchars

```php
function e(string $value): string {
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

// Plain PHP: <?= e($username) ?>
// Blade: {{ $username }} (auto-escaped), {!! $trustedHtml !!} (raw)
// Twig: {{ username }} (auto-escaped), {{ trusted_html|raw }}
```

`ENT_QUOTES` escapes both quote types, preventing attribute breakout. `ENT_SUBSTITUTE` replaces invalid encoding.

**Detection**:
```bash
rg -n 'echo\s+\$|print\s+\$' . --type php | rg -v 'htmlspecialchars\|htmlentities\|e\('
```

---

## Implement CSRF Token Validation

```php
function generateCsrfToken(): string {
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf_token'];
}

function verifyCsrfToken(string $token): bool {
    return hash_equals($_SESSION['csrf_token'] ?? '', $token);
}

// Laravel: @csrf (automatic)
// Symfony: {{ form_start(form) }} (automatic)
```

Use `hash_equals` for timing-safe comparison.

**Detection**:
```bash
rg -n '<form.*method.*POST' . --type php
rg -n 'VerifyCsrfToken\|csrf.*except' . --type php
```

---

## Use Mass Assignment Protection

```php
// Eloquent: always $fillable, never $guarded = []
class User extends Model {
    protected $fillable = ['name', 'email', 'avatar_url'];
}

// Validate and extract specific fields
$validated = $request->validate(['name' => 'required|string|max:100', 'email' => 'required|email']);
$user->update($validated);
```

`User::create($request->all())` lets attackers POST `{"is_admin": true}`.

**Detection**:
```bash
rg -n '\$guarded\s*=\s*\[\s*\]' . --type php
rg -n '::create\(\$request->all\(\)\)' . --type php
```

---

## Validate Outbound URLs to Prevent SSRF

```php
function validateUrl(string $url): string {
    $parsed = parse_url($url);
    if (!$parsed || !in_array($parsed['scheme'] ?? '', ['http', 'https'], strict: true)) {
        throw new \InvalidArgumentException('Invalid URL scheme');
    }
    $ip = gethostbyname($parsed['host'] ?? '');
    if ($ip === ($parsed['host'] ?? '')) { throw new \InvalidArgumentException('DNS failed'); }
    if (filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE) === false) {
        throw new \InvalidArgumentException('Disallowed IP range');
    }
    return $url;
}

// Usage: $validatedUrl = validateUrl($userUrl);
// Guzzle: ['allow_redirects' => false, 'timeout' => 10]
```

Blocks cloud metadata endpoints (`169.254.169.254`) and RFC1918 addresses. Disable redirects to prevent bypass.

**Detection**:
```bash
rg -n 'file_get_contents\(.*\$|curl_exec\|Guzzle.*\$' . --type php
```
