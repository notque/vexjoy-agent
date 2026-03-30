# PHP Security & Testing Reference

Deep-dive patterns for security posture, hard gate violations, and testing methodology.

---

## Security

### Prepared Statements (Mandatory)

Build SQL exclusively with prepared statements or query builders.

```php
// BLOCKED — SQL injection risk
$result = $pdo->query("SELECT * FROM users WHERE email = '$email'");

// CORRECT — PDO prepared statement
$stmt = $pdo->prepare('SELECT * FROM users WHERE email = :email');
$stmt->execute(['email' => $email]);

// CORRECT — Eloquent query builder
$user = User::where('email', $email)->first();

// CORRECT — Doctrine QueryBuilder
$user = $em->createQueryBuilder()
    ->select('u')
    ->from(User::class, 'u')
    ->where('u.email = :email')
    ->setParameter('email', $email)
    ->getQuery()
    ->getOneOrNullResult();
```

**Detection command**:
```bash
grep -rn --include="*.php" -E '(query|exec)\s*\(\s*["\x27].*\$' src/
```

### Mass-Assignment (Eloquent)

Always declare `$fillable` (whitelist) — never use `$guarded = []`.

```php
// BLOCKED — mass-assignment vulnerability
protected $guarded = [];

// CORRECT
protected $fillable = ['name', 'email', 'role'];
```

**Detection command**:
```bash
grep -rn --include="*.php" 'guarded\s*=\s*\[\s*\]' app/
```

### Session Management

Regenerate session ID after authentication and after any privilege change.

```php
// After login
$request->session()->regenerate();

// After privilege escalation (sudo-style)
session_regenerate_id(true);
```

### CSRF Protection

State-changing requests (POST/PUT/PATCH/DELETE) must have CSRF tokens. Any exclusion from Laravel's `VerifyCsrfToken` middleware must have a documented, reviewed reason.

**Detection command**:
```bash
grep -rn --include="*.php" -E 'VerifyCsrfToken|withoutMiddleware.*csrf|except.*csrf' app/Http/
```

### Passwords

Use `password_hash()` / `password_verify()` — never `md5()` or `sha1()` for passwords.

```php
// CORRECT
$hash = password_hash($plaintext, PASSWORD_BCRYPT);
$valid = password_verify($plaintext, $hash);

// BLOCKED — cryptographically broken for passwords
$hash = md5($plaintext);
$hash = sha1($plaintext);
```

### Secrets Management

Secrets (API keys, DB passwords, tokens) must come from environment variables or a secrets manager, never from committed config files.

```php
// CORRECT
$apiKey = env('PAYMENT_API_KEY');

// BLOCKED — secrets stay in environment variables, not in code
$apiKey = 'sk_live_abc123...';
```

### Dependency Audit

Run after every `composer update` or before deploying:
```bash
composer audit
```

---

## Hard Gate Patterns

These patterns are blocked unconditionally. Replace them with the correct alternative in any code you edit.

| Pattern | Reason |
|---------|--------|
| `$$variable` (variable variables) in business logic | Arbitrary indirection; unanalyzable by static analysis tools; creates impossible-to-audit attack surface |
| Dynamic code execution via string-eval functions | Executes arbitrary strings as PHP code; blocked in all contexts without exception |
| `mysql_*` functions | Removed in PHP 7; any occurrence indicates legacy migration debt requiring immediate remediation |
| `preg_replace` with `/e` modifier | Executes replacement string as PHP code; security vulnerability removed in PHP 7 |
| Disabling CSRF protection without documented reason | State-changing endpoints without CSRF tokens are vulnerable to cross-site request forgery |
| `md5()` / `sha1()` for passwords | Cryptographically broken for password storage; use `password_hash()` |

---

## Testing

### PHPUnit vs. Pest Decision Rule

| Condition | Choice |
|-----------|--------|
| New project, greenfield | PHPUnit (default) |
| Existing project already uses Pest | Pest (stay consistent) |
| Laravel project with team preference for expressive syntax | Pest acceptable |
| CI pipeline expects PHPUnit XML output | PHPUnit |

Use one test framework per test class — PHPUnit or Pest, not both.

### Factory Fixtures (Mandatory)

Use Laravel factories or custom builders for test data. Generate fixture data through factories instead of hand-writing large arrays.

```php
// CORRECT — factory with state
$user = User::factory()
    ->verified()
    ->withSubscription('pro')
    ->create();

// CORRECT — custom builder
$order = OrderBuilder::new()
    ->withItems([ProductBuilder::create()->atPrice(1000)])
    ->forCustomer($user)
    ->build();

// BLOCKED — hand-written array fixture
$orderData = [
    'customer_id' => 1,
    'items' => [['product_id' => 5, 'quantity' => 2, 'price' => 1000]],
    // ... 30 more lines of brittle fixture data
];
```

### Unit vs. Integration Separation

| Test Type | What It Tests | Speed | Database |
|-----------|-------------|-------|---------|
| Unit | Single class/method in isolation, all dependencies mocked | Fast (<1ms) | No |
| Integration | Service + real database, or controller + real HTTP stack | Slower (>10ms) | Yes |
| Feature/E2E | Full request lifecycle | Slowest | Yes |

Run unit tests in tight loops; run integration tests in CI. Keep database usage in integration test classes only.

```php
// Unit test — mocked dependencies
final class OrderServiceTest extends TestCase
{
    public function test_place_order_dispatches_event(): void
    {
        $orders = $this->createMock(OrderRepositoryInterface::class);
        $inventory = $this->createMock(InventoryServiceInterface::class);
        $events = $this->createMock(EventDispatcherInterface::class);

        $events->expects($this->once())->method('dispatch');

        $service = new OrderService($orders, $inventory, $events);
        $service->place(PlaceOrderCommandBuilder::default());
    }
}
```

### Coverage Commands

```bash
# PHPUnit with coverage
./vendor/bin/phpunit --coverage-text --coverage-html=coverage/

# Pest with coverage
./vendor/bin/pest --coverage --coverage-html=coverage/
```
